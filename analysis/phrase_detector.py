import librosa
import numpy as np
import json
import os

class PhraseDetector:
    def __init__(self, config):
        self.config = config
        self.metadata_dir = config['paths']['metadata']

    def detect_phrases(self, filepath, song_id):
        """
        Detect musical phrases (4, 8, 16, 32 bar boundaries)
        Returns list of phrase boundary timestamps
        """
        cache_path = os.path.join(
            self.metadata_dir, f"{song_id}_phrases.json"
        )
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        y, sr = librosa.load(filepath, sr=22050)
        
        # Get beat frames
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0]) # Ensure scalar
        beat_times = librosa.frames_to_time(beats, sr=sr)
        
        # Group beats into bars (4 beats per bar)
        bars = []
        for i in range(0, len(beat_times) - 3, 4):
            bars.append({
                'bar_number': len(bars) + 1,
                'start_time': float(beat_times[i]),
                'beats': beat_times[i:i+4].tolist()
            })
        
        # Detect phrase boundaries using spectral flux
        # Phrases typically change every 4, 8, or 16 bars
        spectral_flux = self._compute_spectral_flux(y, sr)
        
        phrases = {
            '4_bar': [],
            '8_bar': [],
            '16_bar': [],
            '32_bar': []
        }
        
        for i, bar in enumerate(bars):
            if i % 4 == 0:
                phrases['4_bar'].append(bar['start_time'])
            if i % 8 == 0:
                phrases['8_bar'].append(bar['start_time'])
            if i % 16 == 0:
                phrases['16_bar'].append(bar['start_time'])
            if i % 32 == 0:
                phrases['32_bar'].append(bar['start_time'])
        
        # Find HIGH ENERGY phrase boundaries (best transition points)
        transition_candidates = self._find_transition_candidates(
            bars, spectral_flux, sr, y
        )
        
        result = {
            'tempo': tempo,
            'total_bars': len(bars),
            'bar_times': [b['start_time'] for b in bars],
            'phrases': phrases,
            'transition_candidates': transition_candidates,
            'best_transition_out': self._best_outro_phrase(
                bars, y, sr
            ),
            'best_transition_in': self._best_intro_phrase(
                bars, y, sr
            )
        }
        
        with open(cache_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result

    def _compute_spectral_flux(self, y, sr):
        """Measure how much spectrum changes over time"""
        hop_length = 512
        spec = np.abs(librosa.stft(y, hop_length=hop_length))
        flux = np.sum(np.diff(spec, axis=1) ** 2, axis=0)
        return flux

    def _find_transition_candidates(self, bars, flux, sr, y):
        """Find bars where energy/spectrum changes significantly"""
        candidates = []
        rms = librosa.feature.rms(y=y)[0]
        
        for i, bar in enumerate(bars[:-1]):
            # Check if this is a phrase boundary (multiple of 4/8/16)
            if i % 4 == 0:
                # Measure energy change at this bar
                bar_sample = int(bar['start_time'] * sr)
                window = sr * 2  # 2 second window
                
                energy_before = np.mean(rms[max(0, bar_sample//512 - 8):
                                            bar_sample//512])
                energy_after = np.mean(rms[bar_sample//512:
                                           bar_sample//512 + 8])
                
                energy_change = abs(energy_after - energy_before)
                
                candidates.append({
                    'time': bar['start_time'],
                    'bar': i + 1,
                    'energy_change': float(energy_change),
                    'phrase_type': '32bar' if i % 32 == 0 else
                                   '16bar' if i % 16 == 0 else
                                   '8bar' if i % 8 == 0 else '4bar'
                })
        
        # Sort by energy change
        candidates.sort(key=lambda x: x['energy_change'], reverse=True)
        return candidates[:10]

    def _best_outro_phrase(self, bars, y, sr):
        """Find best phrase to START transitioning out"""
        rms = librosa.feature.rms(y=y)[0]
        duration = len(y) / sr
        
        # Look in last 30% of song
        start_search = duration * 0.7
        
        for bar in reversed(bars):
            if bar['start_time'] > start_search:
                # Find nearest 8-bar boundary
                bar_num = bar['bar_number']
                if bar_num % 8 == 0:
                    return float(bar['start_time'])
        
        return float(bars[int(len(bars) * 0.75)]['start_time'])

    def _best_intro_phrase(self, bars, y, sr):
        """Find best phrase to bring incoming song in on"""
        # Usually bar 1 or bar 9 (after intro)
        if len(bars) > 8:
            return float(bars[8]['start_time'])
        return float(bars[0]['start_time'])
