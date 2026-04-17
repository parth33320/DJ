import os
import time
import yaml
import sys
import glob

# Configure UTF-8 for Windows 
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import librosa
from analysis.audio_analyzer import AudioAnalyzer

class LocalPreprocessingAgent:
    """
    LOCAL PREPROCESSING AGENT - Pre-analyzes audio files in the background.
    Saves Gemini credits by performing compute-heavy analysis locally 
    and preparing metadata caches before the user even starts the DJ.
    """
    def __init__(self):
        with open('config.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.library_dir = "data/library"
        self.metadata_dir = self.config['paths']['metadata']
        self.analyzer = AudioAnalyzer(self.config)
        
        os.makedirs(self.library_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)

    def run_pre_analysis(self):
        print("💿 [LOCAL PREPROCESSING] Scanning library for un-cached songs...")
        
        while True:
            audio_files = []
            for ext in ['*.mp3', '*.wav', '*.flac']:
                audio_files.extend(glob.glob(os.path.join(self.library_dir, ext)))
            
            for filepath in audio_files:
                song_id = os.path.splitext(os.path.basename(filepath))[0]
                meta_path = os.path.join(self.metadata_dir, f"{song_id}.json")
                
                if not os.path.exists(meta_path):
                    print(f"   📂 Pre-analyzing: {song_id}...")
                    try:
                        # Full analysis
                        analysis = self.analyzer.analyze_track(filepath, song_id)
                        # Metadata is saved by the analyzer
                        print(f"   ✅ Meta-cache ready for: {song_id}")
                    except Exception as e:
                        print(f"   ❌ Error analyzing {song_id}: {e}")
                
            time.sleep(60 * 5) # Check for new files every 5 minutes

if __name__ == "__main__":
    agent = LocalPreprocessingAgent()
    agent.run_pre_analysis()
