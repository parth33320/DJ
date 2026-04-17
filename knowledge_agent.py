import sys
import os
import json
import yt_dlp
import time
import random
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

# Configure UTF-8 for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

KB_FILE = 'data/logs/dj_knowledge_base.json'
PROCESSED_FILE = 'data/logs/processed_videos.json'

CROSSFADER_PLAYLISTS = [
    "https://www.youtube.com/watch?v=oJhNp8rug84&list=PLm8kQbauoU-BmyP6EQJXtVLL0xHtfOb_2",
    "https://www.youtube.com/watch?v=jMISAgNeaGY&list=PLm8kQbauoU-Am4wnh58AFiObXjW_43IlT",
    "https://www.youtube.com/watch?v=Fg_lB3jL4Wg&list=PLm8kQbauoU-D531U7oTMUHCyxG1afUxBI",
    "https://www.youtube.com/watch?v=n5di8dvYFh4&list=PLm8kQbauoU-CCaSZmwUDr8djxke-f5vUT",
    "https://www.youtube.com/watch?v=Pmljt_-Vc3I&list=PLm8kQbauoU-B7RSueT6rbX6_IO556brq0",
    "https://www.youtube.com/watch?v=878fFYpkrzQ&list=PLm8kQbauoU-AVavFOPHesN0hc2EB_LNF2",
    "https://www.youtube.com/watch?v=u2WJ3LFBle8&list=PLm8kQbauoU-AxaaU_VBS3Xh3QTDPoun41",
    "https://www.youtube.com/playlist?list=PLm8kQbauoU-DvElYYt6zzGchZ72eN2pIO",
    "https://www.youtube.com/watch?v=kqMef7vdQmQ&list=PLm8kQbauoU-Aafr2uE0YaAr8elUuDyZ2Z",
    "https://www.youtube.com/watch?v=apKkqQOsAsU&list=PLm8kQbauoU-AgaEuz2uPR8ExDE7VMUtHR",
    "https://www.youtube.com/watch?v=2-SsppdZlWg&list=PLm8kQbauoU-BS8jvC3VW9-V0V65Y32pcL",
    "https://www.youtube.com/watch?v=ufB4Kcmz2_Y&list=PLm8kQbauoU-BHw4hrLiTrEU5mz_683B-z"
]

class TransitionRecipe(BaseModel):
    technique_name: str = Field(description="Name of the transition (e.g., Echo Out, Bass Swap, Filter Sweep)")
    suitable_for: str = Field(description="When to use this (e.g., matching BPM, genre change, drop swap)")
    steps: list[str] = Field(description="Step-by-step instructions. Be specific with beats and phrasing.")
    parameters: dict = Field(description="Specific knob values, FX timings (e.g. 1/2 beat echo), and EQ moves")

