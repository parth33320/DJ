import os
import sys
import random
import json
import time

# Handle Windows Unicode issues
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

from main import DJApp

def run_automated_test():
    print("STARTING AUTOMATED TRANSITION TEST...")
    app = DJApp()
    app.metadata_cache = {}
    
    # 1. Fetch playlist metadata
    playlist_url = app.config['youtube']['playlist_url']
    print(f"Fetching playlist from {playlist_url}...")
    app.playlist = app.downloader.get_playlist_metadata(playlist_url)
    
    if len(app.playlist) < 2:
        print("Need at least 2 songs!")
        return

    # 2. Pick from existing metadata
    meta_dir = 'data/metadata'
    meta_files = [f for f in os.listdir(meta_dir) if f.endswith('.json')]
    
    if len(meta_files) < 2:
        print("Need at least 2 metadata files in data/metadata/")
        return
        
    picked_files = random.sample(meta_files, 2)
    song_ids = [f.replace('.json', '') for f in picked_files]
    
    print(f"\n🎧 TEST PAIR (from Metadata):")
    
    # 3. Load metadata
    for sid in song_ids:
        meta_path = os.path.join(meta_dir, f"{sid}.json")
        with open(meta_path, 'r') as f:
            data = json.load(f)
            app.metadata_cache[sid] = data
            print(f"   - {data.get('title', sid)}")

    cur_ana = app.metadata_cache[song_ids[0]]
    nxt_ana = app.metadata_cache[song_ids[1]]
    
    # 4. Agent decides transition
    compatibility = random.randint(40, 90)
    technique = app.transition_decider.decide(cur_ana, nxt_ana, compatibility)
    params = app.transition_decider.get_params(cur_ana, nxt_ana, technique)
    
    print(f"\n--- LOGIC REPORT ---")
    print(f"Technique: {technique}")
    print(f"Compatibility Score: {compatibility}")
    
    # Send ntfy summary
    from utils.notifier import send_notification
    msg = f"🧪 TRANSITION TEST\nFROM: {cur_ana.get('title', 'A')}\nTO: {nxt_ana.get('title', 'B')}\nTECH: {technique}"
    send_notification(msg, topic='dj-agent-parth')
    
    print("\n✅ TEST COMPLETE. LOGGED TO NTFY.")

if __name__ == "__main__":
    run_automated_test()
