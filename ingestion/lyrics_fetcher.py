import os
import json
import requests
from langdetect import detect
try:
    import whisper
except ImportError:
    whisper = None


class LyricsFetcher:
    def __init__(self, config):
        self.config = config
        self.lyrics_dir = config['paths']['lyrics']
        self.genius_token = os.getenv('GENIUS_API_TOKEN', '')
        self.whisper_model = None
        os.makedirs(self.lyrics_dir, exist_ok=True)

    def fetch(self, title, song_id, vocals_path=None):
        """Try Genius first, fall back to Whisper transcription"""
        cache_path = os.path.join(self.lyrics_dir, f"{song_id}.json")
        
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        lyrics_data = None
        
        # Try Genius API first
        if self.genius_token:
            lyrics_data = self._fetch_genius(title)
        
        # Fall back to Whisper
        if not lyrics_data and vocals_path and os.path.exists(vocals_path):
            lyrics_data = self._transcribe_whisper(vocals_path)
        
        if lyrics_data:
            # Detect language
            try:
                lyrics_data['language'] = detect(lyrics_data['text'])
            except:
                lyrics_data['language'] = 'unknown'
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(lyrics_data, f, indent=2, ensure_ascii=False)
        
        return lyrics_data

    def _fetch_genius(self, title):
        """Fetch from Genius API"""
        try:
            headers = {'Authorization': f'Bearer {self.genius_token}'}
            params = {'q': title}
            r = requests.get(
                'https://api.genius.com/search',
                headers=headers, params=params, timeout=10
            )
            data = r.json()
            hits = data.get('response', {}).get('hits', [])
            if hits:
                return {
                    'text': hits[0]['result'].get('full_title', ''),
                    'source': 'genius',
                    'timed': False
                }
        except Exception as e:
            print(f"Genius fetch failed: {e}")
        return None

    def _transcribe_whisper(self, vocals_path):
        """Transcribe vocals using Whisper AI"""
        if not self.whisper_model:
            print("📝 Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")
        
        try:
            result = self.whisper_model.transcribe(
                vocals_path,
                word_timestamps=True,
                task="transcribe"
            )
            
            # Extract timed words
            timed_words = []
            for segment in result.get('segments', []):
                for word in segment.get('words', []):
                    timed_words.append({
                        'word': word['word'].strip(),
                        'start': word['start'],
                        'end': word['end']
                    })
            
            return {
                'text': result['text'],
                'timed_words': timed_words,
                'language': result.get('language', 'unknown'),
                'source': 'whisper',
                'timed': True
            }
        except Exception as e:
            print(f"Whisper transcription failed: {e}")
            return None
