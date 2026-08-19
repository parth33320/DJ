import os
import sys
import json
import logging
import numpy as np
import librosa
import yt_dlp
from typing import Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='[ShortsEvaluator] %(asctime)s - %(message)s')

class ShortsEvaluator:
    """
    Ingests reference transition clips from YouTube Shorts (@BestDJTransitions),
    extracts acoustic benchmarks (spectral flux, onset density, harmonic continuity),
    and evaluates generated transition mixes against the established 'Golden Set'.
    """
    def __init__(self, config: Dict):
        self.config = config
        self.shorts_url = config.get('youtube_channels', {}).get(
            'shorts_source', 'https://www.youtube.com/@BestDJTransitions/shorts'
        )
        self.cache_dir = os.path.join(config.get('paths', {}).get('audio_cache', 'data/audio_cache'), 'shorts')
        self.benchmark_file = os.path.join(config.get('paths', {}).get('metadata', 'data/metadata'), 'shorts_golden_benchmarks.json')
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.benchmark_file), exist_ok=True)

        self.benchmarks = self._load_benchmarks()

    def _load_benchmarks(self) -> Dict:
        if os.path.exists(self.benchmark_file):
            try:
                with open(self.benchmark_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load benchmarks file: {e}")
        # Default baseline benchmark if file missing
        return {
            'spectral_flux_mean': 1.25,
            'onset_density_mean': 4.50,
            'harmonic_continuity_mean': 0.78,
            'count': 1
        }

    def extract_acoustic_features(self, filepath: str) -> Optional[Dict[str, float]]:
        """
        Extracts spectral flux, onset density, and harmonic continuity profiles via librosa.
        """
        if not os.path.exists(filepath):
            logging.error(f"File not found: {filepath}")
            return None

        try:
            y, sr = librosa.load(filepath, sr=22050, mono=True)
            if len(y) == 0:
                return None

            # 1. Onset Density (onsets per second)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
            duration = len(y) / sr
            onset_density = float(len(onsets) / max(duration, 1.0))

            # 2. Spectral Flux (mean change in magnitude spectrum)
            spectral_flux = float(np.mean(onset_env))

            # 3. Harmonic Continuity (energy ratio of harmonic component vs total)
            y_harmonic, _ = librosa.effects.hpss(y)
            harm_energy = np.sum(y_harmonic ** 2)
            tot_energy = np.sum(y ** 2) + 1e-10
            harmonic_continuity = float(min(1.0, max(0.0, harm_energy / tot_energy)))

            return {
                'onset_density': round(onset_density, 3),
                'spectral_flux': round(spectral_flux, 3),
                'harmonic_continuity': round(harmonic_continuity, 3),
                'rms': float(np.sqrt(np.mean(y ** 2)))
            }
        except Exception as e:
            logging.error(f"Error extracting features from {filepath}: {e}")
            return None

    def ingest_shorts_benchmarks(self, max_shorts: int = 3) -> Dict:
        """
        Downloads sample YouTube Shorts, extracts features, and establishes Golden Set benchmarks.
        """
        logging.info(f"📥 Ingesting reference YouTube Shorts from {self.shorts_url}...")
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
        }

        feature_list = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.shorts_url, download=False)

            entries = [e for e in info.get('entries', []) if e][:max_shorts]
            logging.info(f"Found {len(entries)} shorts clips for benchmark extraction.")

            for entry in entries:
                sid = entry.get('id')
                if not sid:
                    continue
                url = f"https://www.youtube.com/watch?v={sid}"
                target_mp3 = os.path.join(self.cache_dir, f"{sid}.mp3")

                if not os.path.exists(target_mp3):
                    dl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': os.path.join(self.cache_dir, f"{sid}.%(ext)s"),
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'quiet': True,
                    }
                    try:
                        with yt_dlp.YoutubeDL(dl_opts) as d_ydl:
                            d_ydl.download([url])
                    except Exception as de:
                        logging.warning(f"Could not download short {sid}: {de}")

                if os.path.exists(target_mp3):
                    feats = self.extract_acoustic_features(target_mp3)
                    if feats:
                        feature_list.append(feats)

        except Exception as e:
            logging.warning(f"Shorts ingestion error: {e}")

        if feature_list:
            avg_flux = float(np.mean([f['spectral_flux'] for f in feature_list]))
            avg_density = float(np.mean([f['onset_density'] for f in feature_list]))
            avg_harm = float(np.mean([f['harmonic_continuity'] for f in feature_list]))

            self.benchmarks = {
                'spectral_flux_mean': round(avg_flux, 3),
                'onset_density_mean': round(avg_density, 3),
                'harmonic_continuity_mean': round(avg_harm, 3),
                'count': len(feature_list)
            }
            with open(self.benchmark_file, 'w', encoding='utf-8') as f:
                json.dump(self.benchmarks, f, indent=2)

            logging.info(f"✅ Updated Golden Set benchmarks: {self.benchmarks}")

        return self.benchmarks

    def evaluate_mix(self, mix_filepath: str) -> Dict[str, float]:
        """
        Evaluates a generated mix file against the Golden Set benchmarks.
        Returns a dictionary with metric similarity scores (0-100) and overall score.
        """
        feats = self.extract_acoustic_features(mix_filepath)
        if not feats:
            return {'score': 0.0, 'passed': False, 'reason': 'Feature extraction failed'}

        bench = self.benchmarks

        # Calculate absolute deviations
        flux_diff = abs(feats['spectral_flux'] - bench.get('spectral_flux_mean', 1.25))
        density_diff = abs(feats['onset_density'] - bench.get('onset_density_mean', 4.5))
        harm_diff = abs(feats['harmonic_continuity'] - bench.get('harmonic_continuity_mean', 0.78))

        # Normalize score
        flux_score = max(0.0, 100.0 - (flux_diff * 20.0))
        density_score = max(0.0, 100.0 - (density_diff * 10.0))
        harm_score = max(0.0, 100.0 - (harm_diff * 50.0))

        overall_score = round(0.4 * flux_score + 0.3 * density_score + 0.3 * harm_score, 2)
        passed = overall_score >= 50.0 and feats['rms'] > 0.01

        return {
            'overall_score': overall_score,
            'passed': passed,
            'features': feats,
            'benchmark_comparison': {
                'spectral_flux_score': round(flux_score, 2),
                'onset_density_score': round(density_score, 2),
                'harmonic_continuity_score': round(harm_score, 2)
            }
        }
