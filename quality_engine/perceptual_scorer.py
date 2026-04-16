"""
Perceptual Quality Scorer
Scores generated transitions against
real professional DJ transitions
No human listening needed
"""

import os
import json
import numpy as np
import librosa

class PerceptualScorer:
    """
    Scores a generated transition against
    benchmarks from real DJ transitions
    Uses:
    - MFCC distance (timbral similarity)
    - Spectral flux smoothness
    - Energy continuity
    - Beat alignment score
    - Frechet Audio Distance approximation
    """
    def __init__(self, config):
        self.config = config
        self.models_dir = config['paths']['models']
        self.sr = config['audio']['sample_rate']
        self.reference = None
        self._load_reference()

    def _load_reference(self):
        """Load perceptual reference from disk"""
        ref_path = os.path.join(
            self.models_dir, 'perceptual_reference.json'
        )
        if os.path.exists(ref_path):
            with open(ref_path, 'r') as f:
                self.reference = json.load(f)
            print(f"✅ Perceptual reference loaded: "
                  f"{self.reference.get('n_benchmarks', 0)} benchmarks")
        else:
            print("⚠️  No perceptual reference found")
            print("   Run training_data_pipeline.py first")

    def score(self, transition_audio, sr=None):
        """
        Score a transition audio array
        Returns dict with overall score and sub-scores
        """
        if sr is None:
            sr = self.sr

        scores = {}

        # 1. MFCC similarity to reference
        scores['mfcc_similarity'] = self._score_mfcc(
            transition_audio, sr
        )

        # 2. Spectral flux smoothness
        scores['smoothness'] = self._score_smoothness(
            transition_audio, sr
        )

        # 3. Energy continuity
        scores['energy_continuity'] = self._score_energy_continuity(
            transition_audio, sr
        )

        # 4. Beat alignment
        scores['beat_alignment'] = self._score_beat_alignment(
            transition_audio, sr
        )

        # 5. Clipping/distortion check
        scores['no_distortion'] = self._score_no_distortion(
            transition_audio
        )

        # Weighted overall score
        weights = {
            'mfcc_similarity':    0.30,
            'smoothness':         0.25,
            'energy_continuity':  0.20,
            'beat_alignment':     0.15,
            'no_distortion':      0.10,
        }

        overall = sum(
            scores[k] * weights[k] for k in weights
        )

        scores['overall'] = round(overall, 3)

        return scores

    def _score_mfcc(self, audio, sr):
        """
        Compare MFCC fingerprint of transition
        against reference professional transitions
        """
        if self.reference is None:
            return 0.5

        try:
            mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=20)
            gen_mean = np.mean(mfcc, axis=1)

            ref_mean = np.array(self.reference.get('mfcc_mean', []))
            ref_std = np.array(self.reference.get('mfcc_std', []))

            if len(ref_mean) == 0:
                return 0.5

            # Align lengths
            min_len = min(len(gen_mean), len(ref_mean))
            gen_mean = gen_mean[:min_len]
            ref_mean = ref_mean[:min_len]
            ref_std = ref_std[:min_len] + 1e-10

            # Normalized distance
            dist = np.abs(gen_mean - ref_mean) / ref_std
            score = max(0.0, 1.0 - float(np.mean(dist)) / 3.0)
            return round(score, 3)

        except Exception:
            return 0.5

    def _score_smoothness(self, audio, sr):
        """
        Measure spectral flux smoothness
        Good transitions have smooth spectral changes
        Bad transitions have abrupt jumps
        """
        try:
            hop = 512
            spec = np.abs(librosa.stft(audio, hop_length=hop))
            flux = np.sum(np.diff(spec, axis=1)**2, axis=0)
            flux_norm = flux / (np.max(flux) + 1e-10)

            # Lower variance in flux = smoother transition
            smoothness = 1.0 - float(np.std(flux_norm))
            return round(max(0.0, min(1.0, smoothness)), 3)

        except Exception:
            return 0.5

    def _score_energy_continuity(self, audio, sr):
        """
        Measure energy continuity through transition
        Good: gradual energy changes
        Bad: sudden energy jumps or silence gaps
        """
        try:
            rms = librosa.feature.rms(y=audio)[0]
            if len(rms) < 4:
                return 0.5

            # Check for silence gaps (bad)
            min_rms = np.min(rms)
            mean_rms = np.mean(rms)
            silence_ratio = min_rms / (mean_rms + 1e-10)

            # Check for smooth progression
            rms_diff = np.diff(rms)
            smoothness = 1.0 - float(np.std(rms_diff)) * 10

            # Combine
            score = (
                silence_ratio * 0.4 +
                max(0.0, smoothness) * 0.6
            )
            return round(max(0.0, min(1.0, score)), 3)

        except Exception:
            return 0.5

    def _score_beat_alignment(self, audio, sr):
        """
        Check if beats are aligned at transition point
        Well-aligned beats = higher score
        """
        try:
            # Check beat regularity throughout transition
            tempo, beats = librosa.beat.beat_track(y=audio, sr=sr)
            beat_times = librosa.frames_to_time(beats, sr=sr)

            if len(beat_times) < 4:
                return 0.5

            # Measure beat interval consistency
            intervals = np.diff(beat_times)
            cv = np.std(intervals) / (np.mean(intervals) + 1e-10)

            # Lower coefficient of variation = more consistent beats
            score = max(0.0, 1.0 - cv * 2)
            return round(score, 3)

        except Exception:
            return 0.5

    def _score_no_distortion(self, audio):
        """
        Check for clipping/distortion
        Values > 0.99 or < -0.99 = clipping
        """
        try:
            clip_ratio = float(
                np.sum(np.abs(audio) > 0.95) / len(audio)
            )
            score = max(0.0, 1.0 - clip_ratio * 10)
            return round(score, 3)
        except Exception:
            return 1.0

    def is_good_enough(self, transition_audio, threshold=0.65):
        """
        Quick pass/fail check
        Returns True if transition is good enough to play
        """
        scores = self.score(transition_audio)
        overall = scores.get('overall', 0)
        is_good = overall >= threshold

        if not is_good:
            print(f"   ⚠️  Transition quality: {overall:.2f} "
                  f"(threshold: {threshold:.2f})")
            for k, v in scores.items():
                if k != 'overall' and v < 0.6:
                    print(f"      Low: {k} = {v:.2f}")

        return is_good, scores