class KnowledgeIngestionAgent:
    def __init__(self, model_name="deepseek-r1:8b"):
        print(f"🧠 Booting Mass Knowledge Harvester ({model_name})...")
        try:
            self.llm = ChatOllama(model=model_name, temperature=0.1).with_structured_output(TransitionRecipe)
        except Exception as e:
            print(f"❌ Failed to connect to Ollama: {e}")
            sys.exit(1)
            
        os.makedirs(os.path.dirname(KB_FILE), exist_ok=True)
        self.processed_videos = self._load_processed()

    def _load_processed(self):
        if os.path.exists(PROCESSED_FILE):
            try:
                with open(PROCESSED_FILE, 'r') as f:
                    return set(json.load(f))
            except:
                pass
        return set()

    def _save_processed(self, video_id):
        self.processed_videos.add(video_id)
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(list(self.processed_videos), f)

    def get_videos_from_playlists(self):
        """Extract all unique video IDs from the provided playlists"""
        print(f"📡 Extracting video IDs from {len(CROSSFADER_PLAYLISTS)} playlists...")
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True
        }
        
        all_videos = {}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in CROSSFADER_PLAYLISTS:
                try:
                    info = ydl.extract_info(url, download=False)
                    for entry in info.get('entries', []):
                        if entry:
                            v_id = entry.get('id')
                            if v_id and v_id not in self.processed_videos:
                                all_videos[v_id] = entry.get('title', 'Unknown Title')
                except Exception as e:
                    print(f"⚠️ Could not parse playlist {url}: {e}")
        
        print(f"✅ Found {len(all_videos)} unprocessed videos.")
        return all_videos

    def fetch_transcript(self, video_id):
        """Pulls text. Uses Cookies and Sleep to evade IP bans."""
        try:
            # 🛡️ STEALTH MODE 1: Random delay so we don't look like a machine gun
            sleep_time = random.uniform(3.0, 7.0)
            print(f"   ⏱️ Sleeping {sleep_time:.1f}s to evade YouTube bot detection...")
            time.sleep(sleep_time)

            # 🛡️ STEALTH MODE 2: Inject Netscape cookies to prove we are human
            cookie_path = 'data/yt_cookies.txt'
            
            # Check if cookie exists and use it, otherwise try without
            if os.path.exists(cookie_path):
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id, cookies=cookie_path)
            else:
                print("   ⚠️ WARNING: yt_cookies.txt not found. Running naked (High risk of IP ban)...")
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
            
            full_text = " ".join([t['text'] for t in transcript_data])
            
            # THE "NO TALKING" FILTER
            words = full_text.split()
            if len(words) < 100:
                print(f"   ⏩ Skipping: Not enough talking ({len(words)} words).")
                return None
                
            if full_text.count("[Music]") > (len(words) * 0.1):
                print(f"   ⏩ Skipping: Mostly music playback, not a tutorial.")
                return None
                
            return full_text
        except (TranscriptsDisabled, NoTranscriptFound):
            print(f"   ⏩ Skipping: No captions available.")
            return None
        except Exception as e:
            print(f"   ⚠️ Transcript error: {e}")
            return None

    def process_and_save(self, video_id, title):
        print(f"\n🔪 Harvesting: {title} ({video_id})")
        text = self.fetch_transcript(video_id)
        
        if not text:
            self._save_processed(video_id) # Mark as done so we don't try again
            return

        print("   🧠 Asking DeepSeek to extract DJ Recipe...")
        prompt = f"""
        You are an expert DJ instructor analyzing a text transcript from a Crossfader DJ tutorial video.
        Determine if this video is actually teaching a transition technique. If it's just gear review or general talk, output dummy data.
        If it IS a transition tutorial, extract the precise, step-by-step technical recipe for an AI DJ system.
        Focus heavily on quantitative parameters: EQ cuts (e.g., kill the lows), filter sweeps, phrase alignments, and FX beat fractions (like 1/2 beat echo).
        
        Raw Transcript:
        {text}
        """
        
        try:
            recipe = self.llm.invoke([HumanMessage(content=prompt)])
            
            # Quick sanity check: If the LLM realized it wasn't a transition, skip saving
            if "dummy" in recipe.technique_name.lower() or "not a transition" in recipe.technique_name.lower():
                print("   ⏩ LLM determined this video does not contain a transition recipe. Skipping.")
            else:
                self._save_to_kb(recipe.model_dump(), f"https://youtube.com/watch?v={video_id}")
                
        except Exception as e:
            print(f"❌ LLM Parsing Failed: {e}")
            
        # Always mark as processed so we don't get stuck
        self._save_processed(video_id)

    def _save_to_kb(self, recipe_data, source_url):
        recipe_data['source'] = source_url
        kb = []
        if os.path.exists(KB_FILE):
            try:
                with open(KB_FILE, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
            except:
                pass
                
        kb.append(recipe_data)
        
        with open(KB_FILE, 'w', encoding='utf-8') as f:
            json.dump(kb, f, indent=4)
            
        print(f"   ✅ MASTER RECIPE ETCHED: {recipe_data['technique_name']}")

    def run_mass_harvest(self):
        videos = self.get_videos_from_playlists()
        total = len(videos)
        count = 1
        
        for v_id, title in videos.items():
            print(f"\n==============================================")
            print(f"PROGRESS: {count} / {total}")
            self.process_and_save(v_id, title)
            count += 1
            
        print("\n🎉 HARVEST COMPLETE. AI Brain is now full of Crossfader secrets.")

if __name__ == "__main__":
    agent = KnowledgeIngestionAgent()
    agent.run_mass_harvest()
