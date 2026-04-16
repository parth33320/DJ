import os
import json
import numpy as np
from langdetect import detect
try:
    import pronouncing
except:
    pronouncing = None
from difflib import SequenceMatcher

class WordplayAgent:
    def __init__(self, config):
        self.config = config
        self.word_index_dir = config['paths']['word_index']
        self.phoneme_dir = config['paths']['phonemes']
        self.stems_dir = config['paths']['stems']
        self.word_index = {}
        self.same_language_bias = config['transitions'].get(
            'same_language_bias', 0.3
        )
        os.makedirs(self.word_index_dir, exist_ok=True)
        os.makedirs(self.phoneme_dir, exist_ok=True)
        self._load_word_index()

    def _load_word_index(self):
        index_path = os.path.join(self.word_index_dir, 'master_index.json')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                self.word_index = json.load(f)
            print(f"✅ Loaded word index: {len(self.word_index)} words")

    def _save_word_index(self):
        index_path = os.path.join(self.word_index_dir, 'master_index.json')
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(self.word_index, f, indent=2, ensure_ascii=False)

    def build_word_index(self, metadata_cache):
        """
        Build cross-song word/phoneme index from all songs
        Finds words that appear in multiple songs for wordplay transitions
        """
        print("\n🗂️  Building word index...")
        self.word_index = {}

        for song_id, analysis in metadata_cache.items():
            lyrics_data = analysis.get('lyrics')
            if not lyrics_data:
                continue

            timed_words = lyrics_data.get('timed_words', [])
            language = lyrics_data.get('language', 'unknown')

            for word_entry in timed_words:
                word = word_entry['word'].lower().strip()
                word = ''.join(c for c in word if c.isalpha())

                if len(word) < 3:
                    continue

                # Get phoneme representation
                phonemes = self._get_phonemes(word, language)

                if word not in self.word_index:
                    self.word_index[word] = []

                # Check if we have the vocal stem clip
                vocals_stem = os.path.join(
                    self.stems_dir, song_id, 'vocals.wav'
                )

                entry = {
                    'song_id': song_id,
                    'timestamp': word_entry.get('start', 0),
                    'end_time': word_entry.get('end', 0),
                    'language': language,
                    'phonemes': phonemes,
                    'vocals_stem': vocals_stem if os.path.exists(
                        vocals_stem
                    ) else None
                }

                self.word_index[word].append(entry)

        # Build phoneme similarity index for cross-language matching
        self._build_phoneme_similarity_index()

        self._save_word_index()
        print(f"✅ Word index built: {len(self.word_index)} unique words")

    def _get_phonemes(self, word, language):
        """Get phoneme representation of a word"""
        # Try English phoneme lookup first
        phones = pronouncing.phones_for_word(word)
        if phones:
            return phones[0]

        # For non-English: approximate using character mapping
        # This is a simplified cross-language phoneme approximation
        phoneme_map = {
            'a': 'AA', 'e': 'EH', 'i': 'IY', 'o': 'OW', 'u': 'UW',
            'b': 'B', 'c': 'K', 'd': 'D', 'f': 'F', 'g': 'G',
            'h': 'HH', 'j': 'JH', 'k': 'K', 'l': 'L', 'm': 'M',
            'n': 'N', 'p': 'P', 'q': 'K', 'r': 'R', 's': 'S',
            't': 'T', 'v': 'V', 'w': 'W', 'x': 'K S', 'y': 'Y',
            'z': 'Z'
        }
        return ' '.join(phoneme_map.get(c, c.upper()) for c in word.lower())

    def _build_phoneme_similarity_index(self):
        """
        Find phonetically similar words across languages
        e.g. 'daddy' (English) ≈ 'dadi' (Hindi)
        """
        phoneme_index_path = os.path.join(
            self.phoneme_dir, 'similarity_index.json'
        )

        similarity_pairs = []
        words = list(self.word_index.keys())

        print("🔤 Computing phoneme similarities...")
        for i, word_a in enumerate(words):
            entries_a = self.word_index[word_a]
            if not entries_a:
                continue

            phoneme_a = entries_a[0].get('phonemes', '')

            for word_b in words[i+1:]:
                entries_b = self.word_index[word_b]
                if not entries_b:
                    continue

                phoneme_b = entries_b[0].get('phonemes', '')

                # Skip if same word
                if word_a == word_b:
                    continue

                # Calculate phoneme similarity
                sim = self._phoneme_similarity(phoneme_a, phoneme_b)

                if sim > 0.75:
                    similarity_pairs.append({
                        'word_a': word_a,
                        'word_b': word_b,
                        'similarity': sim,
                        'phoneme_a': phoneme_a,
                        'phoneme_b': phoneme_b
                    })

        with open(phoneme_index_path, 'w', encoding='utf-8') as f:
            json.dump(similarity_pairs, f, indent=2)

        print(f"✅ Found {len(similarity_pairs)} phoneme-similar word pairs")

    def _phoneme_similarity(self, phoneme_a, phoneme_b):
        """Calculate similarity between two phoneme strings"""
        return SequenceMatcher(None, phoneme_a, phoneme_b).ratio()

    def find_connection(self, current_analysis, next_analysis):
        """
        Find wordplay connection between two songs
        Returns best word match or None
        """
        cur_id = current_analysis['song_id']
        nxt_id = next_analysis['song_id']

        cur_language = current_analysis.get('lyrics', {}).get(
            'language', 'unknown'
        ) if current_analysis.get('lyrics') else 'unknown'

        nxt_language = next_analysis.get('lyrics', {}).get(
            'language', 'unknown'
        ) if next_analysis.get('lyrics') else 'unknown'

        best_match = None
        best_score = 0

        # Search word index for words in both songs
        for word, entries in self.word_index.items():
            cur_entries = [e for e in entries if e['song_id'] == cur_id]
            nxt_entries = [e for e in entries if e['song_id'] == nxt_id]

            if cur_entries and nxt_entries:
                # Exact word match found!
                score = 1.0

                # Boost score for same language
                if cur_language == nxt_language:
                    score += self.same_language_bias

                if score > best_score:
                    best_score = score
                    best_match = {
                        'type': 'exact',
                        'word': word,
                        'score': score,
                        'cur_entry': cur_entries[-1],  # Use last occurrence
                        'nxt_entry': nxt_entries[0],   # Use first occurrence
                        'transition_time': cur_entries[-1]['timestamp'],
                        'word_time_b': nxt_entries[0]['timestamp'],
                        'word_clip_a': self._extract_word_clip(
                            cur_entries[-1]
                        ),
                        'word_repeats': 2,
                        'languages': f"{cur_language} → {nxt_language}"
                    }

        # If no exact match, try phoneme similarity
        if not best_match:
            best_match = self._find_phoneme_match(
                cur_id, nxt_id, cur_language, nxt_language
            )

        return best_match

    def _find_phoneme_match(self, cur_id, nxt_id, cur_lang, nxt_lang):
        """Find phonetically similar words across songs"""
        phoneme_index_path = os.path.join(
            self.phoneme_dir, 'similarity_index.json'
        )

        if not os.path.exists(phoneme_index_path):
            return None

        with open(phoneme_index_path, 'r') as f:
            similarity_pairs = json.load(f)

        best_match = None
        best_score = 0

        for pair in similarity_pairs:
            word_a = pair['word_a']
            word_b = pair['word_b']
            sim = pair['similarity']

            # Check if word_a is in current song and word_b in next song
            entries_a_cur = [
                e for e in self.word_index.get(word_a, [])
                if e['song_id'] == cur_id
            ]
            entries_b_nxt = [
                e for e in self.word_index.get(word_b, [])
                if e['song_id'] == nxt_id
            ]

            # Also check reverse
            entries_b_cur = [
                e for e in self.word_index.get(word_b, [])
                if e['song_id'] == cur_id
            ]
            entries_a_nxt = [
                e for e in self.word_index.get(word_a, [])
                if e['song_id'] == nxt_id
            ]

            match_found = False
            cur_entry = None
            nxt_entry = None
            matched_words = (word_a, word_b)

            if entries_a_cur and entries_b_nxt:
                cur_entry = entries_a_cur[-1]
                nxt_entry = entries_b_nxt[0]
                match_found = True
            elif entries_b_cur and entries_a_nxt:
                cur_entry = entries_b_cur[-1]
                nxt_entry = entries_a_nxt[0]
                matched_words = (word_b, word_a)
                match_found = True

            if match_found:
                score = sim
                if cur_lang == nxt_lang:
                    score += self.same_language_bias

                if score > best_score:
                    best_score = score
                    best_match = {
                        'type': 'phoneme',
                        'word_a': matched_words[0],
                        'word_b': matched_words[1],
                        'score': score,
                        'similarity': sim,
                        'cur_entry': cur_entry,
                        'nxt_entry': nxt_entry,
                        'transition_time': cur_entry['timestamp'],
                        'word_time_b': nxt_entry['timestamp'],
                        'word_clip_a': self._extract_word_clip(cur_entry),
                        'word_repeats': 2,
                        'languages': f"{cur_lang} → {nxt_lang}"
                    }

        return best_match if best_score > 0.75 else None

    def _extract_word_clip(self, word_entry):
        """
        Extract just the word audio from vocals stem
        Returns path to clipped audio file
        """
        import librosa
        import soundfile as sf

        vocals_path = word_entry.get('vocals_stem')
        if not vocals_path or not os.path.exists(vocals_path):
            return None

        start = word_entry.get('timestamp', 0)
        end = word_entry.get('end_time', start + 0.5)

        # Add small padding
        start = max(0, start - 0.05)
        end = end + 0.05

        clip_path = os.path.join(
            self.phoneme_dir,
            f"{word_entry['song_id']}_{word_entry['word'] if 'word' in word_entry else 'word'}_{start:.2f}.wav"
        )

        if os.path.exists(clip_path):
            return clip_path

        try:
            y, sr = librosa.load(vocals_path, sr=44100,
                                  offset=start, duration=end-start)
            sf.write(clip_path, y, sr)
            return clip_path
        except Exception as e:
            print(f"❌ Word clip extraction failed: {e}")
            return None
