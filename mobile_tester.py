import os
import random
import threading
import time
import json
import socket
import sys
import shutil
import traceback

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
import librosa
import soundfile as sf
import numpy as np
from flask import Flask, render_template_string, jsonify, request, send_file

dj = None
validator = None
app = Flask(__name__)

class TaskState:
    def __init__(self):
        self.lock = threading.Lock()
        self._state = {
            'status': 'idle', 'cur_title': '', 'nxt_title': '', 'technique': '',
            'audio_ready': False, 'last_update': 0, 'eta': 0, 'queue_count': 0, 'error': None
        }
    def get(self):
        with self.lock: return self._state.copy()
    def update(self, **kwargs):
        with self.lock: self._state.update(kwargs)

current_task = TaskState()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# (Keep your HTML_TEMPLATE exact same here as your original to save space. Paste it back in.)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AI DJ Tester PRO</title>
    <style>
        body { font-family: 'Inter', sans-serif; background: #0f172a; color: white; text-align: center; margin: 0; padding: 20px; }
        .card { background: #1e293b; border-radius: 16px; padding: 24px; max-width: 500px; margin: 10px auto; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); position: relative; }
        h1 { color: #38bdf8; font-size: 22px; margin-bottom: 20px; }
        .error { color: #ef4444; font-size: 12px; margin: 10px 0; }
        audio { width: 100%; margin: 15px 0; border-radius: 12px; }
        .btn { border: none; padding: 12px; border-radius: 10px; font-weight: bold; cursor: pointer; transition: 0.1s; font-size: 14px; }
        .btn-pass { background: #22c55e; color: white; font-size: 18px; padding: 18px; }
        .btn-fail { background: #ef4444; color: white; font-size: 18px; padding: 18px; }
        .btn-seek { background: #334155; color: white; padding: 8px 5px; font-size: 12px; }
        #technique-box { background:#334155; padding:15px; border-radius:12px; border:2px solid #38bdf8; margin:15px 0; }
        .tech-label { font-size:10px; color:#38bdf8; font-weight:bold; text-transform:uppercase; }
        .tech-value { font-size:18px; font-weight:bold; color:white; margin:5px 0; }
        textarea { width: 100%; height: 80px; border-radius: 10px; background: #0f172a; color: white; border: 1px solid #334155; padding: 12px; margin: 15px 0; box-sizing: border-box; }
        .loader { border: 4px solid #334155; border-top: 4px solid #38bdf8; border-radius: 50%; width: 40px; height: 40px; animation: spin 0.8s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        #queue-badge { position: absolute; top: 10px; right: 10px; background: #38bdf8; color: #000; font-size: 10px; font-weight: bold; padding: 4px 8px; border-radius: 20px; }
    </style>
</head>
<body>
    <h1>🎧 AI DJ Tester PRO</h1>
    <div class="card" id="task-card">
        <div id="queue-badge">Queue: <span id="q-count">0</span></div>
        <div id="loading" style="display:none;">
            <div class="loader"></div>
            <p style="font-size:20px; font-weight:bold;">🧠 AI DJ is Thinking...</p>
            <p style="color:#fbbf24; font-size:16px;">Estimated: <span id="time-left">--</span></p>
        </div>
        <div id="error-box" class="error" style="display:none;"></div>
        <div id="content">
            <div style="margin-bottom: 20px;">
                <div style="font-size: 10px; color: #94a3b8; font-weight: bold;">OUTGOING</div>
                <div id="outgoing-title" style="font-size: 18px; font-weight: bold; color: #f87171;">WAITING...</div>
                <div style="margin: 10px 0; color: #475569;">⬇️</div>
                <div style="font-size: 10px; color: #94a3b8; font-weight: bold;">INCOMING</div>
                <div id="incoming-title" style="font-size: 18px; font-weight: bold; color: #22c55e;">WAITING...</div>
            </div>
            <div id="technique-box">
                <div class="tech-label">Transition Technique</div>
                <div id="technique-name" class="tech-value">WAITING...</div>
            </div>
            <audio id="player" controls></audio>
            <div style="display: flex; justify-content: center; gap: 10px; margin: 10px 0;">
                <button class="btn btn-seek" onclick="player.currentTime -= 10">-10s</button>
                <button class="btn btn-seek" onclick="player.currentTime = 25">Jump</button>
                <button class="btn btn-seek" onclick="player.currentTime += 10">+10s</button>
            </div>
            <textarea id="comments" placeholder="Feedback for the AI?"></textarea>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap:15px;">
                <button class="btn btn-fail" onclick="sendFeedback(false)">❌ FAIL</button>
                <button class="btn btn-pass" onclick="sendFeedback(true)">✅ PASS</button>
            </div>
        </div>
    </div>
    <script>
        const player = document.getElementById('player');
        let lastUpdate = 0;
        function updateStatus() {
            fetch('/status').then(r => r.json()).then(data => {
                document.getElementById('q-count').innerText = data.queue_count || 0;
                if (data.error) { document.getElementById('error-box').style.display = 'block'; document.getElementById('error-box').innerText = data.error; } 
                else { document.getElementById('error-box').style.display = 'none'; }
                if (data.status === 'generating') {
                    document.getElementById('loading').style.display = 'block'; document.getElementById('content').style.display = 'none';
                    let diff = Math.max(0, data.eta - Math.floor(Date.now()/1000));
                    document.getElementById('time-left').innerText = diff + "s";
                } else if (data.audio_ready) {
                    document.getElementById('loading').style.display = 'none'; document.getElementById('content').style.display = 'block';
                    document.getElementById('outgoing-title').innerText = data.cur_title || 'Unknown';
                    document.getElementById('incoming-title').innerText = data.nxt_title || 'Unknown';
                    document.getElementById('technique-name').innerText = (data.technique || '').toUpperCase().replace(/_/g, ' ');
                    if (data.last_update > lastUpdate) {
                        player.src = '/mix.wav?t=' + data.last_update; lastUpdate = data.last_update; player.currentTime = 15;
                    }
                }
            }).catch(e => console.error(e));
        }
        setInterval(updateStatus, 2000); updateStatus();
        function sendFeedback(pass) {
            const text = document.getElementById('comments').value;
            fetch('/feedback', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({pass: pass, text_feedback: text})
            }).then(() => {
                document.getElementById('comments').value = ""; document.getElementById('loading').style.display = 'block'; document.getElementById('content').style.display = 'none';
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/status')
def status(): return jsonify(current_task.get())

@app.route('/mix.wav')
def get_mix():
    mix_path = 'data/sandbox/test_mix.wav'
    if os.path.exists(mix_path): return send_file(mix_path, mimetype='audio/wav')
    return "No mix available", 404

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    is_pass = data.get('pass', False)
    text = data.get('text_feedback', '')
    state = current_task.get()
    technique = state.get('technique', '')
    if technique:
        try:
            # FIXED: Handle missing directory
            os.makedirs('data/logs', exist_ok=True)
            weight_file = 'data/logs/feedback_weights.json'
            weights = {}
            if os.path.exists(weight_file):
                with open(weight_file, 'r') as f: weights = json.load(f)
            weights[technique] = weights.get(technique, 1.0) + (0.3 if is_pass else -0.2)
            with open(weight_file, 'w') as f: json.dump(weights, f, indent=2)
            
            with open('data/logs/feedback_log.jsonl', 'a') as f:
                f.write(json.dumps({'timestamp': time.time(), 'technique': technique, 'pass': is_pass, 'text': text}) + '\n')
        except Exception as e:
            print(f"Feedback save error: {e}")
            
    current_task.update(audio_ready=False, status='idle')
    return jsonify({'status': 'ok'})

def ensure_library():
    os.makedirs('data/library', exist_ok=True)
    os.makedirs('data/audio_cache', exist_ok=True)
    library_files = [f for f in os.listdir('data/library') if f.endswith('.mp3')]
    if len(library_files) >= 2: return library_files
    
    cache_files = [f for f in os.listdir('data/audio_cache') if f.endswith('.mp3')]
    for f in cache_files:
        if not os.path.exists(os.path.join('data/library', f)):
            shutil.copy(os.path.join('data/audio_cache', f), os.path.join('data/library', f))
            
    return [f for f in os.listdir('data/library') if f.endswith('.mp3')]

def download_random_songs():
    global dj
    if dj is None: return []
    try:
        playlist_url = dj.config.get('youtube', {}).get('playlist_url', '')
        if not playlist_url: return []
        songs = dj.downloader.get_playlist_metadata(playlist_url)
        if len(songs) < 2: return []
        
        for song in random.sample(songs, min(4, len(songs))):
            try:
                filepath = dj.downloader.download_song(song['url'], song['id'])
                if filepath and os.path.exists(filepath):
                    clean_name = "".join(c for c in song['title'] if c.isalnum() or c in ' -_').strip()[:50]
                    shutil.copy(filepath, os.path.join('data/library', f"{clean_name}.mp3"))
            except Exception: continue
        return ensure_library()
    except Exception: return []

def generate_transition_mix(dj_app, cur_id, nxt_id, technique, params, cur_ana, nxt_ana):
    os.makedirs('data/sandbox', exist_ok=True)
    
    # FIXED: Check if transition engine exists. If not, initialize it!
    if not hasattr(dj_app, 'transition_engine') or dj_app.transition_engine is None:
        print("🔧 Initializing MasterTransitionEngine...")
        from transition_engine.master_transition import MasterTransitionEngine
        dj_app.transition_engine = MasterTransitionEngine(dj_app.config)
        
    dj_app.transition_engine.test_mode = True
    dj_app.transition_engine.output_buffer = []
    
    try:
        dj_app.transition_engine.execute(cur_id, nxt_id, technique, params, cur_ana, nxt_ana)
        
        if not dj_app.transition_engine.output_buffer:
            print("❌ Transition engine generated no audio buffer!")
            return None
            
        mix_data = np.concatenate(dj_app.transition_engine.output_buffer)
        max_val = np.max(np.abs(mix_data))
        if max_val > 0:
            mix_data = mix_data / max_val * 0.85
            
        out_path = 'data/sandbox/test_mix.wav'
        sf.write(out_path, mix_data, dj_app.config['audio']['sample_rate'])
        return out_path
    finally:
        dj_app.transition_engine.test_mode = False

def trim_mix(mix_path, target_duration=60):
    try:
        audio, sr = librosa.load(mix_path, sr=44100)
        if len(audio) / sr <= target_duration: return
        center = len(audio) // 2
        half = int(target_duration * sr / 2)
        sf.write(mix_path, audio[max(0, center - half):min(len(audio), center + half)], sr)
    except Exception: pass

def factory_loop():
    global dj, validator
    while dj is None: time.sleep(1)
    
    try:
        from ai_brain.agents.validation_agent import ValidationAgent
        validator = ValidationAgent(dj.config)
    except ImportError:
        validator = None
        
    consecutive_errors = 0
    while True:
        try:
            if current_task.get()['audio_ready']:
                time.sleep(3)
                continue
                
            files = ensure_library()
            if len(files) < 2:
                current_task.update(status='downloading')
                files = download_random_songs()
                if len(files) < 2:
                    current_task.update(status='error', error='Need 2 MP3s in data/library/')
                    time.sleep(10)
                    continue
                    
            current_task.update(status='generating', eta=int(time.time() + 60), error=None)
            s1, s2 = random.sample(files, 2)
            
            cur_id, nxt_id = os.path.splitext(s1)[0], os.path.splitext(s2)[0]
            cur_ana = dj.analyzer.analyze_track(os.path.join('data/library', s1), cur_id)
            nxt_ana = dj.analyzer.analyze_track(os.path.join('data/library', s2), nxt_id)
            cur_ana['title'], nxt_ana['title'] = s1, s2
            
            # FIXED: Add missing phrase detector fallback if None
            if not hasattr(dj, 'phrase_detector') or dj.phrase_detector is None:
                from analysis.phrase_detector import PhraseDetector
                dj.phrase_detector = PhraseDetector(dj.config)
            
            technique, params = dj.transition_decider.decide(cur_id, nxt_id, cur_ana, nxt_ana)
            mix_path = generate_transition_mix(dj, cur_id, nxt_id, technique, params, cur_ana, nxt_ana)
            
            if not mix_path: raise Exception("Mix generation returned None")
            
            try:
                from utils.notifier import send_notification
                send_notification(f"💿 MIX READY: {s1} -> {s2}", topic='dj-agent-parth')
            except: pass
            
            if validator:
                try:
                    if validator.score_transition(mix_path, technique, cur_ana, nxt_ana) < 0.3:
                        continue
                except: pass
                
            trim_mix(mix_path)
            current_task.update(status='ready', cur_title=s1, nxt_title=s2, technique=technique, audio_ready=True, last_update=time.time())
            consecutive_errors = 0
            
        except Exception as e:
            consecutive_errors += 1
            current_task.update(error=str(e)[:100])
            traceback.print_exc()
            time.sleep(60 if consecutive_errors >= 5 else 5)

def init_app():
    global dj
    for d in ['data/library', 'data/sandbox', 'data/logs', 'data/audio_cache', 'data/metadata']:
        os.makedirs(d, exist_ok=True)
    try:
        from main import DJApp
        dj = DJApp()
    except Exception as e:
        print(f"Init error: {e}")

if __name__ == '__main__':
    threading.Thread(target=init_app, daemon=True).start()
    threading.Thread(target=factory_loop, daemon=True).start()
    print(f"\n🌐 Mobile Tester on http://{get_local_ip()}:8080\n")
    try:
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"Server crash: {e}")
