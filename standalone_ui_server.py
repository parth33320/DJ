import os
import json
import logging
import time
from flask import Flask, jsonify, request, render_template_string, send_from_directory

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

LINKS_FILE = 'data/logs/transition_links.json'
WEIGHTS_FILE = 'data/logs/feedback_weights.json'
MEMORY_FILE = 'data/logs/critic_memory.json'
STATE_FILE = 'data/logs/system_state.json'

def load_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return default_val

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

MOBILE_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI DJ Focus Mode</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; }
        .header { text-align: center; margin-bottom: 20px; width: 100%; max-width: 600px; }
        .header h1 { color: #00ffcc; margin: 0; font-size: 1.8rem; text-transform: uppercase; letter-spacing: 2px; }
        .queue-badge { background: #333; padding: 5px 15px; border-radius: 20px; display: inline-block; margin-top: 10px; }
        .card { background: #1a1a1a; padding: 25px; border-radius: 16px; border: 1px solid #333; width: 100%; max-width: 600px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
        .tech-badge { display: block; text-align: center; background: #00ffcc22; color: #00ffcc; padding: 8px; border-radius: 8px; font-weight: bold; margin-bottom: 20px; border: 1px solid #00ffcc; }
        .track-box { background: #111; padding: 15px; border-radius: 8px; border-left: 4px solid; margin-bottom: 10px; }
        .track-out { border-left-color: #ff5252; }
        .track-in { border-left-color: #4caf50; }
        .label-sm { font-size: 0.75rem; font-weight: bold; margin-bottom: 5px; opacity: 0.7; }
        .label-out { color: #ff5252; }
        .label-in { color: #4caf50; }
        .track-title { font-size: 1.1rem; font-weight: bold; color: #fff; overflow: hidden; text-overflow: ellipsis; }
        .player-container { margin: 25px 0; }
        audio { width: 100%; }
        .loading-state { text-align: center; padding: 20px; color: #666; }
        .loading-state.active { color: #00ffcc; }
        textarea { width: 100%; box-sizing: border-box; background: #000; color: #fff; border: 1px solid #444; padding: 15px; border-radius: 8px; min-height: 100px; margin-bottom: 20px; font-size: 1rem; }
        .btn-row { display: flex; gap: 15px; }
        button { flex: 1; padding: 18px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; color: white; text-transform: uppercase; transition: opacity 0.2s; }
        button:disabled { opacity: 0.3; cursor: not-allowed; }
        .btn-fail { background: #d32f2f; }
        .btn-pass { background: #388e3c; }
        .empty { text-align: center; color: #666; margin-top: 50px; }
        .status-bar { font-size: 0.8rem; text-align: center; margin-top: 10px; padding: 5px; border-radius: 4px; }
        .status-loading { background: #333; color: #ffcc00; }
        .status-ready { background: #1b5e20; color: #4caf50; }
        .status-error { background: #b71c1c; color: #ff5252; }
    </style>
</head>
<body>
    <div class="header">
        <h1>DJ God Mode</h1>
        <div class="queue-badge" id="queue-count">Syncing...</div>
    </div>
    <div id="queue-container"></div>
    
    <script>
        let currentItem = null;
        let audioElement = null;
        let isProcessing = false;

        async function fetchQueue() {
            if (isProcessing) return; // Don't fetch while processing a rating
            
            const res = await fetch('/api/queue');
            const data = await res.json();
            const container = document.getElementById('queue-container');
            const counter = document.getElementById('queue-count');
            
            counter.innerText = data.length + ' Mixes Pending';
            
            if (data.length === 0) {
                // Stop any playing audio
                if (audioElement) {
                    audioElement.pause();
                    audioElement = null;
                }
                currentItem = null;
                container.innerHTML = '<div class="empty"><h3>Queue Empty</h3><p>AI Brain is slicing audio...</p></div>';
                return;
            }
            
            const newItem = data[0];
            
            // Only rebuild UI if this is a DIFFERENT mix than what's currently showing
            if (currentItem && currentItem.timestamp === newItem.timestamp) {
                return; // Same item, no need to rebuild
            }
            
            // Stop old audio before switching
            if (audioElement) {
                audioElement.pause();
                audioElement.src = '';
                audioElement = null;
            }
            
            currentItem = newItem;
            
            // Build the UI
            container.innerHTML = `
                <div class="card" id="focus-card">
                    <div class="tech-badge">* ${currentItem.technique}</div>
                    
                    <div class="track-box track-out">
                        <div class="label-sm label-out">OUTGOING TRACK (A) - Playing First</div>
                        <div class="track-title">${escapeHtml(currentItem.from_title)}</div>
                    </div>
                    
                    <div class="track-box track-in">
                        <div class="label-sm label-in">INCOMING TRACK (B) - Playing Second</div>
                        <div class="track-title">${escapeHtml(currentItem.to_title)}</div>
                    </div>
                    
                    <div class="player-container">
                        <audio id="main-audio" controls preload="auto"></audio>
                        <div id="audio-status" class="status-bar status-loading">Loading audio...</div>
                    </div>
                    
                    <textarea id="feedback-input" placeholder="TEACH THE AI: Why was this mix fire or trash?"></textarea>
                    
                    <div class="btn-row">
                        <button id="btn-trash" class="btn-fail" disabled>* Trash</button>
                        <button id="btn-fire" class="btn-pass" disabled>* Fire</button>
                    </div>
                </div>`;
            
            // Setup audio element with proper event handling
            audioElement = document.getElementById('main-audio');
            const statusBar = document.getElementById('audio-status');
            const btnTrash = document.getElementById('btn-trash');
            const btnFire = document.getElementById('btn-fire');
            
            // Audio loading events
            audioElement.oncanplaythrough = function() {
                statusBar.className = 'status-bar status-ready';
                statusBar.innerText = 'Ready to play - Rate this mix!';
                btnTrash.disabled = false;
                btnFire.disabled = false;
            };
            
            audioElement.onerror = function() {
                statusBar.className = 'status-bar status-error';
                statusBar.innerText = 'Error loading audio';
            };
            
            audioElement.onplay = function() {
                statusBar.className = 'status-bar status-ready';
                statusBar.innerText = 'NOW PLAYING - Listen and rate!';
            };
            
            // Set the source and load
            audioElement.src = '/audio?path=' + encodeURIComponent(currentItem.local_path);
            audioElement.load();
            
            // Attach button handlers
            btnTrash.onclick = function() { rateMix(2); };
            btnFire.onclick = function() { rateMix(8); };
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function rateMix(ratingScore) {
            if (!currentItem || isProcessing) return;
            
            isProcessing = true;
            
            // Disable buttons and show processing state
            const btnTrash = document.getElementById('btn-trash');
            const btnFire = document.getElementById('btn-fire');
            const statusBar = document.getElementById('audio-status');
            const card = document.getElementById('focus-card');
            
            btnTrash.disabled = true;
            btnFire.disabled = true;
            statusBar.innerText = 'Submitting rating...';
            statusBar.className = 'status-bar status-loading';
            card.style.opacity = '0.5';
            
            // STOP the audio NOW
            if (audioElement) {
                audioElement.pause();
                audioElement.src = '';
            }
            
            const feedback = document.getElementById('feedback-input').value;
            
            const payload = {
                timestamp: currentItem.timestamp,
                technique: currentItem.technique,
                rating: ratingScore,
                feedback: feedback,
                track_a: currentItem.from_title,
                track_b: currentItem.to_title,
                from_id: currentItem.from_id || "unknown",
                to_id: currentItem.to_id || "unknown"
            };

            try {
                await fetch('/api/rate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
            } catch (e) {
                console.error('Rating failed:', e);
            }
            
            // Clear current item to force reload
            currentItem = null;
            audioElement = null;
            isProcessing = false;
            
            // Small delay to let server update, then fetch new queue
            setTimeout(fetchQueue, 500);
        }

        // Initial fetch
        fetchQueue();
        
        // Poll for new items only when not playing/processing
        setInterval(function() {
            if (!isProcessing && (!audioElement || audioElement.paused)) {
                fetchQueue();
            }
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def serve_ui(): return render_template_string(MOBILE_UI_HTML)

@app.route('/audio')
def serve_audio():
    path = request.args.get('path')
    if path and os.path.exists(path):
        return send_from_directory(os.path.dirname(path), os.path.basename(path))
    return "Not Found", 404

@app.route('/api/queue')
def get_queue():
    links = load_json(LINKS_FILE, [])
    # Sort by timestamp so newest is first, then filter unrated
    unrated = [l for l in links if l.get('rating') is None]
    # Sort by timestamp ASCENDING so oldest unrated is first (FIFO)
    unrated.sort(key=lambda x: x.get('timestamp', 0))
    return jsonify(unrated)

@app.route('/api/rate', methods=['POST'])
def rate_transition():
    data = request.json
    ts = data.get('timestamp')
    tech = data.get('technique')
    rating = data.get('rating')
    feedback = data.get('feedback', '').strip()
    
    links = load_json(LINKS_FILE, [])
    for l in links:
        if l.get('timestamp') == ts:
            l.update({'rating': rating, 'tested': True, 'human_feedback': feedback})
            break
    save_json(LINKS_FILE, links)

    weights = load_json(WEIGHTS_FILE, {})
    weights[tech] = weights.get(tech, 0) + ((rating - 5) / 10.0)
    save_json(WEIGHTS_FILE, weights)

    if feedback:
        mem = load_json(MEMORY_FILE, [])
        mem.append({"timestamp": ts, "technique": tech, "rating": rating, "criticism": feedback})
        save_json(MEMORY_FILE, mem[-50:])
        
    # Trigger REMEDIATION mode on FAIL (Rating < 5)
    if rating < 5:
        state = load_json(STATE_FILE, {})
        
        if data.get('from_id') != "unknown" and data.get('to_id') != "unknown":
            state.update({
                'mode': 'REMEDIATION',
                'failed_technique': tech,
                'failed_from_id': data.get('from_id'),
                'failed_to_id': data.get('to_id'),
                'homework_query': f"How to DJ {tech} transition tutorial step by step"
            })
            save_json(STATE_FILE, state)
            print(f"REMEDIATION TRIGGERED: AI will study {tech}")
        else:
            print("FAILED ON OLD MIX: No track IDs available for remediation")

    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("Flask UI starting on port 8080...")
    app.run(host='0.0.0.0', port=8080, threaded=True, use_reloader=False)
