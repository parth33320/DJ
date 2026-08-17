import unittest
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.web_ui import app as web_ui_app
import standalone_ui_server

class DummyDJApp:
    def __init__(self):
        self.is_playing = True
        self.mode = "auto"
        self.current_song = "song_1"
        self.next_song = "song_2"
        self.playlist = [{'id': 'song_1', 'title': 'Song One'}, {'id': 'song_2', 'title': 'Song Two'}]
        self.metadata_cache = {
            'song_1': {
                'title': 'Song One - Current Track',
                'bpm': 124.0,
                'camelot': '8A',
                'genre_hint': 'House'
            },
            'song_2': {
                'title': 'Song Two - Next Track Transitioning In',
                'bpm': 126.0,
                'camelot': '9A',
                'genre_hint': 'Tech House'
            }
        }

class TestWebUIEndpoints(unittest.TestCase):
    def setUp(self):
        self.dummy_dj = DummyDJApp()
        web_ui_app.dj_app_ref = self.dummy_dj
        self.client = web_ui_app.app.test_client()

    def test_status_returns_current_and_next_song(self):
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn('current_song', data)
        self.assertIn('next_song', data)
        self.assertEqual(data['current_song']['title'], 'Song One - Current Track')
        self.assertEqual(data['next_song']['title'], 'Song Two - Next Track Transitioning In')

    def test_playlist_endpoint(self):
        response = self.client.get('/api/playlist')
        self.assertEqual(response.status_code, 200)
        songs = response.get_json()
        self.assertEqual(len(songs), 2)
        self.assertTrue(songs[0]['is_current'])

class TestStandaloneUI(unittest.TestCase):
    def setUp(self):
        self.client = standalone_ui_server.app.test_client()

    def test_serve_ui_contains_labels(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('▶ CURRENTLY PLAYING (TRACK A)', html)
        self.assertIn('⏭ UP NEXT / TRANSITIONING TO (TRACK B)', html)

    def test_queue_endpoint_structure(self):
        response = self.client.get('/api/queue')
        self.assertEqual(response.status_code, 200)
        queue = response.get_json()
        self.assertIsInstance(queue, list)

if __name__ == '__main__':
    unittest.main()
