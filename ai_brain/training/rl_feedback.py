import os
import json
import numpy as np
from datetime import datetime

class RLFeedback:
    """
    Reinforcement Learning from user feedback
    
    When a transition plays:
    - User gives thumbs up/down via web UI
    - OR app detects skips (implicit negative feedback)
    - Model updates based on what worked/didn't
    
    Over time the app learns:
    - Which techniques work for which song combinations
    - Which songs flow well together
    - What the user/audience responds to
    - Time-of-day preferences
    - Genre sequence preferences
    """
    def __init__(self, config):
        self.config = config
        self.models_dir = config['paths']['models']
        self.logs_dir = config['paths']['logs']
        self.feedback_file = os.path.join(
            self.logs_dir, 'feedback_log.json'
        )
        self.q_table_file = os.path.join(
            self.models_dir, 'q_table.json'
        )

        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        # Q-table: maps state → action → reward
        # state  = (genre_a, genre_b, bpm_bucket, energy_bucket)
        # action = transition technique
        # reward = user feedback score
        self.q_table = self._load_q_table()

        # Feedback history
        self.feedback_log = self._load_feedback_log()

        # Learning parameters
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.epsilon = 0.15  # Exploration rate (try new things)

        # Techniques available
        self.techniques = [
            'beatmatch_crossfade',
            'cut_transition',
            'echo_out',
            'filter_sweep',
            'loop_roll',
            'reverb_wash',
            'spinback',
            'tempo_ramp',
            'white_noise_sweep',
            'vinyl_scratch_flourish',
            'tone_play',
            'wordplay',
            'mashup_short',
            'mashup_extended',
            'acapella_layer',
            'drum_swap',
            'bass_swap',
            'stutter_glitch',
            'half_time_transition',
            'double_time_transition',
        ]

    # ============================================================
    # FEEDBACK COLLECTION
    # ============================================================

    def record_transition(self, current_analysis, next_analysis,
                          technique, params):
        """
        Record that a transition was played
        Returns transition_id for later feedback
        """
        transition_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{technique}"

        record = {
            'transition_id': transition_id,
            'timestamp': str(datetime.now()),
            'song_a_id': current_analysis.get('song_id', ''),
            'song_a_title': current_analysis.get('title', ''),
            'song_b_id': next_analysis.get('song_id', ''),
            'song_b_title': next_analysis.get('title', ''),
            'technique': technique,
            'bpm_a': current_analysis.get('bpm', 120),
            'bpm_b': next_analysis.get('bpm', 120),
            'genre_a': current_analysis.get('genre_hint', 'Pop/Other'),
            'genre_b': next_analysis.get('genre_hint', 'Pop/Other'),
            'camelot_a': current_analysis.get('camelot', ''),
            'camelot_b': next_analysis.get('camelot', ''),
            'energy_a': current_analysis.get('energy_mean', 0),
            'energy_b': next_analysis.get('energy_mean', 0),
            'feedback': None,  # To be filled in later
            'was_skipped': False,
            'play_duration': 0,
            'state': self._get_state(current_analysis, next_analysis),
        }

        self.feedback_log.append(record)
        self._save_feedback_log()

        return transition_id

    def record_feedback(self, transition_id, feedback_type,
                        play_duration=None):
        """
        Record user feedback for a transition

        feedback_type options:
            'thumbs_up'    → +1.0 reward
            'thumbs_down'  → -1.0 reward
            'skip'         → -0.5 reward (implicit negative)
            'replay'       → +0.8 reward (implicit positive)
            'let_play'     → +0.3 reward (neutral positive)
        """
        reward_map = {
            'thumbs_up':   1.0,
            'thumbs_down': -1.0,
            'skip':        -0.5,
            'replay':       0.8,
            'let_play':     0.3,
        }

        reward = reward_map.get(feedback_type, 0.0)

        # Find and update the record
        for record in self.feedback_log:
            if record['transition_id'] == transition_id:
                record['feedback'] = feedback_type
                record['reward'] = reward
                record['was_skipped'] = (feedback_type == 'skip')
                if play_duration:
                    record['play_duration'] = play_duration
                break

        self._save_feedback_log()

        # Update Q-table
        self._update_q_table(transition_id, reward)

        print(f"   📊 Feedback recorded: {feedback_type} "
              f"(reward={reward:+.1f})")

    def record_skip(self, transition_id, time_into_song):
        """
        Record that user skipped a song
        Skip within 30 seconds = strong negative signal
        Skip after 2 minutes = weak negative signal
        """
        if time_into_song < 30:
            reward = -0.8
            feedback_type = 'early_skip'
        elif time_into_song < 60:
            reward = -0.4
            feedback_type = 'skip'
        else:
            reward = -0.1
            feedback_type = 'late_skip'

        for record in self.feedback_log:
            if record['transition_id'] == transition_id:
                record['feedback'] = feedback_type
                record['reward'] = reward
                record['was_skipped'] = True
                record['play_duration'] = time_into_song
                break

        self._save_feedback_log()
        self._update_q_table(transition_id, reward)

        print(f"   📊 Skip recorded at {time_into_song:.0f}s "
              f"(reward={reward:+.1f})")

    # ============================================================
    # Q-LEARNING
    # ============================================================

    def _get_state(self, analysis_a, analysis_b):
        """
        Convert song pair into a discrete state
        for Q-table lookup
        """
        # BPM bucket (10 BPM increments)
        bpm_diff = abs(
            analysis_a.get('bpm', 120) - analysis_b.get('bpm', 120)
        )
        if bpm_diff < 5:
            bpm_bucket = 'same'
        elif bpm_diff < 15:
            bpm_bucket = 'close'
        elif bpm_diff < 30:
            bpm_bucket = 'medium'
        else:
            bpm_bucket = 'far'

        # Energy bucket
        energy_diff = abs(
            analysis_a.get('energy_mean', 0) -
            analysis_b.get('energy_mean', 0)
        )
        if energy_diff < 0.02:
            energy_bucket = 'same'
        elif energy_diff < 0.05:
            energy_bucket = 'close'
        else:
            energy_bucket = 'different'

        # Key compatibility
        c_a = analysis_a.get('camelot', '')
        c_b = analysis_b.get('camelot', '')
        if c_a == c_b:
            key_compat = 'same'
        elif c_a and c_b and c_a[:-1] == c_b[:-1]:
            key_compat = 'compatible'
        else:
            key_compat = 'incompatible'

        genre_a = analysis_a.get('genre_hint', 'Pop/Other')
        genre_b = analysis_b.get('genre_hint', 'Pop/Other')
        same_genre = 'same' if genre_a == genre_b else 'diff'

        state = f"{genre_a}|{genre_b}|{bpm_bucket}|{energy_bucket}|{key_compat}|{same_genre}"
        return state

    def _update_q_table(self, transition_id, reward):
        """
        Update Q-table based on received reward
        Uses standard Q-learning update rule:
        Q(s,a) = Q(s,a) + lr * (reward + γ * max(Q(s')) - Q(s,a))
        """
        # Find the record
        record = None
        for r in self.feedback_log:
            if r['transition_id'] == transition_id:
                record = r
                break

        if not record:
            return

        state = record.get('state', '')
        technique = record.get('technique', '')

        if not state or not technique:
            return

        # Initialize state in Q-table if needed
        if state not in self.q_table:
            self.q_table[state] = {
                t: 0.0 for t in self.techniques
            }

        # Current Q value
        current_q = self.q_table[state].get(technique, 0.0)

        # Max future Q (simplified - no next state lookahead)
        max_future_q = max(self.q_table[state].values())

        # Q-learning update
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_future_q - current_q
        )

        self.q_table[state][technique] = new_q
        self._save_q_table()

        print(f"   🧠 Q-table updated: "
              f"technique={technique} "
              f"Q: {current_q:.2f} → {new_q:.2f}")

    def get_best_technique(self, current_analysis, next_analysis):
        """
        Get the best technique based on learned Q-values
        Uses epsilon-greedy: sometimes explores new techniques
        """
        state = self._get_state(current_analysis, next_analysis)

        # Explore: try random technique
        if np.random.random() < self.epsilon:
            technique = np.random.choice(self.techniques)
            print(f"   🎲 Exploring: {technique}")
            return technique, 0.0

        # Exploit: use best known technique
        if state in self.q_table:
            q_values = self.q_table[state]

            # Get technique with highest Q value
            best_technique = max(q_values, key=q_values.get)
            best_q = q_values[best_technique]

            # Only use if Q value is meaningfully positive
            if best_q > 0.1:
                print(f"   🧠 RL suggests: {best_technique} "
                      f"(Q={best_q:.2f})")
                return best_technique, best_q

        # No learned preference yet - return None
        # (caller will use rule-based fallback)
        return None, 0.0

    def get_technique_scores(self, current_analysis, next_analysis):
        """
        Get Q-values for all techniques for this song pair
        Used to boost/penalize rule-based scores
        """
        state = self._get_state(current_analysis, next_analysis)

        if state not in self.q_table:
            return {}

        return self.q_table[state].copy()

    # ============================================================
    # ANALYTICS
    # ============================================================

    def get_stats(self):
        """
        Get statistics about learned preferences
        """
        if not self.feedback_log:
            return {'message': 'No feedback recorded yet'}

        total = len(self.feedback_log)
        rated = [r for r in self.feedback_log if r.get('reward') is not None]
        positive = [r for r in rated if r.get('reward', 0) > 0]
        negative = [r for r in rated if r.get('reward', 0) < 0]
        skipped = [r for r in rated if r.get('was_skipped')]

        # Best techniques by average reward
        technique_rewards = {}
        for record in rated:
            tech = record.get('technique', '')
            reward = record.get('reward', 0)
            if tech not in technique_rewards:
                technique_rewards[tech] = []
            technique_rewards[tech].append(reward)

        technique_avg = {
            tech: float(np.mean(rewards))
            for tech, rewards in technique_rewards.items()
            if len(rewards) >= 3
        }

        best_technique = max(technique_avg, key=technique_avg.get) \
            if technique_avg else 'not enough data'
        worst_technique = min(technique_avg, key=technique_avg.get) \
            if technique_avg else 'not enough data'

        # Best genre pairs
        genre_pair_rewards = {}
        for record in rated:
            pair = f"{record.get('genre_a', '')} → {record.get('genre_b', '')}"
            reward = record.get('reward', 0)
            if pair not in genre_pair_rewards:
                genre_pair_rewards[pair] = []
            genre_pair_rewards[pair].append(reward)

        best_genre_pairs = sorted(
            [
                (pair, float(np.mean(rewards)))
                for pair, rewards in genre_pair_rewards.items()
                if len(rewards) >= 2
            ],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            'total_transitions': total,
            'rated_transitions': len(rated),
            'positive_feedback': len(positive),
            'negative_feedback': len(negative),
            'skips': len(skipped),
            'approval_rate': len(positive) / max(len(rated), 1),
            'best_technique': best_technique,
            'worst_technique': worst_technique,
            'technique_scores': technique_avg,
            'best_genre_pairs': best_genre_pairs,
            'q_table_states': len(self.q_table),
            'epsilon': self.epsilon,
        }

    def print_stats(self):
        """Print formatted statistics"""
        stats = self.get_stats()

        print("\n📊 RL FEEDBACK STATISTICS")
        print("=" * 50)
        print(f"Total transitions:  {stats.get('total_transitions', 0)}")
        print(f"Rated:              {stats.get('rated_transitions', 0)}")
        print(f"Approval rate:      "
              f"{stats.get('approval_rate', 0):.1%}")
        print(f"Skips:              {stats.get('skips', 0)}")
        print(f"\nBest technique:     {stats.get('best_technique', 'N/A')}")
        print(f"Worst technique:    {stats.get('worst_technique', 'N/A')}")
        print(f"\nQ-table states:     {stats.get('q_table_states', 0)}")
        print(f"Exploration rate:   {stats.get('epsilon', 0):.0%}")

        if stats.get('technique_scores'):
            print("\nTechnique scores:")
            sorted_tech = sorted(
                stats['technique_scores'].items(),
                key=lambda x: x[1],
                reverse=True
            )
            for tech, score in sorted_tech:
                bar = '█' * int(abs(score) * 10)
                sign = '+' if score >= 0 else '-'
                print(f"  {tech:<30} {sign}{abs(score):.2f} {bar}")

        if stats.get('best_genre_pairs'):
            print("\nBest genre transitions:")
            for pair, score in stats['best_genre_pairs']:
                print(f"  {pair:<40} {score:+.2f}")

    def reduce_exploration(self):
        """
        Gradually reduce exploration as model learns
        Called after N transitions
        """
        min_epsilon = 0.05
        decay = 0.995
        self.epsilon = max(min_epsilon, self.epsilon * decay)

    def export_training_data(self):
        """
        Export feedback log as training data
        for transition_trainer.py
        """
        rated = [
            r for r in self.feedback_log
            if r.get('reward') is not None
        ]

        training_examples = []
        for record in rated:
            training_examples.append({
                'technique': record['technique'],
                'features': {
                    'bpm_before': record.get('bpm_a', 120),
                    'bpm_after': record.get('bpm_b', 120),
                    'energy_before': record.get('energy_a', 0.05),
                    'energy_after': record.get('energy_b', 0.05),
                    'centroid_before': 2000,
                    'centroid_after': 2000,
                    'confidence': abs(record.get('reward', 0))
                },
                'reward': record.get('reward', 0),
                'source': 'user_feedback',
                'timestamp': record.get('timestamp', '')
            })

        output_path = os.path.join(
            self.config['paths']['training_data'],
            f"rl_feedback_export_{datetime.now().strftime('%Y%m%d')}.json"
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(training_examples, f, indent=2)

        print(f"✅ Exported {len(training_examples)} "
              f"RL examples to {output_path}")
        return output_path

    # ============================================================
    # PERSISTENCE
    # ============================================================

    def _load_q_table(self):
        """Load Q-table from disk"""
        if os.path.exists(self.q_table_file):
            try:
                with open(self.q_table_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_q_table(self):
        """Save Q-table to disk"""
        with open(self.q_table_file, 'w') as f:
            json.dump(self.q_table, f, indent=2)

    def _load_feedback_log(self):
        """Load feedback history from disk"""
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r',
                          encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_feedback_log(self):
        """Save feedback history to disk"""
        with open(self.feedback_file, 'w', encoding='utf-8') as f:
            json.dump(
                self.feedback_log, f,
                indent=2, ensure_ascii=False
            )
