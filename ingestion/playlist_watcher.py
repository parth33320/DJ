import json
import os
import re
import yt_dlp

class PlaylistWatcher:
    def __init__(self, config):
        self.config = config
        self.output_dir = config.get('paths', {}).get('library', 'data/library')
        self.tutorials_dir = os.path.join(self.output_dir, 'tutorials')
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.tutorials_dir, exist_ok=True)

    def parse_comment_timestamps(self, comments):
        """
        Scans comment strings for timestamp patterns (e.g. 01:23, 2:45)
        Returns aggregated list of anchor points sorted by viewer popularity.
        """
        time_pattern = re.compile(r'(?:(\d{1,2}):)?(\d{1,2}):(\d{2})')
        anchors = []
        for c in comments:
            text = c.get('text', '') if isinstance(c, dict) else str(c)
            likes = c.get('like_count', 1) if isinstance(c, dict) else 1
            matches = time_pattern.findall(text)
            for m in matches:
                hours = int(m[0]) if m[0] else 0
                mins = int(m[1])
                secs = int(m[2])
                total_sec = hours * 3600 + mins * 60 + secs
                anchors.append({
                    'time': float(total_sec),
                    'likes': likes,
                    'text': text
                })
        anchors.sort(key=lambda x: x['likes'], reverse=True)
        return anchors

    def fetch_playlist_with_comments(self, playlist_url, max_videos=None, fetch_comments=True):
        """
        Ingests entire playlist using yt-dlp, extracting video metadata, audio,
        and top viewer comments for timestamp anchor points.
        """
        print(f"\n🔄 Fetching playlist metadata from: {playlist_url}")
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
            
            entries = [e for e in info.get('entries', []) if e]
            if max_videos:
                entries = entries[:max_videos]

            print(f"✅ Found {len(entries)} items in playlist")

            songs = []
            for entry in entries:
                video_id = entry.get('id')
                if not video_id:
                    continue
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                title = entry.get('title', 'Unknown Title')

                comments = []
                anchors = []

                if fetch_comments:
                    comment_opts = {
                        'quiet': True,
                        'skip_download': True,
                        'getcomments': True,
                        'extractor_args': {
                            'youtube': {
                                'max_comments': ['30', 'all', '10', '0']
                            }
                        }
                    }
                    try:
                        with yt_dlp.YoutubeDL(comment_opts) as c_ydl:
                            c_info = c_ydl.extract_info(video_url, download=False)
                            comments = c_info.get('comments', [])
                            anchors = self.parse_comment_timestamps(comments)
                    except Exception as ce:
                        print(f"   ⚠️ Could not fetch comments for {video_id}: {ce}")

                songs.append({
                    'id': video_id,
                    'title': title,
                    'url': video_url,
                    'duration': entry.get('duration', 0),
                    'comments': comments[:20],
                    'anchor_points': anchors
                })

            return songs

        except Exception as e:
            print(f"❌ Failed to process playlist: {e}")
            return []

    def check_for_changes(self, playlist_url, current_playlist, metadata_cache, app):
        """
        Check YouTube playlist for added/removed songs
        """
        print("\n🔄 Checking playlist for changes...")
        fresh_playlist = self.fetch_playlist_with_comments(playlist_url)

        current_ids = {s['id'] for s in current_playlist} if current_playlist else set()
        fresh_ids = {s['id'] for s in fresh_playlist}

        new_ids = fresh_ids - current_ids
        removed_ids = current_ids - fresh_ids

        if new_ids:
            print(f"✨ {len(new_ids)} new songs found!")
            new_songs = [s for s in fresh_playlist if s['id'] in new_ids]
            self._process_new_songs(new_songs, metadata_cache, app)

        if removed_ids:
            print(f"🗑️  {len(removed_ids)} songs removed from playlist (Files kept in cache)")

        if not new_ids and not removed_ids:
            print("✅ No changes detected")

    def _process_new_songs(self, new_songs, metadata_cache, app):
        for song in new_songs:
            print(f"   Processing new song: {song['title'][:40]}")
            try:
                filepath = app.downloader.download_song(song['url'], song['id'])
                if not filepath:
                    continue
                analysis = app.analyzer.analyze_track(filepath, song['id']) if hasattr(app, 'analyzer') else {}
                analysis['title'] = song['title']
                analysis['id'] = song['id']
                analysis['anchor_points'] = song.get('anchor_points', [])
                metadata_cache[song['id']] = analysis
                if hasattr(app, 'playlist') and isinstance(app.playlist, list):
                    app.playlist.append(song)
                print(f"   ✅ New song ready: {song['title'][:40]}")
            except Exception as e:
                print(f"   ❌ Failed to process {song['title']}: {e}")
