import unittest
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from workers.transition_queue_worker import TransitionQueueWorker
from streaming.chat_request_listener import ChatRequestListener
from streaming.request_cooldown_manager import RequestCooldownManager
from streaming.direct_stream_broadcaster import DirectStreamBroadcaster

class TestQueueAndBroadcaster(unittest.TestCase):
    def setUp(self):
        self.config = {
            'audio': {'sample_rate': 44100},
            'paths': {
                'stems': 'data/stems',
                'audio_cache': 'data/audio_cache',
                'sandbox': 'data/sandbox',
                'metadata': 'data/metadata',
                'word_index': 'data/word_index',
                'lyrics': 'data/lyrics',
                'phonemes': 'data/phonemes',
                'logs': f'data/test_logs_{int(time.time()*1000)}'
            },
            'transitions': {'same_language_bias': 0.3},
            'streaming': {'rtmp_url': 'rtmp://localhost/live/test'}
        }

    def test_queue_worker_init(self):
        worker = TransitionQueueWorker(self.config)
        self.assertIsNotNone(worker)
        self.assertTrue(worker.current_pair_file.endswith('current_pair.mp3'))

    def test_cooldown_manager(self):
        cm = RequestCooldownManager(self.config, cooldown_seconds=7200)
        song_id = f'test_song_fresh_{int(time.time()*1000)}'
        on_cd, _ = cm.is_on_cooldown(song_id)
        self.assertFalse(on_cd)

        cm.record_play(song_id)
        on_cd_now, remaining = cm.is_on_cooldown(song_id)
        self.assertTrue(on_cd_now)
        self.assertGreater(remaining, 7100)

    def test_chat_listener_parsing(self):
        listener = ChatRequestListener(self.config)
        msg = "play Paas Woh Aane Lage"
        match = listener.play_pattern.search(msg)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).strip(), "Paas Woh Aane Lage")

    def test_direct_broadcaster_command(self):
        broadcaster = DirectStreamBroadcaster(self.config, rtmp_url="rtmp://localhost/live/test")
        cmd = broadcaster.build_ffmpeg_command()
        self.assertIn("ffmpeg", cmd)
        self.assertIn("rtmp://localhost/live/test", cmd)
        self.assertIn("-stream_loop", cmd)

if __name__ == '__main__':
    unittest.main()
