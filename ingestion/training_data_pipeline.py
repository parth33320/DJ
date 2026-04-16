"""
Complete Training Data Pipeline
Downloads and processes from all DJ tutorial channels
Prioritizes YouTube Shorts for fast AI training
Processes in batches, deletes as it goes
"""

import os
import json
import time
import subprocess
import numpy as np
import librosa
try:
    import whisper
except ImportError:
    whisper = None

import yt_dlp
from datetime import datetime
from pathlib import Path

# ============================================================
# CHANNEL CONFIGURATION
# ============================================================

CHANNELS = {
    'best_dj_transitions': {
        'url': 'https://www.youtube.com/@BestDJTransitions',
        'type': 'transitions',           # Pure transition examples
        'label': 'good_transition',      # All = good transitions
        'extract': ['audio_features',    # What to extract
                    'transition_points',
                    'technique_classify'],
        'use_for': ['perceptual_benchmark',
                    'quality_scorer'],
        'priority': 1,                   # Process first
        'shorts_only': True,             # Shorts = fast, focused
        'max_videos': 500,
    },
    'siangyoo': {
        'url': 'https://www.youtube.com/channel/UCY0VLoxoudeRAOryWO4_5Qg',
        'type': 'transitions_and_tutorials',
        'label': 'good_transition',
        'extract': ['audio_features',
                    'transition_points',
                    'technique_classify',
                    'wordplay_examples',
                    'transcript'],
        'use_for': ['perceptual_benchmark',
                    'wordplay_model',
                    'transition_classifier'],
        'priority': 2,
        'shorts_only': True,             # Shorts show technique clearly
        'max_videos': 500,
    },
    'phil_harris': {
        'url': 'https://www.youtube.com/@DJPhilHarris',
        'type': 'tutorials',
        'label': 'tutorial',
        'extract': ['transcript',
                    'technique_classify',
                    'audio_features'],
        'use_for': ['technique_classifier',
                    'parameter_optimizer'],
        'priority': 3,
        'shorts_only': False,            # Tutorials need full length
        'max_videos': 200,
        'max_duration': 1800,            # Skip videos > 30 mins
    },
    'crossfader': {
        'url': 'https://www.youtube.com/@Crossfader',
        'type': 'tutorials',
        'label': 'tutorial',
        'extract': ['transcript',
                    'technique_classify',
                    'audio_features'],
        'use_for': ['technique_classifier',
                    'parameter_optimizer',
                    'quality_scorer'],
        'priority': 4,
        'shorts_only': False,
        'max_videos': 200,
        'max_duration': 1800,
    },
    '69beats': {
        'url': 'https://www.youtube.com/@69Beats',
        'type': 'transitions',
        'label': 'good_transition',
        'extract': ['audio_features',
                    'transition_points',
                    'technique_classify'],
        'use_for': ['perceptual_benchmark',
                    'quality_scorer'],
        'priority': 5,
        'shorts_only': True,
        'max_videos': 300,
    },
}

# ============================================================
# MAIN PIPELINE CLASS
# ============================================================

