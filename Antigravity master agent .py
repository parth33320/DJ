"""
Antigravity Master Agent - Orchestrates all local agents
UPDATED v6: Wired in CLAUDE_APPLY agent for self-improving loop
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
        self.project_root = os.path.dirname(self.base_path)

        # Agent name → script path (relative to project root)
        self.agents = {
            # ── Core swarm agents ────────────────────────────────────────────
            "LLM_WORKER":    "ai_brain/local_swarm/local_llm_worker.py",
            "HEALING":       "ai_brain/local_swarm/local_healing_agent.py",
            "SELENIUM":      "ai_brain/local_swarm/selenium_agent.py",
            "UI_TESTER":     "ai_brain/local_swarm/local_ui_agent.py",
            "GIT_SYNC":      "ai_brain/local_swarm/local_git_agent.py",
            "APPROVAL":      "ai_brain/local_swarm/local_approval_agent.py",

            # ── NEW: Watches for Claude suggestions and applies them ──────────
            # Paired with scratch/claude_desktop_agent_v6.py which drives the loop
            "CLAUDE_APPLY":  "apply_claude_suggestions.py",
        }

        self.processes: dict[str, subprocess.Popen | None] = {}
        self.is_running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_agent(self, name: str, script: str) -> subprocess.Popen | None:
        """Start a single agent subprocess."""
        script_path = os.path.join(self.project_root, script)

        if not os.path.exists(script_path):
            print(f"⚠️  Agent script not found: {script_path}")
            return None

        try:
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.project_root,
            )
            print(f"✅ Started {name}: PID {process.pid}  ({script})")
            return process
        except Exception as e:
            print(f"❌ Failed to start {name}: {e}")
            return None

    def start_all(self):
        """Start all agents."""
        print("🚀 Antigravity Master starting all agents...")
        self.is_running = True

        for name, script in self.agents.items():
            self.processes[name] = self.start_agent(name, script)

        # Background monitor — auto-restarts crashed agents
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def stop_all(self):
        """Gracefully stop all agents."""
        print("🛑 Stopping all agents...")
        self.is_running = False

        for name, process in self.processes.items():
            if process and process.poll() is None:
                process.terminate()
                print(f"   Stopped {name}")

    # ── Monitor ───────────────────────────────────────────────────────────────

    def _monitor_loop(self):
        """Restart any agent that crashes."""
        while self.is_running:
            time.sleep(30)

            for name, process in list(self.processes.items()):
                if process is not None and process.poll() is not None:
                    print(f"⚠️  {name} crashed (exit {process.returncode})! Restarting...")
                    self.processes[name] = self.start_agent(name, self.agents[name])

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, str]:
        """Return a status dict for all managed agents."""
        status = {}
        for name, process in self.processes.items():
            if process is None:
                status[name] = "NOT_STARTED"
            elif process.poll() is None:
                status[name] = "RUNNING"
            else:
                status[name] = f"STOPPED (code {process.returncode})"
        return status


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    master = AntigravityMasterAgent()
    master.start_all()

    try:
        while True:
            time.sleep(60)
            print(f"\n📊 Agent Status: {master.get_status()}\n")
    except KeyboardInterrupt:
        master.stop_all()
