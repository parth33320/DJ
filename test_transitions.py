import os
import sys
import random
import json
from main import DJApp

def test_random_transitions():
    print("Initialize DJ App Components...")
    app = DJApp()
    
    # 1. Fetch playlist metadata
    playlist_url = app.config['youtube']['playlist_url']
    print(f"Fetching playlist from {playlist_url}...")
    app.playlist = app.downloader.get_playlist_metadata(playlist_url)
    
    if len(app.playlist) < 2:
        print("Need at least 2 songs in playlist!")
        return

    # 2. Pick 2 random songs
    songs_to_test = random.sample(app.playlist, 2)
    cur_song_info = songs_to_test[0]
    nxt_song_info = songs_to_test[1]
    
    print(f"\n🎧 Picked two random songs:")
    print(f"   [A] {cur_song_info['title']}")
    print(f"   [B] {nxt_song_info['title']}")

    # 3. Download and Analyze if needed
    for song_info in [cur_song_info, nxt_song_info]:
        song_id = song_info['id']
        
        # Try to load existing
        if os.path.exists(f'data/metadata/{song_id}.json'):
            with open(f'data/metadata/{song_id}.json', 'r') as f:
                app.metadata_cache[song_id] = json.load(f)
        
        filepath = os.path.join(app.config['paths']['audio_cache'], f"{song_id}.mp3")
        
        if not os.path.exists(filepath):
            print(f"Downloading {song_info['title']}...")
            filepath = app.downloader.download_song(song_info['url'], song_id)
            
            # ANTI-CRASH FIX: Catch bad downloads!
            if filepath is None or not os.path.exists(filepath):
                print(f"❌ Failed to download '{song_info['title']}'. Skipping this transition test.")
                return
            
        if song_id not in app.metadata_cache:
            print(f"Analyzing {song_info['title']}...")
            analysis = app.analyzer.analyze_track(filepath, song_id)
            analysis['title'] = song_info['title']
            app.metadata_cache[song_id] = analysis

    cur_analysis = app.metadata_cache[cur_song_info['id']]
    nxt_analysis = app.metadata_cache[nxt_song_info['id']]
    
    # 4. Agent decides transition using NEW Tree of Thoughts method
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
    print("Generating audio mix file... Please wait! (No headless hang)")
    
    # 5. GENERATE FILE (Fixes headless hang bug)
    out_path = app.transition_engine.generate_transition_mix(
        cur_id=cur_song_info['id'],
        nxt_id=nxt_song_info['id'],
        technique=technique,
        params=params,
        cur_ana=cur_analysis,
        nxt_ana=nxt_analysis
    )
    
    if out_path:
        print(f"✅ Mix generated successfully: {out_path}")
    else:
        print("❌ Failed to generate mix.")
        return
    
    # 6. Ask for user rating
    print("\n" + "="*50)
    rating = input("How would you rate this transition (1-10)? ")
    try:
        rating = int(rating)
        update_weights(technique, rating)
    except Exception as e:
        print("Invalid rating. Skipping feedback.")

def update_weights(technique, rating):
    weight_file = 'data/logs/feedback_weights.json'
    os.makedirs('data/logs', exist_ok=True)
    
    weights = {}
    if os.path.exists(weight_file):
        with open(weight_file, 'r') as f:
            try:
                weights = json.load(f)
            except Exception:
                pass
                
    # Scale rating 1-10 to an adjustment: 
    # 5 -> +0.0, 10 -> +0.5, 1 -> -0.4
    adjustment = (rating - 5) / 10.0
    
    current_weight = weights.get(technique, 0)
    weights[technique] = current_weight + adjustment
    
    with open(weight_file, 'w') as f:
        json.dump(weights, f, indent=4)
        
    print(f"Agent learned! Adjusted weight for '{technique}' by {adjustment:+.2f}")

if __name__ == "__main__":
    test_random_transitions()
