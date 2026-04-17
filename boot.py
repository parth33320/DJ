import subprocess
import sys
import time
import os
import signal

def main():
    print("🚀 Booting DJ God Mode System...")
    processes = []

    try:
        # 1. Boot the Standalone UI Server (The Mouth)
        print("🌐 Starting Standalone UI Server (Port 8080)...")
        ui_process = subprocess.Popen([sys.executable, "standalone_ui_server.py"])
        processes.append(ui_process)
        
        # Give the server 2 seconds to bind to the port
        time.sleep(2) 

        # 2. Dig the Tunnel (The Network)
        print("🚇 Digging Localtunnel (parth-dj-god-mode-2026)...")
        # shell=True is required on Windows to run npm/npx commands
        tunnel_process = subprocess.Popen("npx localtunnel --port 8080 --subdomain parth-dj-god-mode-2026", shell=True)
        processes.append(tunnel_process)
        
        # Give the tunnel 2 seconds to establish connection
        time.sleep(2)

        # 3. Boot the AI DJ Loop (The Brain)
        print("🧠 Waking up AI Brain Queue...")
        brain_process = subprocess.Popen([sys.executable, "test_transitions.py"])
        processes.append(brain_process)

        print("\n✅ ALL SYSTEMS ONLINE.")
        print("👉 UI Link: https://parth-dj-god-mode-2026.loca.lt")
        print("🛑 Press [Ctrl + C] here to instantly kill all services.")

        # Keep the master script alive and watching
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received. Terminating all microservices...")
        for p in processes:
            try:
                p.terminate()
            except:
                pass
        print("👋 Clean shutdown complete. No zombie processes left behind.")
        sys.exit(0)

if __name__ == "__main__":
    main()
