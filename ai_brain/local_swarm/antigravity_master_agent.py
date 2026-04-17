import subprocess
import time
import sys
import os

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

class AntigravityMasterAgent:
    """
    ANTIGRAVITY MASTER AGENT - THE SWARM CONTROLLER
    Spawns and monitors all sub-agents to maximize Gemini credit savings.
    One script to rule them all.
    """
    def __init__(self):
        self.agents = {
            "LOGIC": "local_logic_agent.py",
            "HEALING": "local_healing_agent.py",
            "PREPROCESS": "local_preprocessing_agent.py",
            "SELENIUM": "selenium_agent.py",
            "UI_TESTER": "local_ui_agent.py",
            "GIT_SYNC": "local_git_agent.py"
        }
        self.processes = {}

    def start_swarm(self):
        print("🛸 [MASTER AGENT] Spawning The Antigravity Swarm...")
        print("Goal: Zero Gemini Credit Usage for routine operations.")
        print("="*60)

        for name, script in self.agents.items():
            if os.path.exists(script):
                print(f"🚀 Launching {name} Agent ({script})...")
                # Using CREATE_NEW_CONSOLE on Windows to show separate windows
                # Or just keep them in background
                p = subprocess.Popen([sys.executable, script])
                self.processes[name] = p
            else:
                print(f"⚠️ [WARNING] {script} NOT FOUND. Skipping {name}.")

        print("="*60)
        print("✅ SWARM ACTIVE. Monitoring for crashes...")
        
        try:
            while True:
                for name, p in self.processes.items():
                    if p.poll() is not None:
                        print(f"🚨 [CRASH] {name} Agent died! Restarting...")
                        self.processes[name] = subprocess.Popen([sys.executable, self.agents[name]])
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n⏹️ Terminating Swarm...")
            for name, p in self.processes.items():
                p.terminate()
            print("👋 Swarm offline.")

if __name__ == "__main__":
    master = AntigravityMasterAgent()
    master.start_swarm()
