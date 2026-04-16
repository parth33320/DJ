import os
import json
import numpy as np
import librosa
from datetime import datetime

class AutoLabeler:
    """
    Automatically labels transition points
    in DJ mix videos/audio without tutorials
    Detects WHERE transitions happen and
    tries to classify WHAT technique was used
    """
    def __init__(self, config):
        self.config = config
        self.training_dir = config['paths']['training_data']
        self.sr = config['audio']['sample_rate']
        os.makedirs(self.training_dir, exist_ok=True)

    def label_mix(self, filepath, mix_id):
        """
        Auto-label all transitions in a DJ mix
        Returns list of labeled transition examples
        """
        print(f"\n🔍 Auto-labeling: {mix_id}")

        y, sr = librosa.load(filepath, sr=self.sr, mono=True)

        # Step 1: Find transition points
        transition_points = self._detect_transitions(y, sr)
        print(f"   Found {len(transition_points)} potential transitions")

        # Step 2: Classify each transition
        labeled = []
        for tp in transition_points:
            technique = self._classify_transition(y, sr, tp)
            features = self._extract_features_around(y, sr, tp)

            labeled.append({
                'mix_id': mix_id,
                'timestamp': tp,
                'technique': technique,
                'confidence': features.get('confidence', 0.5),
                'features': features,
                'source': 'auto_labeled',
                'labeled_at': str(datetime.now())
            })

        # Save
        output_path = os.path.join(
            self.training_dir,
            f"autolabeled_{mix_id}.json"
        )
        with open(output_path, 'w') as f:
            json.dump(labeled, f, indent=2)

        print(f"   ✅ Labeled {len(labeled)} transitions")
        return labeled

    def _detect_transitions(self, y, sr):
        """
        Detect transition points using:
        - Spectral flux (sudden spectrum changes)
        - Energy changes
        - Onset detection
        """
        hop_length = 512
        transition_points = []

        # Spectral flux
        spec = np.abs(librosa.stft(y, hop_length=hop_length))
        flux = np.sum(np.diff(spec, axis=1) ** 2, axis=0)
        flux_times = librosa.frames_to_time(
            np.arange(len(flux)), sr=sr, hop_length=hop_length
        )

        # RMS energy
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        rms_times = librosa.frames_to_time(
            np.arange(len(rms)), sr=sr, hop_length=hop_length
        )

        # Find peaks in spectral flux
        from scipy.signal import find_peaks
        flux_normalized = flux / (np.max(flux) + 1e-10)

        # Look for significant changes
        peaks, properties = find_peaks(
            flux_normalized,
            height=0.3,
            distance=sr // hop_length * 10  # Min 10 seconds apart
        )

        for peak in peaks:
            t = flux_times[peak]

            # Skip very beginning and end
            duration = len(y) / sr
            if t < 10 or t > duration - 10:
                continue

            transition_points.append(float(t))

        # Also detect energy drops/jumps
        rms_diff = np.abs(np.diff(rms))
        energy_peaks, _ = find_peaks(
            rms_diff / (np.max(rms_diff) + 1e-10),
            height=0.4,
            distance=sr // hop_length * 10
        )

        for peak in energy_peaks:
            t = float(rms_times[min(peak, len(rms_times)-1)])
            duration = len(y) / sr
            if t < 10 or t > duration - 10:
                continue

            # Add if not already detected within 5 seconds
            if not any(abs(t - existing) < 5 for existing in transition_points):
                transition_points.append(t)

        transition_points.sort()
        return transition_points

    def _classify_transition(self, y, sr, transition_time):
        """
        Classify what technique was used at transition_time
        Returns technique name string
        """
        # Extract audio windows before and after
        window = int(sr * 4)
        t_sample = int(transition_time * sr)

        before = y[max(0, t_sample - window):t_sample]
        after = y[t_sample:min(len(y), t_sample + window)]

        if len(before) < 100 or len(after) < 100:
            return 'cut_transition'

        # Feature extraction
        energy_before = float(np.sqrt(np.mean(before ** 2)))
        energy_after = float(np.sqrt(np.mean(after ** 2)))

        # Check for echo pattern (repeating transients)
        has_echo = self._detect_echo_pattern(before)

        # Check for filter sweep (spectral centroid change)
        has_filter = self._detect_filter_sweep(before, after, sr)

        # Check for reverb tail
        has_reverb = self._detect_reverb_tail(before, sr)

        # Check for loop roll (repeating short segments)
        has_loop = self._detect_loop_pattern(before, sr)

        # Check for hard cut (abrupt change)
        is_cut = self._detect_hard_cut(before, after)

        # Decision logic
        if has_loop:
            return 'loop_roll'
        elif has_echo:
            return 'echo_out'
        elif has_filter:
            return 'filter_sweep'
        elif has_reverb:
            return 'reverb_wash'
        elif is_cut:
            return 'cut_transition'
        elif energy_before > energy_after * 1.5:
            return 'echo_out'
        elif energy_after > energy_before * 1.5:
            return 'filter_sweep'
        else:
            return 'beatmatch_crossfade'

    def _detect_echo_pattern(self, audio):
        """Detect echo/delay pattern in audio"""
        if len(audio) < 1000:
            return False
        # Autocorrelation to find repeating patterns
        corr = np.correlate(audio[:4000], audio[:4000], mode='full')
        corr = corr[len(corr)//2:]
        corr = corr / (corr[0] + 1e-10)
        # Look for secondary peaks (echoes)
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(corr[100:2000], height=0.3)
        return len(peaks) > 2

    def _detect_filter_sweep(self, before, after, sr):
        """Detect spectral centroid change indicating filter sweep"""
        if len(before) < 100 or len(after) < 100:
            return False
        centroid_before = float(np.mean(
            librosa.feature.spectral_centroid(y=before, sr=sr)
        ))
        centroid_after = float(np.mean(
            librosa.feature.spectral_centroid(y=after, sr=sr)
        ))
        # Large centroid change = filter sweep
        return abs(centroid_after - centroid_before) > 1500

    def _detect_reverb_tail(self, audio, sr):
        """Detect reverb tail (long exponential decay)"""
        if len(audio) < sr:
            return False
        rms = librosa.feature.rms(y=audio)[0]
        if len(rms) < 10:
            return False
        # Check if energy decays smoothly (reverb characteristic)
        decay = rms[-len(rms)//3:]
        is_smooth_decay = np.std(np.diff(decay)) < 0.002
        return is_smooth_decay and rms[-1] < rms[0] * 0.3

    def _detect_loop_pattern(self, audio, sr):
        """Detect loop roll (repeating short segments)"""
        if len(audio) < sr:
            return False
        # Check for very regular repeating patterns
        short_len = int(sr * 0.25)  # 250ms
        if len(audio) < short_len * 4:
            return False

        segment = audio[:short_len]
        next_seg = audio[short_len:short_len * 2]

        if len(next_seg) < len(segment):
            return False

        correlation = np.corrcoef(
            segment[:len(next_seg)], next_seg
        )[0, 1]
        return correlation > 0.7

    def _detect_hard_cut(self, before, after):
        """Detect hard cut transition"""
        if len(before) < 100 or len(after) < 100:
            return True
        energy_before = np.sqrt(np.mean(before[-1000:] ** 2))
        energy_after = np.sqrt(np.mean(after[:1000] ** 2))
        # If energy jumps suddenly = hard cut
        ratio = max(energy_before, energy_after) / (
            min(energy_before, energy_after) + 1e-10
        )
        return ratio > 3.0

    def _extract_features_around(self, y, sr, transition_time):
        """Extract audio features around transition point"""
        window = int(sr * 4)
        t_sample = int(transition_time * sr)

        before = y[max(0, t_sample - window):t_sample]
        after = y[t_sample:min(len(y), t_sample + window)]

        features = {}

        if len(before) > 100:
            features['bpm_before'] = float(
                librosa.beat.beat_track(y=before, sr=sr)[0]
            )
            features['energy_before'] = float(
                np.sqrt(np.mean(before ** 2))
            )
            features['centroid_before'] = float(
                np.mean(librosa.feature.spectral_centroid(y=before, sr=sr))
            )

        if len(after) > 100:
            features['bpm_after'] = float(
                librosa.beat.beat_track(y=after, sr=sr)[0]
            )
            features['energy_after'] = float(
                np.sqrt(np.mean(after ** 2))
            )
            features['centroid_after'] = float(
                np.mean(librosa.feature.spectral_centroid(y=after, sr=sr))
            )

        features['confidence'] = 0.6
        return features
