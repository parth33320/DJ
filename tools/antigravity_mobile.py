import os
import json
import time
import threading
from flask import Flask, render_template, jsonify, request, send_file
import socket

app = Flask(__name__)
PORT = 9090 # Different port from DJ tester

# Shared Command Log
LOG_PATH = "data/logs/remote_chat.jsonl"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

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
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Antigravity Mobile Command</title>
        <style>
            body { font-family: 'Courier New', monospace; background: #000; color: #0f0; margin: 0; padding: 10px; }
            #terminal { height: 60vh; overflow-y: auto; border: 1px solid #0f0; padding: 10px; margin-bottom: 10px; font-size: 12px; background: #050505; }
            #input-container { display: flex; gap: 5px; }
            input { flex-grow: 1; background: #000; color: #0f0; border: 1px solid #0f0; padding: 12px; font-size: 16px; outline: none; }
            button { background: #0f0; color: #000; border: none; padding: 12px 20px; font-weight: bold; cursor: pointer; }
            .msg { margin-bottom: 8px; border-bottom: 1px solid #020; padding-bottom: 4px; }
            .user { color: #38bdf8; font-weight: bold; }
            .agent { color: #facc15; }
            .timestamp { color: #444; font-size: 9px; }
        </style>
    </head>
    <body>
        <div style="font-size: 14px; margin-bottom: 10px;">🦖 ANTIGRAVITY MOBILE CMD v1.0</div>
        <div id="terminal"></div>
        <div id="input-container">
            <input type="text" id="cmd" placeholder="Type to Agent..." autocomplete="off">
            <button onclick="send()">SEND</button>
        </div>

        <script>
            const term = document.getElementById('terminal');
            let lastId = 0;

            function load() {
                fetch('/get_messages').then(r => r.json()).then(msgs => {
                    msgs.forEach(m => {
                        const div = document.createElement('div');
                        div.className = 'msg';
                        div.innerHTML = `<span class="timestamp">[${new Date(m.t*1000).toLocaleTimeString()}]</span> <span class="${m.sender}">${m.sender.toUpperCase()}:</span> ${m.text}`;
                        term.appendChild(div);
                        term.scrollTop = term.scrollHeight;
                    });
                });
            }

            function send() {
                const inp = document.getElementById('cmd');
                const text = inp.value;
                if(!text) return;
                fetch('/send_command', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({text: text})
                }).then(() => {
                    inp.value = "";
                    const div = document.createElement('div');
                    div.className = 'msg';
                    div.innerHTML = `<span class="user">USER:</span> ${text}`;
                    term.appendChild(div);
                    term.scrollTop = term.scrollHeight;
                });
            }

            document.getElementById('cmd').addEventListener('keypress', (e) => {
                if(e.key === 'Enter') send();
            });

            setInterval(load_updates, 2000);
            
            async function load_updates() {
                 // Polling for agent responses
            }
            load();
        </script>
    </body>
    </html>
    """

@app.route('/send_command', methods=['POST'])
def send_command():
    data = request.json
    entry = {'t': time.time(), 'sender': 'user', 'text': data['text']}
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + "\n")
    return jsonify({'status': 'ok'})

@app.route('/get_messages')
def get_messages():
    if not os.path.exists(LOG_PATH): return jsonify([])
    msgs = []
    with open(LOG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            msgs.append(json.loads(line))
    return jsonify(msgs[-50:]) # Last 50

if __name__ == '__main__':
    print(f"🚀 Mobile Command Terminal at http://{get_local_ip()}:{PORT}")
    app.run(host='0.0.0.0', port=PORT)
