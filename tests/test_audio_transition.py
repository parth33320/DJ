import unittest
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestAudioTransitionEngine(unittest.TestCase):
    def test_latest_mix_audio_properties(self):
        output_path = os.path.abspath('output/latest_mix.mp3')
        if not os.path.exists(output_path):
            output_path = os.path.abspath('output/latest_mix.wav')

        self.assertTrue(
            os.path.exists(output_path),
            f"Expected generated mix audio file at output/latest_mix.mp3 or output/latest_mix.wav, but file was not found."
        )

        import librosa
        y, sr = librosa.load(output_path, sr=None)
        duration = len(y) / sr
        rms = np.sqrt(np.mean(y**2))

        print(f"\n[Audio Inspection] Path: {output_path} | Duration: {duration:.2f}s | RMS: {rms:.4f}")

        # Duration bound check: ~70-90s covering Track A (30s), transition (10-20s), Track B (30s)
        self.assertGreaterEqual(duration, 65.0, "Audio mix duration is shorter than expected (< 65s)")
        self.assertLessEqual(duration, 95.0, "Audio mix duration is longer than expected (> 95s)")

        # Audio non-silence RMS energy check
        self.assertGreater(rms, 0.01, f"Audio mix RMS energy ({rms:.4f}) indicates silent output (expected > 0.01)")

if __name__ == '__main__':
    unittest.main()
