import os
import time
import yaml
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from utils.drive_manager import DriveManager

class LocalSyncAgent:
    """
    LOCAL SYNC AGENT - Manages Cloud Backup and Offloading.
    Prevents repetitive downloads by keeping Drive and Local in sync.
    """
    def __init__(self):
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        self.dm = DriveManager(self.config)
        self.local_meta = 'data/metadata'

    def run_sync_loop(self):
        print("☁️ [LOCAL SYNC AGENT] Monitor starting...")
        while True:
            # Sync metadata to account_1 as backup
            try:
                files = os.listdir(self.local_meta)
                for f in files:
                    if f.endswith('.json'):
                        path = os.path.join(self.local_meta, f)
                        # Only upload if not already synced (simple check)
                        # In production we'd use a database, but here we just try upload_file
                        # drive_manager.upload_file handles existing files
                        self.dm.upload_file('account_1', path, 'DJ_METADATA_BACKUP')
                
                print(f"✅ Sync complete: {len(files)} items checked.")
            except Exception as e:
                print(f"❌ Sync Error: {e}")
            
            time.sleep(3600) # Sync once an hour

if __name__ == "__main__":
    agent = LocalSyncAgent()
    agent.run_sync_loop()
