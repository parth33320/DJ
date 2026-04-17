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
        .card { background: #1a1a1a; padding: 25px; border-radius: 16px; border: 1px solid #333; width: 100%; max-width: 600px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
        .tech-badge { display: block; text-align: center; background: #00ffcc22; color: #00ffcc; padding: 8px; border-radius: 8px; font-weight: bold; margin-bottom: 20px; border: 1px solid #00ffcc; }
        .track-box { background: #111; padding: 15px; border-radius: 8px; border-left: 4px solid; margin-bottom: 10px; }
        .track-out { border-left-color: #ff5252; }
        .track-in { border-left-color: #4caf50; }
        .track-title { font-size: 1.1rem; font-weight: bold; color: #fff; overflow: hidden; text-overflow: ellipsis; }
        audio { width: 100%; margin: 25px 0; }
        textarea { width: 100%; box-sizing: border-box; background: #000; color: #fff; border: 1px solid #444; padding: 15px; border-radius: 8px; min-height: 100px; margin-bottom: 20px; font-size: 1rem; }
        .btn-row { display: flex; gap: 15px; }
        button { flex: 1; padding: 18px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; color: white; text-transform: uppercase; }
        .btn-fail { background: #d32f2f; }
        .btn-pass { background: #388e3c; }
        .empty { text-align: center; color: #666; margin-top: 50px; }
    </style>
</head>
<body>
    <div class="header"><h1>DJ God Mode</h1><div id="queue-count">Syncing...</div></div>
    <div id="queue-container"></div>
    <script>
        async function fetchQueue() {
            const res = await fetch('/api/queue');
            const data = await res.json();
            const container = document.getElementById('queue-container');
            const counter = document.getElementById('queue-count');
            counter.innerText = `${data.length} Mixes Pending`;
            if (data.length === 0) {
                container.innerHTML = '<div class="empty"><h3>Queue Empty</h3><p>AI Brain is slicing audio...</p></div>';
                return;
            }
            const item = data[0];
            container.innerHTML = `
                <div class="card" id="focus-card">
                    <div class="tech-badge">⚡ ${item.technique}</div>
                    <div class="track-box track-out"><div class="track-title">A: ${item.from_title}</div></div>
                    <div class="track-box track-in"><div class="track-title">B: ${item.to_title}</div></div>
                    <audio controls autoplay src="/audio?path=${encodeURIComponent(item.local_path)}"></audio>
                    <textarea id="feedback-input" placeholder="TEACH THE AI: Why was this mix fire or trash?"></textarea>
                    <div class="btn-row">
                        <button class="btn-fail" onclick="rate(${item.timestamp}, '${item.technique}', 2, '${item.from_title.replace(/'/g,"")}', '${item.to_title.replace(/'/g,"")}', '${item.from_id}', '${item.to_id}')">👎 Trash</button>
                        <button class="btn-pass" onclick="rate(${item.timestamp}, '${item.technique}', 8, '${item.from_title.replace(/'/g,"")}', '${item.to_title.replace(/'/g,"")}', '${item.from_id}', '${item.to_id}')">🔥 Fire</button>
                    </div>
                </div>`;
        }
        async function rate(ts, tech, rating, from, to, from_id, to_id) {
            const feedback = document.getElementById('feedback-input').value;
            document.getElementById('focus-card').style.opacity = '0.3';
            await fetch('/api/rate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ timestamp: ts, technique: tech, rating: rating, feedback: feedback, track_a: from, track_b: to, from_id: from_id, to_id: to_id })
            });
            fetchQueue();
        }
        setInterval(() => { if (!document.getElementById('focus-card')) fetchQueue(); }, 5000);
        fetchQueue();
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
    return jsonify([l for l in links if l.get('rating') is None])

@app.route('/api/rate', methods=['POST'])
def rate_transition():
    data = request.json
    ts, tech, rating, feedback = data.get('timestamp'), data.get('technique'), data.get('rating'), data.get('feedback', '').strip()
    
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
        
        # 🚨 CAVE-MAN FIX: If FAIL, trigger REMEDIATION mode, save IDs!
        if rating < 5:
            state = load_json(STATE_FILE, {})
            state.update({
                'mode': 'REMEDIATION',
                'failed_technique': tech,
                'failed_from_id': data.get('from_id'),
                'failed_to_id': data.get('to_id'),
                'homework_query': f"How to DJ {tech} transition step by step"
            })
            save_json(STATE_FILE, state)
            print(f"🛑 FAIL DETECTED: Agent going to study {tech} for {data.get('track_a')} -> {data.get('track_b')}")

    return jsonify({"status": "success"})

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080, threaded=True)
