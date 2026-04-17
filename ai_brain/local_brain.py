"""
Local AI Brain - Zero API Credits!
Handles all rule-based DJ decisions locally.
Only calls cloud AI for truly creative tasks.
"""

import random
import os
import json

class LocalBrain:
    """
    Caveman-smart DJ brain that uses RULES not API calls!
    Saves your Gemini credits for when you ACTUALLY need creativity.
    """
    
    def __init__(self, config):
        self.config = config
        self.camelot_wheel = self._build_camelot_wheel()
        self.genre_transitions = self._build_genre_rules()
        self.technique_rules = self._build_technique_rules()
        self.feedback_weights = self._load_feedback_weights()
    
    def _build_camelot_wheel(self):
        """Camelot wheel compatibility - no AI needed, just music theory!"""
        # Compatible keys: same number, +1, -1, or switch A/B
        return {
            '1A': ['1A', '1B', '12A', '2A'],
            '1B': ['1B', '1A', '12B', '2B'],
            '2A': ['2A', '2B', '1A', '3A'],
            '2B': ['2B', '2A', '1B', '3B'],
            '3A': ['3A', '3B', '2A', '4A'],
            '3B': ['3B', '3A', '2B', '4B'],
            '4A': ['4A', '4B', '3A', '5A'],
            '4B': ['4B', '4A', '3B', '5B'],
            '5A': ['5A', '5B', '4A', '6A'],
            '5B': ['5B', '5A', '4B', '6B'],
            '6A': ['6A', '6B', '5A', '7A'],
            '6B': ['6B', '6A', '5B', '7B'],
            '7A': ['7A', '7B', '6A', '8A'],
            '7B': ['7B', '7A', '6B', '8B'],
            '8A': ['8A', '8B', '7A', '9A'],
            '8B': ['8B', '8A', '7B', '9B'],
            '9A': ['9A', '9B', '8A', '10A'],
            '9B': ['9B', '9A', '8B', '10B'],
            '10A': ['10A', '10B', '9A', '11A'],
            '10B': ['10B', '10A', '9B', '11B'],
            '11A': ['11A', '11B', '10A', '12A'],
            '11B': ['11B', '11A', '10B', '12B'],
            '12A': ['12A', '12B', '11A', '1A'],
            '12B': ['12B', '12A', '11B', '1B'],
        }
    
    def _build_genre_rules(self):
        """Genre transition compatibility - learned from DJ tutorials, not API!"""
        return {
            'hip-hop': ['hip-hop', 'r&b', 'trap', 'pop'],
            'edm': ['edm', 'house', 'techno', 'pop', 'dubstep'],
            'house': ['house', 'edm', 'disco', 'techno'],
            'pop': ['pop', 'hip-hop', 'edm', 'r&b', 'dance'],
            'rock': ['rock', 'indie', 'alternative', 'metal'],
            'r&b': ['r&b', 'hip-hop', 'soul', 'pop'],
            'latin': ['latin', 'reggaeton', 'pop', 'dance'],
            'bollywood': ['bollywood', 'indian', 'pop', 'dance'],
        }
    
    def _build_technique_rules(self):
        """Transition technique rules - pure logic, no AI!"""
        return {
            'same_bpm_same_key': ['beatmatch_crossfade', 'mashup_short', 'acapella_layer'],
            'same_bpm_diff_key': ['filter_sweep', 'echo_out', 'reverb_wash'],
            'small_bpm_diff': ['tempo_ramp', 'beatmatch_crossfade', 'drum_swap'],
            'large_bpm_diff': ['cut_transition', 'spinback', 'white_noise_sweep'],
            'half_double_bpm': ['half_time_transition', 'loop_roll'],
            'genre_change': ['reverb_wash', 'white_noise_sweep', 'cut_transition'],
            'energy_drop': ['echo_out', 'reverb_wash', 'filter_sweep'],
            'energy_build': ['loop_roll', 'stutter_glitch', 'filter_sweep'],
        }
    
    def _load_feedback_weights(self):
        """Load user feedback to improve decisions over time"""
        weight_file = 'data/logs/feedback_weights.json'
        if os.path.exists(weight_file):
            try:
                with open(weight_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def is_key_compatible(self, key_a, key_b):
        """Check if two Camelot keys are compatible - NO API CALL!"""
        if not key_a or not key_b:
            return True  # Unknown = compatible
        return key_b in self.camelot_wheel.get(key_a, [key_a])
    
    def calculate_bpm_compatibility(self, bpm_a, bpm_b):
        """Calculate BPM compatibility score - NO API CALL!"""
        if not bpm_a or not bpm_b:
            return 0.5
        
        diff = abs(bpm_a - bpm_b)
        
        # Perfect match
        if diff <= 2:
            return 1.0
        
        # Half/double time (e.g., 70 BPM and 140 BPM)
        ratio = max(bpm_a, bpm_b) / min(bpm_a, bpm_b)
        if 1.95 <= ratio <= 2.05:
            return 0.9
        
        # Small difference (can tempo ramp)
        if diff <= 8:
            return 0.8
        
        # Medium difference
        if diff <= 15:
            return 0.5
        
        # Large difference (need hard cut)
        return 0.2
    
    def calculate_energy_flow(self, energy_a, energy_b):
        """Calculate energy flow score - NO API CALL!"""
        if energy_a is None or energy_b is None:
            return 0.5
        
        diff = energy_b - energy_a
        
        # Slight energy increase = good DJ flow
        if 0 <= diff <= 0.15:
            return 1.0
        
        # Maintaining energy
        if abs(diff) <= 0.1:
            return 0.9
        
        # Moderate change
        if abs(diff) <= 0.3:
            return 0.6
        
        # Drastic change (might be intentional drop/build)
        return 0.4
    
    def score_compatibility(self, song_a, song_b):
        """
        Full compatibility score - ALL LOCAL, ZERO API!
        Returns dict with score and reasons.
        """
        scores = []
        reasons = []
        
        # BPM compatibility (40% weight)
        bpm_score = self.calculate_bpm_compatibility(
            song_a.get('bpm'), song_b.get('bpm')
        )
        scores.append(bpm_score * 0.4)
        if bpm_score >= 0.8:
            reasons.append(f"BPM compatible ({song_a.get('bpm', '?')} → {song_b.get('bpm', '?')})")
        
        # Key compatibility (30% weight)
        key_compat = self.is_key_compatible(
            song_a.get('camelot'), song_b.get('camelot')
        )
        key_score = 1.0 if key_compat else 0.3
        scores.append(key_score * 0.3)
        if key_compat:
            reasons.append(f"Key compatible ({song_a.get('camelot', '?')} → {song_b.get('camelot', '?')})")
        
        # Energy flow (20% weight)
        energy_score = self.calculate_energy_flow(
            song_a.get('energy_mean'), song_b.get('energy_mean')
        )
        scores.append(energy_score * 0.2)
        
        # Genre compatibility (10% weight)
        genre_a = song_a.get('genre_hint', 'unknown').lower()
        genre_b = song_b.get('genre_hint', 'unknown').lower()
        compatible_genres = self.genre_transitions.get(genre_a, [genre_a])
        genre_score = 1.0 if genre_b in compatible_genres else 0.5
        scores.append(genre_score * 0.1)
        
        total_score = sum(scores) * 100  # Convert to 0-100
        
        return {
            'score': total_score,
            'bpm_score': bpm_score,
            'key_score': key_score,
            'energy_score': energy_score,
            'genre_score': genre_score,
            'reasons': reasons,
        }
    
    def decide_technique(self, song_a, song_b, compatibility):
        """
        Decide transition technique - ALL LOCAL, ZERO API!
        Uses rules learned from DJ tutorials.
        """
        bpm_a = song_a.get('bpm', 120)
        bpm_b = song_b.get('bpm', 120)
        bpm_diff = abs(bpm_a - bpm_b)
        bpm_ratio = max(bpm_a, bpm_b) / max(min(bpm_a, bpm_b), 1)
        
        key_a = song_a.get('camelot', '')
        key_b = song_b.get('camelot', '')
        key_compatible = self.is_key_compatible(key_a, key_b)
        
        energy_a = song_a.get('energy_mean', 0.5)
        energy_b = song_b.get('energy_mean', 0.5)
        energy_diff = energy_b - energy_a
        
        # Determine situation
        if bpm_diff <= 3 and key_compatible:
            situation = 'same_bpm_same_key'
        elif bpm_diff <= 3 and not key_compatible:
            situation = 'same_bpm_diff_key'
        elif 1.95 <= bpm_ratio <= 2.05:
            situation = 'half_double_bpm'
        elif bpm_diff <= 10:
            situation = 'small_bpm_diff'
        elif bpm_diff > 20:
            situation = 'large_bpm_diff'
        elif energy_diff < -0.2:
            situation = 'energy_drop'
        elif energy_diff > 0.2:
            situation = 'energy_build'
        else:
            situation = 'small_bpm_diff'
        
        # Get candidate techniques
        candidates = self.technique_rules.get(situation, ['beatmatch_crossfade'])
        
        # Apply user feedback weights
        weighted_candidates = []
        for tech in candidates:
            weight = self.feedback_weights.get(tech, 1.0)
            weight = max(0.1, weight)  # Never fully exclude
            weighted_candidates.append((tech, weight))
        
        # Weighted random selection
        techs = [t[0] for t in weighted_candidates]
        weights = [t[1] for t in weighted_candidates]
        total = sum(weights)
        weights = [w / total for w in weights]
        
        technique = random.choices(techs, weights=weights, k=1)[0]
        
        return technique, {'situation': situation, 'candidates': candidates}
    
    def needs_cloud_ai(self, song_a, song_b):
        """
        Decide if we should call Gemini for creative help.
        Returns True only for tasks that ACTUALLY need AI creativity.
        """
        # Check if both songs have lyrics
        lyrics_a = song_a.get('lyrics', {}).get('text', '')
        lyrics_b = song_b.get('lyrics', {}).get('text', '')
        
        if not lyrics_a or not lyrics_b:
            return False  # No lyrics = no wordplay possible
        
        # Check if languages are different (cross-language wordplay is creative!)
        lang_a = song_a.get('lyrics', {}).get('language', 'unknown')
        lang_b = song_b.get('lyrics', {}).get('language', 'unknown')
        
        if lang_a != lang_b and lang_a != 'unknown' and lang_b != 'unknown':
            return True  # Cross-language wordplay needs AI
        
        # Check compatibility score - if already great, no need for creativity
        compat = self.score_compatibility(song_a, song_b)
        if compat['score'] >= 80:
            return False  # Already compatible, use rules
        
        # Low compatibility + has lyrics = try creative wordplay
        if compat['score'] < 50 and lyrics_a and lyrics_b:
            return True
        
        return False


class LocalTransitionDecider:
    """
    Drop-in replacement for TransitionAgent that uses LocalBrain.
    ZERO API CALLS for normal transitions!
    """
    
    def __init__(self, config):
        self.config = config
        self.brain = LocalBrain(config)
    
    def decide(self, song_a, song_b, compatibility=None):
        """Decide technique using local rules"""
        if compatibility is None:
            compatibility = self.brain.score_compatibility(song_a, song_b)
        
        technique, info = self.brain.decide_technique(song_a, song_b, compatibility)
        return technique, self.get_params(song_a, song_b, technique)
    
    def get_params(self, song_a, song_b, technique):
        """Get technique parameters based on song analysis"""
        bpm = song_a.get('bpm', 120)
        
        params = {
            'crossfade_bars': 8,
            'mashup_bars': 8,
            'swap_bars': 8,
            'layer_bars': 16,
        }
        
        # Adjust based on BPM (faster songs = shorter transitions)
        if bpm > 140:
            params['crossfade_bars'] = 4
            params['mashup_bars'] = 4
        elif bpm < 90:
            params['crossfade_bars'] = 16
            params['mashup_bars'] = 16
        
        return params
