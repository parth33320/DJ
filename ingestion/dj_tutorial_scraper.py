import yt_dlp
import os
import json
try:
    import whisper
except ImportError:
    whisper = None


class DJTutorialScraper:
    """
    Scrapes DJ tutorial channels to extract
    transition techniques for AI training
    """
    def __init__(self, config):
        self.config = config
        self.training_dir = config['paths']['training_data']
        os.makedirs(self.training_dir, exist_ok=True)
        self.whisper_model = None

    def scrape_all_channels(self):
        """Scrape all configured tutorial channels"""
        channels = self.config['youtube_channels']['tutorial_sources']
        all_data = []

        for channel in channels:
            print(f"\n📺 Scraping: {channel}")
            data = self.scrape_channel(channel)
            all_data.extend(data)

        # Save training data
        output_path = os.path.join(
            self.training_dir, 'tutorial_data.json'
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Scraped {len(all_data)} tutorials")
        return all_data

    def scrape_channel(self, channel_url, max_videos=20):
        """Scrape a single channel"""
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': max_videos,
        }

        videos = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            entries = info.get('entries', [])

            for entry in entries:
                if entry:
                    videos.append({
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'url': f"https://youtube.com/watch?v={entry.get('id')}",
                        'duration': entry.get('duration', 0)
                    })

        results = []
        for video in videos:
            # Skip very long videos (full sets)
            if video['duration'] and video['duration'] > 1800:
                continue

            transcript = self._transcribe_video(video)
            if transcript:
                techniques = self._extract_techniques(transcript)
                results.append({
                    'video_id': video['id'],
                    'title': video['title'],
                    'url': video['url'],
                    'transcript': transcript,
                    'techniques_mentioned': techniques
                })

        return results

    def _transcribe_video(self, video):
        """Download and transcribe a tutorial video"""
        if not self.whisper_model:
            print("   Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")

        audio_path = os.path.join(
            self.training_dir, f"tmp_{video['id']}.mp3"
        )

        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_path.replace('.mp3', '.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video['url']])

            result = self.whisper_model.transcribe(audio_path)
            return result['text']

        except Exception as e:
            print(f"   ❌ Transcription failed: {e}")
            return None
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def _extract_techniques(self, transcript):
        """Extract DJ technique mentions from transcript"""
        keywords = [
            'phrase', 'bar', 'beat', 'crossfade', 'beatmatch',
            'filter', 'echo', 'reverb', 'loop', 'roll', 'spinback',
            'scratch', 'key', 'camelot', 'harmonic', 'energy',
            'drop', 'build', 'breakdown', 'transition', 'mix in',
            'mix out', 'eq', 'high pass', 'low pass', 'acapella',
            'stems', 'vocal', 'intro', 'outro'
        ]

        found = {}
        lower_transcript = transcript.lower()

        for keyword in keywords:
            count = lower_transcript.count(keyword)
            if count > 0:
                found[keyword] = count

        return found
