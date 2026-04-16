import numpy as np
import librosa
import os

class QualityAgent:
    """
    Pre-flight quality check before executing transition
    Renders transition silently and scores it
    """
    def __init__(self, config):
        self.config = config
        self.threshold = config['transitions']['quality_threshold']

    def check(self, current_analysis, next_analysis,
              technique, params):
        """
        Score how good this transition will sound
        Returns score 0.0 - 1.0
        """
        score = 1.0
        penalties = []

        # ---- BPM Check ----
        bpm_diff = abs(
            current_analysis.get('bpm', 120) -
            next_analysis.get('bpm', 120)
        )

        if technique == 'beatmatch_crossfade':
            if bpm_diff > 10:
                penalties.append(('bpm_mismatch', 0.3))
            elif bpm_diff > 5:
                penalties.append(('bpm_slight', 0.1))

        # ---- Key Check ----
        if technique in ['beatmatch_crossfade', 'tone_play',
                         'filter_sweep']:
            camelot_a = current_analysis.get('camelot', '')
            camelot_b = next_analysis.get('camelot', '')

            if camelot_a and camelot_b:
                if camelot_a == camelot_b:
                    pass  # Perfect
                elif camelot_a[:-1] == camelot_b[:-1]:
                    penalties.append(('key_slight', 0.05))
                else:
                    penalties.append(('key_mismatch', 0.2))

        # ---- Energy Check ----
        energy_diff = abs(
            current_analysis.get('energy_mean', 0) -
            next_analysis.get('energy_mean', 0)
        )
        if energy_diff > 0.1:
            penalties.append(('energy_mismatch', 0.15))

        # ---- Technique-specific checks ----
        if technique == 'wordplay':
            if not params.get('word_clip_a'):
                penalties.append(('no_word_clip', 0.5))

        if technique == 'tone_play':
            if not params.get('melody_notes'):
                penalties.append(('no_melody', 0.4))

        # ---- Apply penalties ----
        for reason, penalty in penalties:
            score -= penalty

        score = max(0.0, min(1.0, score))

        if penalties:
            print(f"   Quality issues: {[p[0] for p in penalties]}")
        print(f"   Quality score: {score:.2f}")

        return score
