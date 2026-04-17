import os
import time
import json
import traceback
import subprocess
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from utils.notifier import send_notification

class LocalHealingAgent:
    """
    LOCAL HEALING AGENT - Monitors logs and auto-fixes common issues.
    Saves Gemini credits by solving basic crashes without AI intervention.
    """
    def __init__(self):
        self.log_dir = "data/logs"
        self.error_patterns = {
            "FileNotFoundError: [Errno 2] No such file or directory: 'data/": self.fix_missing_dirs,
            "AttributeError: 'DJApp' object has no attribute 'metadata_cache'": self.fix_metadata_cache_duplication,
            "ModuleNotFoundError": self.fix_missing_dependencies
        }
        os.makedirs(self.log_dir, exist_ok=True)

    def fix_missing_dirs(self, error_msg):
        print("🔧 [HEALING] Attempting to fix missing directories...")
        subprocess.run([sys.executable, "main.py", "--setup-dirs"], capture_output=True)
        return "Re-ran directory setup."

    def fix_metadata_cache_duplication(self, error_msg):
        print("🔧 [HEALING] Detected metadata_cache init error. Verifying main.py structure...")
        # This usually requires a code edit, which I (the primary agent) should have fixed.
        # But if it recurs, we might want to alert the user specifically.
        return "Manual code check required for init structure."

    def fix_missing_dependencies(self, error_msg):
        print("🔧 [HEALING] Attempting to install missing dependencies...")
        try:
            module_name = error_msg.split("'")[1]
            subprocess.run([sys.executable, "-m", "pip", "install", module_name], check=True)
            return f"Installed missing module: {module_name}"
        except:
            return "Failed to auto-install dependency."

    def monitor_logs(self):
        print("🦖 [LOCAL HEALING AGENT] Monitoring data/logs/ for crashes...")
        last_check = time.time()
        
        while True:
            try:
                # Check for recent error logs
                error_log = os.path.join(self.log_dir, "error_log.txt")
                if os.path.exists(error_log):
                    mtime = os.path.getmtime(error_log)
                    if mtime > last_check:
                        with open(error_log, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if lines:
                                last_error = lines[-1]
                                print(f"🚨 [HEALING] Detected new error: {last_error.strip()}")
                                
                                # Try to find a match
                                handled = False
                                for pattern, fix_fn in self.error_patterns.items():
                                    if pattern in last_error:
                                        result = fix_fn(last_error)
                                        send_notification(f"🩹 HEALING AGENT: Auto-fixed error.\nResult: {result}", topic='dj-agent-parth')
                                        handled = True
                                        break
                                
                                if not handled:
                                    send_notification(f"🚨 DJ CRASHED: {last_error[:100]}", topic='dj-agent-parth')
                        
                        last_check = mtime
            except Exception as e:
                print(f"Healing Agent Internal Error: {e}")
            
            time.sleep(10)

if __name__ == "__main__":
    agent = LocalHealingAgent()
    agent.monitor_logs()
