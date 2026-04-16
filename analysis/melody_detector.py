import librosa
import numpy as np
import json
import os

class MelodyDetector:
    """
    Detects main melody from audio
    Used by tone_play transition engine
    to preview incoming song's melody
    using outgoing song's instrument timbre
    """
    def __init__(self, config):
        self.config = config
        self.metadata_dir = config['paths']['metadata']
        self.sr = config['audio']['sample_rate']
        os.makedirs(self.metadata_dir, exist_ok=True)

    def detect(self, filepath, song_id):
        """
        Full melody detection pipeline
        Returns melody note sequence + timing
        """
        cache_path = os.path.join(
            self.metadata_dir, f"{song_id}_melody.json"
        )
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        print(f"   🎵 Detecting melody: {song_id}")

        y, sr = librosa.load(filepath, sr=self.sr, mono=True)

        # ---- Pitch Detection ----
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=sr
        )

        # Get voiced (non-silent) frames
        times = librosa.times_like(f0, sr=sr)
        voiced_f0 = np.where(voiced_flag, f0, np.nan)

        # Convert Hz to MIDI note numbers
        midi_notes = []
        note_times = []

        for i, (freq, t) in enumerate(zip(voiced_f0, times)):
            if not np.isnan(freq) and freq > 0:
                midi = librosa.hz_to_midi(freq)
                midi_notes.append(float(midi))
                note_times.append(float(t))

        # ---- Simplify melody (quantize to scale) ----
        quantized = self._quantize_to_scale(midi_notes)

        # ---- Find melodic phrases ----
        phrases = self._find_melodic_phrases(
            quantized, note_times
        )

        # ---- Find most memorable phrase ----
        hook = self._find_hook(phrases)

        # ---- Get instrument timbre info ----
        timbre = self._analyze_timbre(y, sr)

        result = {
            'song_id': song_id,
            'raw_notes': midi_notes[:100],
            'note_times': note_times[:100],
            'quantized_notes': quantized[:100],
            'phrases': phrases[:10],
            'hook': hook,
            'timbre': timbre,
            'dominant_note': int(np.median(midi_notes)) if midi_notes else 60,
            'note_range': {
                'min': int(min(midi_notes)) if midi_notes else 48,
                'max': int(max(midi_notes)) if midi_notes else 72,
            }
        }

        with open(cache_path, 'w') as f:
            json.dump(result, f, indent=2)

        return result

    def _quantize_to_scale(self, midi_notes):
        """
        Snap notes to nearest chromatic pitch
        Removes micro-tonal variations
        """
        return [round(n) for n in midi_notes]

    def _find_melodic_phrases(self, notes, times, gap_threshold=0.5):
        """
        Group notes into phrases based on timing gaps
        A gap > 0.5 seconds = new phrase
        """
        if not notes or not times:
            return []

        phrases = []
        current_phrase = {'notes': [], 'times': [], 'start': times[0]}

        for i in range(len(notes)):
            if i > 0:
                gap = times[i] - times[i-1]
                if gap > gap_threshold:
                    # Save current phrase
                    if len(current_phrase['notes']) >= 3:
                        current_phrase['end'] = times[i-1]
                        current_phrase['duration'] = (
                            current_phrase['end'] -
                            current_phrase['start']
                        )
                        phrases.append(current_phrase)
                    # Start new phrase
                    current_phrase = {
                        'notes': [],
                        'times': [],
                        'start': times[i]
                    }

            current_phrase['notes'].append(notes[i])
            current_phrase['times'].append(times[i])

        # Add last phrase
        if len(current_phrase['notes']) >= 3:
            current_phrase['end'] = times[-1]
            current_phrase['duration'] = (
                current_phrase['end'] - current_phrase['start']
            )
            phrases.append(current_phrase)

        return phrases

    def _find_hook(self, phrases):
        """
        Find the most memorable/repeated melodic phrase
        Hook = phrase that appears most often OR
               has highest note variety
        """
        if not phrases:
            return {'notes': [60, 62, 64, 65, 67], 'start': 0}

        # Score each phrase
        scored = []
        for phrase in phrases:
            notes = phrase['notes']
            # Score: note variety + length
            variety = len(set(notes))
            length = len(notes)
            # Prefer phrases in first third of song
            early_bonus = 1.5 if phrase.get('start', 0) < 60 else 1.0
            score = (variety * 2 + length) * early_bonus
            scored.append((score, phrase))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _analyze_timbre(self, y, sr):
        """
        Analyze timbral qualities to help
        tone_play engine pick best instrument sound
        """
        # Spectral centroid (brightness)
        centroid = float(np.mean(
            librosa.feature.spectral_centroid(y=y, sr=sr)
        ))

        # Spectral rolloff
        rolloff = float(np.mean(
            librosa.feature.spectral_rolloff(y=y, sr=sr)
        ))

        # Zero crossing rate (noisiness)
        zcr = float(np.mean(
            librosa.feature.zero_crossing_rate(y=y)
        ))

        # MFCCs (timbral texture)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_means = np.mean(mfccs, axis=1).tolist()

        # Classify dominant instrument type
        instrument_type = self._classify_instrument(
            centroid, rolloff, zcr
        )

        return {
            'spectral_centroid': centroid,
            'spectral_rolloff': rolloff,
            'zero_crossing_rate': zcr,
            'mfcc_means': mfcc_means,
            'instrument_type': instrument_type,
            'brightness': 'bright' if centroid > 3000 else 'warm',
        }

    def _classify_instrument(self, centroid, rolloff, zcr):
        """Classify dominant instrument from spectral features"""
        if centroid > 5000 and zcr > 0.1:
            return 'strings_or_synth'
        elif centroid > 3000 and zcr < 0.05:
            return 'piano_or_keys'
        elif centroid < 1500:
            return 'bass_or_pad'
        elif zcr > 0.15:
            return 'guitar_or_percussion'
        else:
            return 'vocal_or_mixed'

    def get_tone_play_sample(self, filepath, song_id,
                              sample_duration=0.5):
        """
        Extract the best short audio sample to use
        as the 'instrument' in tone play transitions
        Returns: (audio_array, sample_rate)
        """
        import soundfile as sf

        melody_data = self.detect(filepath, song_id)
        hook = melody_data.get('hook', {})
        start_time = hook.get('start', 10.0)

        y, sr = librosa.load(
            filepath,
            sr=self.sr,
            offset=start_time,
            duration=sample_duration,
            mono=True
        )

        return y, sr
