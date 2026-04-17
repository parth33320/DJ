import sys, os, json, time, random, yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

KB_FILE = 'data/logs/dj_knowledge_base.json'
COOKIES = 'data/yt_cookies.txt'

class TransitionRecipe(BaseModel):
    technique_name: str; suitable_for: str; steps: list; parameters: dict

def load_json_safe(fp, default):
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_json_safe(fp, data):
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

class KnowledgeIngestionAgent:
    def __init__(self):
        self.llm = ChatOllama(model="deepseek-r1:8b", temperature=0.1).with_structured_output(TransitionRecipe)

    # 🎯 NEW: SNIPER MODE FOR REMEDIATION
    def run_targeted_search(self, query, technique):
        print(f"\n🚨 [KNOWLEDGE AGENT] TARGETED REMEDIATION: Searching YouTube for '{query}'...")
        ydl_opts = {'extract_flat': True, 'quiet': True, 'default_search': 'ytsearch3'}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch3:{query}", download=False)
            entries = info.get('entries', [])
            
            for entry in entries:
                if not entry: continue
                try:
                    ts = YouTubeTranscriptApi.get_transcript(entry['id'], cookies=COOKIES if os.path.exists(COOKIES) else None)
                    text = " ".join([t['text'] for t in ts])
                    
                    print(f"📚 Found transcript for {entry['title']}! Brain extracting recipe...")
                    recipe = self.llm.invoke([HumanMessage(content=f"Extract step-by-step DJ transition recipe for {technique} from this text. Focus on audio engineering steps: {text[:4000]}")])
                    
                    recipe_dump = recipe.model_dump()
                    
                    # 1. Save specifically for immediate LLM injection
                    save_json_safe(f"data/knowledge/{technique.lower()}_recipe.json", recipe_dump)
                    
                    # 2. Add to general knowledge base
                    self._save(recipe_dump, entry['id'])
                    
                    print(f"✅ [KNOWLEDGE AGENT] Fix for {technique} learned and saved!\n")
                    return # Stop after finding one good tutorial
                except Exception as e:
                    print(f"  ⚠️ Skip video (no transcript/error): {e}")

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
        kb = load_json_safe(KB_FILE, [])
        existing_index = next((i for i, item in enumerate(kb) if item.get('vid') == vid), None)
        data['vid'] = vid
        data['last_updated'] = time.time()
        
        if existing_index is not None: kb[existing_index] = data
        else: kb.append(data)
        save_json_safe(KB_FILE, kb)

if __name__ == "__main__":
    agent = KnowledgeIngestionAgent()
    # If called by test_transitions.py with args, use SNIPER MODE
    if len(sys.argv) > 2:
        agent.run_targeted_search(sys.argv[1], sys.argv[2])
    else:
        # Otherwise run mass harvest
        agent.run_mass_harvest([
            "https://www.youtube.com/playlist?list=PLm8kQbauoU-BmyP6EQJXtVLL0xHtfOb_2",
            "https://www.youtube.com/playlist?list=PLm8kQbauoU-Am4wnh58AFiObXjW_43IlT"
        ])
