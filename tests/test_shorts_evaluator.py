import unittest
import os
import sys
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from quality_engine.shorts_evaluator import ShortsEvaluator

class TestShortsEvaluator(unittest.TestCase):
    def setUp(self):
        self.config = {
            'paths': {
                'audio_cache': 'data/audio_cache',
                'metadata': 'data/metadata'
            },
            'youtube_channels': {
                'shorts_source': 'https://www.youtube.com/@BestDJTransitions/shorts'
            }
        }
        self.evaluator = ShortsEvaluator(self.config)

    def test_extract_features_and_evaluate(self):
        mix_path = os.path.abspath('output/latest_mix.wav')
        self.assertTrue(os.path.exists(mix_path), "expected latest_mix.wav to exist for evaluation")

        res = self.evaluator.evaluate_mix(mix_path)
        self.assertIn('overall_score', res)
        self.assertIn('passed', res)
        self.assertTrue(res['passed'])
        self.assertGreater(res['overall_score'], 40.0)

if __name__ == '__main__':
    unittest.main()
