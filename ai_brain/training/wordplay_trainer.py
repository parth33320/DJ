    def score_connection(self, word_match, analysis_a, analysis_b):
        """
        Score how good a wordplay connection would sound
        Returns float 0.0 - 1.0
        """
        import pickle

        model_path = os.path.join(
            self.models_dir, 'wordplay_classifier.pkl'
        )

        # Rule-based scoring baseline
        score = 0.5

        # Exact word match bonus
        if word_match.get('type') == 'exact':
            score += 0.3
        elif word_match.get('type') == 'phoneme':
            # Partial bonus based on phoneme similarity
            sim = word_match.get('similarity', 0.5)
            score += 0.15 * sim

        # Same language bonus
        lang_a = analysis_a.get('lyrics', {})
        lang_b = analysis_b.get('lyrics', {})
        if lang_a and lang_b:
            la = lang_a.get('language', '')
            lb = lang_b.get('language', '')
            if la == lb and la not in ('', 'unknown'):
                score += 0.2

        # Key compatibility bonus
        if analysis_a.get('camelot') == analysis_b.get('camelot'):
            score += 0.1

        # Energy compatibility bonus
        energy_diff = abs(
            analysis_a.get('energy_mean', 0) -
            analysis_b.get('energy_mean', 0)
        )
        if energy_diff < 0.02:
            score += 0.05

        # Use ML model if available
        if os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    saved = pickle.load(f)
                ml_model = saved['model']

                lang_a_str = analysis_a.get('lyrics', {}).get(
                    'language', ''
                ) if analysis_a.get('lyrics') else ''
                lang_b_str = analysis_b.get('lyrics', {}).get(
                    'language', ''
                ) if analysis_b.get('lyrics') else ''

                features = np.array([
                    1.0 if lang_a_str == lang_b_str else 0.0,
                    1.0 if word_match.get('type') == 'exact' else 0.5,
                    analysis_a.get('energy_mean', 0.05) * 10,
                    analysis_b.get('energy_mean', 0.05) * 10,
                    abs(
                        analysis_a.get('bpm', 120) -
                        analysis_b.get('bpm', 120)
                    ) / 100.0,
                    1.0 if (
                        analysis_a.get('camelot') ==
                        analysis_b.get('camelot')
                    ) else 0.0,
                ], dtype=np.float32).reshape(1, -1)

                proba = ml_model.predict_proba(features)[0]
                ml_score = float(proba[1])

                # Blend rule-based and ML scores
                score = (score * 0.4) + (ml_score * 0.6)

            except Exception as e:
                print(f"   ⚠️  ML scoring failed, using rules: {e}")

        return min(1.0, max(0.0, score))
