import random
import os
import json

class TransitionAgent:
    """
    Decides which transition technique to use
    and what parameters to apply
    """
    def __init__(self, config):
        self.config = config
        self.weights_path = 'data/logs/feedback_weights.json'
        
        # Technique rules: (technique, rule_func)
        self.technique_rules = [
            ('beatmatch_crossfade', self._rule_beatmatch),
            ('filter_sweep', self._rule_filter_sweep),
            ('echo_out', self._rule_echo_out),
            ('loop_roll', self._rule_loop_roll),
            ('reverb_wash', self._rule_reverb_wash),
            ('spinback', self._rule_spinback),
            ('cut_transition', self._rule_cut),
            ('tempo_ramp', self._rule_tempo_ramp),
            ('white_noise_sweep', self._rule_white_noise),
            ('vinyl_scratch_flourish', self._rule_scratch),
            ('tone_play', self._rule_tone_play),
            ('half_time_transition', self._rule_half_time),
            ('double_time_transition', self._rule_double_time),
        ]

    def _load_feedback_weights(self):
        """Load user feedback weights to influence decision"""
        if os.path.exists(self.weights_path):
            try:
                with open(self.weights_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def decide(self, *args):
        """
        Flexible decide method to handle multiple call signatures:
        1. (current_ana, next_ana, compatibility) -> Main Loop
        2. (current_id, next_id, current_ana, next_ana) -> UI/Mobile Tester
        """
        feedback = self._load_feedback_weights()
        
        if len(args) == 4:
            # Signiture: (current_id, next_id, cur_ana, nxt_ana)
            cur_id, nxt_id, cur_ana, nxt_ana = args
        elif len(args) == 3:
            # Signiture: (cur_ana, nxt_ana, compatibility)
            cur_ana, nxt_ana, compatibility = args
            cur_id, nxt_id = "unknown", "unknown"
        else:
            raise ValueError(f"TransitionAgent.decide received {len(args)} args, expected 3 or 4")

        scores = {}
        for technique, rule_func in self.technique_rules:
            # Base score from musical theory
            base_score = rule_func(cur_ana, nxt_ana, {})
            
            # Apply learning weight (defaults to 1.0)
            user_weight = feedback.get(technique, 1.0)
            
            # Final score (clamped)
            scores[technique] = max(0.01, base_score * user_weight)

        # Sort by score
        sorted_techniques = sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        )

        # Pick from top 3 with weighted randomness
        top3 = sorted_techniques[:3]
        techniques = [t[0] for t in top3]
        weights = [t[1] for t in top3]
        
        chosen = random.choices(techniques, weights=weights, k=1)[0]
        
        # If called from UI/Mobile, return (technique, params)
        if len(args) == 4:
            params = self.get_params(cur_ana, nxt_ana, chosen)
            return chosen, params
            
        # If called from Main Loop, return just the technique (it calls get_params later)
        return chosen

    def get_params(self, current_analysis, next_analysis, technique):
        """Get parameters for chosen technique"""
        bpm = current_analysis.get('bpm', 120)
        seconds_per_bar = (60 / bpm) * 4

        params = {
            'beatmatch_crossfade': {
                'crossfade_bars': 8,
                'bpm_a': current_analysis.get('bpm', 120),
                'bpm_b': next_analysis.get('bpm', 120),
            },
            'filter_sweep': {
                'sweep_duration': seconds_per_bar * 4,
                'start_freq': 20,
                'end_freq': 8000,
            },
            'echo_out': {
                'delay_ms': 375,
                'feedback': 0.6,
                'echo_bars': 4,
            },
            'loop_roll': {
                'bars': [1, 0.5, 0.25, 0.125],
                'repeats_per_division': 2,
            },
            'reverb_wash': {
                'reverb_size': 'large',
                'wash_duration': seconds_per_bar * 4,
            },
            'spinback': {
                'spin_duration': 2.0,
                'speed_multiplier': 4,
            },
            'cut_transition': {
                'cut_time': current_analysis.get(
                    'transition_points', {}
                ).get('outro_beat', 0),
                'nxt_start_time': next_analysis.get(
                    'entry_points', {}
                ).get('best_entry', {}).get('time', 0) if next_analysis.get(
                    'entry_points'
                ) else 0,
            },
            'tempo_ramp': {
                'ramp_bars': 16,
                'bpm_a': current_analysis.get('bpm', 120),
                'bpm_b': next_analysis.get('bpm', 120),
            },
            'white_noise_sweep': {
                'sweep_duration': 4.0,
                'noise_volume': 0.1,
            },
            'vinyl_scratch_flourish': {
                'rewind_bars': 4,
                'scratch_time': current_analysis.get(
                    'transition_points', {}
                ).get('outro_beat', 0),
            },
            'tone_play': {
                'melody_notes': next_analysis.get('melody_notes', [60, 62, 64]),
                'note_duration': 60 / current_analysis.get('bpm', 120),
                'preview_bars': 4,
            },
        }

        return params.get(technique, {})

    def get_fallback(self, current_analysis, next_analysis):
        """Get safe fallback technique"""
        bpm_diff = abs(
            current_analysis.get('bpm', 120) - next_analysis.get('bpm', 120)
        )
        if bpm_diff < 10:
            return 'beatmatch_crossfade'
        elif bpm_diff < 30:
            return 'echo_out'
        else:
            return 'cut_transition'

    # ---- Rule Functions (return score 0-1) ----

    def _rule_beatmatch(self, cur, nxt, compat):
        bpm_diff = abs(cur.get('bpm', 120) - nxt.get('bpm', 120))
        if bpm_diff < 5:
            return 0.95
        elif bpm_diff < 15:
            return 0.6
        return 0.1

    def _rule_filter_sweep(self, cur, nxt, compat):
        genres = [cur.get('genre_hint', ''), nxt.get('genre_hint', '')]
        if any('EDM' in g or 'House' in g or 'Dance' in g for g in genres):
            return 0.85
        return 0.2

    def _rule_echo_out(self, cur, nxt, compat):
        energy_drop = (
            cur.get('energy_mean', 0) > nxt.get('energy_mean', 0)
        )
        if energy_drop:
            return 0.8
        return 0.3

    def _rule_loop_roll(self, cur, nxt, compat):
        genres = [cur.get('genre_hint', ''), nxt.get('genre_hint', '')]
        if any('EDM' in g or 'House' in g or 'Drum' in g for g in genres):
            return 0.75
        return 0.25

    def _rule_reverb_wash(self, cur, nxt, compat):
        if cur.get('bpm', 120) < 90:
            return 0.8
        if 'Ambient' in cur.get('genre_hint', ''):
            return 0.9
        return 0.2

    def _rule_spinback(self, cur, nxt, compat):
        genre_change = cur.get('genre_hint') != nxt.get('genre_hint')
        bpm_diff = abs(cur.get('bpm', 120) - nxt.get('bpm', 120))
        if genre_change and bpm_diff > 20:
            return 0.75
        return 0.1

    def _rule_cut(self, cur, nxt, compat):
        bpm_diff = abs(cur.get('bpm', 120) - nxt.get('bpm', 120))
        if bpm_diff > 30:
            return 0.85
        return 0.3

    def _rule_tempo_ramp(self, cur, nxt, compat):
        bpm_diff = abs(cur.get('bpm', 120) - nxt.get('bpm', 120))
        if 10 <= bpm_diff <= 30:
            return 0.8
        return 0.2

    def _rule_white_noise(self, cur, nxt, compat):
        genre_change = cur.get('genre_hint') != nxt.get('genre_hint')
        if genre_change:
            return 0.6
        return 0.2

    def _rule_scratch(self, cur, nxt, compat):
        genres = [cur.get('genre_hint', ''), nxt.get('genre_hint', '')]
        if any('Hip-Hop' in g or 'R&B' in g for g in genres):
            return 0.8
        return 0.15

    def _rule_tone_play(self, cur, nxt, compat):
        camelot_cur = cur.get('camelot', '')
        camelot_nxt = nxt.get('camelot', '')
        if camelot_cur and camelot_nxt:
            if camelot_cur == camelot_nxt:
                return 0.85
            if camelot_cur[:-1] == camelot_nxt[:-1]:
                return 0.7
        return 0.2

    def _rule_half_time(self, cur, nxt, compat):
        bpm_a = cur.get('bpm', 120)
        bpm_b = nxt.get('bpm', 120)
        if 130 <= bpm_a <= 160 and 65 <= bpm_b <= 85:
            return 0.95
        return 0.1

    def _rule_double_time(self, cur, nxt, compat):
        bpm_a = cur.get('bpm', 120)
        bpm_b = nxt.get('bpm', 120)
        if 60 <= bpm_a <= 85 and 120 <= bpm_b <= 165:
            return 0.95
        return 0.1
