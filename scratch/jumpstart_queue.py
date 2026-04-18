import json
import os
import time
from main import DJApp

def jumpstart():
    print("[JUMPSTART] Initializing DJApp...")
    app = DJApp()
    
    # Load cached songs to avoid YouTube 404s
    app.playlist = app.downloader.load_cached_playlist()
    if len(app.playlist) < 2:
        print("[ERROR] Not enough cached songs to jumpstart.")
        return

    # Pick two distinct cached songs
    cur = app.playlist[0]
    nxt = app.playlist[1]
    
    print(f"[JUMPSTART] Pairing: {cur['title']} -> {nxt['title']}")
    
    # Analyze snippets
    cur_snip_id = f"{cur['id']}_snip"
    nxt_snip_id = f"{nxt['id']}_snip"
    
    ana_a = app.analyzer.analyze_track(f"data/audio_cache/{cur_snip_id}.mp3", cur_snip_id)
    ana_b = app.analyzer.analyze_track(f"data/audio_cache/{nxt_snip_id}.mp3", nxt_snip_id)

    # Decide and Mix
    res = app.transition_decider.decide_transition(cur['title'], nxt['title'], ana_a, ana_b)
    if isinstance(res, tuple):
        tech, params = res
    else:
        tech, params = res, {"duration": 16}
        
    print(f"[JUMPSTART] Technique: {tech}")
    
    out_path = app.transition_engine.generate_transition_mix(
        cur_snip_id, nxt_snip_id, tech, params, ana_a, ana_b
    )

    if out_path and os.path.exists(out_path):
        print(f"[SUCCESS] Mix generated: {out_path}")
        
        # Upload to Drive
        drive_link = app.drive_manager.upload_transition(out_path)
        
        # Inject into Ledger
        links_file = 'data/logs/transition_links.json'
        links = []
        if os.path.exists(links_file):
            with open(links_file, 'r', encoding='utf-8') as f:
                links = json.load(f)
        
        links.append({
            'from_title': cur['title'],
            'to_title': nxt['title'],
            'technique': tech,
            'drive_link': drive_link,
            'local_path': out_path,
            'timestamp': time.time(),
            'tested': False,
            'rating': None
        })
        
        with open(links_file, 'w', encoding='utf-8') as f:
            json.dump(links, f, indent=2)
            
        print("[JUMPSTART] Injection COMPLETE. Refresh your UI now!")
    else:
        print("[ERROR] Failed to generate manual mix.")

if __name__ == "__main__":
    jumpstart()
