import os
import json
import time
import requests
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

class LocalLogicAgent:
    """
    LOCAL LOGIC AGENT - Uses local Ollama for code/logic tasks.
    Ensures zero Gemini credit usage for routine logic requests.
    """
    def __init__(self, model="llama3"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def ask_logic(self, prompt):
        print(f"🧠 [LOCAL LOGIC] Analyzing: {prompt[:50]}...")
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(self.url, json=payload)
            return response.json().get('response', '')
        except Exception as e:
            return f"Error connecting to Ollama: {e}"

    def run_task_loop(self):
        print("🐙 [LOCAL LOGIC AGENT] Listening for task file 'data/logs/logic_task.json'...")
        task_file = "data/logs/logic_task.json"
        while True:
            if os.path.exists(task_file):
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task = json.load(f)
                    
                    print(f"📝 New Task: {task.get('name')}")
                    result = self.ask_logic(task.get('prompt', ''))
                    
                    with open(task_file.replace('.json', '_result.json'), 'w', encoding='utf-8') as f:
                        json.dump({"result": result, "time": time.time()}, f)
                    
                    os.remove(task_file)
                    print("✅ Task complete.")
                except Exception as e:
                    print(f"❌ Task Error: {e}")
            
            time.sleep(5)

if __name__ == "__main__":
    agent = LocalLogicAgent()
    agent.run_task_loop()
