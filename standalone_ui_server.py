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
MEMORY_FILE = 'data/logs/critic_memory.json'  # NEW: LLM Text Feedback Memory

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

# --- PRO DJ HTML UI ---
MOBILE_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI DJ God Mode</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0a0a; color: #e0e0e0; margin: 0; padding: 15px; }
        .header { text-align: center; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 15px; }
        .header h1 { color: #00ffcc; margin: 0; font-size: 1.8rem; text-transform: uppercase; letter-spacing: 2px; }
        .queue-status { color: #888; font-size: 0.9rem; margin-top: 5px; }
        
        .card { background: #1a1a1a; padding: 20px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #333; box-shadow: 0 8px 16px rgba(0,0,0,0.5); }
        .track-info { display: flex; flex-direction: column; gap: 8px; margin-bottom: 15px; }
        .track-title { font-size: 1.1rem; font-weight: bold; color: #fff; }
        .arrow { color: #555; font-size: 1.2rem; margin: 0 10px; }
        
        .tech-badge { display: inline-block; background: #333; color: #00ffcc; padding: 5px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; width: max-content; margin-bottom: 15px; border: 1px solid #00ffcc; }
        
        audio { width: 100%; margin-bottom: 15px; border-radius: 8px; outline: none; }
        audio::-webkit-media-controls-panel { background-color: #2a2a2a; }
        audio::-webkit-media-controls-current-time-display, audio::-webkit-media-controls-time-remaining-display { color: #fff; }
        
        textarea { width: 100%; box-sizing: border-box; background: #111; color: #fff; border: 1px solid #444; padding: 12px; border-radius: 8px; font-family: inherit; resize: vertical; min-height: 80px; margin-bottom: 15px; font-size: 0.95rem; }
        textarea:focus { outline: none; border-color: #00ffcc; }
        
        .btn-row { display: flex; gap: 10px; }
        button { flex: 1; padding: 15px; border: none; border-radius: 8px; font-weight: bold; font-size: 1.1rem; cursor: pointer; transition: opacity 0.2s; text-transform: uppercase; letter-spacing: 1px; }
        button:active { opacity: 0.7; }
        .btn-fail { background: #d32f2f; color: white; }
        .btn-pass { background: #388e3c; color: white; }
        
        .empty { text-align: center; color: #666; margin-top: 50px; padding: 40px; border: 2px dashed #333; border-radius: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎧 Transition Queue</h1>
        <div class="queue-status" id="queue-count">Scanning local memory...</div>
    </div>
    
    <div id="queue-container"></div>

    <script>
        async function fetchQueue() {
            const res = await fetch('/api/queue');
            const data = await res.json();
            const container = document.getElementById('queue-container');
            const counter = document.getElementById('queue-count');
            
            counter.innerText = `${data.length} Mixes Awaiting Evaluation`;
            
            if (data.length === 0) {
                container.innerHTML = '<div class="empty"><h3>Queue Empty</h3><p>The AI Brain is crunching audio. Refresh in a moment.</p></div>';
                return;
            }

            container.innerHTML = data.map((item, index) => `
                <div class="card" id="card-${index}">
                    <div class="tech-badge">⚡ ${item.technique}</div>
                    
                    <div class="track-info">
                        <div class="track-title" style="color: #ff5252;">A: ${item.from_title}</div>
                        <div class="track-title" style="color: #4caf50;">B: ${item.to_title}</div>
                    </div>
                    
                    <audio controls src="/audio?path=${encodeURIComponent(item.local_path)}"></audio>
                    
                    <textarea id="feedback-${index}" placeholder="Optional: Give the AI text feedback. Why was this mix fire or trash? (e.g. 'Beat drop clashed, vocal cut out too early')"></textarea>
                    
                    <div class="btn-row">
                        <button class="btn-fail" onclick="rateTransition(${index}, '${item.technique}', 2, '${item.from_title}', '${item.to_title}')">FAIL</button>
                        <button class="btn-pass" onclick="rateTransition(${index}, '${item.technique}', 8, '${item.from_title}', '${item.to_title}')">PASS</button>
                    </div>
                </div>
            `).join('');
        }

        async function rateTransition(index, technique, rating, fromTitle, toTitle) {
            const feedbackText = document.getElementById(`feedback-${index}`).value;
            
            // Hide the card instantly for good UX
            document.getElementById(`card-${index}`).style.opacity = '0.5';
            document.getElementById(`card-${index}`).style.pointerEvents = 'none';
            
            await fetch('/api/rate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ 
                    index: index, 
                    technique: technique, 
                    rating: rating,
                    feedback: feedbackText,
                    track_a: fromTitle,
                    track_b: toTitle
                })
            });
            
            fetchQueue(); // Refresh queue
        }

        // Auto-refresh every 10 seconds to catch newly generated mixes
        setInterval(fetchQueue, 10000);
        fetchQueue();
    </script>
</body>
</html>
"""

@app.route('/')
def serve_ui():
    return render_template_string(MOBILE_UI_HTML)

# NEW: Route to securely serve the local MP3 mix directly to the browser
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
    idx = data.get('index')
    technique = data.get('technique')
    rating = data.get('rating')
    feedback_text = data.get('feedback', '').strip()
    
    # 1. Update Links JSON (Mark as tested)
    links = load_json(LINKS_FILE, [])
    unrated = [l for l in links if l.get('rating') is None]
    
    if 0 <= idx < len(unrated):
        target_item = unrated[idx]
        for l in links:
            if l['timestamp'] == target_item['timestamp']:
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
            "timestamp": time.time(),
            "technique": technique,
            "track_a": data.get('track_a'),
            "track_b": data.get('track_b'),
            "rating": rating,
            "criticism": feedback_text
        })
        # Keep only the last 50 memories so the LLM context window doesn't explode
        save_json(MEMORY_FILE, memory[-50:])
        print(f"📝 Saved text critique for LLM: '{feedback_text[:30]}...'")

    print(f"✅ User Rated: {technique} -> {rating}/10 (Weight adjusted: {adjustment:+.2f})")
    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("🌐 Standalone UI Server Booting on port 8080...")
    app.run(host='0.0.0.0', port=8080, threaded=True)
