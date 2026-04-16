import librosa
import numpy as np
import json
import os
import warnings
warnings.filterwarnings('ignore')

class AudioAnalyzer:
    def __init__(self, config):
        self.config = config
        self.metadata_dir = config['paths']['metadata']
        os.makedirs(self.metadata_dir, exist_ok=True)

        self.camelot_wheel = {
            'C major': '8B',  'A minor': '8A',
            'G major': '9B',  'E minor': '9A',
            'D major': '10B', 'B minor': '10A',
            'A major': '11B', 'F# minor': '11A',
            'E major': '12B', 'C# minor': '12A',
            'B major': '1B',  'G# minor': '1A',
            'F# major': '2B', 'D# minor': '2A',
            'C# major': '3B', 'A# minor': '3A',
            'G# major': '4B', 'F minor': '4A',
            'D# major': '5B', 'C minor': '5A',
            'A# major': '6B', 'G minor': '6A',
            'F major': '7B',  'D minor': '7A',
        }

    def analyze_track(self, filepath, song_id):
        cache_path = os.path.join(self.metadata_dir, f"{song_id}.json")
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        print(f"   🔍 Analyzing audio...")
        y, sr = librosa.load(filepath, sr=22050)

        # BPM & beats
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0]) # Ensure scalar
        beat_times = librosa.frames_to_time(beats, sr=sr)

        # Key detection
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)
        key_index = int(np.argmax(chroma_mean))
        keys = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
        detected_key = keys[key_index]
        mode = 'major'
        key_full = f"{detected_key} {mode}"
        camelot = self.camelot_wheel.get(key_full, 'Unknown')

        # Energy
        rms = librosa.feature.rms(y=y)[0]
        energy_mean = float(np.mean(rms))
        energy_sections = []
        section_size = max(1, len(rms) // 10)
        for i in range(10):
            section = rms[i*section_size:(i+1)*section_size]
            energy_sections.append(float(np.mean(section)))

        # Spectral features
        spectral_centroid = float(np.mean(
            librosa.feature.spectral_centroid(y=y, sr=sr)
        ))
        zero_crossing = float(np.mean(
            librosa.feature.zero_crossing_rate(y=y)
        ))

        # Genre
        genre_hint = self._classify_genre(
            tempo, spectral_centroid, energy_mean, zero_crossing
        )

        # Melody notes (simplified)
        melody_notes = self._extract_melody_notes(y, sr)

        # Transition points
        duration = float(len(y) / sr)
        outro_time = duration * 0.8
        if len(beat_times) > 0:
            outro_beat = float(min(
                beat_times, key=lambda x: abs(x - outro_time)
            ))
        else:
            outro_beat = outro_time

        analysis = {
            'song_id': song_id,
            'bpm': tempo,
            'key': detected_key,
            'mode': mode,
            'key_full': key_full,
            'camelot': camelot,
            'duration': duration,
            'energy_mean': energy_mean,
            'energy_sections': energy_sections,
            'spectral_centroid': spectral_centroid,
            'zero_crossing_rate': zero_crossing,
            'genre_hint': genre_hint,
            'melody_notes': melody_notes,
            'beat_times': beat_times[:20].tolist(),
            'transition_points': {
                'outro_beat': outro_beat,
                'safe_transition_start': duration * 0.75,
                'emergency_cutpoint': duration * 0.95
            }
        }

        with open(cache_path, 'w') as f:
            json.dump(analysis, f, indent=2)

        return analysis

    def load_all_metadata(self):
        """Load all cached metadata"""
        metadata = {}
        for filename in os.listdir(self.metadata_dir):
            if filename.endswith('.json') and '_phrases' not in filename \
               and '_entries' not in filename:
                song_id = filename.replace('.json', '')
                filepath = os.path.join(self.metadata_dir, filename)
                with open(filepath, 'r') as f:
                    metadata[song_id] = json.load(f)
        print(f"✅ Loaded {len(metadata)} cached analyses")
        return metadata

    def _classify_genre(self, bpm, spectral_centroid, energy, zcr):
        if bpm > 140 and energy > 0.1:
            return 'EDM/Techno'
        elif bpm > 120 and spectral_centroid > 3000:
            return 'House/Dance'
        elif bpm > 130 and zcr > 0.1:
            return 'Drum & Bass'
        elif bpm < 80 and energy < 0.05:
            return 'Ambient/Chill'
        elif 85 < bpm < 110 and zcr > 0.08:
            return 'Hip-Hop/Rap'
        elif 60 < bpm < 100 and spectral_centroid < 2000:
            return 'R&B/Soul'
        elif spectral_centroid > 4000 and zcr > 0.1:
            return 'Rock/Metal'
        else:
            return 'Pop/Other'

    def _extract_melody_notes(self, y, sr):
        """Extract main melody as MIDI note numbers"""
        try:
            f0, voiced_flag, _ = librosa.pyin(
                y, fmin=librosa.note_to_hz('C2'),
                fmax=librosa.note_to_hz('C7')
            )
            voiced_f0 = f0[voiced_flag]
            if len(voiced_f0) > 0:
                notes = librosa.hz_to_midi(voiced_f0[::10])
                return [int(n) for n in notes[:16] if not np.isnan(n)]
        except:
            pass
        return [60, 62, 64, 65, 67]  # Default C major scale
