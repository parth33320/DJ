import json
import os
import time
import yt_dlp
from typing import Dict, Optional, Tuple

class RequestCooldownManager:
    """
    Manages 2-hour playback cooldown per unique song ID/URL to prevent spam requests.
    Uses yt-dlp to search YouTube for requested track keywords.
    """
    def __init__(self, config: Dict, cooldown_seconds: int = 7200):
        self.config = config
        self.cooldown_seconds = cooldown_seconds
        self.history_file = os.path.join(
            config.get('paths', {}).get('logs', 'data/logs'),
            'request_cooldown_history.json'
        )
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        self.history = self._load_history()

    def _load_history(self) -> Dict[str, float]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save request history: {e}")

    def is_on_cooldown(self, song_id: str) -> Tuple[bool, float]:
        """
        Returns (is_cooldown, seconds_remaining)
        """
        now = time.time()
        last_played = self.history.get(song_id, 0)
        elapsed = now - last_played
        if elapsed < self.cooldown_seconds:
            remaining = self.cooldown_seconds - elapsed
            return True, remaining
        return False, 0.0

    def record_play(self, song_id: str):
        self.history[song_id] = time.time()
        self._save_history()

    def search_and_validate_request(self, query: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Searches YouTube for song query using yt-dlp, extracts metadata, and checks 2-hour cooldown.
        Returns (success, message, song_metadata_or_None)
        """
        query_str = query.strip()
        if not query_str:
            return False, "Empty query string provided.", None

        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'default_search': 'ytsearch1'
        }

        try:
            search_target = query_str if query_str.startswith('http') else f"ytsearch1:{query_str}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_target, download=False)

            entries = info.get('entries', []) if 'entries' in info else [info]
            if not entries or not entries[0]:
                return False, f"No tracks found for query: '{query_str}'", None

            top = entries[0]
            song_id = top.get('id')
            title = top.get('title', query_str)
            url = f"https://www.youtube.com/watch?v={song_id}" if song_id else query_str

            on_cd, remaining = self.is_on_cooldown(song_id)
            if on_cd:
                mins = int(remaining // 60)
                return False, f"⌛ '{title}' is on a 2-hour cooldown ({mins}m remaining).", None

            metadata = {
                'id': song_id,
                'title': title,
                'url': url,
                'duration': top.get('duration', 180),
                'requested_at': time.time()
            }

            self.record_play(song_id)
            return True, f"✅ Successfully queued '{title}'!", metadata

        except Exception as e:
            return False, f"❌ YouTube search error: {str(e)[:100]}", None
