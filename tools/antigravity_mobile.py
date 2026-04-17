import os
import json
import time
import threading
from flask import Flask, render_template, jsonify, request, send_file
import socket

app = Flask(__name__)
PORT = 8081

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
        <title>Antigravity Workbench</title>
        <style>
            body { font-family: 'Courier New', monospace; background: #000; color: #0f0; margin: 0; padding: 0; }
            header { background: #111; padding: 10px; border-bottom: 1px solid #0f0; display: flex; justify-content: space-between; align-items: center; }
            .tabs { display: flex; background: #111; }
            .tab { flex: 1; padding: 10px; border: 1px solid #222; text-align: center; color: #444; cursor: pointer; }
            .tab.active { color: #0f0; border-bottom: 2px solid #0f0; }
            .panel { display: none; padding: 15px; }
            .panel.active { display: block; }
            #terminal { height: 60vh; overflow-y: auto; border: 1px solid #0f0; padding: 10px; margin-bottom: 10px; font-size: 11px; background: #050505; }
            #input-container { display: flex; gap: 5px; }
            input { flex-grow: 1; background: #000; color: #0f0; border: 1px solid #0f0; padding: 12px; font-size: 16px; outline: none; }
            button { background: #0f0; color: #000; border: none; padding: 12px 20px; font-weight: bold; }
            .msg { margin-bottom: 8px; }
            .user { color: #38bdf8; font-weight: bold; }
            .agent { color: #facc15; }
            .file-item { padding: 8px; border-bottom: 1px solid #222; font-size: 14px; color: #94a3b8; }
            pre { background: #050505; padding: 10px; border: 1px solid #222; color: #94a3b8; overflow-x: auto; font-size: 10px; }
        </style>
    </head>
    <body>
        <header>
            <div style="font-size: 12px; font-weight: bold;">🦖 ANTIGRAVITY WORKBENCH</div>
            <div id="agent-status" style="font-size: 10px; color: #facc15; font-weight: bold;">STATUS: IDLE</div>
        </header>
        <div class="tabs">
            <div class="tab active" onclick="showTab('chat')">CHAT</div>
            <div class="tab" onclick="showTab('files')">FILES</div>
            <div class="tab" onclick="showTab('code')">CODE</div>
        </div>

        <div id="chat" class="panel active">
            <div id="terminal"></div>
            <div id="input-container">
                <input type="text" id="cmd" placeholder="Command Agent..." autocomplete="off">
                <button onclick="send()">SEND</button>
            </div>
            <div style="margin-top: 10px; display: flex; gap: 5px;">
                <button onclick="sync()" style="background: #22c55e; flex: 1; padding: 15px;">🚀 SYNC</button>
                <button onclick="restartTunnels()" style="background: #f43f5e; flex: 1; padding: 15px;">🔄 TUNNELS</button>
            </div>
            <div style="margin-top: 5px;">
                <button onclick="startFleet()" style="background: #a855f7; width: 100%; padding: 15px; font-weight: bold; border-radius: 5px;">🦖 START LOCAL FLEET (Save Credits)</button>
            </div>
        </div>

        <div id="files" class="panel">
            <div id="file-list">Loading files...</div>
        </div>

        <div id="code" class="panel">
            <div id="file-path" style="font-size: 10px; color: #0f0; margin-bottom: 5px;">No file selected</div>
            <pre id="code-viewer">Select a file from the FILES tab</pre>
        </div>

        <script>
            let lastUpdate = 0;

            function showTab(id) {
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.getElementById(id).classList.add('active');
                event.target.classList.add('active');
                if(id === 'files') loadFiles();
            }

            function loadFiles() {
                fetch('/list_files').then(r => r.json()).then(files => {
                    const list = document.getElementById('file-list');
                    list.innerHTML = '';
                    files.forEach(f => {
                        const div = document.createElement('div');
                        div.className = 'file-item';
                        div.innerText = (f.isDir ? '📁 ' : '📄 ') + f.name;
                        div.onclick = () => { if(!f.isDir) viewCode(f.name); };
                        list.appendChild(div);
                    });
                });
            }

            function viewCode(path) {
                document.getElementById('file-path').innerText = path;
                document.getElementById('code-viewer').innerText = "Loading " + path + "...";
                showTab('code');
                fetch('/get_code?path='+path).then(r => r.json()).then(data => {
                    document.getElementById('code-viewer').innerText = data.code;
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
                    load();
                });
            }

            function load() {
                fetch('/get_messages?t=' + Date.now()).then(r => r.json()).then(data => {
                    const term = document.getElementById('terminal');
                    term.innerHTML = '';
                    data.msgs.forEach(m => {
                        const div = document.createElement('div');
                        div.className = 'msg';
                        let senderClass = m.sender === 'user' ? 'user' : 'agent';
                        div.innerHTML = `<span class="${senderClass}">${m.sender.toUpperCase()}:</span> ${m.text}`;
                        term.appendChild(div);
                    });
                    term.scrollTop = term.scrollHeight;
                    
                    const status = document.getElementById('agent-status');
                    status.innerText = 'STATUS: ' + data.status.toUpperCase();
                    status.style.color = data.status === 'idle' ? '#22c55e' : '#facc15';
                });
            }

            function sync() {
                if(!confirm("Push all changes to GitHub?")) return;
                fetch('/sync_now').then(r => r.json()).then(data => {
                    alert(data.msg);
                });
            }

            function restartTunnels() {
                if(!confirm("Restart all public tunnels? Link might change!")) return;
                fetch('/restart_tunnels').then(r => r.json()).then(data => {
                    alert("Tunnels restarting... Refresh in 10 seconds!");
                });
            }

            function startFleet() {
                fetch('/start_fleet').then(r => r.json()).then(data => {
                    alert(data.msg);
                });
            }

            setInterval(load, 2000);
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
    status = "idle"
    if os.path.exists("data/logs/agent_status.txt"):
        with open("data/logs/agent_status.txt", "r") as f:
            status = f.read().strip()
            
    msgs = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                msgs.append(json.loads(line))
    return jsonify({'msgs': msgs[-50:], 'status': status})

@app.route('/list_files')
def list_files():
    files = []
    for item in os.listdir('.'):
        if item.startswith('.') or item == '__pycache__': continue
        files.append({'name': item, 'isDir': os.path.isdir(item)})
    return jsonify(sorted(files, key=lambda x: (not x['isDir'], x['name'])))

@app.route('/get_code')
def get_code():
    path = request.args.get('path')
    if not path or not os.path.exists(path): return jsonify({'code': 'File not found'})
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            return jsonify({'code': content})
    except Exception as e:
        return jsonify({'code': f'Error reading file: {e}'})

@app.route('/sync_now')
def sync_now():
    import subprocess
    try:
        # Run the sync tool
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Remote Sync from Antigravity Workbench"], check=True)
        subprocess.run(["git", "push", "origin", "master:main", "--force"], check=True)
        return jsonify({'status': 'ok', 'msg': 'Successfully Pushed to GitHub!'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': f'Sync failed: {e}'})
@app.route('/restart_tunnels')
def restart_tunnels():
    import subprocess
    # Kill existing npx/node processes
    subprocess.run(["taskkill", "/F", "/IM", "node.exe", "/T"], capture_output=True)
    # Restart them in background
    # (These will use the same subdomains as before)
    subprocess.Popen(["npx", "localtunnel", "--port", "8081", "--subdomain", "dj-agent-cmd-parth"], shell=True)
    subprocess.Popen(["npx", "localtunnel", "--port", "8080", "--subdomain", "parth-dj-express-2026"], shell=True)
    return jsonify({'status': 'ok', 'msg': 'Tunnels are restarting...'})

@app.route('/start_fleet')
def start_fleet():
    import subprocess
    import sys
    # Start the fleet commander in a new process
    try:
        subprocess.Popen([sys.executable, "local_fleet_commander.py"])
        return jsonify({'status': 'ok', 'msg': '🦖 Fleet Commander Launched! Logic tasks are now LOCAL.'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': f'Failed to launch fleet: {e}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
