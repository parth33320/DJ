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
from ai_brain.agents.validation_agent import ValidationAgent

app = Flask(__name__)
dj = None
validator = None
current_task = {
    'status': 'idle',
    'cur_title': '',
    'nxt_title': '',
    'technique': '',
    'audio_ready': False,
    'last_update': 0,
    'eta': 0,
    'queue_count': 0
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
            body { font-family: 'Inter', sans-serif; background: #0f172a; color: white; text-align: center; margin: 0; padding: 20px; }
            .card { background: #1e293b; border-radius: 16px; padding: 24px; max-width: 500px; margin: 10px auto; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); position: relative; }
            h1 { color: #38bdf8; font-size: 22px; margin-bottom: 20px; }
            h2 { font-size: 18px; margin: 10px 0; }
            .status { font-style: italic; color: #94a3b8; margin: 15px 0; font-size: 14px; }
            audio { width: 100%; margin: 15px 0; border-radius: 12px; }
            .btn { border: none; padding: 12px; border-radius: 10px; font-weight: bold; cursor: pointer; transition: 0.1s; font-size: 14px; }
            .btn-blue { background: #0ea5e9; color: white; }
            .btn-pass { background: #22c55e; color: white; font-size: 18px; padding: 18px; }
            .btn-fail { background: #ef4444; color: white; font-size: 18px; padding: 18px; }
            .btn-seek { background: #334155; color: white; padding: 8px 5px; font-size: 12px; }
            #technique-box { background:#334155; padding:15px; border-radius:12px; border:2px solid #38bdf8; margin:15px 0; transition: 0.3s; }
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
                <p id="loading-text" style="font-size:20px; font-weight:bold; margin-bottom:5px;">🧠 AI DJ is Thinking...</p>
                <p id="eta-text" style="color:#fbbf24; font-size:16px;">Estimated Ready: <span id="time-left">--</span></p>
            </div>
            
            <div id="content">
                <div style="margin-bottom: 20px;">
                    <div style="font-size: 10px; color: #94a3b8; font-weight: bold; text-transform: uppercase;">Outgoing Song</div>
                    <div id="outgoing-title" style="font-size: 18px; font-weight: bold; color: #f87171;">WAITING...</div>
                    <div style="margin: 10px 0; color: #475569;">⬇️</div>
                    <div style="font-size: 10px; color: #94a3b8; font-weight: bold; text-transform: uppercase;">Incoming Song</div>
                    <div id="incoming-title" style="font-size: 18px; font-weight: bold; color: #22c55e;">WAITING...</div>
                </div>
                <div id="technique-box">
                    <div style="display: flex; justify-content: center; align-items: center; gap: 8px; margin-bottom: 5px;">
                        <span class="tech-label">Transition Technique</span>
                        <span id="innovation-badge" style="display:none; background: #fbbf24; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold;">💡 INNOVATION</span>
                    </div>
                    <div id="technique-name" class="tech-value">WAITING...</div>
                </div>
                <audio id="player" controls></audio>
                <div class="controls">
                    <button class="btn btn-seek" onclick="player.currentTime -= 10">-10s</button>
                    <button class="btn btn-seek" onclick="player.currentTime = 25">Jump to Trans</button>
                    <button class="btn btn-seek" onclick="player.currentTime += 10">+10s</button>
                </div>
                <textarea id="comments" placeholder="Suggestions for the Agent?"></textarea>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap:15px;">
                    <button class="btn btn-fail" onclick="sendFeedback(false)">❌ FAIL</button>
                    <button class="btn btn-pass" onclick="sendFeedback(true)">✅ PASS</button>
                </div>
            </div>
        </div>
        <script>
            let lastUpdate = 0;
            function updateStatus() {
                fetch('/status').then(r => r.json()).then(data => {
                    document.getElementById('q-count').innerText = data.queue_count;
                    if (data.status === 'generating') {
                        document.getElementById('loading').style.display = 'block';
                        document.getElementById('content').style.display = 'none';
                        let diff = Math.max(0, data.eta - Math.floor(Date.now()/1000));
                        document.getElementById('time-left').innerText = diff + "s remaining";
                    } else if (data.audio_ready) {
                        document.getElementById('loading').style.display = 'none';
                        document.getElementById('content').style.display = 'block';
                        document.getElementById('outgoing-title').innerText = data.cur_title;
                        document.getElementById('incoming-title').innerText = data.nxt_title;
                        document.getElementById('technique-name').innerText = data.technique.toUpperCase();
                        document.getElementById('innovation-badge').style.display = data.technique.includes('novel') ? 'inline-block' : 'none';
                        if (data.last_update > lastUpdate) {
                            document.getElementById('player').src = '/mix.wav?t=' + data.last_update;
                            lastUpdate = data.last_update;
                            document.getElementById('player').currentTime = 15;
                        }
                    }
                });
            }
            setInterval(updateStatus, 2000);
            function sendFeedback(pass) {
                const text = document.getElementById('comments').value;
                fetch('/feedback', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({pass, text_feedback: text})
                }).then(() => {
                    document.getElementById('comments').value = "";
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
    # Just mark current as done and the loop will pick up next
    current_task['audio_ready'] = False
    return jsonify({'status': 'ok'})

def factory_loop():
    global current_task, validator
    innovation_batch = []
    
    while True:
        if current_task['audio_ready']:
            time.sleep(5)
            continue
            
        current_task['status'] = 'generating'
        current_task['eta'] = int(time.time() + 90)
        
        try:
            files = [f for f in os.listdir('data/library') if f.endswith('.mp3')]
            if len(files) < 2:
                time.sleep(10)
                continue

            random.shuffle(files)
            s1, s2 = files[0], files[1]
            cur = {'id': s1.replace('.mp3',''), 'title': s1, 'path': os.path.join('data/library', s1)}
            nxt = {'id': s2.replace('.mp3',''), 'title': s2, 'path': os.path.join('data/library', s2)}
            
            cur_ana = dj.analyzer.analyze_track(cur['path'], cur['id'])
            nxt_ana = dj.analyzer.analyze_track(nxt['path'], nxt['id'])
            
            technique, params = dj.transition_decider.decide(cur['id'], nxt['id'], cur_ana, nxt_ana)
            
            # 🚀 Mutation check
            is_innovation = "novel" in technique.lower()
            
            mix_path = dj.transition_engine.generate_transition_mix(cur['id'], nxt['id'], technique, params, cur_ana, nxt_ana)
            
            # 🚀 Validation
            score = validator.score_transition(mix_path, technique, cur_ana, nxt_ana)
            
            if is_innovation:
                innovation_batch.append({'path': mix_path, 'score': score, 'tech': technique, 'titles': (cur['title'], nxt['title'])})
                print(f"   🧪 Innovation Batch: {len(innovation_batch)}/10 collected.")
                
                if len(innovation_batch) >= 10:
                    # Pick winner
                    winner = max(innovation_batch, key=lambda x: x['score'])
                    msg = f"🏆 TOP INNOVATION FOUND!\nMethod: {winner['tech']}\nScore: {winner['score']:.2f}\nSongs: {winner['titles'][0]} -> {winner['titles'][1]}"
                    send_notification(msg)
                    innovation_batch = [] # Reset
            
            if score < 0.4:
                print(f"   🗑️  Validation failed ({score:.2f}). Deleting...")
                if os.path.exists(mix_path): os.remove(mix_path)
                continue
                
            # 🚀 Slice
            audio, sr = librosa.load(mix_path, sr=44100)
            center = 30.0
            start, end = int((center-30)*sr), int((center+30)*sr)
            sf.write(mix_path, audio[max(0,start):min(len(audio),end)], sr)

            # 🚀 Update Local
            current_task.update({
                'status': 'ready',
                'cur_title': cur['title'],
                'nxt_title': nxt['title'],
                'technique': technique,
                'audio_ready': True,
                'last_update': time.time()
            })
            
            # 🚀 Drive Upload (Optional background)
            try:
                # me could push to drive here using drive_manager
                pass
            except:
                pass

        except Exception as e:
            print(f"❌ Factory Error: {e}")
            time.sleep(10)

def init():
    global dj, validator
    dj = DJApp()
    validator = ValidationAgent(dj.config)
    factory_loop()

if __name__ == '__main__':
    threading.Thread(target=init, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)
