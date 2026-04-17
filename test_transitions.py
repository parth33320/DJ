import os, sys, random, json, time, subprocess, librosa, numpy as np
from main import DJApp
from utils.notifier import send_notification

MOBILE_UI_URL = "https://parth-dj-god-mode-2026.loca.lt"
MAX_UNRATED_QUEUE = 20

def load_json_safe(fp, default):
    if os.path.exists(fp):
        try:
            with open(fp, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return default

def save_json_safe(fp, data):
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

def get_unrated_count():
    return len([l for l in load_json_safe('data/logs/transition_links.json', []) if l.get('rating') is None])

def get_smart_slice_timestamp(filepath):
    try:
        y, sr = librosa.load(filepath, sr=11025, mono=True)
        rms = librosa.feature.rms(y=y)[0]
        smooth = np.convolve(rms, np.ones(int((sr/512)*5))/int((sr/512)*5), mode='valid')
        drop_time = librosa.frames_to_time(np.argmax(np.diff(smooth)), sr=sr)
        return max(0, drop_time - 30)
    except: return 45.0

def test_random_transitions():
    print("🔧 Booting AI DJ Brain (Active Remediation Engine)...")
    app = DJApp(); app.playlist = app.downloader.get_playlist_metadata(app.config['youtube']['playlist_url'])
    blacklist = set(load_json_safe('data/logs/blacklist.json', []))
    session_skips = set(); is_sleeping = False

    while True:
        state = load_json_safe('data/logs/system_state.json', {})
        mode = state.get('mode', 'NORMAL')
        ready = []

        # 1. REMEDIATION BRANCH (SAME SONGS, NEW KNOWLEDGE)
        if mode == 'REMEDIATION':
            tech = state.get('failed_technique', 'cut')
            print(f"📚 STUDY MODE: Fetching tutorial for {tech}...")
            
            # Call knowledge agent to fetch real steps
            subprocess.run([sys.executable, 'knowledge_agent.py', state['homework_query'], tech])
            
            f_id = state.get('failed_from_id')
            t_id = state.get('failed_to_id')
            
            # Find the exact same songs in playlist
            c_i = next((s for s in app.playlist if s['id'] == f_id), None)
            n_i = next((s for s in app.playlist if s['id'] == t_id), None)
            
            if c_i and n_i:
                # Load the snips directly (they already exist from last failure)
                ready = [
                    {'path': os.path.join(app.config['paths']['audio_cache'], f"{c_i['id']}_snip.mp3"), 'info': c_i},
                    {'path': os.path.join(app.config['paths']['audio_cache'], f"{n_i['id']}_snip.mp3"), 'info': n_i}
                ]
                print(f"🔄 RETRY MODE: Same songs, new brain! ({c_i['title']} -> {n_i['title']})")
            
            # Reset state immediately so we don't loop forever
            state['mode'] = 'NORMAL'
            save_json_safe('data/logs/system_state.json', state)

        # 2. NORMAL ACQUISITION BRANCH
        else:
            unrated = get_unrated_count()
            if unrated >= MAX_UNRATED_QUEUE:
                if not is_sleeping: print(f"⏸️ Queue full ({unrated}/{MAX_UNRATED_QUEUE}). Paused."); is_sleeping = True
                time.sleep(10); continue
            is_sleeping = False

            drive_index = load_json_safe('data/logs/drive_index.json', {})
            candidates = [s for s in app.playlist if s['id'] not in blacklist and s['id'] not in session_skips]
            
            while len(ready) < 2 and candidates:
                uncharted = [s for s in candidates if s['id'] not in drive_index]
                chosen = random.choice(uncharted) if uncharted else random.choice(candidates)
                candidates = [c for c in candidates if c['id'] != chosen['id']]
                
                sid = chosen['id']; snip_id = f"{sid}_snip"; snip_p = os.path.join(app.config['paths']['audio_cache'], f"{snip_id}.mp3")
                if os.path.exists(snip_p): ready.append({'path': snip_p, 'info': chosen}); continue
                
                raw_p = os.path.join(app.config['paths']['audio_cache'], f"{sid}.mp3")
                if sid in drive_index: 
                    app.drive_manager.download_file(app.downloader._get_account_for_song(sid), drive_index[sid], raw_p)
                elif app.downloader.download_song(chosen['url'], sid): raw_p = os.path.join(app.config['paths']['audio_cache'], f"{sid}.mp3")
                else: session_skips.add(sid); continue

                start = get_smart_slice_timestamp(raw_p)
                subprocess.run(['ffmpeg', '-y', '-i', raw_p, '-ss', str(start), '-t', '90', '-c:a', 'libmp3lame', '-q:a', '2', snip_p], capture_output=True)
                if sid not in drive_index:
                    did = app.downloader.upload_to_drive(sid, app.drive_manager)
                    if did: drive_index[sid] = did; save_json_safe('data/logs/drive_index.json', drive_index)
                elif os.path.exists(raw_p): os.remove(raw_p)
                ready.append({'path': snip_p, 'info': chosen})

        if len(ready) < 2: continue
        
        # 3. DECIDE & MIX (Both modes hit this!)
        c_i, n_i = ready[0]['info'], ready[1]['info']
        c_a = app.analyzer.analyze_track(ready[0]['path'], f"{c_i['id']}_snip")
        n_a = app.analyzer.analyze_track(ready[1]['path'], f"{n_i['id']}_snip")
        
        # Force technique if remediation, else let it decide
        if mode == 'REMEDIATION': tech = state.get('failed_technique', 'cut_transition'); params = {}
        else: tech, params = app.transition_decider.decide_transition(c_i['title'], n_i['title'], c_a, n_a)
        
        out_p = app.transition_engine.generate_transition_mix(f"{c_i['id']}_snip", f"{n_i['id']}_snip", tech, params, c_a, n_a)
        if out_p:
            d_l = app.drive_manager.upload_transition(out_p)
            links = load_json_safe('data/logs/transition_links.json', [])
            
            # 🚨 CAVE-MAN FIX: Save from_id and to_id here so UI can access them!
            links.append({
                'from_id': c_i['id'], 'to_id': n_i['id'],
                'from_title': c_i['title'], 'to_title': n_i['title'], 
                'technique': tech, 'drive_link': d_l, 
                'local_path': out_p, 'timestamp': time.time(), 'rating': None
            })
            save_json_safe('data/logs/transition_links.json', links)
            
            mix_type = "🛠️ REMEDIATION MIX" if mode == 'REMEDIATION' else "🎧 NEW MIX"
            send_notification(f"{mix_type} Ready: {tech}\n{MOBILE_UI_URL}")

if __name__ == "__main__": test_random_transitions()
