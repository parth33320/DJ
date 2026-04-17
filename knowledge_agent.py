import sys, os, json, time, random, yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

KB_FILE = 'data/logs/dj_knowledge_base.json'
COOKIES = 'data/yt_cookies.txt'

class TransitionRecipe(BaseModel):
    technique_name: str; suitable_for: str; steps: list; parameters: dict

class KnowledgeIngestionAgent:
    def __init__(self):
        self.llm = ChatOllama(model="deepseek-r1:8b", temperature=0.1).with_structured_output(TransitionRecipe)

    def run_mass_harvest(self, playlists):
        processed = set(load_json_safe('data/logs/processed_videos.json', []))
        with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
            for url in playlists:
                entries = ydl.extract_info(url, download=False).get('entries', [])
                for entry in entries:
                    if not entry or entry['id'] in processed: continue
                    print(f"🎬 Harvesting: {entry['title']}")
                    time.sleep(random.uniform(3, 7))
                    try:
                        ts = YouTubeTranscriptApi.get_transcript(entry['id'], cookies=COOKIES if os.path.exists(COOKIES) else None)
                        text = " ".join([t['text'] for t in ts])
                        if len(text.split()) > 100:
                            recipe = self.llm.invoke([HumanMessage(content=f"Extract DJ recipe from: {text}")])
                            self._save(recipe.model_dump(), entry['id'])
                    except Exception as e: print(f"  ⚠️ Error: {e}")
                    processed.add(entry['id']); save_json_safe('data/logs/processed_videos.json', list(processed))

    def _save(self, data, vid):
        kb = load_json_safe(KB_FILE, []); data['vid'] = vid; kb.append(data)
        save_json_safe(KB_FILE, kb)

def load_json_safe(fp, default):
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_json_safe(fp, data):
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

if __name__ == "__main__":
    KnowledgeIngestionAgent().run_mass_harvest([
        "https://www.youtube.com/playlist?list=PLm8kQbauoU-BmyP6EQJXtVLL0xHtfOb_2",
        "https://www.youtube.com/playlist?list=PLm8kQbauoU-Am4wnh58AFiObXjW_43IlT"
        # ... add rest of your links here
    ])
