import os
import json
import librosa
import numpy as np

class VocalAnalyzer:
    def __init__(self, config):
        self.config = config
        self.phoneme_dir = config['paths']['phonemes']
        os.makedirs(self.phoneme_dir, exist_ok=True)

    def analyze(self, vocals_path, lyrics_data, song_id):
        """
        Analyze vocal track and match words to timestamps
        Returns phoneme data for word index
        """
        cache_path = os.path.join(
            self.phoneme_dir, f"{song_id}_phonemes.json"
        )
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)

        if not vocals_path or not os.path.exists(vocals_path):
            return None

        timed_words = lyrics_data.get('timed_words', [])
        if not timed_words:
            return None

        phoneme_data = []
        y, sr = librosa.load(vocals_path, sr=22050)

        for word_entry in timed_words:
            word = word_entry.get('word', '').strip().lower()
            start = word_entry.get('start', 0)
            end = word_entry.get('end', start + 0.3)

            if not word or len(word) < 2:
                continue

            # Extract word audio segment
            start_sample = int(start * sr)
            end_sample = int(end * sr)
            word_audio = y[start_sample:end_sample]

            if len(word_audio) < 100:
                continue

            # Calculate word clarity (RMS energy)
            clarity = float(np.sqrt(np.mean(word_audio ** 2)))

            phoneme_data.append({
                'word': word,
                'start': start,
                'end': end,
                'clarity': clarity,
                'duration': end - start
            })

        result = {
            'song_id': song_id,
            'word_count': len(phoneme_data),
            'words': phoneme_data
        }

        with open(cache_path, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result
