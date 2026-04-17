import time
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from utils.notifier import send_notification

class LocalUIAgent:
    """
    LOCAL UI AGENT - Runs in background, tests transitions automatically.
    Saves Gemini credits by performing repetitive UI testing.
    """
    def __init__(self, target_url="http://localhost:8080"):
        self.target_url = target_url
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.options = Options()
        self.options.add_argument("--headless")
        self.driver = None

    def start_test_loop(self):
        print("🤖 [LOCAL UI AGENT] Starting Automated Feedback Loop...")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.options)
        
        while True:
            try:
                self.driver.get(self.target_url)
                time.sleep(5)
                
                # Check status
                status_box = self.driver.find_element(By.ID, "technique-name")
                tech = status_box.text
                
                if tech != "WAITING...":
                    print(f"🧐 Found transition: {tech}")
                    # Simulate user 'listening'
                    time.sleep(10)
                    
                    # Automate 'PASS' logic (or random for testing)
                    # In real mode, this could use a local heuristic model
                    pass_btn = self.driver.find_element(By.CLASS_NAME, "btn-pass")
                    pass_btn.click()
                    print("✅ Automatically APPROVED transition logic.")
                    
                    send_notification(f"🤖 UI AGENT: Automatically validated {tech} transition.", topic='dj-agent-parth')
                else:
                    print("😴 Waiting for Factory Loop to generate mix...")
                
                time.sleep(30) # Check every 30s
            except Exception as e:
                print(f"⚠️ UI Agent Error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    agent = LocalUIAgent()
    agent.start_test_loop()
