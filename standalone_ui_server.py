import os
import json
import logging
from flask import Flask, jsonify, request, render_template_string

# Disable noisy logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

LINKS_FILE = 'data/logs/transition_links.json'
WEIGHTS_FILE = 'data/logs/feedback_weights.json'

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

# --- HTML TEMPLATE ---
# A clean, mobile-first dark mode UI
MOBILE_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI DJ Workbench</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #121212; color: #fff; margin: 0; padding: 20px; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h2 { margin-top: 0; color: #00e5ff; font-size: 1.2rem; }
        p { color: #aaa; font-size: 0.9rem; line-height: 1.4; }
        .btn-row { display: flex; gap: 10px; margin-top: 15px; }
        button { flex: 1; padding: 15px; border: none; border-radius: 8px; font-weight: bold; font-size: 1rem; cursor: pointer; }
        .btn-pass { background: #00c853; color: white; }
        .btn-fail { background: #d50000; color: white; }
        .audio-link { display: inline-block; padding: 10px 15px; background: #333; color: #fff; text-decoration: none; border-radius: 6px; margin-bottom: 15px; width: 100%; box-sizing: border-box; text-align: center; }
        .empty { text-align: center; color: #666; margin-top: 50px; }
    </style>
</head>
<body>
    <h1 style="text-align: center; color: #fff;">🎧 Transition Queue</h1>
    <div id="queue-container"></div>

    <script>
        async function fetchQueue() {
            const res = await fetch('/api/queue');
            const data = await res.json();
            const container = document.getElementById('queue-container');
            
            if (data.length === 0) {
                container.innerHTML = '<div class="empty"><h3>No mixes waiting.</h3><p>Agent is crunching audio...</p></div>';
                return;
            }

            container.innerHTML = data.map((item, index) => `
                <div class="card" id="card-${index}">
                    <h2>${item.from_title.substring(0, 30)}... <br>⬇️<br> ${item.to_title.substring(0, 30)}...</h2>
                    <p><b>Technique:</b> ${item.technique.toUpperCase()}</p>
                    <a href="${item.drive_link}" target="_blank" class="audio-link">▶️ Listen on GDrive</a>
                    <div class="btn-row">
                        <button class="btn-fail" onclick="rateTransition(${index}, '${item.technique}', 2)">FAIL</button>
                        <button class="btn-pass" onclick="rateTransition(${index}, '${item.technique}', 8)">PASS</button>
                    </div>
                </div>
            `).join('');
        }

        async function rateTransition(index, technique, rating) {
            document.getElementById(`card-${index}`).style.display = 'none';
            await fetch('/api/rate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ index, technique, rating })
            });
            fetchQueue();
        }

        // Auto-refresh every 5 seconds
        setInterval(fetchQueue, 5000);
        fetchQueue();
    </script>
</body>
</html>
"""

@app.route('/')
def serve_ui():
    return render_template_string(MOBILE_UI_HTML)

@app.route('/api/queue', methods=['GET'])
def get_queue():
    links = load_json(LINKS_FILE, [])
    # Return only unrated mixes
    unrated = [l for l in links if l.get('rating') is None]
    return jsonify(unrated)

@app.route('/api/rate', methods=['POST'])
def rate_transition():
    data = request.json
    idx = data.get('index')
    technique = data.get('technique')
    rating = data.get('rating')

    # 1. Update Links JSON (Mark as tested)
    links = load_json(LINKS_FILE, [])
    unrated = [l for l in links if l.get('rating') is None]
    if 0 <= idx < len(unrated):
        # Find the actual item in the main list
        target_item = unrated[idx]
        for l in links:
            if l['timestamp'] == target_item['timestamp']:
                l['rating'] = rating
                l['tested'] = True
                break
        save_json(LINKS_FILE, links)

    # 2. Update AI Weights JSON
    weights = load_json(WEIGHTS_FILE, {})
    adjustment = (rating - 5) / 10.0
    weights[technique] = weights.get(technique, 0) + adjustment
    save_json(WEIGHTS_FILE, weights)

    print(f"✅ User Rated: {technique} -> {rating}/10 (Weight adjusted: {adjustment:+.2f})")
    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("🌐 Standalone UI Server Booting on port 8080...")
    print("🛡️  This server will stay alive even if you restart the AI Brain.")
    app.run(host='0.0.0.0', port=8080, threaded=True)
