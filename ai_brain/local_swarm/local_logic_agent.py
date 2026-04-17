"""
Local Logic Agent - Runs on YOUR computer with Ollama
Uses Llama 3.2 or Gemma 2 for creative tasks WITHOUT cloud API costs!
"""

import os
import json
import requests
from typing import Optional

class LocalLogicAgent:
    """
    Uses Ollama to run local LLM for creative DJ tasks.
    FREE after initial model download!
    
    Install: 
    1. Download Ollama from ollama.ai
    2. Run: ollama pull llama3.2
    3. This agent will use it automatically!
    """
    
    def __init__(self, config):
        self.config = config
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = config.get('ai', {}).get('local_model', 'llama3.2')
        self.available = self._check_ollama()
    
    def _check_ollama(self):
        """Check if Ollama is running"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                print("✅ Ollama detected! Local AI ready.")
                return True
        except:
            pass
        print("⚠️ Ollama not running. Install from ollama.ai for free local AI!")
        return False
    
    def _query(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        """Query local Ollama model"""
        if not self.available:
            return None
        
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
        except Exception as e:
            print(f"⚠️ Ollama query failed: {e}")
        
        return None
    
    def find_wordplay_connection(self, lyrics_a: str, lyrics_b: str, title_a: str, title_b: str) -> Optional[dict]:
        """
        Find creative wordplay connection between two songs.
        This is where local AI shines - creative language tasks!
        """
        prompt = f"""You are a creative DJ finding wordplay connections between songs.

Song A: "{title_a}"
Lyrics snippet: {lyrics_a[:500]}

Song B: "{title_b}"  
Lyrics snippet: {lyrics_b[:500]}

Find a word, phrase, or sound that appears in BOTH songs that could create a smooth DJ transition.
Look for:
- Same words
- Rhyming words
- Similar sounds (phonetic matches)
- Thematic connections

Reply in JSON format only:
{{"found": true/false, "word_a": "word from song A", "word_b": "word from song B", "type": "exact/rhyme/phonetic/thematic", "explanation": "brief explanation"}}
"""
        
        result = self._query(prompt, max_tokens=150)
        
        if result:
            try:
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except:
                pass
        
        return None
    
    def suggest_creative_transition(self, song_a: dict, song_b: dict) -> Optional[str]:
        """
        Suggest a creative transition when standard rules don't work.
        """
        prompt = f"""You are a professional DJ. Suggest ONE creative transition technique.

Song A: {song_a.get('title', 'Unknown')}
- BPM: {song_a.get('bpm', 'Unknown')}
- Key: {song_a.get('camelot', 'Unknown')}
- Energy: {song_a.get('energy_mean', 'Unknown')}

Song B: {song_b.get('title', 'Unknown')}
- BPM: {song_b.get('bpm', 'Unknown')}
- Key: {song_b.get('camelot', 'Unknown')}
- Energy: {song_b.get('energy_mean', 'Unknown')}

Choose ONE technique from: beatmatch_crossfade, echo_out, filter_sweep, reverb_wash, spinback, cut_transition, loop_roll, stutter_glitch

Reply with just the technique name, nothing else.
"""
        
        result = self._query(prompt, max_tokens=20)
        
        if result:
            result = result.strip().lower().replace(' ', '_')
            valid = ['beatmatch_crossfade', 'echo_out', 'filter_sweep', 'reverb_wash', 
                     'spinback', 'cut_transition', 'loop_roll', 'stutter_glitch']
            if result in valid:
                return result
        
        return None
