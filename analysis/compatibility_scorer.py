class CompatibilityScorer:
    def __init__(self, config):
        self.config = config
        self.compatible_camelot_pairs = self._build_camelot_pairs()

    def score(self, analysis_a, analysis_b):
        """
        Score compatibility 0-100 considering BPM, Camelot key proximity,
        energy flow, and language/genre safety constraints.
        """
        score = 0
        reasons = []

        # 1. BPM (40 points)
        bpm_a = analysis_a.get('bpm', 120)
        bpm_b = analysis_b.get('bpm', 120)
        bpm_diff = abs(bpm_a - bpm_b)

        # Allow half-time / double-time matching
        half_diff = abs(bpm_a * 2 - bpm_b)
        double_diff = abs(bpm_a / 2 - bpm_b)
        min_bpm_diff = min(bpm_diff, half_diff, double_diff)

        if min_bpm_diff < 3:
            score += 40
            reasons.append("✅ Perfect BPM / Harmonic tempo match")
        elif min_bpm_diff < 8:
            score += 28
            reasons.append("⚠️ Close BPM match")
        elif min_bpm_diff < 15:
            score += 18
            reasons.append("⚠️ Moderate BPM difference (Tempo ramp recommended)")
        else:
            score += 5
            reasons.append("❌ Large BPM difference")

        # 2. Key Compatibility (Camelot Wheel) (35 points)
        c1 = analysis_a.get('camelot', '')
        c2 = analysis_b.get('camelot', '')
        if c1 and c2:
            if c1 == c2:
                score += 35
                reasons.append("✅ Same key")
            elif (c1, c2) in self.compatible_camelot_pairs or (c2, c1) in self.compatible_camelot_pairs:
                score += 25
                reasons.append("✅ Compatible Camelot key proximity")
            else:
                score += 8
                reasons.append("⚠️ Distant Camelot keys")
        else:
            score += 15
            reasons.append("ℹ️ Key information incomplete")

        # 3. Structural Energy & RMS Flow (25 points)
        e_a = analysis_a.get('energy_mean', 0.5)
        e_b = analysis_b.get('energy_mean', 0.5)
        e_diff = abs(e_a - e_b)

        if e_diff < 0.05:
            score += 25
            reasons.append("✅ Smooth energy flow match")
        elif e_diff < 0.15:
            score += 15
            reasons.append("⚠️ Moderate energy shift")
        else:
            score += 5
            reasons.append("⚠️ High energy transition gap")

        # 4. Multi-Language / Genre Safety Bias
        lang_a = analysis_a.get('lyrics', {}).get('language', '') if isinstance(analysis_a.get('lyrics'), dict) else ''
        lang_b = analysis_b.get('lyrics', {}).get('language', '') if isinstance(analysis_b.get('lyrics'), dict) else ''
        if lang_a and lang_b and lang_a == lang_b and lang_a != 'unknown':
            bias = self.config.get('transitions', {}).get('same_language_bias', 0.3)
            score += int(bias * 20)
            reasons.append(f"✅ Matching language ({lang_a}) bonus")

        # Recommend transition technique
        transition = self._recommend_transition(analysis_a, analysis_b, score, min_bpm_diff)

        return {
            'score': min(100, max(0, score)),
            'reasons': reasons,
            'recommended_transition': transition
        }

    def _recommend_transition(self, a1, a2, score, bpm_diff):
        if score >= 75 and bpm_diff < 5:
            return 'beatmatch_crossfade'
        elif bpm_diff > 15:
            return 'tempo_ramp'
        elif a1.get('energy_mean', 0) < a2.get('energy_mean', 0):
            return 'filter_sweep'
        else:
            return 'bass_swap'

    def _build_camelot_pairs(self):
        pairs = set()
        for k in range(1, 13):
            nxt = k % 12 + 1
            pairs.add((f"{k}A", f"{nxt}A"))
            pairs.add((f"{k}B", f"{nxt}B"))
            pairs.add((f"{k}A", f"{k}B"))
            # Adjacent keys
            prev = (k - 2) % 12 + 1
            pairs.add((f"{k}A", f"{prev}A"))
            pairs.add((f"{k}B", f"{prev}B"))
        return pairs
