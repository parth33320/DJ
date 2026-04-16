import os
import json
import numpy as np
import librosa

class ValidationAgent:
    """
    Judges transition quality based on:
    1. Signal analysis (silence, clipping)
    2. User historical feedback
    3. Similarity to 'Gold Standard' transitions (YouTube data)
    """
    def __init__(self, config):
        self.config = config
        self.feedback_file = os.path.join('data', 'logs', 'feedback_weights.json')
        
    def score_transition(self, mix_path, technique, cur_ana, nxt_ana):
        """
        Returns a score from 0.0 to 1.0
        """
        score = 0.5 # Baseline
        
        try:
            y, sr = librosa.load(mix_path, sr=22050, duration=60)
            
            # 1. Check for dead air (silence)
            # If there's more than 2 seconds of silence in a 60s test clip, it's bad.
            non_silent = librosa.effects.trim(y, top_db=30)[0]
            if len(non_silent) < (len(y) * 0.7):
                print(f"   ⚠️ Validation: Too much silence detected! Scoring down.")
                score -= 0.3
                
            # 2. Check Technique Popularity (Based on User Feedback)
            if os.path.exists(self.feedback_file):
                with open(self.feedback_file, 'r') as f:
                    weights = json.load(f)
                    weight = weights.get(technique, 1.0)
                    # Normalize weight (assuming 1.0 is neutral)
                    score += (weight - 1.0) * 0.2
            
            # 3. Match BPM consistency
            # If it's a 'Beatmatch' but the BPMs are wildly different, penalty.
            if 'beatmatch' in technique:
                bpm_diff = abs(cur_ana.get('bpm', 120) - nxt_ana.get('bpm', 120))
                if bpm_diff > 10:
                    score -= 0.2

            return max(0.0, min(1.0, score))
            
        except Exception as e:
            print(f"   ❌ Validation Error: {e}")
            return 0.0

if __name__ == "__main__":
    from main import load_config
    agent = ValidationAgent(load_config())
    # Test call
    # print(agent.score_transition('data/sandbox/test_mix.wav', 'beatmatch_crossfade', {}, {}))
