import os
import json
import re
try:
    import whisper
except ImportError:
    whisper = None

import yt_dlp
from datetime import datetime

class TutorialParser:
    """
    Parses DJ tutorial videos to extract
    labeled transition technique examples
    for AI training data
    """
    def __init__(self, config):
        self.config = config
        self.training_dir = config['paths']['training_data']
        self.whisper_model = None
        os.makedirs(self.training_dir, exist_ok=True)

        # Keywords that indicate technique explanation
        self.technique_indicators = {
            'beatmatch_crossfade': [
                'beatmatch', 'beat match', 'sync', 'crossfade',
                'cross fade', 'blend', 'mix in', 'bpm match'
            ],
            'filter_sweep': [
                'filter', 'high pass', 'low pass', 'eq sweep',
                'filter sweep', 'kill the bass', 'open the filter'
            ],
            'echo_out': [
                'echo', 'delay', 'echo out', 'delay out',
                'bounce out', 'delay effect'
            ],
            'loop_roll': [
                'loop', 'roll', 'loop roll', 'stutter',
                'loop out', 'rolling loop'
            ],
            'reverb_wash': [
                'reverb', 'wash', 'reverb wash', 'reverb out',
                'atmospheric', 'reverb effect'
            ],
            'spinback': [
                'spinback', 'spin back', 'rewind', 'brake',
                'spin out', 'backspin'
            ],
            'phrase_matching': [
                'phrase', 'eight bar', '8 bar', 'sixteen bar',
                '16 bar', 'phrase match', 'on the one',
                'bar count', 'count the bars'
            ],
            'harmonic_mixing': [
                'harmonic', 'camelot', 'key', 'same key',
                'compatible key', 'harmonic mix', 'key mixing'
            ],
            'wordplay': [
                'word', 'vocal', 'acapella', 'word play',
                'vocal transition', 'word match', 'lyric'
            ],
            'tone_play': [
                'tone', 'melody', 'note', 'pitch',
                'melodic', 'tune', 'musical'
            ],
        }

    def parse_channel(self, channel_url, max_videos=30):
        """
        Parse all tutorial videos from a channel
        Returns list of labeled training examples
        """
        print(f"\n📺 Parsing channel: {channel_url}")

        # Get video list
        videos = self._get_channel_videos(channel_url, max_videos)
        print(f"   Found {len(videos)} videos")

        all_examples = []

        for i, video in enumerate(videos):
            print(f"   [{i+1}/{len(videos)}] {video['title'][:50]}")

            try:
                examples = self._parse_video(video)
                all_examples.extend(examples)
                print(f"      → {len(examples)} training examples extracted")
            except Exception as e:
                print(f"      ❌ Failed: {e}")
                continue

        # Save training data
        output_path = os.path.join(
            self.training_dir,
            f"parsed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_examples, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved {len(all_examples)} examples to {output_path}")
        return all_examples

    def _get_channel_videos(self, channel_url, max_videos):
        """Get list of videos from YouTube channel"""
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': max_videos,
        }
        videos = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            for entry in info.get('entries', []):
                if entry and entry.get('duration', 0) < 1800:
                    videos.append({
                        'id': entry.get('id'),
                        'title': entry.get('title', ''),
                        'url': f"https://youtube.com/watch?v={entry.get('id')}",
                        'duration': entry.get('duration', 0)
                    })
        return videos

    def _parse_video(self, video):
        """
        Parse a single tutorial video
        Returns list of training examples
        """
        # Download audio
        audio_path = self._download_audio(video)
        if not audio_path:
            return []

        # Transcribe
        transcript_data = self._transcribe(audio_path)

        # Cleanup audio
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if not transcript_data:
            return []

        # Extract technique examples from transcript
        examples = self._extract_examples(
            transcript_data, video
        )

        return examples

    def _download_audio(self, video):
        """Download audio for transcription"""
        output_path = os.path.join(
            self.training_dir, f"tmp_{video['id']}.mp3"
        )

        if os.path.exists(output_path):
            return output_path

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'quiet': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video['url']])
            return output_path
        except Exception as e:
            print(f"      ❌ Download failed: {e}")
            return None

    def _transcribe(self, audio_path):
        """Transcribe audio with word timestamps"""
        if not self.whisper_model:
            print("      Loading Whisper...")
            self.whisper_model = whisper.load_model("base")

        try:
            result = self.whisper_model.transcribe(
                audio_path,
                word_timestamps=True
            )
            return result
        except Exception as e:
            print(f"      ❌ Transcription failed: {e}")
            return None

    def _extract_examples(self, transcript_data, video):
        """
        Extract labeled training examples
        from transcript segments
        """
        examples = []
        segments = transcript_data.get('segments', [])
        full_text = transcript_data.get('text', '').lower()

        # Check which techniques are mentioned
        mentioned_techniques = []
        for technique, keywords in self.technique_indicators.items():
            for kw in keywords:
                if kw in full_text:
                    mentioned_techniques.append(technique)
                    break

        # Extract context around each technique mention
        for technique in mentioned_techniques:
            keywords = self.technique_indicators[technique]

            for segment in segments:
                seg_text = segment.get('text', '').lower()

                for kw in keywords:
                    if kw in seg_text:
                        # Found technique mention in this segment
                        context = self._get_context(
                            segments,
                            segment,
                            window=3
                        )

                        examples.append({
                            'video_id': video['id'],
                            'video_title': video['title'],
                            'technique': technique,
                            'timestamp': segment.get('start', 0),
                            'text': segment.get('text', ''),
                            'context': context,
                            'keyword_found': kw,
                            'source': 'tutorial',
                        })
                        break

        return examples

    def _get_context(self, segments, target_segment, window=3):
        """Get surrounding segments for context"""
        try:
            idx = segments.index(target_segment)
        except ValueError:
            return target_segment.get('text', '')

        start = max(0, idx - window)
        end = min(len(segments), idx + window + 1)

        context_texts = [
            s.get('text', '') for s in segments[start:end]
        ]
        return ' '.join(context_texts)