class TrainingDataPipeline:
    def __init__(self, config):
        self.config = config
        self.training_dir = config['paths']['training_data']
        self.models_dir = config['paths']['models']
        self.tmp_dir = os.path.join(self.training_dir, 'tmp')
        self.sr = 22050

        os.makedirs(self.training_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)

        # Whisper model (load once)
        self.whisper_model = None

        # Progress tracking
        self.progress_file = os.path.join(
            self.training_dir, 'pipeline_progress.json'
        )
        self.progress = self._load_progress()

        # Results accumulator
        self.all_training_examples = []
        self.perceptual_benchmarks = []

    # ============================================================
    # ENTRY POINT
    # ============================================================

    def run_full_pipeline(self):
        """
        Run complete training data collection
        Processes all channels in priority order
        """
        print("""
╔══════════════════════════════════════════╗
║     DJ AI TRAINING DATA PIPELINE         ║
║     Processing all channels...           ║
╚══════════════════════════════════════════╝
        """)

        # Sort channels by priority
        sorted_channels = sorted(
            CHANNELS.items(),
            key=lambda x: x[1]['priority']
        )

        for channel_name, channel_config in sorted_channels:
            print(f"\n{'='*60}")
            print(f"📺 CHANNEL: {channel_name.upper()}")
            print(f"   Type: {channel_config['type']}")
            print(f"   Priority: {channel_config['priority']}")
            print(f"   Shorts only: {channel_config['shorts_only']}")
            print(f"{'='*60}")

            # Skip if already completed
            if self.progress.get(channel_name, {}).get('completed'):
                print(f"   ✅ Already processed - skipping")
                continue

            self._process_channel(channel_name, channel_config)

        # Final save
        self._save_all_results()

        print(f"""
╔══════════════════════════════════════════╗
║     PIPELINE COMPLETE! 🎧                ║
║                                          ║
║  Training examples: {len(self.all_training_examples):<5}              ║
║  Perceptual benchmarks: {len(self.perceptual_benchmarks):<3}           ║
╚══════════════════════════════════════════╝
        """)

    # ============================================================
    # CHANNEL PROCESSING
    # ============================================================

    def _process_channel(self, channel_name, channel_config):
        """Process all videos from one channel"""

        # Get video list
        videos = self._get_video_list(channel_config)
        print(f"\n   Found {len(videos)} videos to process")

        processed = 0
        failed = 0

        for i, video in enumerate(videos):
            print(f"\n   [{i+1}/{len(videos)}] "
                  f"{video['title'][:50]}")
            print(f"   Duration: {video.get('duration', 0):.0f}s | "
                  f"Short: {video.get('is_short', False)}")

            # Skip if already processed
            if video['id'] in self.progress.get(
                channel_name, {}
            ).get('processed_ids', []):
                print(f"   ⏭️  Already processed")
                continue

            try:
                # Download audio
                audio_path = self._download_audio(video)
                if not audio_path:
                    failed += 1
                    continue

                # Process based on channel type
                examples = self._process_video(
                    audio_path, video, channel_config
                )

                self.all_training_examples.extend(examples)

                # If transition channel, add to benchmark
                if channel_config['type'] in [
                    'transitions', 'transitions_and_tutorials'
                ]:
                    benchmarks = self._extract_benchmarks(
                        audio_path, video
                    )
                    self.perceptual_benchmarks.extend(benchmarks)

                processed += 1

                # Update progress
                self._update_progress(
                    channel_name, video['id']
                )

                # Save intermediate results every 10 videos
                if processed % 10 == 0:
                    self._save_intermediate_results()
                    print(f"\n   💾 Saved {processed} videos processed")

            except Exception as e:
                print(f"   ❌ Failed: {e}")
                failed += 1
            finally:
                # ALWAYS delete audio after processing
                self._cleanup_audio(video['id'])

        # Mark channel as complete
        self._mark_channel_complete(channel_name)

        print(f"\n   ✅ Channel complete: "
              f"{processed} processed, {failed} failed")

    # ============================================================
    # VIDEO LIST FETCHING
    # ============================================================

    def _get_video_list(self, channel_config):
        """
        Get list of videos from channel
        Prioritizes Shorts if shorts_only=True
        """
        url = channel_config['url']
        shorts_only = channel_config.get('shorts_only', False)
        max_videos = channel_config.get('max_videos', 100)
        max_duration = channel_config.get('max_duration', 3600)

        videos = []

        # Try Shorts playlist first if shorts_only
        if shorts_only:
            shorts_url = url + '/shorts'
            shorts = self._fetch_video_list(
                shorts_url, max_videos, max_duration=60
            )
            for v in shorts:
                v['is_short'] = True
            videos.extend(shorts)
            print(f"   📱 Found {len(shorts)} Shorts")

        # If not shorts_only or not enough shorts,
        # get regular videos too
        if not shorts_only or len(videos) < 10:
            regular = self._fetch_video_list(
                url, max_videos - len(videos), max_duration
            )
            for v in regular:
                v['is_short'] = False
            videos.extend(regular)
            print(f"   🎥 Found {len(regular)} regular videos")

        # Sort: Shorts first (faster to process)
        videos.sort(
            key=lambda x: (not x.get('is_short', False),
                          x.get('duration', 999))
        )

        return videos[:max_videos]

    def _fetch_video_list(self, url, max_count, max_duration=3600):
        """Fetch video metadata from YouTube"""
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': max_count * 2,  # Get extra, filter below
        }

        videos = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                entries = info.get('entries', [])

                for entry in entries:
                    if not entry:
                        continue

                    duration = entry.get('duration', 0) or 0

                    # Skip too long
                    if duration > max_duration:
                        continue

                    # Skip too short (< 5 seconds)
                    if duration < 5:
                        continue

                    videos.append({
                        'id': entry.get('id', ''),
                        'title': entry.get('title', ''),
                        'url': f"https://youtube.com/watch?v={entry.get('id')}",
                        'duration': duration,
                        'thumbnail': entry.get('thumbnail', ''),
                    })

                    if len(videos) >= max_count:
                        break

        except Exception as e:
            print(f"   ❌ Failed to fetch video list: {e}")

        return videos

    # ============================================================
    # AUDIO DOWNLOAD
    # ============================================================

    def _download_audio(self, video):
        """
        Download audio for a video
        Returns filepath or None
        """
        output_path = os.path.join(
            self.tmp_dir, f"{video['id']}.mp3"
        )

        if os.path.exists(output_path):
            return output_path

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(
                self.tmp_dir, f"{video['id']}.%(ext)s"
            ),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video['url']])
            return output_path
        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            return None

    def _cleanup_audio(self, video_id):
        """Delete audio file after processing"""
        for ext in ['mp3', 'wav', 'webm', 'm4a', 'opus']:
            path = os.path.join(self.tmp_dir, f"{video_id}.{ext}")
            if os.path.exists(path):
                os.remove(path)

    # ============================================================
    # VIDEO PROCESSING
    # ============================================================

    def _process_video(self, audio_path, video, channel_config):
        """
        Process a single video based on channel type
        Returns list of training examples
        """
        examples = []
        extract = channel_config.get('extract', [])
        channel_type = channel_config['type']

        # Load audio
        try:
            y, sr = librosa.load(audio_path, sr=self.sr, mono=True)
        except Exception as e:
            print(f"   ❌ Audio load failed: {e}")
            return examples

        # ---- Extract based on channel type ----

        # For transition channels: find & label transitions
        if 'transition_points' in extract:
            transition_examples = self._extract_transitions(
                y, sr, video, channel_config
            )
            examples.extend(transition_examples)
            print(f"   🎚️  Found {len(transition_examples)} transitions")

        # For tutorial channels: transcribe & extract knowledge
        if 'transcript' in extract:
            transcript_examples = self._extract_transcript_knowledge(
                audio_path, video, channel_config
            )
            examples.extend(transcript_examples)
            print(f"   📝 Extracted {len(transcript_examples)} "
                  f"knowledge items")

        # For all: extract audio features
        if 'audio_features' in extract:
            features = self._extract_audio_features(y, sr, video)
            if features:
                examples.append({
                    'type': 'audio_features',
                    'video_id': video['id'],
                    'title': video['title'],
                    'features': features,
                    'label': channel_config['label'],
                    'source': channel_config['type'],
                })

        # Wordplay specific extraction
        if 'wordplay_examples' in extract:
            wp_examples = self._extract_wordplay_examples(
                y, sr, video
            )
            examples.extend(wp_examples)
            print(f"   🗣️  Found {len(wp_examples)} wordplay examples")

        return examples

    # ============================================================
    # TRANSITION EXTRACTION
    # ============================================================

    def _extract_transitions(self, y, sr, video, channel_config):
        """
        Find and extract transition moments from audio
        Labels them as good transitions (from these channels
        we assume ALL transitions are good quality)
        """
        examples = []

        # Detect transition points
        transition_times = self._detect_transition_points(y, sr)

        for t in transition_times:
            # Extract features around transition
            window = int(sr * 4)
            t_sample = int(t * sr)

            before = y[max(0, t_sample - window):t_sample]
            after = y[t_sample:min(len(y), t_sample + window)]

            if len(before) < sr or len(after) < sr:
                continue

            # Classify technique
            technique = self._classify_transition_technique(
                before, after, sr
            )

            # Extract features
            features = {
                'bpm_before': self._get_bpm(before, sr),
                'bpm_after': self._get_bpm(after, sr),
                'energy_before': float(np.sqrt(np.mean(before**2))),
                'energy_after': float(np.sqrt(np.mean(after**2))),
                'centroid_before': self._get_centroid(before, sr),
                'centroid_after': self._get_centroid(after, sr),
                'transition_duration': self._estimate_transition_duration(
                    y, sr, t
                ),
            }

            examples.append({
                'type': 'transition',
                'video_id': video['id'],
                'title': video['title'],
                'timestamp': t,
                'technique': technique,
                'quality': 'good',      # From quality channels = good
                'features': features,
                'label': 1,             # Positive label
                'source': 'transition_channel',
                'is_short': video.get('is_short', False),
            })

        return examples

    def _detect_transition_points(self, y, sr):
        """Detect where transitions happen in audio"""
        hop = 512
        transition_times = []

        # Spectral flux
        spec = np.abs(librosa.stft(y, hop_length=hop))
        flux = np.sum(np.diff(spec, axis=1)**2, axis=0)
        flux_norm = flux / (np.max(flux) + 1e-10)
        flux_times = librosa.frames_to_time(
            np.arange(len(flux)), sr=sr, hop_length=hop
        )

        # RMS energy changes
        rms = librosa.feature.rms(y=y, hop_length=hop)[0]
        rms_diff = np.abs(np.diff(rms))

        # Find peaks
        from scipy.signal import find_peaks

        min_gap = sr // hop * 8  # Min 8 seconds between transitions

        peaks, _ = find_peaks(
            flux_norm,
            height=0.25,
            distance=min_gap
        )

        for peak in peaks:
            if peak < len(flux_times):
                t = float(flux_times[peak])
                duration = len(y) / sr
                if 5 < t < duration - 5:
                    transition_times.append(t)

        return transition_times

    def _classify_transition_technique(self, before, after, sr):
        """Classify what technique was used"""
        energy_b = np.sqrt(np.mean(before**2))
        energy_a = np.sqrt(np.mean(after**2))
        centroid_b = self._get_centroid(before, sr)
        centroid_a = self._get_centroid(after, sr)

        # Echo detection
        if self._has_echo(before):
            return 'echo_out'

        # Filter sweep detection
        if abs(centroid_a - centroid_b) > 2000:
            return 'filter_sweep'

        # Loop roll detection
        if self._has_loop_pattern(before, sr):
            return 'loop_roll'

        # Reverb detection
        if self._has_reverb_tail(before):
            return 'reverb_wash'

        # Hard cut
        bpm_b = self._get_bpm(before, sr)
        bpm_a = self._get_bpm(after, sr)
        if abs(bpm_b - bpm_a) > 20:
            return 'cut_transition'

        return 'beatmatch_crossfade'

    def _estimate_transition_duration(self, y, sr, transition_time):
        """Estimate how long the transition lasts"""
        window = int(sr * 8)
        t_sample = int(transition_time * sr)
        segment = y[
            max(0, t_sample - window//2):
            min(len(y), t_sample + window//2)
        ]
        if len(segment) < 100:
            return 4.0
        rms = librosa.feature.rms(y=segment)[0]
        # Find region of mixed audio (moderate energy variance)
        variance = np.var(rms)
        return float(min(8.0, max(1.0, variance * 1000)))

    # ============================================================
    # BENCHMARK EXTRACTION
    # ============================================================

    def _extract_benchmarks(self, audio_path, video):
        """
        Extract perceptual quality benchmarks
        These are reference 'good transition' audio clips
        Used to compare our generated transitions against
        """
        benchmarks = []

        try:
            y, sr = librosa.load(audio_path, sr=self.sr, mono=True)
        except Exception:
            return benchmarks

        transition_times = self._detect_transition_points(y, sr)

        for t in transition_times:
            # Extract 8 second clip centered on transition
            clip_start = max(0, int((t - 4) * sr))
            clip_end = min(len(y), int((t + 4) * sr))
            clip = y[clip_start:clip_end]

            if len(clip) < sr * 4:
                continue

            # Extract fingerprint features
            mfcc = librosa.feature.mfcc(y=clip, sr=sr, n_mfcc=20)
            chroma = librosa.feature.chroma_cqt(y=clip, sr=sr)
            spectral = librosa.feature.spectral_centroid(y=clip, sr=sr)

            benchmark = {
                'video_id': video['id'],
                'title': video['title'],
                'timestamp': t,
                'duration': len(clip) / sr,
                'is_short': video.get('is_short', False),
                'mfcc_mean': np.mean(mfcc, axis=1).tolist(),
                'mfcc_std': np.std(mfcc, axis=1).tolist(),
                'chroma_mean': np.mean(chroma, axis=1).tolist(),
                'spectral_centroid_mean': float(np.mean(spectral)),
                'energy': float(np.sqrt(np.mean(clip**2))),
            }

            benchmarks.append(benchmark)

        return benchmarks

    # ============================================================
    # TRANSCRIPT EXTRACTION (Tutorial channels)
    # ============================================================

    def _extract_transcript_knowledge(self, audio_path,
                                       video, channel_config):
        """
        Transcribe tutorial video and extract
        technique knowledge
        """
        examples = []

        # Load Whisper once
        if self.whisper_model is None:
            print("   Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")

        try:
            result = self.whisper_model.transcribe(
                audio_path,
                word_timestamps=True
            )
            transcript = result.get('text', '')
            segments = result.get('segments', [])

        except Exception as e:
            print(f"   ❌ Transcription failed: {e}")
            return examples

        # Technique keyword mapping
        technique_keywords = {
            'beatmatch_crossfade': [
                'beatmatch', 'beat match', 'sync', 'crossfade',
                'blend', 'mix in', 'smooth transition'
            ],
            'filter_sweep': [
                'filter', 'high pass', 'low pass', 'eq sweep',
                'kill the bass', 'open the filter', 'filter out'
            ],
            'echo_out': [
                'echo', 'delay', 'echo out', 'bounce',
                'delay effect', 'echo effect'
            ],
            'loop_roll': [
                'loop', 'roll', 'loop roll', 'stutter',
                'rolling', 'loop out'
            ],
            'reverb_wash': [
                'reverb', 'wash', 'reverb out',
                'atmospheric', 'reverb effect', 'hall'
            ],
            'spinback': [
                'spinback', 'spin back', 'rewind',
                'brake', 'backspin', 'spin out'
            ],
            'phrase_matching': [
                'phrase', 'eight bar', '8 bar', '16 bar',
                'sixteen bar', 'on the one', 'count the bars',
                'bar count', 'phrase match'
            ],
            'harmonic_mixing': [
                'harmonic', 'camelot', 'key', 'same key',
                'compatible', 'harmonic mix', 'key mixing',
                'musical key'
            ],
            'wordplay': [
                'word', 'vocal', 'word play', 'acapella',
                'vocal transition', 'word match', 'lyric',
                'same word', 'vocal chop'
            ],
            'tone_play': [
                'tone', 'melody', 'note', 'pitch',
                'melodic', 'tune', 'musical note', 'play the melody'
            ],
            'cut_transition': [
                'cut', 'hard cut', 'chop', 'slice',
                'instant', 'sharp cut', 'quick cut'
            ],
        }

        # Extract knowledge from each segment
        for segment in segments:
            seg_text = segment.get('text', '').lower()
            seg_start = segment.get('start', 0)

            for technique, keywords in technique_keywords.items():
                for kw in keywords:
                    if kw in seg_text:
                        # Get surrounding context
                        context = self._get_segment_context(
                            segments, segment, window=3
                        )

                        examples.append({
                            'type': 'tutorial_knowledge',
                            'video_id': video['id'],
                            'title': video['title'],
                            'technique': technique,
                            'timestamp': seg_start,
                            'text': segment.get('text', ''),
                            'context': context,
                            'keyword': kw,
                            'source': 'tutorial',
                            'label': 1,
                        })
                        break

        return examples

    def _get_segment_context(self, segments, target, window=3):
        """Get text context around a segment"""
        try:
            idx = segments.index(target)
        except ValueError:
            return target.get('text', '')

        start = max(0, idx - window)
        end = min(len(segments), idx + window + 1)
        return ' '.join(s.get('text', '') for s in segments[start:end])

    # ============================================================
    # WORDPLAY EXTRACTION
    # ============================================================

    def _extract_wordplay_examples(self, y, sr, video):
        """
        Extract wordplay transition examples
        Specifically for SiangyOO-style transitions
        """
        examples = []

        # Detect transitions
        transition_times = self._detect_transition_points(y, sr)

        for t in transition_times:
            # Look for vocal-heavy sections around transition
            vocal_score = self._estimate_vocal_presence(y, sr, t)

            if vocal_score > 0.5:
                features = {
                    'timestamp': t,
                    'vocal_score': vocal_score,
                    'bpm': self._get_bpm(
                        y[max(0, int((t-4)*sr)):int((t+4)*sr)], sr
                    ),
                    'energy': float(np.sqrt(np.mean(
                        y[max(0, int((t-2)*sr)):int((t+2)*sr)]**2
                    ))),
                }

                examples.append({
                    'type': 'wordplay_transition',
                    'video_id': video['id'],
                    'title': video['title'],
                    'timestamp': t,
                    'vocal_score': vocal_score,
                    'features': features,
                    'technique': 'wordplay',
                    'quality': 'good',
                    'label': 1,
                    'source': 'siangyoo',
                })

        return examples

    def _estimate_vocal_presence(self, y, sr, time):
        """
        Estimate how much vocal is present
        High ZCR + mid-range spectral centroid = likely vocal
        """
        window = int(sr * 2)
        t_sample = int(time * sr)
        segment = y[max(0, t_sample - window):t_sample + window]

        if len(segment) < 100:
            return 0.0

        zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=segment)))
        centroid = float(np.mean(
            librosa.feature.spectral_centroid(y=segment, sr=sr)
        ))

        # Vocals typically: ZCR 0.05-0.15, centroid 1000-4000 Hz
        zcr_score = 1.0 if 0.04 < zcr < 0.18 else 0.0
        centroid_score = 1.0 if 800 < centroid < 4500 else 0.0

        return (zcr_score + centroid_score) / 2.0

    # ============================================================
    # AUDIO FEATURE HELPERS
    # ============================================================

    def _get_bpm(self, audio, sr):
        """Get BPM of audio segment"""
        if len(audio) < sr:
            return 120.0
        try:
            tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
            return float(tempo)
        except Exception:
            return 120.0

    def _get_centroid(self, audio, sr):
        """Get spectral centroid"""
        if len(audio) < 100:
            return 2000.0
        try:
            return float(np.mean(
                librosa.feature.spectral_centroid(y=audio, sr=sr)
            ))
        except Exception:
            return 2000.0

    def _extract_audio_features(self, y, sr, video):
        """Extract full audio feature set"""
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            rms = librosa.feature.rms(y=y)[0]
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            zcr = librosa.feature.zero_crossing_rate(y=y)[0]
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

            return {
                'bpm': float(tempo),
                'energy_mean': float(np.mean(rms)),
                'energy_std': float(np.std(rms)),
                'centroid_mean': float(np.mean(centroid)),
                'zcr_mean': float(np.mean(zcr)),
                'mfcc_means': np.mean(mfcc, axis=1).tolist(),
                'duration': float(len(y) / sr),
            }
        except Exception as e:
            print(f"   ❌ Feature extraction failed: {e}")
            return None

    def _has_echo(self, audio):
        """Detect echo/delay pattern"""
        if len(audio) < 4000:
            return False
        corr = np.correlate(audio[:4000], audio[:4000], mode='full')
        corr = corr[len(corr)//2:]
        corr = corr / (corr[0] + 1e-10)
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(corr[100:2000], height=0.25)
        return len(peaks) > 2

    def _has_loop_pattern(self, audio, sr):
        """Detect loop/roll pattern"""
        short_len = int(sr * 0.25)
        if len(audio) < short_len * 4:
            return False
        seg_a = audio[:short_len]
        seg_b = audio[short_len:short_len*2]
        if len(seg_b) < len(seg_a):
            return False
        try:
            corr = np.corrcoef(seg_a[:len(seg_b)], seg_b)[0, 1]
            return corr > 0.65
        except Exception:
            return False

    def _has_reverb_tail(self, audio):
        """Detect reverb tail"""
        if len(audio) < 1000:
            return False
        rms = librosa.feature.rms(y=audio)[0]
        if len(rms) < 10:
            return False
        decay = rms[-len(rms)//3:]
        smooth = np.std(np.diff(decay)) < 0.002
        return smooth and rms[-1] < rms[0] * 0.3

    # ============================================================
    # PERCEPTUAL QUALITY SCORER
    # ============================================================

    def build_perceptual_scorer(self):
        """
        Build perceptual quality scorer from benchmarks
        Saves model that can score any transition
        against known good transitions
        """
        if not self.perceptual_benchmarks:
            print("❌ No benchmarks collected yet")
            print("   Run run_full_pipeline() first")
            return False

        print(f"\n🎯 Building perceptual scorer from "
              f"{len(self.perceptual_benchmarks)} benchmarks...")

        # Build reference distribution
        # (what good transitions look like)
        mfcc_matrix = []
        for b in self.perceptual_benchmarks:
            if b.get('mfcc_mean'):
                mfcc_matrix.append(b['mfcc_mean'])

        if not mfcc_matrix:
            print("❌ No MFCC data in benchmarks")
            return False

        mfcc_array = np.array(mfcc_matrix)

        # Compute reference statistics
        reference = {
            'mfcc_mean': np.mean(mfcc_array, axis=0).tolist(),
            'mfcc_std': np.std(mfcc_array, axis=0).tolist(),
            'mfcc_cov': np.cov(mfcc_array.T).tolist(),
            'n_benchmarks': len(self.perceptual_benchmarks),
            'built_at': str(datetime.now()),
            'channels': list(CHANNELS.keys()),
        }

        # Save reference
        ref_path = os.path.join(
            self.models_dir, 'perceptual_reference.json'
        )
        with open(ref_path, 'w') as f:
            json.dump(reference, f, indent=2)

        print(f"✅ Perceptual scorer saved: {ref_path}")
        print(f"   Based on {len(self.perceptual_benchmarks)} "
              f"real transitions")
        return True

    def score_transition_quality(self, transition_audio):
        """
        Score a generated transition against
        real DJ transition benchmarks
        Returns score 0.0 - 1.0
        1.0 = sounds like a professional DJ transition
        0.0 = sounds nothing like a pro transition
        """
        ref_path = os.path.join(
            self.models_dir, 'perceptual_reference.json'
        )

        if not os.path.exists(ref_path):
            print("   ⚠️  No perceptual reference built yet")
            return 0.5  # Neutral score

        with open(ref_path, 'r') as f:
            reference = json.load(f)

        # Extract MFCC from generated transition
        try:
            mfcc = librosa.feature.mfcc(
                y=transition_audio,
                sr=self.sr,
                n_mfcc=20
            )
            gen_mfcc = np.mean(mfcc, axis=1)
        except Exception:
            return 0.5

        # Compare against reference distribution
        ref_mean = np.array(reference['mfcc_mean'])
        ref_std = np.array(reference['mfcc_std']) + 1e-10

        # Normalize distance
        distances = np.abs(gen_mfcc[:len(ref_mean)] - ref_mean)
        normalized = distances / ref_std

        # Score: lower distance = more similar to pro transitions
        mean_distance = float(np.mean(normalized))
        score = max(0.0, 1.0 - (mean_distance / 5.0))

        return score

    # ============================================================
    # PROGRESS & PERSISTENCE
    # ============================================================

    def _load_progress(self):
        """Load pipeline progress"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _update_progress(self, channel_name, video_id):
        """Mark video as processed"""
        if channel_name not in self.progress:
            self.progress[channel_name] = {
                'processed_ids': [],
                'completed': False
            }
        if video_id not in self.progress[channel_name]['processed_ids']:
            self.progress[channel_name]['processed_ids'].append(video_id)

        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def _mark_channel_complete(self, channel_name):
        """Mark channel as fully processed"""
        if channel_name not in self.progress:
            self.progress[channel_name] = {'processed_ids': []}
        self.progress[channel_name]['completed'] = True

        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def _save_intermediate_results(self):
        """Save results collected so far"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if self.all_training_examples:
            path = os.path.join(
                self.training_dir,
                f'training_examples_{timestamp}.json'
            )
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(
                    self.all_training_examples, f,
                    indent=2, ensure_ascii=False
                )

        if self.perceptual_benchmarks:
            path = os.path.join(
                self.training_dir,
                f'benchmarks_{timestamp}.json'
            )
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(
                    self.perceptual_benchmarks, f,
                    indent=2, ensure_ascii=False
                )

    def _save_all_results(self):
        """Final save of all results"""
        self._save_intermediate_results()

        # Build perceptual scorer from all benchmarks
        self.build_perceptual_scorer()

        print(f"\n💾 All results saved to {self.training_dir}")

# ============================================================
# STANDALONE RUNNER
# ============================================================

if __name__ == "__main__":
    import yaml

    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    pipeline = TrainingDataPipeline(config)

    print("""
Choose what to run:
1. Full pipeline (all channels)
2. Shorts only (fastest - best for quick AI training)
3. Transitions only (BestDJTransitions + 69Beats)
4. Tutorials only (Phil Harris + Crossfader)
5. SiangyOO only
6. Build perceptual scorer from existing data
    """)

    choice = input("Enter choice (1-6): ").strip()

    if choice == '1':
        pipeline.run_full_pipeline()

    elif choice == '2':
        # Override all channels to shorts only
        for ch in CHANNELS.values():
            ch['shorts_only'] = True
            ch['max_videos'] = 100
        pipeline.run_full_pipeline()

    elif choice == '3':
        for name in ['phil_harris', 'crossfader', 'siangyoo']:
            CHANNELS[name]['priority'] = 99
        pipeline.run_full_pipeline()

    elif choice == '4':
        for name in ['best_dj_transitions', '69beats', 'siangyoo']:
            CHANNELS[name]['priority'] = 99
        pipeline.run_full_pipeline()

    elif choice == '5':
        for name in CHANNELS:
            if name != 'siangyoo':
                CHANNELS[name]['priority'] = 99
        pipeline.run_full_pipeline()

    elif choice == '6':
        # Load existing benchmarks and build scorer
        for filename in os.listdir(pipeline.training_dir):
            if filename.startswith('benchmarks_'):
                path = os.path.join(pipeline.training_dir, filename)
                with open(path, 'r') as f:
                    pipeline.perceptual_benchmarks.extend(
                        json.load(f)
                    )
        print(f"Loaded {len(pipeline.perceptual_benchmarks)} benchmarks")
        pipeline.build_perceptual_scorer()
