import yt_dlp
import os
import json
from tqdm import tqdm

class PlaylistDownloader:
    def __init__(self, config):
        self.config = config
        self.cache_dir = config['paths']['audio_cache']
        self.metadata_dir = config['paths']['metadata']
        self.playlist_cache_file = "data/playlist_cache.json"
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_playlist_metadata(self, playlist_url):
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
        }
        
        # FIXED: Pass cookies to avoid YouTube blocking your IP!
        cookie_path = self.config.get('youtube', {}).get('cookie_file', '')
        if cookie_path and os.path.exists(cookie_path):
            ydl_opts['cookiefile'] = cookie_path
            
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)

            songs = []
            for entry in info.get('entries', []):
                if entry:
                    songs.append({
                        'id': entry.get('id'),
                        'title': entry.get('title', 'Unknown'),
                        'url': f"https://youtube.com/watch?v={entry.get('id')}",
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'cached': False,
                        'analyzed': False
                    })

            # Save playlist cache
            with open(self.playlist_cache_file, 'w', encoding='utf-8') as f:
                json.dump(songs, f, indent=2, ensure_ascii=False)

            print(f"✅ Found {len(songs)} songs")
            return songs
            
        except Exception as e:
            print(f"❌ YouTube Playlist Fetch Failed: {e}")
            return []

    def load_cached_playlist(self):
        if os.path.exists(self.playlist_cache_file):
            try:
                with open(self.playlist_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def download_song(self, url, song_id, drive_manager=None, timeout=300):
        output_path = os.path.join(self.cache_dir, f"{song_id}.mp3")
        
        # Check if already local
        if os.path.exists(output_path):
            return output_path

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.cache_dir, f"{song_id}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
        }
        
        # FIXED: Pass cookies here too! Very important!
        cookie_path = self.config.get('youtube', {}).get('cookie_file', '')
        if cookie_path and os.path.exists(cookie_path):
            ydl_opts['cookiefile'] = cookie_path
        
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Download timed out after {timeout}s")
        
        # Set timeout (Unix only, must be main thread)
        old_handler = None
        try:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
        except (AttributeError, ValueError):
            pass  # Windows or running in background thread safely skips this
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return output_path
        except Exception as e:
            # FIXED: Catch crash, print error, return None instead of breaking app
            print(f"❌ Download error for {song_id}: {str(e)[:100]}")
            return None
        finally:
            try:
                if old_handler is not None:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            except (AttributeError, ValueError):
                pass

    def _get_account_for_song(self, song_id):
        """Uniformly distribute songs across all available accounts"""
        accounts = self.config.get('storage', {}).get('drive_accounts', ['account_1'])
        if not accounts:
            accounts = ['account_1']
        val = sum(ord(c) for c in song_id)
        return accounts[val % len(accounts)]

    def upload_to_drive(self, song_id, drive_manager):
        """Upload local MP3 to the assigned Drive account"""
        # FIXED: Guard against None drive_manager
        if not drive_manager:
            print("❌ DriveManager not initialized")
            return None
            
        local_path = os.path.join(self.cache_dir, f"{song_id}.mp3")
        if not os.path.exists(local_path):
            return None
            
        account_id = self._get_account_for_song(song_id)
        folder_name = "AI_DJ_Library"
        
        print(f"☁️ Offloading {song_id} to Google Drive ({account_id})...")
        try:
            drive_id = drive_manager.upload_file(account_id, local_path, folder_name)
            # Once uploaded, we can delete local
            if drive_id:
                os.remove(local_path)
                print(f"✅ Offloaded. Saved space on disk!")
            return drive_id
        except Exception as e:
            print(f"❌ Drive upload failed: {str(e)[:100]}")
            return None

    def delete_audio(self, song_id):
        filepath = os.path.join(self.cache_dir, f"{song_id}.mp3")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
