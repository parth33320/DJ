"""
Antigravity Master Agent - Orchestrates all local agents
FIXED: Removed dead Colab agents, points to LangGraph worker
"""

import os
import sys
import subprocess
import threading
import time

class AntigravityMasterAgent:
    """
    The Master that controls all local agents.
    Starts, monitors, and restarts agents as needed.
    """
    
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        
        # FIXED: Removed dead Colab agents, using LangGraph worker
        self.agents = {
            "LLM_WORKER": "local_llm_worker.py",      # LangGraph-based local AI
            "HEALING": "local_healing_agent.py",      # Self-healing monitor
            "SELENIUM": "selenium_agent.py",          # Browser automation (optional)
            "UI_TESTER": "local_ui_agent.py",         # UI testing
            "GIT_SYNC": "local_git_agent.py",         # Git operations
            "APPROVAL": "local_approval_agent.py",    # Human approval workflow
        }
        
        self.processes = {}
        self.is_running = False
    
    def start_agent(self, name, script):
        """Start a single agent"""
        script_path = os.path.join(self.base_path, script)
        
        if not os.path.exists(script_path):
            print(f"⚠️ Agent script not found: {script_path}")
            return None
        
        try:
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(self.base_path)  # Run from project root
            )
            print(f"✅ Started {name}: PID {process.pid}")
            return process
        except Exception as e:
            print(f"❌ Failed to start {name}: {e}")
            return None
    
    def start_all(self):
        """Start all agents"""
        print("🚀 Antigravity Master starting all agents...")
        self.is_running = True
        
        for name, script in self.agents.items():
            self.processes[name] = self.start_agent(name, script)
        
        # Start monitor thread
        threading.Thread(target=self._monitor_loop, daemon=True).start()
    
    def stop_all(self):
        """Stop all agents"""
        print("🛑 Stopping all agents...")
        self.is_running = False
        
        for name, process in self.processes.items():
            if process and process.poll() is None:
                process.terminate()
                print(f"   Stopped {name}")
    
    def _monitor_loop(self):
        """Monitor and restart crashed agents"""
        while self.is_running:
            time.sleep(30)
            
            for name, process in self.processes.items():
                if process and process.poll() is not None:
                    # Agent crashed, restart it
                    print(f"⚠️ {name} crashed! Restarting...")
                    self.processes[name] = self.start_agent(name, self.agents[name])
    
    def get_status(self):
        """Get status of all agents"""
        status = {}
        for name, process in self.processes.items():
            if process is None:
                status[name] = "NOT_STARTED"
            elif process.poll() is None:
                status[name] = "RUNNING"
            else:
                status[name] = f"STOPPED (code {process.returncode})"
        return status


if __name__ == "__main__":
    master = AntigravityMasterAgent()
    master.start_all()
    
    try:
        while True:
            time.sleep(60)
            print(f"📊 Agent Status: {master.get_status()}")
    except KeyboardInterrupt:
        master.stop_all()
