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
    Now optimized for organized project structure.
    """
    def __init__(self):
        self.swarm_base = os.path.join("ai_brain", "local_swarm")
        self.agents = {
            "LOGIC": "local_logic_agent.py",
            "HEALING": "local_healing_agent.py",
            "PREPROCESS": "local_preprocessing_agent.py",
            "SELENIUM": "selenium_agent.py",
            "UI_TESTER": "local_ui_agent.py",
            "GIT_SYNC": "local_git_agent.py",
            "APPROVAL": "local_approval_agent.py"
        }
        self.processes = {}

    def start_swarm(self):
        print("🛸 [MASTER AGENT] Spawning The Antigravity Swarm...")
        print("Goal: Zero Gemini Credit Usage for routine operations.")
        print("="*60)

        for name, script_name in self.agents.items():
            script_path = os.path.join(self.swarm_base, script_name)
            # Some might still be in root for now, check both
            if not os.path.exists(script_path):
                script_path = script_name
                
            if os.path.exists(script_path):
                print(f"🚀 Launching {name} Agent ({script_path})...")
                p = subprocess.Popen([sys.executable, script_path])
                self.processes[name] = { "proc": p, "path": script_path }
            else:
                print(f"⚠️ [WARNING] {script_name} NOT FOUND in swarm or root. Skipping {name}.")

        print("="*60)
        print("✅ SWARM ACTIVE. Monitoring for crashes...")
        
        try:
            while True:
                for name, data in self.processes.items():
                    if data["proc"].poll() is not None:
                        print(f"🚨 [CRASH] {name} Agent died! Restarting...")
                        self.processes[name]["proc"] = subprocess.Popen([sys.executable, data["path"]])
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n⏹️ Terminating Swarm...")
            for name, data in self.processes.items():
                data["proc"].terminate()
            print("👋 Swarm offline.")

if __name__ == "__main__":
    master = AntigravityMasterAgent()
    master.start_swarm()
