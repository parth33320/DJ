import os
import sys
import random
import json
import time
import subprocess
import librosa
import numpy as np
from main import DJApp
from utils.notifier import send_notification

# ==========================================
# CONFIGURATION
# ==========================================
# 1. Update this to your active localtunnel/ngrok URL
MOBILE_UI_URL = "https://parth-dj-god-mode-2026.loca.lt"

# 2. Pause generation if you have this many unrated mixes waiting
MAX_UNRATED_QUEUE = 3  

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

def get_smart_slice_timestamp(filepath: str) -> float:
    """
    DSP Speed Hack: Loads track at very low sample rate to find the Drop.
    Calculates RMS Energy derivative to find biggest energy spike.
    Returns the ideal start time (in seconds) to capture buildup + drop + vocals.
    """
    print(f"   🧠 Scanning audio topography to find beat drop...")
    try:
        # Load audio very fast (mono, low sample rate 11025Hz)
        y, sr = librosa.load(filepath, sr=11025, mono=True)
        
        # Calculate RMS energy across the track
        rms = librosa.feature.rms(y=y)[0]
        
        # Smooth energy to find macro track structure, not micro beats
        # ~21 frames per second at this sample rate. Smooth over 5 seconds.
        frames_per_sec = sr / 512 
        smooth_window = int(frames_per_sec * 5)
        smoothed_rms = np.convolve(rms, np.ones(smooth_window)/smooth_window, mode='valid')
        
        # Find the Drop: Maximum positive gradient (energy explosion)
        energy_gradient = np.diff(smoothed_rms)
        drop_frame = np.argmax(energy_gradient)
        
        # Convert frame index back to seconds
        drop_time = librosa.frames_to_time(drop_frame, sr=sr)
        
        # DJ Logic: We want 30 seconds of buildup (usually contains main vocal hook)
        # and 60 seconds of the drop/chorus to mix out of.
        start_time = max(0, drop_time - 30)
        print(f"   🎯 Drop detected at {drop_time:.1f}s. Slicing from {start_time:.1f}s.")
        return start_time
        
    except Exception as e:
        print(f"   ⚠️ Smart scan failed ({e}). Falling back to 45s default.")
        return 45.0

def test_random_transitions():
    print("🔧 Booting Async Test Queue (Smart Snippet Mode)...")
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
        # 3. DOWNLOAD & SMART PRE-CLIP (Speed & Brain Hack)
        # ---------------------------------------------------------
        for song_info in [cur_song_info, nxt_song_info]:
            song_id = song_info['id']
            snip_id = f"{song_id}_snip"  # Create a unique ID for the chunk
            
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
                    
                    if filepath is None or not os.path.exists(filepath):
                        print(f"❌ Failed to download '{song_info['title']}'. Me tag as BAD.")
                        blacklist.add(song_id)
                        save_blacklist(blacklist)
                        skip_loop = True
                        break
                
                # ✂️ THE SMART CLIPPER: Find real DJ buildup & drop
                slice_start = get_smart_slice_timestamp(filepath)
                SMART_LENGTH = 90  # 90 seconds gives room for 32-beat intros/outros
                
                print(f"✂️ Slicing optimal 90-second snippet (Vocals + Drop)...")
                # Using subprocess.run is safer than os.system to prevent terminal hanging
                subprocess.run([
                    'ffmpeg', '-y', '-i', filepath, 
                    '-ss', str(slice_start), 
                    '-t', str(SMART_LENGTH), 
                    '-c:a', 'libmp3lame', '-q:a', '2', 
                    snip_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Analyze Snippet (Fast)
            if snip_id not in app.metadata_cache:
                print(f"🔍 Analyzing Snippet: {song_info['title']}...")
                try:
                    analysis = app.analyzer.analyze_track(snip_path, snip_id)
                    analysis['title'] = song_info['title']
                    app.metadata_cache[snip_id] = analysis
                    with open(meta_path, 'w', encoding='utf-8') as f:
                        json.dump(analysis, f)
                except Exception as e:
                    print(f"❌ Analysis fail: {e}. Tagging as bad.")
                    blacklist.add(song_id)
                    save_blacklist(blacklist)
                    skip_loop = True
                    break

        if skip_loop:
            continue

        # Point pipeline to the tiny snippets
        cur_snip_id = f"{cur_song_info['id']}_snip"
        nxt_snip_id = f"{nxt_song_info['id']}_snip"
        
        cur_analysis = app.metadata_cache[cur_snip_id]
        nxt_analysis = app.metadata_cache[nxt_snip_id]
        
        # ---------------------------------------------------------
        # 4. AGENT DECIDES TRANSITION
        # ---------------------------------------------------------
        decide_result = app.transition_decider.decide_transition(
            cur_song_info['title'], nxt_song_info['title'], cur_analysis, nxt_analysis
        )
        
        if isinstance(decide_result, tuple):
            technique, params = decide_result
        else:
            technique = decide_result
            params = {"duration": 16}
        
        print(f"\n--- TESTING TRANSITION ---")
        print(f"From: {cur_song_info['title']} (BPM: {cur_analysis.get('bpm', 'Unknown')})")
        print(f"To:   {nxt_song_info['title']} (BPM: {nxt_analysis.get('bpm', 'Unknown')})")
        print(f"Chosen Technique: {technique}")
        
        # ---------------------------------------------------------
        # 5. GENERATE FILE & NOTIFY (Non-Blocking)
        # ---------------------------------------------------------
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
                print("☁️ Uploading to Drive...")
                drive_link = app.drive_manager.upload_transition(output_path)
            
            # Save to JSON queue for Local UI Agent to read
            append_to_queue(output_path, drive_link, cur_song_info['title'], nxt_song_info['title'], technique)
            
            # Ping Mobile Phone
            msg = f"🎧 Mix Ready ({get_unrated_count()}/{MAX_UNRATED_QUEUE})\n{cur_song_info['title'][:20]} -> {nxt_song_info['title'][:20]}\nTech: {technique}\n\n👉 Test here: {MOBILE_UI_URL}"
            send_notification(msg)
            
            print("🚀 Notification dispatched. Background loop continuing...")
        else:
            print("❌ Failed to generate mix.")
            
        # Do not wait for input. Let loop continue filling queue!
        time.sleep(2)

if __name__ == "__main__":
    try:
        test_random_transitions()
    except KeyboardInterrupt:
        print("\n👋 Background Queue Stopped safely.")
