import os
import random
import threading
import time
import json
from flask import Flask, render_template, jsonify, request, send_file
import numpy as np
import soundfile as sf
import requests
from colorama import Fore, Style
from main import DJApp
from utils.notifier import send_notification
import socket

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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI DJ Mobile Tester</title>
        <style>
            body { font-family: -apple-system, sans-serif; background: #1a1a1a; color: white; text-align: center; padding: 20px; }
            .card { background: #2b2b2b; padding: 20px; border-radius: 15px; margin: 20px 0; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
            .btn { display: block; width: 100%; padding: 15px; margin: 10px 0; border: none; border-radius: 10px; font-size: 18px; font-weight: bold; cursor: pointer; }
            .btn-pass { background: #28a745; color: white; }
            .btn-fail { background: #dc3545; color: white; }
            .btn-play { background: #007bff; color: white; }
            .status { color: #aaa; font-size: 14px; }
            audio { width: 100%; margin-top: 15px; }
            .loader { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 2s linear infinite; display: inline-block; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        <h1>🎧 AI DJ Tester</h1>
        <div class="card" id="task-card">
            <div id="loading" style="display:none;">
                <div class="loader"></div>
                <p id="loading-text" style="font-size:20px; font-weight:bold; margin-bottom:5px;">🧠 AI DJ is Thinking...</p>
                <p id="eta-text" style="color:#ffc107; font-size:16px;">Estimated Ready: <span id="time-left">--</span></p>
                <p id="return-text" style="color:#aaa; font-size:14px;">Come back at: <span id="ready-at">--</span></p>
            </div>
            <div id="content">
                <h2 id="songs">Waiting...</h2>
                <p id="technique" class="status"></p>
                <audio id="player" controls></audio>
                <div style="margin-top:20px;">
                    <button class="btn btn-pass" onclick="feedback(1)">✅ PASS (Good)</button>
                    <button class="btn btn-fail" onclick="feedback(0)">❌ FAIL (Bad)</button>
                </div>
            </div>
            <div id="error-box" style="display:none; color: #ff4444; border: 1px solid #ff4444; padding: 10px; border-radius: 5px; margin-top: 10px;">
                <p>⚠️ Error: <span id="error-msg"></span></p>
                <button class="btn btn-play" onclick="location.reload()">Retry</button>
            </div>
        </div>
        <p class="status">Automatically generating next transition after feedback.</p>

        <script>
            function updateStatus() {
                fetch('/status')
                    .then(r => r.json())
                    .then(data => {
                        if (data.status === 'generating') {
                            document.getElementById('loading').style.display = 'block';
                            document.getElementById('content').style.display = 'none';
                            document.getElementById('error-box').style.display = 'none';
                            
                            // Update ETA
                            let now = Math.floor(Date.now() / 1000);
                            let diff = Math.max(0, data.eta - now);
                            document.getElementById('time-left').innerText = diff + "s remaining";
                            
                            let date = new Date(data.eta * 1000);
                            document.getElementById('ready-at').innerText = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                        } else if (data.status === 'error') {
                            document.getElementById('loading').style.display = 'none';
                            document.getElementById('error-box').style.display = 'block';
                            document.getElementById('error-msg').innerText = data.error || "Unknown Error";
                        } else if (data.audio_ready) {
                            document.getElementById('loading').style.display = 'none';
                            document.getElementById('content').style.display = 'block';
                            document.getElementById('songs').innerText = data.cur_title + " → " + data.nxt_title;
                            document.getElementById('technique').innerText = "Technique: " + data.technique;
                            if (document.getElementById('player').src.indexOf('mix.wav') === -1 || data.last_update > window.lastUpdate) {
                                document.getElementById('player').src = '/mix.wav?t=' + data.last_update;
                                window.lastUpdate = data.last_update;
                            }
                        }
                    });
            }

            function feedback(is_pass) {
                fetch('/feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({pass: is_pass})
                }).then(() => {
                    document.getElementById('content').style.display = 'none';
                    document.getElementById('loading').style.display = 'block';
                    setTimeout(updateStatus, 2000);
                });
            }

            window.lastUpdate = 0;
            setInterval(updateStatus, 3000);
            updateStatus();
        </script>
    </body>
    </html>
    """

from utils.json_utils import make_serializable

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
    
    # Record feedback
    technique = current_task['technique']
    rating = 8 if is_pass else 3
    weight_file = os.path.join('data', 'logs', 'feedback_weights.json')
    os.makedirs(os.path.dirname(weight_file), exist_ok=True)
    
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
        
    print(f"✅ Feedback received: {'PASS' if is_pass else 'FAIL'} for {technique}")
    
    # Trigger next generation
    threading.Thread(target=generate_loop).start()
    return jsonify({'success': True})

def generate_loop():
    global current_task
    if current_task['status'] == 'generating':
        return
        
    current_task['status'] = 'generating'
    current_task['audio_ready'] = False
    current_task['eta'] = int(time.time() + 120) # Est 120 seconds for DL + Analysis
    
    try:
        # Pick 2 songs
        songs = random.sample(dj.playlist, 2)
        cur, nxt = songs[0], songs[1]
        
        # Download & Analyze
        for s in [cur, nxt]:
            if s['id'] not in dj.metadata_cache:
                path = dj.downloader.download_song(s['url'], s['id'])
                analysis = dj.analyzer.analyze_track(path, s['id'])
                analysis['title'] = s['title']
                dj.metadata_cache[s['id']] = analysis
        
        cur_ana = dj.metadata_cache[cur['id']]
        nxt_ana = dj.metadata_cache[nxt['id']]
        
        # Decide & Execute
        try:
            technique, params = dj.transition_decider.decide(cur['id'], nxt['id'], cur_ana, nxt_ana)
        except:
            technique = 'cut_transition'
            params = {}
        
        # Capture audio
        captured = []
        def mock_play(audio, sr=None):
            if audio is not None: captured.append(audio)
        dj.transition_engine._play_audio = mock_play
        
        dj.transition_engine.execute(cur['id'], nxt['id'], technique, params, cur_ana, nxt_ana)
        
        if captured:
            mix = np.concatenate(captured)
            os.makedirs('data/sandbox', exist_ok=True)
            sf.write('data/sandbox/test_mix.wav', mix, 44100)
            
            current_task.update({
                'status': 'ready',
                'cur_title': cur['title'],
                'nxt_title': nxt['title'],
                'technique': technique,
                'audio_ready': True,
                'last_update': time.time()
            })
            
            # Notify phone
            msg = f"Transition Ready!\n{cur['title'][:30]} -> {nxt['title'][:30]}"
            requests.post(f"https://ntfy.sh/dj-agent-parth", 
                          data=msg.encode('utf-8'),
                          headers={
                              "Title": "AI DJ Transition Ready!",
                              "Click": f"http://{get_local_ip()}:8080",
                              "Tags": "musical_note,headphones"
                          })
            
            send_notification(msg)
            
    except Exception as e:
        print(f"❌ Generation error: {e}")
        current_task['status'] = 'error'
        current_task['error'] = str(e)

def init_and_loop():
    global dj
    print(f"{Fore.YELLOW}🔧 Initializing DJ App in background...{Style.RESET_ALL}")
    dj = DJApp()
    playlist_url = dj.config['youtube']['playlist_url']
    dj.playlist = dj.downloader.get_playlist_metadata(playlist_url)
    print(f"{Fore.GREEN}✅ DJ App Ready! Starting generation loop...{Style.RESET_ALL}")
    generate_loop()

def start_mobile_server():
    # Start DJ logic in background so Server can start immediately
    threading.Thread(target=init_and_loop, daemon=True).start()
    
    ip = get_local_ip()
    print(f"\n🚀 Mobile Tester running at: http://{ip}:8080")
    print(f"📖 Open this URL on your phone to test transitions!\n")
    # Using threaded=True to ensure multiple requests (like status check + audio stream) work
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

if __name__ == "__main__":
    start_mobile_server()
