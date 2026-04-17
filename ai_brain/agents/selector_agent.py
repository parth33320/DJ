import json
import random
import numpy as np
from analysis.compatibility_scorer import CompatibilityScorer

class SelectorAgent:
    """
    Decides which song plays next
    Considers: compatibility, energy flow, 
    language bias, genre variety, history
    """
    def __init__(self, config):
        self.config = config
        self.scorer = CompatibilityScorer(config)
        self.play_history = []
        self.max_history = 50

    def pick_first_song(self, metadata_cache):
        """Pick a good opening song safely"""
        if not metadata_cache:
            print("⚠️ Cache empty! Cannot pick first song.")
            return None
            
        # FIXED: Use cache keys directly instead of guessing dictionary keys!
        songs = [(sid, data) for sid, data in metadata_cache.items()]

        # Sort by energy, pick from middle third
        songs.sort(key=lambda x: x[1].get('energy_mean', 0))
        middle = songs[len(songs)//3: 2*len(songs)//3]

        if middle:
            chosen_id = random.choice(middle)[0]
        else:
            chosen_id = songs[0][0]
            
        self.play_history.append(chosen_id)
        return chosen_id

    def pick_next_song(self, current_analysis, metadata_cache,
                       exclude=None):
        """
        Pick best next song based on multiple factors
        Returns (song_id, compatibility_dict)
        """
        exclude = exclude or []
        exclude.extend(self.play_history[-5:])  # Avoid recent songs

        candidates = []
        
        # FIXED: Safely get current ID (main.py uses 'id', not 'song_id')
        cur_id = current_analysis.get('id', current_analysis.get('song_id', None))

        for song_id, analysis in metadata_cache.items():
            if song_id in exclude:
                continue
            if song_id == cur_id:
                continue

            # Score compatibility
            try:
                compat = self.scorer.score(current_analysis, analysis)
            except Exception as e:
                print(f"⚠️ Compatibility scoring failed for {song_id}: {e}")
                compat = {'score': 50, 'reasons': ['scoring failed']}

            # Apply language bias (prefer same language)
            cur_lang = current_analysis.get('lyrics', {})
            nxt_lang = analysis.get('lyrics', {})
            if cur_lang and nxt_lang:
                cur_l = cur_lang.get('language', '')
                nxt_l = nxt_lang.get('language', '')
                if cur_l == nxt_l and cur_l != 'unknown':
                    # FIXED: Safe config fallback
                    bias = self.config.get('transitions', {}).get('same_language_bias', 0.3)
                    compat['score'] += (bias * 100)

            # Penalize if played recently
            if song_id in self.play_history:
                recency = self.play_history[::-1].index(song_id)
                penalty = max(0, 20 - recency * 2)
                compat['score'] -= penalty

            candidates.append((song_id, compat))

        if not candidates:
            # Fallback: pick random not recently played
            available = [
                sid for sid in metadata_cache.keys()
                if sid not in self.play_history[-3:] and sid != cur_id
            ]
            if available:
                chosen_id = random.choice(available)
                return chosen_id, {'score': 50, 'recommended_transition':
                                   'cut_transition', 'reasons': ['random fallback']}
            elif metadata_cache:
                # Extreme fallback - just grab anything!
                chosen_id = list(metadata_cache.keys())[0]
                return chosen_id, {'score': 50, 'reasons': ['extreme fallback']}
            else:
                return None, None

        # Sort by score
        candidates.sort(key=lambda x: x[1]['score'], reverse=True)

        # Add some randomness - pick from top 5
        top_candidates = candidates[:5]
        
        # FIXED: Ensure weights are never negative!
        weights = [max(0.1, c[1]['score']) for c in top_candidates]
        total = sum(weights)
        if total > 0:
            weights = [w/total for w in weights]
        else:
            weights = [1/len(top_candidates)] * len(top_candidates)

        chosen = random.choices(top_candidates, weights=weights, k=1)[0]

        # Update history
        self.play_history.append(chosen[0])
        if len(self.play_history) > self.max_history:
            self.play_history.pop(0)

        return chosen[0], chosen[1]
