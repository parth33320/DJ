import os
import sys
import random
import json
import time
from main import DJApp
from utils.notifier import send_notification

# ==========================================
# CONFIGURATION
# ==========================================
# 1. Update this to your active localtunnel/ngrok URL
MOBILE_UI_URL = "https://parth-dj-god-mode-2026.loca.lt"

# 2. Pause generation if you have this many unrated mixes waiting
MAX_UNRATED_QUEUE = 3  

# 3. Length of audio to extract BEFORE stem separation (saves massive compute)
SNIPPET_LENGTH = 60    

def load_blacklist():
    path = 'data/logs/blacklist.json'
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_blacklist(blacklist):
    os.makedirs('data/logs', exist_ok=True)
    with open('data/logs/blacklist.json', 'w', encoding='utf-8') as f:
        json.dump(list(blacklist), f)

def get_unrated_count():
    """Check how many mixes are waiting for your approval on the mobile UI"""
    try:
        with open('data/logs/transition_links.json', 'r') as f:
            links = json.load(f)
            # Count entries that haven't been rated
            return len([l for l in links if l.get('rating') is None])
    except:
        return 0

def append_to_queue(output_path, drive_link, cur_title, nxt_title, technique):
    """Safely append to the UI JSON queue without blocking thread"""
    links_file = 'data/logs/transition_links.json'
    try:
        links = []
        if os.path.exists(links_file):
            with open(links_file, 'r') as f:
                links = json.load(f)
        
        links.append({
            'from_title': cur_title,
            'to_title': nxt_title,
            'technique': technique,
            'drive_link': drive_link,
            'local_path': output_path,
            'timestamp': time.time(),
            'tested': False,
            'rating': None
        })
        
        with open(links_file, 'w') as f:
            json.dump(links, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to queue link: {e}")

def test_random_transitions():
    print("🔧 Booting Async Test Queue (Snippet Mode)...")
    app = DJApp()
    
    playlist_url = app.config['youtube']['playlist_url']
    print(f"📥 Fetching playlist from {playlist_url}...")
    
    try:
        app.playlist = app.downloader.get_playlist_metadata(playlist_url)
    except:
        app.playlist = []
        
    if not app.playlist:
        print("⚠️ Live fetch fail. Me hunt in local cache...")
        app.playlist = app.downloader.load_cached_playlist()

    if len(app.playlist) < 2:
        print("❌ Need at least 2 songs in playlist!")
        return

    blacklist = load_blacklist()

    while True:
        # ---------------------------------------------------------
        # 1. ASYNC QUEUE CHECK (Non-Blocking)
        # ---------------------------------------------------------
        unrated = get_unrated_count()
        if unrated >= MAX_UNRATED_QUEUE:
            print(f"⏸️ Queue full ({unrated}/{MAX_UNRATED_QUEUE} unrated). Sleeping 10s. Go click PASS/FAIL on Mobile UI!")
            time.sleep(10)
            continue

        # ---------------------------------------------------------
        # 2. SELECT SONGS
        # ---------------------------------------------------------
        candidates = [s for s in app.playlist if s['id'] not in blacklist]
        if len(candidates) < 2:
            print("❌ All songs exhausted or blacklisted. Queue shutting down.")
            break

        songs_to_test = random.sample(candidates, 2)
        cur_song_info = songs_to_test[0]
        nxt_song_info = songs_to_test[1]
        
        print(f"\n🎧 ME PICK TWO SONGS:")
        print(f"   [A] {cur_song_info['title']}")
        print(f"   [B] {nxt_song_info['title']}")

        skip_loop = False
        
        # ---------------------------------------------------------
        # 3. DOWNLOAD & PRE-CLIP (Speed Hack)
        # ---------------------------------------------------------
        for song_info in [cur_song_info, nxt_song_info]:
            song_id = song_info['id']
            snip_id = f"{song_id}_snip"  # Create a unique ID for the 60s chunk
            
            meta_path = f'data/metadata/{snip_id}.json'
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        app.metadata_cache[snip_id] = json.load(f)
                except Exception as e:
                    print(f"❌ Corrupt metadata for {snip_id}. Tagging as bad.")
                    blacklist.add(song_id)
                    save_blacklist(blacklist)
                    skip_loop = True
                    break
            
            filepath = os.path.join(app.config['paths']['audio_cache'], f"{song_id}.mp3")
            snip_path = os.path.join(app.config['paths']['audio_cache'], f"{snip_id}.mp3")
            
            if not os.path.exists(snip_path):
                if not os.path.exists(filepath):
                    print(f"📥 Downloading {song_info['title']}...")
                    filepath = app.downloader.download_song(song_info['url'], song_id)
