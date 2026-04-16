import librosa
import numpy as np
import json
import os

class EntryPointFinder:
    """
    Implements the Farooq Got Audio technique:
    Find the most emotionally powerful entry point
    rather than always starting from the beginning
    """
    
    def __init__(self, config):
        self.config = config
        self.metadata_dir = config['paths']['metadata']

    def find_entry_points(self, filepath, analysis, song_id):
        """
        Analyze all possible entry points and rank them
        """
        cache_path = os.path.join(
            self.metadata_dir, f"{song_id}_entries.json"
        )
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        y, sr = librosa.load(filepath, sr=22050)
        
        # Get all phrase boundaries
        phrases = analysis.get('phrases', {})
        bar_times = analysis.get('bar_times', [])
        
        entry_candidates = []
        
        for bar_time in bar_times[::8]:  # Check every 8 bars
            score = self._score_entry_point(y, sr, bar_time, analysis)
            entry_candidates.append({
                'time': float(bar_time),
                'score': float(score),
                'energy': float(self._get_energy_at(y, sr, bar_time)),
                'is_standard_start': bar_time < 5.0,
            })
        
        # Sort by score
        entry_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        result = {
            'standard_start': 0.0,
            'best_entry': entry_candidates[0] if entry_candidates else None,
            'top_5_entries': entry_candidates[:5],
            'all_candidates': entry_candidates
        }
        
        with open(cache_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result

    def _score_entry_point(self, y, sr, time, analysis):
        """
        Score how good an entry point is
        Higher = more impactful/emotional start
        """
        score = 0.0
        sample = int(time * sr)
        window = int(sr * 4)  # 4 second window
        
        if sample + window > len(y):
            return 0.0
        
        segment = y[sample:sample + window]
        
        # Energy score (higher energy = more impactful)
        rms = np.sqrt(np.mean(segment ** 2))
        score += rms * 10
        
        # Spectral richness (more instruments = more interesting)
        spec = np.abs(librosa.stft(segment))
        spectral_entropy = -np.sum(
            spec * np.log(spec + 1e-10)
        ) / spec.size
        score += spectral_entropy * 0.1
        
        # Onset strength (rhythmic hits = good entry)
        onset_strength = np.mean(
            librosa.onset.onset_strength(y=segment, sr=sr)
        )
        score += onset_strength * 2
        
        # Penalize very beginning (too common)
        if time < 5.0:
            score *= 0.7
        
        # Bonus for being in first third (avoid starting too late)
        duration = len(y) / sr
        if time < duration * 0.33:
            score *= 1.2
        
        return score

    def _get_energy_at(self, y, sr, time):
        sample = int(time * sr)
        window = int(sr * 2)
        if sample + window > len(y):
            return 0.0
        segment = y[sample:sample + window]
        return float(np.sqrt(np.mean(segment ** 2)))
