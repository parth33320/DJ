import os
import json
import logging
from flask import Flask, jsonify, request, render_template_string, send_from_directory

# Disable noisy Flask terminal logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

LINKS_FILE = 'data/logs/transition_links.json'
WEIGHTS_FILE = 'data/logs/feedback_weights.json'
MEMORY_FILE = 'data/logs/critic_memory.json'

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

# --- FOCUS MODE HTML UI ---
MOBILE_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI DJ Focus Mode</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0a0a; color: #e0e0e0; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; min-height: 100vh;}
        .header { text-align: center; margin-bottom: 20px; width: 100%; max-width: 600px; padding-top: 10px; }
        .header h1 { color: #00ffcc; margin: 0; font-size: 1.8rem; text-transform: uppercase; letter-spacing: 2px; }
        .queue-status { background: #222; color: #aaa; padding: 5px 15px; border-radius: 20px; font-size: 0.9rem; display: inline-block; margin-top: 10px; }
        
        #queue-container { width: 100%; max-width: 600px; }
        
        .card { background: #1a1a1a; padding: 25px; border-radius: 16px; border: 1px solid #333; box-shadow: 0 10px 30px rgba(0,0,0,0.8); transition: opacity 0.3s ease; }
        
        .tech-badge { display: block; text-align: center; background: #00ffcc22; color: #00ffcc; padding: 8px 15px; border-radius: 8px; font-size: 1rem; font-weight: bold; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 20px; border: 1px solid #00ffcc; }
        
        .track-box { background: #111; padding: 15px; border-radius: 8px; border-left: 4px solid; margin-bottom: 10px; }
        .track-out { border-left-color: #ff5252; }
        .track-in { border-left-color: #4caf50; }
        .track-label { font-size: 0.75rem; color: #777; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
        .track-title { font-size: 1.1rem; font-weight: bold; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .arrow-down { text-align: center; color: #444; font-size: 1.5rem; margin: 5px 0; }
        
        audio { width: 100%; margin: 25px 0; border-radius: 8px; height: 50px; }
        audio::-webkit-media-controls-panel { background-color: #2a2a2a; }
        
        textarea { width: 100%; box-sizing: border-box; background: #000; color: #fff; border: 1px solid #444; padding: 15px; border-radius: 8px; font-family: inherit; resize: vertical; min-height: 100px; margin-bottom: 20px; font-size: 1rem; }
        textarea:focus { outline: none; border-color: #00ffcc; background: #111; }
        
        .btn-row { display: flex; gap: 15px; }
        button { flex: 1; padding: 18px; border: none; border-radius: 8px; font-weight: bold; font-size: 1.2rem; cursor: pointer; transition: transform 0.1s, filter 0.2s; text-transform: uppercase; letter-spacing: 1px; color: white; }
        button:active { transform: scale(0.95); }
        .btn-fail { background: linear-gradient(135deg, #d32f2f, #b71c1c); box-shadow: 0 4px 15px rgba(211, 47, 47, 0.4); }
        .btn-pass { background: linear-gradient(135deg, #388e3c, #1b5e20); box-shadow: 0 4px 15px rgba(56, 142, 60, 0.4); }
        
        .empty { text-align: center; color: #666; margin-top: 50px; padding: 40px; border: 2px dashed #333; border-radius: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>DJ God Mode</h1>
        <div class="queue-status" id="queue-count">Syncing...</div>
    </div>
    
    <div id="queue-container"></div>

    <script>
        function escapeHtml(unsafe) {
            return (unsafe || '').toString()
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        async function fetchQueue() {
            const res = await fetch('/api/queue');
            const data = await res.json();
            const container = document.getElementById('queue-container');
            const counter = document.getElementById('queue-count');
            
            if (data.length === 0) {
                counter.innerText = "0 Mixes Pending";
                container.innerHTML = '<div class="empty"><h3>Queue Empty</h3><p>AI Brain is slicing audio... Please wait.</p></div>';
                return;
            }

            counter.innerText = `${data.length} Mixes in Queue`;

            // FOCUS MODE: Only render the FIRST unrated item
            const item = data[0];
            
            // Clean strings for JS injection
            const safeFrom = escapeHtml(item.from_title);
            const safeTo = escapeHtml(item.to_title);
            const safeTech = escapeHtml(item.technique);

            container.innerHTML = `
                <div class="card" id="focus-card">
                    <div class="tech-badge">⚡ ${safeTech}</div>
                    
                    <div class="track-box track-out">
                        <div class="track-label">Outgoing Track (A)</div>
                        <div class="track-title">${safeFrom}</div>
                    </div>
                    
                    <div class="arrow-down">⬇</div>
                    
                    <div class="track-box track-in">
                        <div class="track-label">Incoming Track (B)</div>
                        <div class="track-title">${safeTo}</div>
                    </div>
                    
                    <audio controls autoplay src="/audio?path=${encodeURIComponent(item.local_path)}"></audio>
                    
                    <textarea id="feedback-input" placeholder="TEACH THE AI: Why was this mix fire or trash? (e.g. 'Beat drop clashed, cut the bass earlier')"></textarea>
                    
                    <div class="btn-row">
                        <button class="btn-fail" onclick="rateTransition(${item.timestamp}, '${safeTech}', 2, '${safeFrom}', '${safeTo}')">👎 Trash</button>
                        <button class="btn-pass" onclick="rateTransition(${item.timestamp}, '${safeTech}', 8, '${safeFrom}', '${safeTo}')">🔥 Fire</button>
                    </div>
                </div>
            `;
        }

        async function rateTransition(timestamp, technique, rating, fromTitle, toTitle) {
            const feedbackText = document.getElementById('feedback-input').value;
            
            // Fade out the card
            document.getElementById('focus-card').style.opacity = '0.2';
            document.getElementById('focus-card').style.pointerEvents = 'none';
            
            await fetch('/api/rate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ 
                    timestamp: timestamp, 
                    technique: technique, 
                    rating: rating,
                    feedback: feedbackText,
                    track_a: fromTitle,
                    track_b: toTitle
                })
            });
            
            // Instantly pull the next card
            fetchQueue();
        }

        // Auto-refresh every 5 seconds to catch new mixes if empty
        setInterval(() => {
            if (!document.getElementById('focus-card')) {
                fetchQueue();
            }
        }, 5000);
        
        fetchQueue();
    </script>
</body>
</html>
"""

@app.route('/')
def serve_ui():
    return render_template_string(MOBILE_UI_HTML)

# SERVE LOCAL MP3 DIRECTLY TO BROWSER PLAYER
@app.route('/audio')
def serve_audio():
    path = request.args.get('path')
    if path and os.path.exists(path):
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        return send_from_directory(directory, filename)
    return "Audio file not found or deleted from local cache", 404

@app.route('/api/queue', methods=['GET'])
def get_queue():
    links = load_json(LINKS_FILE, [])
    unrated = [l for l in links if l.get('rating') is None]
    return jsonify(unrated)

@app.route('/api/rate', methods=['POST'])
def rate_transition():
    data = request.json
    ts = data.get('timestamp')
    technique = data.get('technique')
    rating = data.get('rating')
    feedback_text = data.get('feedback', '').strip()
    
    # 1. Update Links JSON (Mark as tested)
    links = load_json(LINKS_FILE, [])
    for l in links:
        if l.get('timestamp') == ts:
            l['rating'] = rating
            l['tested'] = True
            l['human_feedback'] = feedback_text
            break
    save_json(LINKS_FILE, links)

    # 2. Mathematical Learning (Adjust Weights)
    weights = load_json(WEIGHTS_FILE, {})
    adjustment = (rating - 5) / 10.0
    weights[technique] = weights.get(technique, 0) + adjustment
    save_json(WEIGHTS_FILE, weights)

    # 3. Textual Learning (Save LLM Memory)
    if feedback_text:
        memory = load_json(MEMORY_FILE, [])
        memory.append({
            "timestamp": ts,
            "technique": technique,
            "track_a": data.get('track_a'),
            "track_b": data.get('track_b'),
            "rating": rating,
            "criticism": feedback_text
        })
        save_json(MEMORY_FILE, memory[-50:])
        print(f"📝 Saved text critique for LLM: '{feedback_text[:30]}...'")

    print(f"✅ User Rated: {technique} -> {rating}/10 (Weight adjusted: {adjustment:+.2f})")
    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("🌐 UI Focus Server Booting on port 8080...")
    app.run(host='0.0.0.0', port=8080, threaded=True)
