import os
import random
import json
import threading
import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter import ttk, messagebox

from main import DJApp

class DJUITester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PRO AI DJ - Transition Tester")
        self.geometry("600x450")
        self.configure(bg="#2b2b2b")
        
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except:
            pass
        
        self.app = None
        self.current_technique = None
        self.audio_arr = None
        
        self.setup_ui()
        
        # Load in background
        threading.Thread(target=self.init_dj_app, daemon=True).start()

    def setup_ui(self):
        self.lbl_status = tk.Label(self, text="Initializing DJ App... Please wait.", fg="white", bg="#2b2b2b", font=("Arial", 14))
        self.lbl_status.pack(pady=20)
        
        self.lbl_songs = tk.Label(self, text="", fg="#00ff00", bg="#2b2b2b", font=("Arial", 12))
        self.lbl_songs.pack(pady=10)
        
        self.btn_generate = tk.Button(self, text="Generate New Transition", command=self.generate_transition, state=tk.DISABLED, bg="#444", fg="white", font=("Arial", 12))
        self.btn_generate.pack(pady=10)

        self.btn_play = tk.Button(self, text="▶ Play Action", command=self.play_audio, state=tk.DISABLED, bg="#444", fg="white", font=("Arial", 12))
        self.btn_play.pack(pady=5)
        
        self.btn_stop = tk.Button(self, text="⏹ Stop Audio", command=self.stop_audio, state=tk.DISABLED, bg="#444", fg="white", font=("Arial", 12))
        self.btn_stop.pack(pady=5)
        
        frame_feedback = tk.Frame(self, bg="#2b2b2b")
        frame_feedback.pack(pady=20)
        
        self.btn_pass = tk.Button(frame_feedback, text="✅ Pass (Good)", command=lambda: self.submit_feedback(1), state=tk.DISABLED, bg="#006600", fg="white", font=("Arial", 12, "bold"), width=15)
        self.btn_pass.pack(side=tk.LEFT, padx=10)
        
        self.btn_fail = tk.Button(frame_feedback, text="❌ Fail (Bad)", command=lambda: self.submit_feedback(0), state=tk.DISABLED, bg="#660000", fg="white", font=("Arial", 12, "bold"), width=15)
        self.btn_fail.pack(side=tk.LEFT, padx=10)

    def init_dj_app(self):
        try:
            self.app = DJApp()
            playlist_url = self.app.config['youtube']['playlist_url']
            self.after(0, lambda: self.lbl_status.config(text="Fetching playlist info (titles only)..."))
            
            # This only gets labels/ids, does NOT download audio
            self.app.playlist = self.app.downloader.get_playlist_metadata(playlist_url)
            
            def mock_play(audio, sr=None):
                if audio is not None and len(audio) > 0:
                    self.captured_audio.append(audio)
                    
            self.app.transition_engine._play_audio = mock_play
            
            self.after(0, lambda: self.lbl_status.config(text=f"Ready! Found {len(self.app.playlist)} songs in playlist."))
            self.after(0, lambda: self.btn_generate.config(state=tk.NORMAL))
        except Exception as e:
            self.after(0, lambda: self.lbl_status.config(text=f"Error initializing: {e}"))

    def generate_transition(self):
        if len(self.app.playlist) < 2:
            messagebox.showerror("Error", "Need at least 2 songs in playlist.")
            return
            
        self.btn_generate.config(state=tk.DISABLED)
        self.btn_play.config(state=tk.DISABLED)
        self.btn_pass.config(state=tk.DISABLED)
        self.btn_fail.config(state=tk.DISABLED)
        self.lbl_status.config(text="Downloading & analyzing songs... This may take a minute.")
        self.update()
        
        threading.Thread(target=self._generate_task, daemon=True).start()
        
    def _generate_task(self):
        try:
            songs_to_test = random.sample(self.app.playlist, 2)
            cur_song, nxt_song = songs_to_test[0], songs_to_test[1]
            
            for song in [cur_song, nxt_song]:
                song_id = song['id']
                
                # Check for existing metadata cache file
                meta_path = os.path.join("data", "metadata", f"{song_id}.json")
                if os.path.exists(meta_path) and song_id not in self.app.metadata_cache:
                    try:
                        with open(meta_path, 'r') as f:
                            self.app.metadata_cache[song_id] = json.load(f)
                    except:
                        pass
                
                filepath = os.path.join(self.app.config['paths']['audio_cache'], f"{song_id}.mp3")
                if not os.path.exists(filepath):
                    self.after(0, lambda s=song: self.lbl_status.config(text=f"Downloading (1 of 2): {s['title'][:30]}..."))
                    filepath = self.app.downloader.download_song(song['url'], song_id)
                else:
                    self.after(0, lambda s=song: self.lbl_status.config(text=f"Using cached: {s['title'][:30]}"))
                    
                if song_id not in self.app.metadata_cache:
                    self.after(0, lambda s=song: self.lbl_status.config(text=f"Analyzing: {s['title'][:30]}..."))
                    analysis = self.app.analyzer.analyze_track(filepath, song_id)
                    analysis['title'] = song['title']
                    self.app.metadata_cache[song_id] = analysis

            cur_ana = self.app.metadata_cache[cur_song['id']]
            nxt_ana = self.app.metadata_cache[nxt_song['id']]
            
            compatibility = random.randint(40, 80)
            technique = self.app.transition_decider.decide(cur_ana, nxt_ana, compatibility)
            params = self.app.transition_decider.get_params(cur_ana, nxt_ana, technique)
            
            self.after(0, lambda: self.lbl_status.config(text=f"Generating Transition ({technique})..."))
            self.captured_audio = []
            
            self.app.transition_engine.execute(
                current_id=cur_song['id'], next_id=nxt_song['id'],
                technique=technique, params=params,
                current_analysis=cur_ana, next_analysis=nxt_ana
            )
            
            if self.captured_audio:
                self.audio_arr = np.concatenate(self.captured_audio)
                max_val = np.max(np.abs(self.audio_arr))
                if max_val > 0:
                    self.audio_arr = self.audio_arr / max_val * 0.9
            else:
                self.audio_arr = np.zeros(44100)
                
            self.current_technique = technique
            
            # ☁️ Now that audio is generated, offload original files to Google Drive
            if os.path.exists('data/tokens/token_account_1.json'):
                for song in [cur_song, nxt_song]:
                    self.after(0, lambda s=song: self.lbl_status.config(text=f"☁️ Offloading to Drive: {s['title'][:30]}..."))
                    self.app.downloader.upload_to_drive(song['id'], self.app.drive_manager)
            
            song_text = f"From: {cur_song['title'][:40]}\nTo: {nxt_song['title'][:40]}\n\nTechnique: {technique}"
            
            self.after(0, lambda: self.lbl_songs.config(text=song_text))
            self.after(0, lambda: self.lbl_status.config(text="Transition generated! You can now play and rate it."))
            
            self.after(0, lambda: self.btn_generate.config(state=tk.NORMAL))
            self.after(0, lambda: self.btn_play.config(state=tk.NORMAL))
            self.after(0, lambda: self.btn_pass.config(state=tk.NORMAL))
            self.after(0, lambda: self.btn_fail.config(state=tk.NORMAL))
            self.after(0, lambda: self.btn_stop.config(state=tk.NORMAL))
            
            self.after(0, self.play_audio)
            
        except Exception as e:
            self.after(0, lambda: self.lbl_status.config(text=f"Error generating transition: {str(e)}"))
            self.after(0, lambda: self.btn_generate.config(state=tk.NORMAL))

    def play_audio(self):
        if self.audio_arr is not None:
            sd.stop()
            sd.play(self.audio_arr, self.app.config['audio']['sample_rate'])
            
    def stop_audio(self):
        sd.stop()
        
    def submit_feedback(self, is_pass):
        if not self.current_technique:
            return
            
        sd.stop()
        rating = 8 if is_pass else 3
        
        weight_file = os.path.join('data', 'logs', 'feedback_weights.json')
        os.makedirs(os.path.join('data', 'logs'), exist_ok=True)
        
        weights = {}
        if os.path.exists(weight_file):
            try:
                with open(weight_file, 'r') as f:
                    weights = json.load(f)
            except Exception:
                pass
                
        # 8 -> 30% positive adjustment, 3 -> 20% negative adjustment
        adjustment = (rating - 5) / 10.0
        current_weight = weights.get(self.current_technique, 0)
        weights[self.current_technique] = current_weight + adjustment
        
        with open(weight_file, 'w') as f:
            json.dump(weights, f, indent=4)
            
        self.lbl_status.config(text=f"Learned! Adjusted '{self.current_technique}' weight by {adjustment:+.2f}")
        self.lbl_songs.config(text="")
        
        self.btn_play.config(state=tk.DISABLED)
        self.btn_pass.config(state=tk.DISABLED)
        self.btn_fail.config(state=tk.DISABLED)
        self.current_technique = None

if __name__ == "__main__":
    app = DJUITester()
    app.mainloop()
