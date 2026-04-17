import os
import time
import yaml
import json
import sys

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from analysis.audio_analyzer import AudioAnalyzer

class LocalAudioAgent:
    """
    LOCAL AUDIO AGENT - Handles heavy compute audio analysis.
    No LLM/Gemini credits needed.
    """
    def __init__(self):
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        self.analyzer = AudioAnalyzer(self.config)
        self.cache_dir = self.config['paths']['audio_cache']
        self.meta_dir = 'data/metadata'
        os.makedirs(self.meta_dir, exist_ok=True)

    def scan_and_analyze(self):
        print("🎵 [LOCAL AUDIO AGENT] Scanning for new music...")
        while True:
            files = [f for f in os.listdir(self.cache_dir) if f.endswith('.mp3')]
            for f in files:
                song_id = f.replace('.mp3', '')
                meta_path = os.path.join(self.meta_dir, f"{song_id}.json")
                
                if not os.path.exists(meta_path):
                    print(f"🎸 Analyzing: {f}")
                    try:
                        audio_path = os.path.join(self.cache_dir, f)
                        analysis = self.analyzer.analyze_track(audio_path, song_id)
                        
                        with open(meta_path, 'w') as out:
                            json.dump(analysis, out)
                        print(f"✅ Metadata saved for {song_id}")
                    except Exception as e:
                        print(f"❌ Analysis failed: {e}")
                
            time.sleep(60) # Scan every minute

if __name__ == "__main__":
    agent = LocalAudioAgent()
    agent.scan_and_analyze()
