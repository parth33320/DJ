import os
import json
import numpy as np
from datetime import datetime

class TransitionTrainer:
    """
    Trains the transition technique classifier
    from labeled tutorial data
    Input: song features of A + B
    Output: best transition technique
    """
    def __init__(self, config):
        self.config = config
        self.training_dir = config['paths']['training_data']
        self.models_dir = config['paths']['models']
        os.makedirs(self.models_dir, exist_ok=True)

        self.model = None
        self.label_encoder = None
        self.feature_names = [
            'bpm_a', 'bpm_b', 'bpm_diff', 'bpm_ratio',
            'energy_a', 'energy_b', 'energy_diff',
            'centroid_a', 'centroid_b', 'centroid_diff',
            'camelot_compatible', 'same_genre',
            'genre_a_encoded', 'genre_b_encoded',
        ]

        self.genre_map = {
            'EDM/Techno': 0, 'House/Dance': 1,
            'Hip-Hop/Rap': 2, 'R&B/Soul': 3,
            'Rock/Metal': 4, 'Ambient/Chill': 5,
            'Pop/Other': 6, 'Drum & Bass': 7,
        }

        self.technique_map = {
            'beatmatch_crossfade': 0,
            'cut_transition': 1,
            'echo_out': 2,
            'filter_sweep': 3,
            'loop_roll': 4,
            'reverb_wash': 5,
            'spinback': 6,
            'tempo_ramp': 7,
            'white_noise_sweep': 8,
            'wordplay': 9,
            'tone_play': 10,
            'mashup_short': 11,
            'acapella_layer': 12,
            'drum_swap': 13,
            'bass_swap': 14,
            'stutter_glitch': 15,
            'half_time_transition': 16,
            'wordplay_mashup': 17,
            'phrasal_interlace': 18,
            'semantic_bridge': 19,
            'mashup_extended': 20,
            'double_time_transition': 21,
        }

    def load_training_data(self):
        """Load all labeled training examples"""
        all_examples = []

        for filename in os.listdir(self.training_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.training_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        all_examples.extend(data)
                except Exception as e:
                    print(f"   ❌ Could not load {filename}: {e}")

        print(f"   📊 Loaded {len(all_examples)} training examples")
        return all_examples

    def extract_features(self, analysis_a, analysis_b):
        """
        Extract feature vector from two song analyses
        This is what the model uses to decide technique
        """
        bpm_a = analysis_a.get('bpm', 120)
        bpm_b = analysis_b.get('bpm', 120)
        bpm_diff = abs(bpm_a - bpm_b)
        bpm_ratio = min(bpm_a, bpm_b) / max(bpm_a, bpm_b)

        energy_a = analysis_a.get('energy_mean', 0.05)
        energy_b = analysis_b.get('energy_mean', 0.05)
        energy_diff = abs(energy_a - energy_b)

        centroid_a = analysis_a.get('spectral_centroid', 2000)
        centroid_b = analysis_b.get('spectral_centroid', 2000)
        centroid_diff = abs(centroid_a - centroid_b)

        # Camelot wheel compatibility
        c_a = analysis_a.get('camelot', '')
        c_b = analysis_b.get('camelot', '')
        camelot_compat = 1.0 if c_a == c_b else (
            0.5 if c_a[:-1] == c_b[:-1] else 0.0
        )

        genre_a = analysis_a.get('genre_hint', 'Pop/Other')
        genre_b = analysis_b.get('genre_hint', 'Pop/Other')
        same_genre = 1.0 if genre_a == genre_b else 0.0

        genre_a_enc = self.genre_map.get(genre_a, 6) / 7.0
        genre_b_enc = self.genre_map.get(genre_b, 6) / 7.0

        features = np.array([
            bpm_a / 200.0,
            bpm_b / 200.0,
            bpm_diff / 100.0,
            bpm_ratio,
            energy_a * 10,
            energy_b * 10,
            energy_diff * 10,
            centroid_a / 10000.0,
            centroid_b / 10000.0,
            centroid_diff / 10000.0,
            camelot_compat,
            same_genre,
            genre_a_enc,
            genre_b_enc,
        ], dtype=np.float32)

        return features

    def train(self):
        """Train the transition classifier"""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import classification_report
            import pickle
        except ImportError:
            print("❌ scikit-learn not installed")
            print("   Run: pip install scikit-learn")
            return False

        examples = self.load_training_data()

        if len(examples) < 10:
            print("   ⚠️  Not enough training data yet")
            print(f"   Need at least 10 examples, have {len(examples)}")
            print("   Run dj_tutorial_scraper.py first")
            return False

        # Build feature matrix
        X = []
        y = []

        for example in examples:
            technique = example.get('technique', '')
            if technique not in self.technique_map:
                continue

            features = example.get('features', {})
            if not features:
                continue

            # Build feature vector from stored features
            bpm_before = features.get('bpm_before', 120)
            bpm_after = features.get('bpm_after', 120)
            energy_before = features.get('energy_before', 0.05)
            energy_after = features.get('energy_after', 0.05)
            centroid_before = features.get('centroid_before', 2000)
            centroid_after = features.get('centroid_after', 2000)

            feature_vec = np.array([
                bpm_before / 200.0,
                bpm_after / 200.0,
                abs(bpm_before - bpm_after) / 100.0,
                min(bpm_before, bpm_after) / max(bpm_before, bpm_after),
                energy_before * 10,
                energy_after * 10,
                abs(energy_before - energy_after) * 10,
                centroid_before / 10000.0,
                centroid_after / 10000.0,
                abs(centroid_before - centroid_after) / 10000.0,
                0.5, 0.5, 0.5, 0.5  # Unknown camelot/genre for auto-labeled
            ], dtype=np.float32)

            X.append(feature_vec)
            y.append(self.technique_map[technique])

        if len(X) < 10:
            print("   ⚠️  Not enough valid examples after filtering")
            return False

        X = np.array(X)
        y = np.array(y)

        print(f"   🏋️  Training on {len(X)} examples...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train Random Forest
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'
        )
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = np.mean(y_pred == y_test)
        print(f"   ✅ Training accuracy: {accuracy:.2%}")

        # Save model
        model_path = os.path.join(
            self.models_dir, 'transition_classifier.pkl'
        )
        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'technique_map': self.technique_map,
                'feature_names': self.feature_names,
                'trained_at': str(datetime.now()),
                'accuracy': accuracy,
                'n_examples': len(X)
            }, f)

        print(f"   ✅ Model saved to {model_path}")
        return True

    def predict(self, analysis_a, analysis_b):
        """
        Predict best transition technique
        Returns (technique_name, confidence)
        """
        import pickle

        model_path = os.path.join(
            self.models_dir, 'transition_classifier.pkl'
        )

        if not os.path.exists(model_path):
            return None, 0.0

        if self.model is None:
            with open(model_path, 'rb') as f:
                saved = pickle.load(f)
            self.model = saved['model']
            self.technique_map = saved['technique_map']

        features = self.extract_features(analysis_a, analysis_b)
        features = features.reshape(1, -1)

        prediction = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]
        confidence = float(np.max(probabilities))

        # Reverse map
        reverse_map = {v: k for k, v in self.technique_map.items()}
        technique = reverse_map.get(prediction, 'beatmatch_crossfade')

        return technique, confidence
