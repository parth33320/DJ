import os
import time
import yaml
import sys
import traceback

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from utils.notifier import send_notification
from utils.drive_manager import DriveManager

class SeleniumAgent:
    def __init__(self):
        with open('config.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.mobile_ui_url = "http://localhost:8080"
        self.public_url = "https://parth-dj-god-mode-2026.loca.lt"
        
        # FIXED: Only keep valid URLs, ignore empty strings
        raw_links = self.config.get('colab', {}).get('links', [])
        self.colab_links = [url for url in raw_links if url.strip()]
        
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless") # Run in background
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = None
        self.last_update_time = 0
        self.routine_interval = 15 * 60 # 15 minutes
        self.critical_interval = 60      # 1 minute
        self.last_routine_time = 0
        
    def init_driver(self):
        # FIXED: Close old driver if it exists to stop memory leak 503s!
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
                
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.chrome_options)

    def check_mobile_ui(self):
        try:
            self.init_driver()
            self.driver.get(self.mobile_ui_url)
            time.sleep(2)
            
            status_text = "OFFLINE"
            try:
                outgoing = self.driver.find_element(By.ID, "outgoing-title").text
                incoming = self.driver.find_element(By.ID, "incoming-title").text
                status_text = f"RUNNING: {outgoing} -> {incoming}"
            except Exception:
                status_text = "UI LOADED BUT NO TASK"
                
            return status_text
        except Exception as e:
            return f"ERROR: {str(e)[:50]}"

    def check_fleet(self):
        try:
            dm = DriveManager(self.config)
            results = []
            # FIXED: Use config drive accounts instead of hardcoded 5
            accounts = self.config.get('storage', {}).get('drive_accounts', [])
            for acc_id in accounts:
                try:
                    service = dm.authenticate(acc_id)
                    in_id = dm.get_folder_id(service, 'COLAB_INPUT')
                    res_in = service.files().list(q=f"'{in_id}' in parents and trashed=false", fields='files(name)').execute()
                    inputs = len(res_in.get('files', []))
                    
                    out_id = dm.get_folder_id(service, 'COLAB_OUTPUT')
                    res_out = service.files().list(q=f"'{out_id}' in parents and trashed=false", fields='files(id, name)').execute()
                    outputs = len(res_out.get('files', []))
                    
                    results.append(f"{acc_id}: {inputs} In / {outputs} Out")
                except Exception:
                    results.append(f"{acc_id}: ERROR")
            return " | ".join(results) if results else "NO ACCOUNTS CONFIGURED"
        except Exception as e:
            return f"Fleet check failed: {str(e)[:50]}"

    def colab_keep_alive(self):
        if not self.colab_links:
            return "No Colab links active."
            
        reports = []
        for url in self.colab_links:
            try:
                self.init_driver()
                self.driver.get(url)
                time.sleep(5)
                
                found_action = False
                try:
                    selectors = [
                        "//colab-connect-button",
                        "//paper-button[@id='connect']",
                        "//*[contains(text(), 'Reconnect')]",
                        "//*[contains(text(), 'Connect')]"
                    ]
                    for s in selectors:
                        elements = self.driver.find_elements(By.XPATH, s)
                        if elements:
                            elements[0].click()
                            found_action = True
                            break
                            
                except Exception as e:
                    print(f"Colab button error: {e}")

                try:
                    cells = self.driver.find_elements(By.CSS_SELECTOR, "div.run-button-container")
                    for cell in cells:
                        if "running" not in cell.get_attribute("class"):
                            cell.click()
                            reports.append(f"▶️ TRIGGERED CELL on {url[:20]}...")
                            break 
                except Exception as e:
                    print(f"Colab cell error: {e}")
                    
                if found_action:
                    reports.append(f"🔗 CLICKED RECONNECT on {url[:20]}...")
                elif not any("TRIGGERED CELL" in r for r in reports):
                    reports.append(f"✅ Still Connected: {url[:20]}...")
                    
            except Exception as e:
                reports.append(f"❌ Failed {url[:20]}: {str(e)[:20]}")
                
        return "\n".join(reports)

    def start(self):
        print("🐙 [SELENIUM AGENT] High-frequency monitoring started...")
        while True:
            try:
                now = time.time()
                
                ui_status = self.check_mobile_ui()
                fleet_status = self.check_fleet()
                
                # FIXED: Actually call colab_keep_alive! You forgot it in original!
                colab_status = self.colab_keep_alive() 
                
                actions = []
                if "ERROR" in ui_status:
                    actions.append("Restart mobile_tester.py!")
                if "ERROR" in fleet_status:
                    actions.append("Check Google Drive credentials!")
                    
                if actions:
                    alert = f"🚨 IMMEDIATE ACTION REQUIRED\n\n" + "\n".join([f"- {a}" for a in actions])
                    if now - self.last_update_time > 600:
                        try:
                            send_notification(alert, topic='dj-agent-parth')
                        except:
                            pass
                        self.last_update_time = now
                
                if now - self.last_routine_time > self.routine_interval:
                    summary = f"🦖 15-MIN STATUS REPORT\n\n📱 UI: {ui_status}\n🚢 FLEET: {fleet_status}\n🧪 COLAB: {colab_status}\n"
                    summary += "\n✅ EVERYTHING SMOOTH." if not actions else f"\n🚨 STILL WAITING ON: {', '.join(actions)}"
                    try:
                        send_notification(summary, topic='dj-agent-parth')
                    except:
                        pass
                    self.last_routine_time = now
                    
                time.sleep(self.critical_interval)
                
            except Exception as e:
                print(f"Selenium Agent crash caught: {e}")
                time.sleep(30) # Prevent tight crash loops

if __name__ == "__main__":
    agent = SeleniumAgent()
    agent.start()
