import os
import subprocess
import sys
try:
    import torch
except ImportError:
    torch = None


class StemSeparator:
    def __init__(self, config):
        self.config = config
        self.stems_dir = config['paths']['stems']
        self.cache_dir = config['paths']['audio_cache']
        os.makedirs(self.stems_dir, exist_ok=True)
        
        # Check GPU availability
        self.device = "cuda" if (False if torch is None else torch.cuda.is_available()) else "cpu"
        print(f"🎵 Stem separator using: {self.device}")

    def separate(self, filepath, song_id, start_time=0):
        """
        Offload separation to Google Drive / Colab
        Uses Round Robin across authenticated accounts
        """
        import time
        song_stems_dir = os.path.join(self.stems_dir, song_id)
        stems = {
            'vocals': os.path.join(song_stems_dir, 'vocals.wav'),
            'melody': os.path.join(song_stems_dir, 'other.wav'),
        }
        
        if all(os.path.exists(v) for v in stems.values()):
            return stems

        # 🔄 ROUND ROBIN ACCOUNT SELECTION
        accounts = [f"account_{i}" for i in range(1, 6)] # 5 accounts detected
        if not hasattr(self, '_account_idx'): self._account_idx = 0
        acc_id = accounts[self._account_idx]
        self._account_idx = (self._account_idx + 1) % len(accounts)
        
        print(f"☁️  OFFLOADING to Drive: {song_id} (using {acc_id})")
        
        try:
            from utils.drive_manager import DriveManager
            dm = DriveManager(self.config)
            
            # 1. Prepare small trim locally (keep it fast)
            temp_trim = os.path.join(self.cache_dir, f"{song_id}_trimmed.wav").replace("\\", "/")
            subprocess.run([
                "ffmpeg", "-y", "-i", filepath.replace("\\", "/"), 
                "-ss", str(start_time), "-t", "90", 
                "-ac", "2", "-ar", "44100", temp_trim
            ], check=True, capture_output=True)
            
            # 2. Upload to COLAB_INPUT
            dm.upload_file(acc_id, temp_trim, "COLAB_INPUT")
            os.remove(temp_trim)
            
            # 3. Wait for Results (COLAB_OUTPUT/song_id/vocals.wav)
            print(f"⏳ Waiting for Colab GPU to separate {song_id}...")
            start_wait = time.time()
            found = False
            
            while time.time() - start_wait < 600: # 10 min timeout
                service = dm.authenticate(acc_id)
                parent_id = dm.get_folder_id(service, "COLAB_OUTPUT")
                
                # Check for the folder song_id
                q = f"name = '{song_id}' and '{parent_id}' in parents and trashed = false"
                res = service.files().list(q=q, fields="files(id)").execute()
                items = res.get('files', [])
                
                if items:
                    folder_id = items[0]['id']
                    # Check for vocals.wav inside
                    q2 = f"name = 'vocals.wav' and '{folder_id}' in parents"
                    res2 = service.files().list(q=q2, fields="files(id)").execute()
                    
                    if res2.get('files'):
                        # Stems are ready!
                        os.makedirs(song_stems_dir, exist_ok=True)
                        
                        # Download all files in that folder
                        q3 = f"'{folder_id}' in parents"
                        res3 = service.files().list(q=q3, fields="files(id, name)").execute()
                        for f in res3.get('files', []):
                            if 'vocals' in f['name'] and 'no_vocals' not in f['name']:
                                dm.download_file(acc_id, f['id'], stems['vocals'])
                            else:
                                dm.download_file(acc_id, f['id'], stems['melody'])
                        
                        found = True
                        break
                
                time.sleep(15) # Watcher loop
            
            if not found:
                print(f"❌ Timed out waiting for Colab: {song_id}")
                return stems # Return partial for fallback
                
            print(f"✅ Stems retrieved from Cloud: {song_id}")
            return stems

        except Exception as e:
            print(f"❌ Cloud separation failed: {e}")
            return stems
