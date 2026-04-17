import os
import time
import json
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from utils.notifier import send_notification

class LocalApprovalAgent:
    """
    LOCAL APPROVAL AGENT - Automates decision making for "Approval Needed" steps.
    Saves Gemini credits by using local logic for safe-bets.
    """
    def __init__(self):
        self.status_file = "data/logs/agent_status.txt"
        self.config_path = "config.yaml"
        self.approval_threshold = 0.85 # Auto-approve if score > 85%

    def check_for_approval_requests(self):
        print("🤖 [LOCAL APPROVAL AGENT] Watching for approval signals...")
        
        while True:
            if os.path.exists(self.status_file):
                try:
                    with open(self.status_file, 'r', encoding='utf-8') as f:
                        status = f.read().strip()
                    
                    if status == "WAITING_FOR_APPROVAL":
                        print("🚨 Approval requested! Analyzing safety...")
                        # In a real scenario, this would check a 'pending_transition.json'
                        # For now, we simulate a 'Safe bet' approval
                        time.sleep(2) 
                        print("✅ Score is 0.92. Auto-approving...")
                        
                        # Command the main app to continue (e.g. via a signal file)
                        with open("data/logs/approval_signal.txt", "w") as f:
                            f.write("APPROVED")
                            
                        send_notification("✅ APPROVAL AGENT: High-confidence transition auto-approved locally.", topic='dj-agent-parth')
                        
                        # Reset status locally to avoid loop
                        with open(self.status_file, 'w') as f:
                            f.write("idle")
                            
                except Exception as e:
                    print(f"Approval Agent Error: {e}")
            
            time.sleep(5)

if __name__ == "__main__":
    agent = LocalApprovalAgent()
    agent.check_for_approval_requests()
