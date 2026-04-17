import subprocess
import time
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# =================================================================
# 🦖 LOCAL FLEET COMMANDER
# =================================================================
# Starts all local agents to save Gemini Credits.
# =================================================================

AGENTS = [
    "selenium_agent.py",
    "local_ui_agent.py",
    "local_audio_agent.py",
    "local_sync_agent.py",
    "local_git_agent.py",
    "local_logic_agent.py"
]

def start_fleet():
    print("🦖 FLEET COMMANDER: Launching Local Agents...")
    processes = []
    
    for agent in AGENTS:
        print(f"🚀 Launching {agent}...")
        p = subprocess.Popen([sys.executable, agent])
        processes.append(p)
        time.sleep(2) # Stagger start
    
    print("\n✅ FLEET IS ACTIVE. 🦖")
    print("Press Ctrl+C to stop all agents.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping Fleet...")
        for p in processes:
            p.terminate()
        print("🦖 Fleet resting.")

if __name__ == "__main__":
    start_fleet()
