import os
import random
import threading
import time
import json
import socket
import librosa
import soundfile as sf
import requests
import numpy as np
from flask import Flask, render_template, jsonify, request, send_file
from colorama import Fore, Style
from main import DJApp
from utils.notifier import send_notification
from utils.json_utils import make_serializable

app = Flask(__name__)
dj = None
current_task = {
    'status': 'idle',
    'cur_title': '',
    'nxt_title': '',
    'technique': '',
    'audio_ready': False,
    'last_update': 0,
    'eta': 0
}

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>AI DJ Tester PRO</title>
        <style>
            body { font-family: 'Inter', system-ui, sans-serif; background: #0f172a; color: white; text-align: center; margin: 0; padding: 20px; }
            .card { background: #1e293b; border-radius: 16px; padding: 24px; max-width: 500px; margin: 10px auto; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); }
            h1 { color: #38bdf8; font-size: 22px; margin-bottom: 20px; }
            h2 { font-size: 18px; margin: 10px 0; }
            .status { font-style: italic; color: #94a3b8; margin: 15px 0; font-size: 14px; }
            audio { width: 100%; margin: 15px 0; border-radius: 12px; }
            
            .controls { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 15px; }
            .btn { border: none; padding: 12px; border-radius: 10px; font-weight: bold; cursor: pointer; transition: 0.1s; font-size: 14px; }
            .btn-blue { background: #0ea5e9; color: white; }
            .btn-pass { background: #22c55e; color: white; font-size: 18px; padding: 18px; }
            .btn-fail { background: #ef4444; color: white; font-size: 18px; padding: 18px; }
            .btn-seek { background: #334155; color: white; padding: 8px 5px; font-size: 12px; }
            .btn:active { transform: scale(0.95); opacity: 0.8; }
            
            #marker-info { background: #0c4a6e; padding: 10px; border-radius: 10px; font-size: 13px; margin: 10px 0; color: #38bdf8; font-weight: bold; }
            textarea { width: 100%; height: 80px; border-radius: 10px; background: #0f172a; color: white; border: 1px solid #334155; padding: 12px; margin: 15px 0; box-sizing: border-box; }
            
            .speed-row { margin: 15px 0; display: flex; justify-content: center; align-items: center; gap: 10px; }
            select { background: #334155; color: white; border: 1px solid #475569; padding: 8px; border-radius: 8px; }
            
            .loader { border: 4px solid #334155; border-top: 4px solid #38bdf8; border-radius: 50%; width: 40px; height: 40px; animation: spin 0.8s linear infinite; margin: 20px auto; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        <h1>🎧 AI DJ Tester PRO</h1>
        <div class="card" id="task-card">
            <div id="loading" style="display:none;">
                <div class="loader"></div>
                <p id="loading-text" style="font-size:20px; font-weight:bold; margin-bottom:5px;">🧠 AI DJ is Thinking...</p>
                <p id="eta-text" style="color:#fbbf24; font-size:16px;">Estimated Ready: <span id="time-left">--</span></p>
                <p id="return-text" style="color:#94a3b8; font-size:14px;">Come back at: <span id="ready-at">--</span></p>
            </div>
            
            <div id="content">
                <h2 id="songs">Waiting...</h2>
                <div id="marker-info">📍 Transition Marker: 30.0s</div>
                
                <audio id="player" controls controlsList="nodownload"></audio>
                
                <div class="controls">
                    <button class="btn btn-seek" onclick="seek(-30)">-30s</button>
                    <button class="btn btn-seek" onclick="seek(-10)">-10s</button>
                    <button class="btn btn-seek" onclick="seek(-5)">-5s</button>
                    <button class="btn btn-seek" onclick="seek(5)">+5s</button>
                    <button class="btn btn-seek" onclick="seek(10)">+10s</button>
                    <button class="btn btn-seek" onclick="seek(30)">+30s</button>
                </div>
                
                <div class="speed-row">
                    <span style="font-size:12px;">Speed:</span>
                    <select id="speed" onchange="changeSpeed()">
                        <option value="0.75">0.75x</option>
                        <option value="1.0" selected>1.0x</option>
                        <option value="1.25">1.25x</option>
                        <option value="1.5">1.5x</option>
                    </select>
                    <button class="btn btn-blue" onclick="jumpToTrans()" style="padding: 8px 15px;">Jump to Trans</button>
                </div>

                <p id="technique" class="status"></p>

                <textarea id="comments" placeholder="Suggestions for the Agent? (e.g. 'Beat was off')"></textarea>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap:15px;">
                    <button class="btn btn-fail" onclick="sendFeedback(false)">❌ FAIL</button>
                    <button class="btn btn-pass" onclick="sendFeedback(true)">✅ PASS</button>
                </div>
            </div>

            <div id="error-box" style="display:none; color:#f87171; background:#450a0a; padding:15px; border-radius:12px; margin-top:20px; font-family:monospace; font-size:11px; text-align:left;">
                <div id="error-msg" style="white-space:pre-wrap;"></div>
                <button class="btn btn-blue" onclick="location.reload()" style="margin-top:10px; width:100%">Retry</button>
            </div>
        </div>

        <script>
            const player = document.getElementById('player');
            let lastUpdate = 0;

            function seek(s) { player.currentTime += s; }
            function changeSpeed() { player.playbackRate = parseFloat(document.getElementById('speed').value); }
            function jumpToTrans() { player.currentTime = 25; }

            function updateStatus() {
                fetch('/status')
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'generating') {
                            document.getElementById('loading').style.display = 'block';
                            document.getElementById('content').style.display = 'none';
                            document.getElementById('error-box').style.display = 'none';
                            
                            let now = Math.floor(Date.now() / 1000);
                            let diff = Math.max(0, data.eta - now);
                            document.getElementById('time-left').innerText = diff + "s remaining";
                            let date = new Date(data.eta * 1000);
                            document.getElementById('ready-at').innerText = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                        } else if (data.status === 'error') {
                            document.getElementById('loading').style.display = 'none';
                            document.getElementById('content').style.display = 'none';
                            document.getElementById('error-box').style.display = 'block';
                            document.getElementById('error-msg').innerText = data.error_msg || "Unknown Error";
                        } else if (data.audio_ready) {
                            document.getElementById('loading').style.display = 'none';
                            document.getElementById('content').style.display = 'block';
                            document.getElementById('error-box').style.display = 'none';
                            document.getElementById('songs').innerText = data.cur_title + " → " + data.nxt_title;
                            document.getElementById('technique').innerText = "Technique: " + data.technique.toUpperCase();
                            
                            if (data.last_update > lastUpdate) {
                                player.src = '/mix.wav?t=' + data.last_update;
                                lastUpdate = data.last_update;
                                player.currentTime = 15; // Start 15s before transition (at 15s mark of 60s clip)
                            }
                        }
                    });
            }

            setInterval(updateStatus, 2000);

            function sendFeedback(isPass) {
                const text = document.getElementById('comments').value;
                document.getElementById('content').style.display = 'none';
                document.getElementById('loading').style.display = 'block';
                document.getElementById('loading-text').innerText = "Logging Feedback...";

                fetch('/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        pass: isPass,
                        text_feedback: text
                    })
                }).then(() => {
                    document.getElementById('comments').value = "";
                    document.getElementById('loading-text').innerText = "Generating Next...";
                });
            }
        </script>
    </body>
    </html>
    """

@app.route('/status')
def status():
    return jsonify(make_serializable(current_task))

@app.route('/mix.wav')
def get_mix():
    return send_file('data/sandbox/test_mix.wav', mimetype='audio/wav')

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    is_pass = data.get('pass')
    text_feedback = data.get('text_feedback', '')
    
    # Record feedback
    technique = current_task['technique']
    rating = 8 if is_pass else 3
    weight_file = os.path.join('data', 'logs', 'feedback_weights.json')
    text_log_file = os.path.join('data', 'logs', 'text_feedback.jsonl')
    os.makedirs(os.path.dirname(weight_file), exist_ok=True)
    
    # Update weights
    weights = {}
    if os.path.exists(weight_file):
        try:
            with open(weight_file, 'r') as f:
                weights = json.load(f)
        except:
            pass
            
    adjustment = (rating - 5) / 10.0
    weights[technique] = weights.get(technique, 1.0) + adjustment
    
    with open(weight_file, 'w') as f:
        json.dump(make_serializable(weights), f, indent=4)

    # Log text feedback
    if text_feedback:
        log_entry = {
            'timestamp': time.time(),
            'song_a': current_task['cur_title'],
            'song_b': current_task['nxt_title'],
            'technique': technique,
            'pass': is_pass,
            'feedback': text_feedback
        }
        with open(text_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(make_serializable(log_entry)) + "\n")
            
    print(f"✅ Feedback received: {'PASS' if is_pass else 'FAIL'} for {technique}")
    
    # Trigger next generation
    threading.Thread(target=generate_loop, daemon=True).start()
    return jsonify({'status': 'ok'})

def generate_loop():
    global current_task
    
    current_task['status'] = 'generating'
    current_task['audio_ready'] = False
    current_task['eta'] = int(time.time() + 120) 
    
    try:
        # Pick 2 songs from library
        files = [f for f in os.listdir('data/library') if f.endswith('.mp3')]
        if len(files) < 2:
            current_task.update({'status': 'error', 'error_msg': 'Need 2+ songs in data/library'})
            return

        random.shuffle(files)
        s1, s2 = files[0], files[1]
        
        cur = {'id': s1.replace('.mp3', ''), 'title': s1, 'path': os.path.join('data/library', s1)}
        nxt = {'id': s2.replace('.mp3', ''), 'title': s2, 'path': os.path.join('data/library', s2)}
        
        # Analyze
        cur_ana = dj.analyzer.analyze_track(cur['path'], cur['id'])
        nxt_ana = dj.analyzer.analyze_track(nxt['path'], nxt['id'])
        
        # Decide
        technique, params = dj.transition_decider.decide(cur['id'], nxt['id'], cur_ana, nxt_ana)
        
        # Execute mix
        mix_path = dj.transition_engine.generate_transition_mix(
            cur['id'], nxt['id'], technique, params, cur_ana, nxt_ana
        )
        
        # 🚀 60S SLICE LOGIC
        audio_full, sr = librosa.load(mix_path, sr=44100)
        center_sec = 30.0 # Engine puts trans center here for test_mix
        if len(audio_full) > (60 * sr):
            start_sample = max(0, int((center_sec - 30) * sr))
            end_sample = min(len(audio_full), int((center_sec + 30) * sr))
            audio_slice = audio_full[start_sample:end_sample]
            sf.write(mix_path, audio_slice, sr)
        
        current_task.update({
            'status': 'ready',
            'cur_title': cur['title'],
            'nxt_title': nxt['title'],
            'technique': technique,
            'audio_ready': True,
            'last_update': time.time()
        })
        
        # Notify
        msg = f"🎧 Ready: {cur['title']} ➔ {nxt['title']}\nMethod: {technique.upper()}"
        public_url = "https://antiques-roommate-warcraft-bodies.trycloudflare.com"
        send_notification(msg, click_url=public_url)
        
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"❌ Generation Error: {err}")
        current_task.update({'status': 'error', 'error_msg': err})

def init_and_loop():
    global dj
    print(f"{Fore.CYAN}🔧 Initializing DJ App in background...{Style.RESET_ALL}")
    try:
        dj = DJApp()
        print(f"{Fore.GREEN}✅ All components initialized{Style.RESET_ALL}")
        generate_loop()
    except Exception as e:
        print(f"{Fore.RED}❌ Initialization failed: {e}{Style.RESET_ALL}")
        current_task.update({'status': 'error', 'error_msg': str(e)})

if __name__ == '__main__':
    threading.Thread(target=init_and_loop, daemon=True).start()
    print(f"\n{Fore.CYAN}🚀 Mobile Tester running at: http://{get_local_ip()}:8080{Style.RESET_ALL}")
    app.run(host='0.0.0.0', port=8080)
