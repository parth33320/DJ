# boot_master.py
# THE GOD SCRIPT - Launches everything, heals everything, needs no human

import subprocess
import threading
import time
import os
import sys
import signal
import requests

# ============== CONFIGURATION ==============
FLASK_PORT = 8080
TUNNEL_SUBDOMAIN = "parth-dj-god-mode-2026"
TUNNEL_URL = f"https://{TUNNEL_SUBDOMAIN}.loca.lt"
NTFY_TOPIC = "dj-agent-parth"
HEALTH_CHECK_INTERVAL = 30  # seconds

# ============== GLOBAL STATE ==============
processes = {}
shutdown_flag = False

def log(emoji, msg):
    print(f"{emoji} [{time.strftime('%H:%M:%S')}] {msg}")

def send_notification(msg):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode('utf-8'), timeout=5)
    except:
        pass

def save_status(status):
    os.makedirs('data/logs', exist_ok=True)
    with open('data/logs/boot_status.json', 'w') as f:
        import json
        json.dump({'status': status, 'url': TUNNEL_URL, 'timestamp': time.time()}, f)

# ============== PROCESS LAUNCHERS ==============

def run_flask():
    """Flask UI Server - restarts forever until shutdown"""
    global shutdown_flag
    while not shutdown_flag:
        log("🌐", "Starting Flask UI server...")
        proc = subprocess.Popen(
            [sys.executable, 'standalone_ui_server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes['flask'] = proc
        
        # Stream output
        for line in iter(proc.stdout.readline, b''):
            if shutdown_flag:
                break
            line_text = line.decode('utf-8', errors='ignore').strip()
            if line_text:
                log("🌐", f"[Flask] {line_text}")
        
        proc.wait()
        if not shutdown_flag:
            log("⚠️", "Flask died! Restarting in 3 seconds...")
            time.sleep(3)

def run_tunnel():
    """Localtunnel - restarts forever until shutdown"""
    global shutdown_flag
    while not shutdown_flag:
        log("🚇", f"Starting tunnel to {TUNNEL_URL}...")
        proc = subprocess.Popen(
            ['lt', '--port', str(FLASK_PORT), '--subdomain', TUNNEL_SUBDOMAIN],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes['tunnel'] = proc
        
        for line in iter(proc.stdout.readline, b''):
            if shutdown_flag:
                break
            line_text = line.decode('utf-8', errors='ignore').strip()
            if line_text:
                log("🚇", f"[Tunnel] {line_text}")
        
        proc.wait()
        if not shutdown_flag:
            log("⚠️", "Tunnel died! Restarting in 3 seconds...")
            time.sleep(3)

def run_transition_engine():
    """Main DJ Brain Loop - restarts forever until shutdown"""
    global shutdown_flag
    time.sleep(10)  # Wait for Flask and Tunnel to stabilize
    
    while not shutdown_flag:
        log("🧠", "Starting DJ Transition Engine...")
        proc = subprocess.Popen(
            [sys.executable, 'test_transitions.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes['engine'] = proc
        
        for line in iter(proc.stdout.readline, b''):
            if shutdown_flag:
                break
            line_text = line.decode('utf-8', errors='ignore').strip()
            if line_text:
                log("🧠", f"[Engine] {line_text}")
        
        proc.wait()
        if not shutdown_flag:
            log("⚠️", "Engine died! Restarting in 5 seconds...")
            time.sleep(5)

def run_health_monitor():
    """Check if everything is alive, send status notifications"""
    global shutdown_flag
    time.sleep(15)  # Let everything boot first
    
    last_ok = False
    while not shutdown_flag:
        try:
            # Check if Flask responds
            r = requests.get(f"http://localhost:{FLASK_PORT}/api/queue", timeout=5)
            flask_ok = r.status_code == 200
        except:
            flask_ok = False
        
        try:
            # Check if Tunnel responds
            r = requests.get(TUNNEL_URL, timeout=10, headers={'Bypass-Tunnel-Reminder': 'true'})
            tunnel_ok = r.status_code == 200
        except:
            tunnel_ok = False
        
        engine_ok = 'engine' in processes and processes['engine'].poll() is None
        
        all_ok = flask_ok and tunnel_ok and engine_ok
        
        status = {
            'flask': '✅' if flask_ok else '❌',
            'tunnel': '✅' if tunnel_ok else '❌',
            'engine': '✅' if engine_ok else '❌'
        }
        
        if all_ok and not last_ok:
            msg = f"🟢 DJ AGENT FULLY ONLINE!\n📱 {TUNNEL_URL}\nFlask:{status['flask']} Tunnel:{status['tunnel']} Engine:{status['engine']}"
            log("✅", msg)
            send_notification(msg)
            save_status('ONLINE')
        elif not all_ok and last_ok:
            msg = f"🔴 DJ AGENT DEGRADED!\nFlask:{status['flask']} Tunnel:{status['tunnel']} Engine:{status['engine']}"
            log("❌", msg)
            send_notification(msg)
            save_status('DEGRADED')
        
        last_ok = all_ok
        time.sleep(HEALTH_CHECK_INTERVAL)

# ============== GRACEFUL SHUTDOWN ==============

def shutdown_handler(signum, frame):
    global shutdown_flag
    log("🛑", "Shutdown signal received! Killing all processes...")
    shutdown_flag = True
    
    for name, proc in processes.items():
        try:
            proc.terminate()
            proc.wait(timeout=5)
            log("🛑", f"Killed {name}")
        except:
            proc.kill()
    
    send_notification("🛑 DJ Agent shut down.")
    save_status('OFFLINE')
    sys.exit(0)

# ============== MAIN ==============

def main():
    global shutdown_flag
    
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    log("🚀", "=" * 50)
    log("🚀", "   DJ AGENT MASTER BOOT SEQUENCE")
    log("🚀", "=" * 50)
    log("📱", f"Public URL: {TUNNEL_URL}")
    log("📱", f"Notifications: ntfy.sh/{NTFY_TOPIC}")
    log("🚀", "=" * 50)
    
    save_status('BOOTING')
    send_notification(f"🚀 DJ Agent booting...\n📱 {TUNNEL_URL}")
    
    # Launch all services as daemon threads
    threads = [
        threading.Thread(target=run_flask, daemon=True, name="Flask"),
        threading.Thread(target=run_tunnel, daemon=True, name="Tunnel"),
        threading.Thread(target=run_transition_engine, daemon=True, name="Engine"),
        threading.Thread(target=run_health_monitor, daemon=True, name="Monitor"),
    ]
    
    for t in threads:
        t.start()
        log("🧵", f"Started thread: {t.name}")
        time.sleep(2)  # Stagger startup
    
    # Keep main thread alive
    log("✅", "All systems launched! Running forever until Ctrl+C...")
    
    while not shutdown_flag:
        time.sleep(1)

if __name__ == "__main__":
    main()
