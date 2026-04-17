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
    print("🔧 Booting AI DJ Brain (Penalty Box + Local KB Logic)...")
    app = DJApp(); app.playlist = app.downloader.get_playlist_metadata(app.config['youtube']['playlist_url'])
    blacklist = set(load_json_safe('data/logs/blacklist.json', []))
    session_skips = set(); is_sleeping = False

    while True:
        # 1. PENALTY BOX CHECK
        state = load_json_safe('data/logs/system_state.json', {})
        if state.get('penalty_until', 0) > time.time():
            if not state.get('homework_completed', False):
                query = state.get('homework_query', '')
                kb = load_json_safe('data/logs/dj_knowledge_base.json', [])
                matches = [r['technique_name'] for r in kb if any(w in (r['technique_name']+r['suitable_for']).lower() for w in query.lower().split() if len(w)>3)]
                print(f"🛑 PENALTY BOX: Learning '{query}'. Matches found: {matches}")
                state['homework_completed'] = True; save_json_safe('data/logs/system_state.json', state)
            time.sleep(60); continue

        # 2. QUEUE CHECK
        unrated = get_unrated_count()
        if unrated >= MAX_UNRATED_QUEUE:
            if not is_sleeping: print(f"⏸️ Queue full ({unrated}/{MAX_UNRATED_QUEUE}). Paused."); is_sleeping = True
            time.sleep(10); continue
        is_sleeping = False

        # 3. ACQUISITION
        drive_index = load_json_safe('data/logs/drive_index.json', {})
        candidates = [s for s in app.playlist if s['id'] not in blacklist and s['id'] not in session_skips]
        ready = []
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

            # Slice & Process
            start = get_smart_slice_timestamp(raw_p)
            subprocess.run(['ffmpeg', '-y', '-i', raw_p, '-ss', str(start), '-t', '90', '-c:a', 'libmp3lame', '-q:a', '2', snip_p], capture_output=True)
            if sid not in drive_index:
                did = app.downloader.upload_to_drive(sid, app.drive_manager)
                if did: drive_index[sid] = did; save_json_safe('data/logs/drive_index.json', drive_index)
            elif os.path.exists(raw_p): os.remove(raw_p)
            ready.append({'path': snip_p, 'info': chosen})

        if len(ready) < 2: continue
        
        # 4. DECIDE & MIX
        c_i, n_i = ready[0]['info'], ready[1]['info']
        c_a = app.analyzer.analyze_track(ready[0]['path'], f"{c_i['id']}_snip")
        n_a = app.analyzer.analyze_track(ready[1]['path'], f"{n_i['id']}_snip")
        tech, params = app.transition_decider.decide_transition(c_i['title'], n_i['title'], c_a, n_a)
        
        out_p = app.transition_engine.generate_transition_mix(f"{c_i['id']}_snip", f"{n_i['id']}_snip", tech, params, c_a, n_a)
        if out_p:
            d_l = app.drive_manager.upload_transition(out_p)
            links = load_json_safe('data/logs/transition_links.json', [])
            links.append({'from_title': c_i['title'], 'to_title': n_i['title'], 'technique': tech, 'drive_link': d_l, 'local_path': out_p, 'timestamp': time.time(), 'rating': None})
            save_json_safe('data/logs/transition_links.json', links)
            send_notification(f"🎧 Mix Ready: {tech}\n{MOBILE_UI_URL}")

if __name__ == "__main__": test_random_transitions()
