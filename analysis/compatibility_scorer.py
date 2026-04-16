class CompatibilityScorer:
    def __init__(self, config):
        self.config = config
        self.compatible_camelot_pairs = self._build_camelot_pairs()

    def score(self, analysis_a, analysis_b):
        """Score compatibility 0-100"""
        score = 0
        reasons = []

        # BPM (40 points)
        bpm_diff = abs(
            analysis_a.get('bpm', 120) - analysis_b.get('bpm', 120)
        )
        if bpm_diff < 3:
            score += 40
            reasons.append("✅ Perfect BPM match")
        elif bpm_diff < 8:
            score += 28
            reasons.append("⚠️ Close BPM")
        elif bpm_diff < 20:
            score += 15
            reasons.append("⚠️ Moderate BPM difference")
        else:
            score += 5
            reasons.append("❌ Large BPM difference")

        # Key (35 points)
        c1 = analysis_a.get('camelot', '')
        c2 = analysis_b.get('camelot', '')
        if c1 and c2:
            if c1 == c2:
                score += 35
                reasons.append("✅ Same key")
            elif (c1, c2) in self.compatible_camelot_pairs or \
                 (c2, c1) in self.compatible_camelot_pairs:
                score += 25
                reasons.append("✅ Compatible keys")
            else:
                score += 5
                reasons.append("❌ Incompatible keys")

        # Energy (25 points)
        e_diff = abs(
            analysis_a.get('energy_mean', 0) -
            analysis_b.get('energy_mean', 0)
        )
        if e_diff < 0.02:
            score += 25
            reasons.append("✅ Matching energy")
        elif e_diff < 0.05:
            score += 15
            reasons.append("⚠️ Slight energy difference")
        else:
            score += 5
            reasons.append("⚠️ Energy shift")

        # Recommend technique
        transition = self._recommend_transition(analysis_a, analysis_b, score)

        return {
            'score': score,
            'reasons': reasons,
            'recommended_transition': transition
        }

    def _recommend_transition(self, a1, a2, score):
        bpm_diff = abs(a1.get('bpm', 120) - a2.get('bpm', 120))
        if score >= 70:
            return 'beatmatch_crossfade'
        elif bpm_diff > 20:
            return 'echo_out'
        elif a1.get('energy_mean', 0) < a2.get('energy_mean', 0):
            return 'filter_sweep'
        else:
            return 'reverb_wash'

    def _build_camelot_pairs(self):
        pairs = set()
        keys = list(range(1, 13))
        for k in keys:
            nxt = k % 12 + 1
            pairs.add((f"{k}A", f"{nxt}A"))
            pairs.add((f"{k}B", f"{nxt}B"))
            pairs.add((f"{k}A", f"{k}B"))
        return pairs
