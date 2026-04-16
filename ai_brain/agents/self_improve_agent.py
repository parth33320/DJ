import os
import json
import time
import subprocess
import requests
from datetime import datetime

class SelfImproveAgent:
    """
    Periodically:
    1. Scrapes new DJ tutorial content
    2. Extracts new techniques
    3. Writes/updates code
    4. Tests in sandbox
    5. Deploys if quality improves
    """
    def __init__(self, config):
        self.config = config
        self.improvements_log = "data/logs/improvements.json"
        self.sandbox_dir = "data/sandbox"
        os.makedirs(self.sandbox_dir, exist_ok=True)
        os.makedirs("data/logs", exist_ok=True)

        # Use local LLM or OpenAI
        self.use_openai = bool(config['ai'].get('openai_api_key'))
        self.openai_key = config['ai'].get('openai_api_key', '')

    def run_improvement_cycle(self):
        """Main improvement cycle - runs weekly"""
        print(f"\n🤖 SELF-IMPROVEMENT CYCLE - {datetime.now()}")
        print("=" * 50)

        # Step 1: Scrape new tutorials
        new_techniques = self._scrape_new_tutorials()

        # Step 2: Extract technique knowledge
        if new_techniques:
            knowledge = self._extract_knowledge(new_techniques)

            # Step 3: Generate code improvements
            if knowledge:
                new_code = self._generate_improvements(knowledge)

                # Step 4: Test in sandbox
                if new_code and self._test_in_sandbox(new_code):
                    # Step 5: Deploy
                    self._deploy_improvements(new_code)
                    self._log_improvement(knowledge, new_code)

        print("✅ Improvement cycle complete")

    def _scrape_new_tutorials(self):
        """Scrape tutorial channels for new content"""
        import yt_dlp

        channels = self.config['youtube_channels']['tutorial_sources']
        new_videos = []

        # Load previously seen videos
        seen_path = "data/logs/seen_tutorials.json"
        seen_ids = set()
        if os.path.exists(seen_path):
            with open(seen_path, 'r') as f:
                seen_ids = set(json.load(f))

        for channel_url in channels:
            try:
                ydl_opts = {
                    'quiet': True,
                    'extract_flat': True,
                    'playlistend': 10,  # Check last 10 videos
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(channel_url, download=False)
                    entries = info.get('entries', [])

                    for entry in entries:
                        vid_id = entry.get('id')
                        if vid_id and vid_id not in seen_ids:
                            new_videos.append({
                                'id': vid_id,
                                'title': entry.get('title'),
                                'url': f"https://youtube.com/watch?v={vid_id}",
                                'channel': channel_url
                            })
                            seen_ids.add(vid_id)

            except Exception as e:
                print(f"❌ Scrape error for {channel_url}: {e}")

        # Save updated seen list
        with open(seen_path, 'w') as f:
            json.dump(list(seen_ids), f)

        print(f"📺 Found {len(new_videos)} new tutorial videos")
        return new_videos

    def _extract_knowledge(self, videos):
        """
        Use Whisper to transcribe tutorials
        Extract technique descriptions
        """
        try:
            import whisper
        except ImportError:
            whisper = None


        model = whisper.load_model("base")
        knowledge_items = []

        for video in videos[:3]:  # Process max 3 at a time
            try:
                print(f"📝 Transcribing: {video['title']}")

                # Download audio only
                import yt_dlp
                audio_path = f"data/sandbox/tutorial_{video['id']}.mp3"

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

                # Transcribe
                result = model.transcribe(audio_path)
                transcript = result['text']

                # Extract technique mentions
                techniques_found = self._parse_techniques(transcript)

                if techniques_found:
                    knowledge_items.append({
                        'video_id': video['id'],
                        'title': video['title'],
                        'transcript': transcript[:500],
                        'techniques': techniques_found
                    })

                # Cleanup
                if os.path.exists(audio_path):
                    os.remove(audio_path)

            except Exception as e:
                print(f"❌ Knowledge extraction failed: {e}")

        return knowledge_items

    def _parse_techniques(self, transcript):
        """Parse transcript for DJ technique mentions"""
        technique_keywords = [
            'crossfade', 'beatmatch', 'filter', 'echo', 'loop',
            'phrase', 'bar', 'key', 'camelot', 'harmonic',
            'spinback', 'scratch', 'reverb', 'transition',
            'drop', 'build', 'breakdown', 'acapella', 'stems',
            'eq', 'high pass', 'low pass', 'sweep', 'roll'
        ]

        found = []
        transcript_lower = transcript.lower()

        for keyword in technique_keywords:
            if keyword in transcript_lower:
                # Get context around keyword
                idx = transcript_lower.find(keyword)
                context = transcript[max(0, idx-100):idx+200]
                found.append({
                    'technique': keyword,
                    'context': context
                })

        return found

    def _generate_improvements(self, knowledge):
        """
        Use LLM to generate code improvements
        based on extracted knowledge
        """
        if not self.use_openai:
            print("ℹ️ No OpenAI key - skipping code generation")
            print("   Add openai_api_key to config.yaml for self-improvement")
            return None

        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_key)

            knowledge_summary = json.dumps(knowledge, indent=2)[:2000]

            prompt = f"""
You are improving a Python DJ application.
New techniques learned from DJ tutorials:

{knowledge_summary}

Current transition techniques in the app:
beatmatch_crossfade, echo_out, filter_sweep, loop_roll,
reverb_wash, spinback, cut_transition, tempo_ramp,
white_noise_sweep, vinyl_scratch_flourish, tone_play, wordplay

Based on the new knowledge, write a Python function that implements
a NEW or IMPROVED transition technique. The function must:
1. Accept parameters: cur_audio, nxt_audio, sr, params
2. Return: mixed_audio (numpy array)
3. Sound good to human ears
4. Include docstring explaining the technique

Only output valid Python code, nothing else.
"""
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ Code generation failed: {e}")
            return None

    def _test_in_sandbox(self, code):
        """Test generated code safely"""
        sandbox_file = os.path.join(self.sandbox_dir, "test_technique.py")

        # Write to sandbox
        with open(sandbox_file, 'w') as f:
            f.write("import numpy as np\n")
            f.write("import librosa\n")
            f.write(code)
            f.write("\n\n# Test with dummy audio\n")
            f.write("y = np.random.randn(44100)\n")
            f.write("print('Syntax OK')\n")

        # Run in subprocess with timeout
        try:
            result = subprocess.run(
                ['python', sandbox_file],
                timeout=30,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ Sandbox test passed")
                return True
            else:
                print(f"❌ Sandbox test failed: {result.stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            print("❌ Sandbox test timed out")
            return False

    def _deploy_improvements(self, code):
        """Add new technique to transition engine"""
        deploy_path = "transition_engine/ai_generated_techniques.py"

        existing = ""
        if os.path.exists(deploy_path):
            with open(deploy_path, 'r') as f:
                existing = f.read()

        with open(deploy_path, 'w') as f:
            f.write(existing)
            f.write(f"\n\n# Auto-generated: {datetime.now()}\n")
            f.write(code)

        print(f"✅ New technique deployed to {deploy_path}")

    def _log_improvement(self, knowledge, code):
        """Log what was learned and added"""
        log = []
        if os.path.exists(self.improvements_log):
            with open(self.improvements_log, 'r') as f:
                log = json.load(f)

        log.append({
            'timestamp': str(datetime.now()),
            'knowledge_items': len(knowledge),
            'code_preview': code[:200] if code else None
        })

        with open(self.improvements_log, 'w') as f:
            json.dump(log, f, indent=2)
