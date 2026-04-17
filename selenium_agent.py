import os
import time
import yaml
import threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.notifier import send_notification
from utils.drive_manager import DriveManager

class SeleniumAgent:
    def __init__(self):
        with open('config.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.mobile_ui_url = "http://localhost:8080"
        self.public_url = "https://parth-dj-god-mode-2026.loca.lt"
        self.colab_links = self.config.get('colab', {}).get('links', [])
        
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless") # Run in background
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = None
        self.last_update_time = 0
        self.update_interval = 15 * 60 # 15 minutes
        
    def init_driver(self):
        if not self.driver:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)

    def check_mobile_ui(self):
        """Check if Mobile UI is responsive and what it is doing"""
        try:
            self.init_driver()
            self.driver.get(self.mobile_ui_url)
            time.sleep(2)
            
            status_text = "OFFLINE"
            # Try to find status or song title
            try:
                outgoing = self.driver.find_element(By.ID, "outgoing-title").text
                incoming = self.driver.find_element(By.ID, "incoming-title").text
                status_text = f"RUNNING: {outgoing} -> {incoming}"
            except:
                status_text = "UI LOADED BUT NO TASK"
                
            return status_text
        except Exception as e:
            return f"ERROR: {str(e)[:50]}"

    def check_fleet(self):
        """Check Google Drive for fleet activity"""
        try:
            dm = DriveManager(self.config)
            results = []
            for i in range(1, 6):
                acc_id = f'account_{i}'
                try:
                    service = dm.authenticate(acc_id)
                    in_id = dm.get_folder_id(service, 'COLAB_INPUT')
                    res_in = service.files().list(q=f"'{in_id}' in parents and trashed=false", fields='files(name)').execute()
                    inputs = len(res_in.get('files', []))
                    
                    out_id = dm.get_folder_id(service, 'COLAB_OUTPUT')
                    res_out = service.files().list(q=f"'{out_id}' in parents and trashed=false", fields='files(id, name)').execute()
                    outputs = len(res_out.get('files', []))
                    
                    results.append(f"{acc_id}: {inputs} In / {outputs} Out")
                except:
                    results.append(f"{acc_id}: ERROR")
            return " | ".join(results)
        except Exception as e:
            return f"Fleet check failed: {str(e)[:50]}"

    def colab_keep_alive(self):
        """Simple automation: Visit Colab links to try and keep them alive"""
        if not self.colab_links:
            return "No Colab links provided in config."
            
        reports = []
        for url in self.colab_links:
            try:
                self.init_driver()
                self.driver.get(url)
                # Wait for Colab to load
                time.sleep(5)
                # Look for 'Connect' button or similar if possible
                # This is hard in headless without login, but visiting helps
                reports.append(f"Visited {url[:30]}...")
            except:
                reports.append(f"Failed {url[:30]}")
        return "\n".join(reports)

    def run_cycle(self):
        print(f"[{time.strftime('%H:%M:%S')}] Selenium Agent running cycle...")
        
        ui_status = self.check_mobile_ui()
        fleet_status = self.check_fleet()
        keep_alive_report = self.colab_keep_alive()
        
        summary = f"🦖 15-MIN UPDATE\n\n"
        summary += f"📱 UI: {ui_status}\n"
        summary += f"🚢 FLEET: {fleet_status}\n"
        
        # Determine actions
        actions = []
        if "ERROR" in ui_status:
            actions.append("Restart mobile_tester.py!")
        if "ERROR" in fleet_status:
            actions.append("Check Google Drive credentials!")
        
        if not actions:
            summary += "\n✅ EVERYTHING SMOOTH. NO ACTION NEEDED."
        else:
            summary += f"\n🚨 ACTIONS NEEDED:\n" + "\n".join([f"- {a}" for a in actions])
            
        send_notification(summary, topic='dj-agent-parth')
        print(f"Summary sent to ntfy.")

    def start(self):
        while True:
            self.run_cycle()
            time.sleep(self.update_interval)

if __name__ == "__main__":
    agent = SeleniumAgent()
    agent.start()
