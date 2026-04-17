import os
import sys
import random
import json
import time
import subprocess
import librosa
import numpy as np
import glob
from main import DJApp
from utils.notifier import send_notification

# ==========================================
# CONFIGURATION
# ==========================================
MOBILE_UI_URL = "https://parth-dj-god-mode-2026.loca.lt"
MAX_UNRATED_QUEUE = 3  

def load_json_safe(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return default_val

def save_json_safe(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def load_blacklist():
    return set(load_json_safe('data/logs/blacklist.json', []))

def save_blacklist(blacklist):
    save_json_safe('data/logs/blacklist.json', list(blacklist))

def get_unrated_count():
    links = load_json_safe('data/logs/transition_links.json', [])
    return len([l for l in links if l.get('rating') is None])

def append_to_queue(output_path, drive_link, cur_title, nxt_title, technique):
    links = load_json_safe('data/logs/transition_links.json', [])
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
    save_json_safe('data/logs/transition_links.json', links)

def get_cloud_playlist_items(app, blacklist, drive_index, exclude_ids):
    """Scan Cloud Data Lake for fallbacks, ignoring local disk and already picked songs"""
    return [s for s in app.playlist if s['id'] in drive_index and s['id'] not in blacklist and s['id'] not in exclude_ids]

def get_smart_slice_timestamp(filepath: str) -> float:
    print(f"   🧠 Scanning audio topography to find beat drop...")
    try:
        y, sr = librosa.load(filepath, sr=11025, mono=True)
        rms = librosa.feature.rms(y=y)[0]
        frames_per_sec = sr / 512 
        smooth_window = int(frames_per_sec * 5)
        smoothed_rms = np.convolve(rms, np.ones(smooth_window)/smooth_window, mode='valid')
        energy_gradient = np.diff(smoothed_rms)
        drop_frame = np.argmax(energy_gradient)
        drop_time = librosa.frames_to_time(drop_frame, sr=sr)
        start_time = max(0, drop_time - 30)
        print(f"   🎯 Drop detected at {drop_time:.1f}s. Slicing from {start_time:.1f}s.")
        return start_time
    except Exception as e:
        print(f"   ⚠️ Smart scan failed ({e}). Falling back to 45s default.")
        return 45.0

def test_random_transitions():
    print("🔧 Booting Async Test Queue (Independent Sourcing Architecture)...")
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
    session_skips = set()

    while True:
        drive_index = load_json_safe('data/logs/drive_index.json', {})
        
        # 0. ASYNC QUEUE CHECK
        unrated = get_unrated_count()
        if unrated >= MAX_UNRATED_QUEUE:
            print(f"⏸️ Queue full ({unrated}/{MAX_UNRATED_QUEUE} unrated). Sleeping 10s. Go click PASS/FAIL on Mobile UI!")
            time.sleep(10)
            continue

        # ========================================================
        # 1. INDEPENDENT ACQUISITION PHASE
        # ========================================================
        ready_tracks = []
        
        while len(ready_tracks) < 2:
            candidates = [s for s in app.playlist if s['id'] not in blacklist and s['id'] not in session_skips]
            
            # Remove any track we already successfully secured in the basket
            for rt in ready_tracks:
                candidates = [c for c in candidates if c['id'] != rt['info']['id']]
                
            if not candidates:
                print("❌ Exhausted all valid candidates.")
                break

            # 🧠 EXPLORER BIAS: Prioritize new YouTube downloads
            uncharted_youtube = [s for s in candidates if s['id'] not in drive_index]
            if uncharted_youtube:
                chosen_info = random.choice(uncharted_youtube)
            else:
                chosen_info = random.choice(candidates)

            def resolve_track(song_info):
                song_id = song_info['id']
                
                # Hard Ban
                if "[Private video]" in song_info['title'] or "[Deleted video]" in song_info['title']:
                    print(f"🚫 '{song_info['title']}' is dead endpoint. PERMANENT BAN.")
                    blacklist.add(song_id); save_blacklist(blacklist)
                    return None, song_info

                # Local Snippet exists? (Fastest)
                snip_id = f"{song_id}_snip"
                snip_path = os.path.join(app.config['paths']['audio_cache'], f"{snip_id}.mp3")
                if os.path.exists(snip_path):
                    return snip_path, song_info

                filepath = os.path.join(app.config['paths']['audio_cache'], f"{song_id}.mp3")

                # Cloud Retrieval
                if song_id in drive_index:
                    print(f"☁️ Pulling '{song_info['title'][:30]}...' from Google Drive Data Lake...")
                    account_id = app.downloader._get_account_for_song(song_id)
                    try:
                        app.drive_manager.download_file(account_id, drive_index[song_id], filepath)
                        if os.path.exists(filepath):
                            return filepath, song_info
                    except Exception as e:
                        print(f"⚠️ Cloud retrieve fail: {e}")
                
                # YouTube Retrieval
                print(f"📥 Downloading '{song_info['title'][:30]}...' from YouTube...")
                dl_path = app.downloader.download_song(song_info['url'], song_id)
                if dl_path and os.path.exists(dl_path):
                    return dl_path, song_info

                # Hot-Swap Fallback (Keep basket safe, fetch from Drive)
                print(f"⚠️ Network fail. Soft skipping '{song_info['title'][:30]}...'.")
                session_skips.add(song_id)
                
                print(f"🔄 Hunting for Google Drive fallback track to save the pair...")
                exclude_ids = [rt['info']['id'] for rt in ready_tracks] + [song_id]
                cached_pool = get_cloud_playlist_items(app, blacklist, drive_index, exclude_ids)
                
                if cached_pool:
                    fb_info = random.choice(cached_pool)
                    print(f"✅ Hot-Swapped with Cloud track: {fb_info['title'][:30]}...")
                    return resolve_track(fb_info) # Recurse to pull the replacement from Cloud
                
                print(f"❌ No cloud tracks available for hot-swap. Pulling new YT candidate.")
                return None, song_info

            # Execute track resolution
            path, final_info = resolve_track(chosen_info)
            if path:
                ready_tracks.append({'path': path, 'info': final_info})

        # Check if we successfully got 2 tracks
        if len(ready_tracks) < 2:
            print("❌ Could not form a pair. Sleeping...")
            time.sleep(5)
            continue

        cur_info = ready_tracks[0]['info']
        cur_path = ready_tracks[0]['path']
        nxt_info = ready_tracks[1]['info']
        nxt_path = ready_tracks[1]['path']
        
        print(f"\n🎧 PAIR SECURED:")
        print(f"   [A] {cur_info['title']}")
        print(f"   [B] {nxt_info['title']}")

        # ========================================================
        # 2. PROCESSING & EPHEMERAL STORAGE PHASE
        # ========================================================
        skip_loop = False
        for track_data in ready_tracks:
            song_info = track_data['info']
            raw_path = track_data['path']
            song_id = song_info['id']
            snip_id = f"{song_id}_snip" 
            
            meta_path = f'data/metadata/{snip_id}.json'
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        app.metadata_cache[snip_id] = json.load(f)
                except Exception as e:
                    print(f"❌ Corrupt metadata for {snip_id}. PERMANENT BAN.")
                    blacklist.add(song_id); save_blacklist(blacklist)
                    skip_loop = True
                    break
            
            snip_path = os.path.join(app.config['paths']['audio_cache'], f"{snip_id}.mp3")
            
            if not os.path.exists(snip_path):
                slice_start = get_smart_slice_timestamp(raw_path)
                SMART_LENGTH = 90  
                print(f"✂️ Slicing optimal 90-second snippet for {song_info['title'][:20]}...")
                subprocess.run([
                    'ffmpeg', '-y', '-i', raw_path, 
                    '-ss', str(slice_start), 
                    '-t', str(SMART_LENGTH), 
                    '-c:a', 'libmp3lame', '-q:a', '2', 
                    snip_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # 🗑️ GARBAGE COLLECTION & CLOUD UPLOAD
                if song_id not in drive_index:
                    drive_id = app.downloader.upload_to_drive(song_id, app.drive_manager)
                    if drive_id:
                        drive_index[song_id] = drive_id
                        save_json_safe('data/logs/drive_index.json', drive_index)
                else:
                    if os.path.exists(raw_path) and "_snip" not in raw_path:
                        os.remove(raw_path)
                        print(f"🗑️ Ephemeral storage cleared for {song_id}")
            
            if snip_id not in app.metadata_cache:
                print(f"🔍 Analyzing Snippet: {song_info['title'][:20]}...")
                try:
                    analysis = app.analyzer.analyze_track(snip_path, snip_id)
                    analysis['title'] = song_info['title']
                    app.metadata_cache[snip_id] = analysis
                    save_json_safe(meta_path, analysis)
                except Exception as e:
                    print(f"❌ Analysis fail: {e}. File corrupt. PERMANENT BAN.")
                    blacklist.add(song_id); save_blacklist(blacklist)
                    skip_loop = True
                    break

        if skip_loop: continue

        cur_snip_id = f"{cur_info['id']}_snip"
        nxt_snip_id = f"{nxt_info['id']}_snip"
        
        cur_analysis = app.metadata_cache[cur_snip_id]
        nxt_analysis = app.metadata_cache[nxt_snip_id]
        
        # ========================================================
        # 3. AGENT DECISION PHASE
        # ========================================================
        decide_result = app.transition_decider.decide_transition(
            cur_info['title'], nxt_info['title'], cur_analysis, nxt_analysis
        )
        
        if isinstance(decide_result, tuple):
            technique, params = decide_result
        else:
            technique = decide_result
            params = {"duration": 16}
        
        print(f"\n--- TESTING TRANSITION ---")
        print(f"From: {cur_info['title']} (BPM: {cur_analysis.get('bpm', 'Unknown')})")
        print(f"To:   {nxt_info['title']} (BPM: {nxt_analysis.get('bpm', 'Unknown')})")
        print(f"Chosen Technique: {technique}")
        
        # ========================================================
        # 4. GENERATION PHASE
        # ========================================================
        try:
            output_path = app.transition_engine.generate_transition_mix(
                cur_id=cur_snip_id,
                nxt_id=nxt_snip_id,
                technique=technique,
                params=params,
                cur_ana=cur_analysis,
                nxt_ana=nxt_analysis
            )
        except Exception as e:
            print(f"❌ Mix fail: {e}")
            output_path = None
        
        if output_path and os.path.exists(output_path):
            print(f"✅ Fast Mix generated: {output_path}")
            
            drive_link = None
            if getattr(app, 'drive_manager', None):
                print("☁️ Uploading mix artifact to Drive...")
                drive_link = app.drive_manager.upload_transition(output_path)
            
            append_to_queue(output_path, drive_link, cur_info['title'], nxt_info['title'], technique)
            
            msg = f"🎧 Mix Ready ({get_unrated_count()}/{MAX_UNRATED_QUEUE})\n{cur_info['title'][:20]} -> {nxt_info['title'][:20]}\nTech: {technique}\n\n👉 Test here: {MOBILE_UI_URL}"
            send_notification(msg)
            
            print("🚀 Notification dispatched. Background loop continuing...")
        else:
            print("❌ Failed to generate mix.")
            
        time.sleep(2)

if __name__ == "__main__":
    try:
        test_random_transitions()
    except KeyboardInterrupt:
        print("\n👋 Background Queue Stopped safely.")
