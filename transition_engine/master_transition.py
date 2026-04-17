import numpy as np
import sounddevice as sd
import soundfile as sf
import librosa
import os
import threading
from scipy import signal
from pydub import AudioSegment
from ai_brain.agents.wordplay_agent import WordplayAgent

class MasterTransitionEngine:
    """
    Executes all transition techniques
    Central hub that routes to correct technique
    """
    def __init__(self, config):
        self.config = config
        self.sr = config['audio']['sample_rate']
        self.stems_dir = config['paths']['stems']
        self.cache_dir = config['paths']['audio_cache']
        self.is_playing = False
        self.playback_thread = None
        self.test_mode = False
        self.output_buffer = []
        self.wordplay_agent = WordplayAgent(config)

    # ============================================================
    # CORE ROUTING
    # ============================================================

    def execute(self, current_id, next_id, technique, params,
                current_analysis, next_analysis):
        """Route to correct transition technique"""

        techniques = {
            'beatmatch_crossfade':      self.beatmatch_crossfade,
            'cut_transition':           self.cut_transition,
            'echo_out':                 self.echo_out,
            'filter_sweep':             self.filter_sweep,
            'loop_roll':                self.loop_roll,
            'reverb_wash':              self.reverb_wash,
            'spinback':                 self.spinback,
            'tempo_ramp':               self.tempo_ramp,
            'white_noise_sweep':        self.white_noise_sweep,
            'vinyl_scratch_flourish':   self.vinyl_scratch_flourish,
            'tone_play':                self.tone_play,
            'wordplay':                 self.wordplay_transition,
            'mashup_short':             self.mashup_short,
            'mashup_extended':          self.mashup_extended,
            'acapella_layer':           self.acapella_layer,
            'drum_swap':                self.drum_swap,
            'bass_swap':                self.bass_swap,
            'stutter_glitch':           self.stutter_glitch,
            'half_time_transition':     self.half_time_transition,
            'wordplay_mashup':          self.wordplay_mashup,
            'phrasal_interlace':        self.phrasal_interlace,
            'semantic_bridge':          self.semantic_bridge,
        }

        handler = techniques.get(technique, self.beatmatch_crossfade)
        print(f"   🎚️  Executing: {technique}")

        try:
            handler(current_id, next_id, params,
                    current_analysis, next_analysis)
        except Exception as e:
            print(f"   ❌ Transition error: {e}")
            import traceback
            traceback.print_exc()
            self.cut_transition(current_id, next_id, {},
                                current_analysis, next_analysis)
                                
        # FIXED: Return the output path if we are in test mode so main.py gets it
        if self.test_mode and self.output_buffer:
            mix_data = np.concatenate(self.output_buffer)
            out_path = os.path.join(self.config['paths']['sandbox'], 'test_mix.wav')
            sf.write(out_path, mix_data, self.sr)
            return out_path
        return None

    def generate_transition_mix(self, cur_id, nxt_id, technique, params, cur_ana, nxt_ana):
        """Generates a mix file instead of playing live"""
        self.test_mode = True
        self.output_buffer = []
        
        out_path = self.execute(cur_id, nxt_id, technique, params, cur_ana, nxt_ana)
        
        self.test_mode = False
        return out_path

    # ============================================================
    # AUDIO UTILITIES
    # ============================================================

    def _load_audio(self, song_id):
        """Load full song audio"""
        path = os.path.join(self.cache_dir, f"{song_id}.mp3")
        if os.path.exists(path):
            y, sr = librosa.load(path, sr=self.sr, mono=True)
            return y, sr
        print(f"   ❌ Audio not found: {song_id}")
        return None, None

    def _load_stem(self, song_id, stem_name):
        """Load a specific stem (vocals/drums/bass/melody)"""
        for ext in ['wav', 'mp3']:
            path = os.path.join(
                self.stems_dir, song_id, f"{stem_name}.{ext}"
            )
            if os.path.exists(path):
                y, sr = librosa.load(path, sr=self.sr, mono=True)
                return y, sr
        return None, None

    def _play_audio(self, audio, sr=None):
        """Play audio or save to buffer if in test mode"""
        if self.test_mode:
            self.output_buffer.append(audio)
            return
            
        if sr is None:
            sr = self.sr
        if audio is None or len(audio) == 0:
            return
        # Normalize to prevent clipping
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.85
        sd.play(audio.astype(np.float32), sr)
        sd.wait()

    def _get_transition_point(self, analysis, audio_len):
        """Get the sample index where transition should start"""
        sr = self.sr
        trans_time = analysis.get(
            'transition_points', {}
        ).get('outro_beat', (audio_len / sr) * 0.80)
        return int(trans_time * sr)

    def _get_entry_point(self, analysis):
        """Get best entry time for incoming song in seconds"""
        entry_points = analysis.get('entry_points', {})
        if entry_points and entry_points.get('best_entry'):
            return entry_points['best_entry'].get('time', 0)
        return 0.0

    def _fade_out(self, audio, fade_samples=None):
        if fade_samples is None:
            fade_samples = min(int(self.sr * 2), len(audio))
        if fade_samples == 0 or len(audio) == 0:
            return audio
        fade = np.ones(len(audio))
        fade[-fade_samples:] = np.linspace(1, 0, fade_samples)
        return audio * fade

    def _fade_in(self, audio, fade_samples=None):
        if fade_samples is None:
            fade_samples = min(int(self.sr * 2), len(audio))
        if fade_samples == 0 or len(audio) == 0:
            return audio
        fade = np.ones(len(audio))
        fade[:fade_samples] = np.linspace(0, 1, fade_samples)
        return audio * fade

    def _apply_reverb(self, audio, room_size=0.5):
        delay_times = [0.03, 0.05, 0.07, 0.11, 0.13, 0.17]
        gains = [room_size * g for g in [0.8, 0.6, 0.5, 0.4, 0.3, 0.2]]
        output = audio.copy()
        for delay_time, gain in zip(delay_times, gains):
            delay_samples = int(delay_time * self.sr)
            if delay_samples < len(audio):
                delayed = np.zeros_like(audio)
                delayed[delay_samples:] = audio[:-delay_samples] * gain
                output = output + delayed
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val
        return output

    def _apply_echo(self, audio, delay_ms=375, feedback=0.6, num_echoes=4):
        delay_samples = int((delay_ms / 1000) * self.sr)
        output = audio.copy()
        for i in range(1, num_echoes + 1):
            offset = delay_samples * i
            if offset < len(audio):
                echo = np.zeros_like(audio)
                echo[offset:] = audio[:-offset] * (feedback ** i)
                output = output + echo
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val
        return output

    def _apply_highpass(self, audio, cutoff_hz, order=4):
        cutoff_norm = min(0.99, max(0.001, cutoff_hz / (self.sr / 2)))
        b, a = signal.butter(order, cutoff_norm, btype='high')
        return signal.filtfilt(b, a, audio)

    def _apply_lowpass(self, audio, cutoff_hz, order=4):
        cutoff_norm = min(0.99, max(0.001, cutoff_hz / (self.sr / 2)))
        b, a = signal.butter(order, cutoff_norm, btype='low')
        return signal.filtfilt(b, a, audio)

    def _pitch_shift_semitones(self, audio, semitones):
        return librosa.effects.pitch_shift(audio, sr=self.sr, n_steps=semitones)

    def _time_stretch(self, audio, rate):
        if abs(rate - 1.0) < 0.01:
            return audio
        return librosa.effects.time_stretch(audio, rate=rate)

    def _mix(self, audio_a, audio_b, weight_a=0.5, weight_b=0.5):
        max_len = max(len(audio_a), len(audio_b))
        a_padded = np.pad(audio_a, (0, max_len - len(audio_a)))
        b_padded = np.pad(audio_b, (0, max_len - len(audio_b)))
        return a_padded * weight_a + b_padded * weight_b

    def _crossfade(self, audio_a, audio_b, cf_samples):
        cf_len = min(cf_samples, len(audio_a), len(audio_b))
        if cf_len == 0:
            return np.concatenate([audio_a, audio_b])
        fade_out = np.linspace(1, 0, cf_len)
        fade_in = np.linspace(0, 1, cf_len)
        cf = audio_a[-cf_len:] * fade_out + audio_b[:cf_len] * fade_in
        return cf

    # ============================================================
    # TECHNIQUES (1-19)
    # ============================================================

    def beatmatch_crossfade(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        crossfade_bars = params.get('crossfade_bars', 8)
        bpm = cur_ana.get('bpm', 120)
        cf_samples = int(((60 / max(bpm, 1)) * 4) * crossfade_bars * sr)

        bpm_ratio = bpm / max(nxt_ana.get('bpm', 120), 1)
        if abs(bpm_ratio - 1.0) > 0.02:
            nxt_audio = self._time_stretch(nxt_audio, bpm_ratio)

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        self._play_audio(cur_audio[:trans_sample], sr)
        cf = self._crossfade(cur_audio[trans_sample:], nxt_audio[nxt_entry:], cf_samples)
        self._play_audio(cf, sr)
        self._play_audio(nxt_audio[nxt_entry + cf_samples:], sr)

    def cut_transition(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        bar_times = cur_ana.get('bar_times', [])
        if bar_times:
            trans_time = trans_sample / sr
            nearest_bar = min(bar_times, key=lambda x: abs(x - trans_time))
            trans_sample = int(nearest_bar * sr)

        self._play_audio(cur_audio[:trans_sample], sr)
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    def echo_out(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        echo_segment = cur_audio[trans_sample:trans_sample + sr * 4].copy()
        echoed = self._fade_out(self._apply_echo(echo_segment, params.get('delay_ms', 375), params.get('feedback', 0.6)))

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            nxt_start = nxt_audio[nxt_entry:nxt_entry + len(echoed)]
            nxt_fadein = self._fade_in(nxt_start, fade_samples=len(nxt_start))
            self._play_audio(self._mix(echoed, nxt_fadein, 0.7, 0.3), sr)
            self._play_audio(nxt_audio[nxt_entry + len(echoed):], sr)

    def filter_sweep(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        sweep_dur = int(sr * params.get('sweep_duration', 8))

        self._play_audio(cur_audio[:trans_sample], sr)

        sweep_out = cur_audio[trans_sample:trans_sample + sweep_dur].copy()
        swept_out = np.zeros_like(sweep_out)
        chunk = sr // 4

        for i in range(0, len(sweep_out), chunk):
            seg = sweep_out[i:i + chunk]
            progress = i / max(len(sweep_out), 1)
            filtered = self._apply_highpass(seg, 20 + (8000 - 20) * (progress ** 1.5))
            swept_out[i:i + len(filtered)] = filtered * (1.0 - (progress * 0.8))

        self._play_audio(swept_out, sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            sweep_in = nxt_audio[nxt_entry:nxt_entry + sweep_dur].copy()
            swept_in = np.zeros_like(sweep_in)

            for i in range(0, len(sweep_in), chunk):
                seg = sweep_in[i:i + chunk]
                progress = i / max(len(sweep_in), 1)
                filtered = self._apply_lowpass(seg, min(200 + (20000 - 200) * progress, 20000))
                swept_in[i:i + len(filtered)] = filtered * (0.2 + (progress * 0.8))

            self._play_audio(swept_in, sr)
            self._play_audio(nxt_audio[nxt_entry + sweep_dur:], sr)

    def loop_roll(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        seconds_per_bar = (60 / max(cur_ana.get('bpm', 120), 1)) * 4

        self._play_audio(cur_audio[:trans_sample], sr)

        rolled_parts = []
        for div in [1, 0.5, 0.25, 0.125]:
            loop_len = max(int((seconds_per_bar * div) * sr), 100)
            loop = cur_audio[trans_sample:trans_sample + loop_len].copy()
            for r in range(max(1, int(1 / div))):
                rolled_parts.append(loop * (1.0 - (r * 0.1)))

        if rolled_parts:
            self._play_audio(self._pitch_shift_semitones(np.concatenate(rolled_parts), 2), sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    def reverb_wash(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        wash_segment = cur_audio[trans_sample:trans_sample + int(sr * 6)].copy()
        washed = self._fade_out(self._apply_reverb(wash_segment, room_size=0.85), fade_samples=len(wash_segment))
        self._play_audio(washed, sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(self._fade_in(nxt_audio[nxt_entry:], fade_samples=int(sr * 4)), sr)

    def spinback(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        spin_seg = cur_audio[trans_sample:trans_sample + int(sr * 1.5)].copy()
        chunks, chunk_size, spun_parts = 12, len(spin_seg) // 12, []

        for i in range(chunks):
            chunk = spin_seg[i * chunk_size:(i + 1) * chunk_size]
            if len(chunk) < 10: continue
            try: spun_parts.append(self._time_stretch(chunk[::-1], 1.0 + (i / chunks) * 5.0))
            except: spun_parts.append(chunk[::-1])

        if spun_parts:
            spun = np.concatenate(spun_parts)
            try: spun = self._pitch_shift_semitones(spun, 6)
            except: pass
            self._play_audio(self._fade_out(spun, fade_samples=len(spun) // 3), sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    def tempo_ramp(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        bpm_a, bpm_b = cur_ana.get('bpm', 120), max(nxt_ana.get('bpm', 120), 1)
        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        ramp_dur = int(((60 / max(bpm_a, 1)) * 4) * 16 * sr)
        ramp_seg = cur_audio[trans_sample:trans_sample + ramp_dur].copy()
        
        chunks, chunk_size, ramped_parts = 16, len(ramp_seg) // 16, []
        for i in range(chunks):
            chunk = ramp_seg[i * chunk_size:(i + 1) * chunk_size]
            if len(chunk) < 10: continue
            try: ramped_parts.append(self._time_stretch(chunk, 1.0 + (bpm_b / bpm_a - 1.0) * (i / chunks)))
            except: ramped_parts.append(chunk)

        if ramped_parts: self._play_audio(np.concatenate(ramped_parts), sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            cf_len = int(sr * 4)
            self._play_audio(self._crossfade(np.zeros(cf_len), nxt_audio[nxt_entry:nxt_entry + cf_len], cf_len), sr)
            self._play_audio(nxt_audio[nxt_entry + cf_len:], sr)

    def white_noise_sweep(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        sweep_dur = int(sr * 4)
        noise = np.random.normal(0, 0.08, sweep_dur)
        env = np.concatenate([np.linspace(0, 1, sweep_dur // 2) ** 2, np.linspace(1, 0, sweep_dur // 2) ** 2])
        noise_sweep = noise * env

        cur_tail = cur_audio[trans_sample:trans_sample + sweep_dur]
        if len(cur_tail) > 0:
            self._play_audio(self._mix(self._fade_out(cur_tail, fade_samples=len(cur_tail))[:len(noise_sweep)], noise_sweep[:len(cur_tail)], 0.6, 0.4), sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(self._fade_in(nxt_audio[nxt_entry:], fade_samples=int(sr * 2)), sr)

    def vinyl_scratch_flourish(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        if cur_audio is None: return

        scratch_time = params.get('scratch_time', cur_ana.get('transition_points', {}).get('outro_beat', len(cur_audio) / sr * 0.75))
        scratch_sample = int(scratch_time * sr)
        self._play_audio(cur_audio[:scratch_sample], sr)

        scratch_len = int(sr * 0.6)
        scratch_seg = cur_audio[scratch_sample:scratch_sample + scratch_len].copy()
        scratch_parts = []

        for i in range(4):
            chunk = scratch_seg[i * (scratch_len // 4):(i + 1) * (scratch_len // 4)]
            if len(chunk) > 10:
                try: scratch_parts.append(self._time_stretch(chunk, max(0.3, 1.0 - (i * 0.2))))
                except: scratch_parts.append(chunk)

        scratch_parts.append(scratch_seg[::-1])

        for i in range(4):
            chunk = scratch_seg[i * (scratch_len // 4):(i + 1) * (scratch_len // 4)]
            if len(chunk) > 10:
                try: scratch_parts.append(self._time_stretch(chunk, 0.5 + (i * 0.2)))
                except: scratch_parts.append(chunk)

        scratch_audio = np.concatenate(scratch_parts)
        wobble = (np.sin(np.linspace(0, 8.0 * np.pi, len(scratch_audio))) * 0.3 + 1.0)
        self._play_audio(scratch_audio * wobble, sr)

        nxt_audio, _ = self._load_audio(nxt_id)
        if nxt_audio is not None and params.get('is_transition', False):
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)
        else:
            rewind_sample = max(0, scratch_sample - int(((60 / max(cur_ana.get('bpm', 120), 1)) * 4) * params.get('rewind_bars', 4) * sr))
            self._play_audio(cur_audio[rewind_sample:], sr)

    def tone_play(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        melody_notes = params.get('melody_notes', nxt_ana.get('melody_notes', [60, 62, 64, 65, 67]))
        note_samples = int(params.get('note_duration', 60 / max(cur_ana.get('bpm', 120), 1)) * sr)

        melody_stem, _ = self._load_stem(cur_id, 'other')
        source_audio = melody_stem if melody_stem is not None else cur_audio
        instrument_sample = source_audio[trans_sample:trans_sample + note_samples].copy()
        if len(instrument_sample) < 100: instrument_sample = cur_audio[trans_sample:trans_sample + note_samples].copy()

        preview_parts = []
        for note_midi in melody_notes[:8]:
            try: preview_parts.append(self._pitch_shift_semitones(instrument_sample, int(note_midi - 60)))
            except: preview_parts.append(instrument_sample.copy())

        if preview_parts:
            preview = np.concatenate(preview_parts)
            self._play_audio(self._fade_out(preview, len(preview) // 3), sr)

        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
        self._play_audio(self._fade_in(nxt_audio[nxt_entry:], fade_samples=int(sr * 8)), sr)

    def wordplay_transition(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = int(params.get('transition_time', cur_ana.get('transition_points', {}).get('outro_beat', len(cur_audio) / sr * 0.8)) * sr)
        self._play_audio(cur_audio[:trans_sample], sr)

        word_clip_path = params.get('word_clip_a')
        word_audio = None

        if word_clip_path and os.path.exists(word_clip_path):
            word_audio, _ = librosa.load(word_clip_path, sr=sr)
        else:
            vocals, _ = self._load_stem(cur_id, 'vocals')
            if vocals is not None:
                word_audio = vocals[max(0, trans_sample - int(sr * 0.5)):trans_sample + int(sr * 0.5)]

        if word_audio is not None and len(word_audio) > 100:
            echoed_word = self._apply_echo(word_audio, delay_ms=250, feedback=0.5, num_echoes=3)
            word_sequence = [echoed_word * (1.0 - (i * 0.25)) for i in range(params.get('word_repeats', 3))]
            self._play_audio(self._apply_reverb(np.concatenate(word_sequence), room_size=0.4), sr)

        if nxt_audio is not None:
            nxt_start = int(params.get('word_time_b', 0) * sr)
            self._play_audio(self._fade_in(nxt_audio[nxt_start:], fade_samples=int(sr * 2)), sr)

    def mashup_short(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        bpm_ratio = cur_ana.get('bpm', 120) / max(nxt_ana.get('bpm', 120), 1)
        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        drums_a, _ = self._load_stem(cur_id, 'drums')
        vocals_b, _ = self._load_stem(nxt_id, 'vocals')
        melody_b, _ = self._load_stem(nxt_id, 'other')

        if abs(bpm_ratio - 1.0) > 0.02:
            if vocals_b is not None: vocals_b = self._time_stretch(vocals_b, bpm_ratio)
            if melody_b is not None: melody_b = self._time_stretch(melody_b, bpm_ratio)

        mashup_samples = int(((60 / max(cur_ana.get('bpm', 120), 1)) * 4) * params.get('mashup_bars', 8) * sr)
        mashup = np.zeros(mashup_samples)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        if drums_a is not None:
            seg = drums_a[trans_sample:trans_sample + mashup_samples]
            if len(seg) > 0:
                pad = np.zeros(mashup_samples)
                pad[:len(seg)] = seg
                mashup += pad * 0.8

        if vocals_b is not None:
            seg = vocals_b[nxt_entry:nxt_entry + mashup_samples]
            if len(seg) > 0:
                pad = np.zeros(mashup_samples)
                pad[:len(seg)] = seg
                mashup += self._fade_in(pad, fade_samples=mashup_samples // 4) * 0.85

        if melody_b is not None:
            seg = melody_b[nxt_entry:nxt_entry + mashup_samples]
            if len(seg) > 0:
                pad = np.zeros(mashup_samples)
                pad[:len(seg)] = seg
                mashup += self._fade_in(pad, fade_samples=mashup_samples // 2) * 0.6

        if np.max(np.abs(mashup)) > 0:
            self._play_audio(mashup / np.max(np.abs(mashup)) * 0.85, sr)

        if nxt_audio is not None:
            self._play_audio(self._fade_in(nxt_audio[nxt_entry:], fade_samples=int(sr * 4)), sr)

    def mashup_extended(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        bpm_ratio = cur_ana.get('bpm', 120) / max(nxt_ana.get('bpm', 120), 1)
        key_shift = self._calculate_key_shift(cur_ana.get('camelot', ''), nxt_ana.get('camelot', ''))
        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        drums_a, _ = self._load_stem(cur_id, 'drums')
        bass_a, _ = self._load_stem(cur_id, 'bass')
        vocals_a, _ = self._load_stem(cur_id, 'vocals')

        vocals_b, _ = self._load_stem(nxt_id, 'vocals')
        melody_b, _ = self._load_stem(nxt_id, 'other')
        bass_b, _ = self._load_stem(nxt_id, 'bass')
        drums_b, _ = self._load_stem(nxt_id, 'drums')

        stems_b = [vocals_b, melody_b, bass_b, drums_b]
        if abs(bpm_ratio - 1.0) > 0.02:
            for i in range(len(stems_b)):
                if stems_b[i] is not None: stems_b[i] = self._time_stretch(stems_b[i], bpm_ratio)
        
        if key_shift != 0:
            for i in [0, 1, 2]: # vocals, melody, bass
                if stems_b[i] is not None: stems_b[i] = self._pitch_shift_semitones(stems_b[i], key_shift)
        
        vocals_b, melody_b, bass_b, drums_b = stems_b

        mashup_samples = int(((60 / max(cur_ana.get('bpm', 120), 1)) * 4) * params.get('mashup_bars', 32) * sr)
        mashup = np.zeros(mashup_samples)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
        phase1, phase2_start, phase2_end = mashup_samples // 4, mashup_samples // 4, (mashup_samples // 4) * 2

        # Phase 1
        if drums_a is not None:
            seg = drums_a[trans_sample:trans_sample + phase1]
            mashup[:len(seg)] += seg * 0.85
        if bass_a is not None:
            seg = bass_a[trans_sample:trans_sample + phase1]
            mashup[:len(seg)] += seg * 0.80
        if vocals_a is not None:
            seg = self._fade_out(vocals_a[trans_sample:trans_sample + phase1], phase1 // 2)
            mashup[:len(seg)] += seg * 0.70

        # Phase 2
        if drums_a is not None:
            seg = drums_a[trans_sample + phase1:trans_sample + phase2_end]
            mashup[phase2_start:phase2_start + len(seg)] += seg * 0.70
        if vocals_b is not None:
            seg = self._fade_in(vocals_b[nxt_entry:nxt_entry + phase1], phase1 // 2)
            mashup[phase2_start:phase2_start + len(seg)] += seg * 0.80
        if melody_b is not None:
            seg = self._fade_in(melody_b[nxt_entry:nxt_entry + phase1], phase1 // 2)
            mashup[phase2_start:phase2_start + len(seg)] += seg * 0.60

        # Phase 3
        phase3_len = mashup_samples - phase2_end
        if drums_b is not None:
            seg = drums_b[nxt_entry:nxt_entry + phase3_len]
            mashup[phase2_end:phase2_end + len(seg)] += seg * 0.85
        if bass_b is not None:
            seg = bass_b[nxt_entry:nxt_entry + phase3_len]
            mashup[phase2_end:phase2_end + len(seg)] += seg * 0.80
        if vocals_b is not None:
            seg = vocals_b[nxt_entry + phase1:nxt_entry + phase1 + phase3_len]
            mashup[phase2_end:phase2_end + len(seg)] += seg * 0.85

        if np.max(np.abs(mashup)) > 0:
            self._play_audio(mashup / np.max(np.abs(mashup)) * 0.85, sr)

        if nxt_audio is not None:
            self._play_audio(nxt_audio[nxt_entry + mashup_samples:], sr)

    def acapella_layer(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        vocals_a, _ = self._load_stem(cur_id, 'vocals')
        drums_b, _ = self._load_stem(nxt_id, 'drums')
        bass_b, _ = self._load_stem(nxt_id, 'bass')
        melody_b, _ = self._load_stem(nxt_id, 'other')

        bpm_ratio = cur_ana.get('bpm', 120) / max(nxt_ana.get('bpm', 120), 1)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
        layer_samples = int(((60 / max(cur_ana.get('bpm', 120), 1)) * 4) * params.get('layer_bars', 16) * sr)
        layer = np.zeros(layer_samples)

        if vocals_a is not None:
            seg = vocals_a[trans_sample:trans_sample + layer_samples]
            if abs(bpm_ratio - 1.0) > 0.02: seg = self._time_stretch(seg, bpm_ratio)
            layer[:len(seg)] += seg * 0.9

        for stem, vol in [(drums_b, 0.8), (bass_b, 0.75), (melody_b, 0.7)]:
            if stem is not None:
                seg = stem[nxt_entry:nxt_entry + layer_samples]
                layer[:len(seg)] += seg * vol

        if np.max(np.abs(layer)) > 0:
            self._play_audio(layer / np.max(np.abs(layer)) * 0.85, sr)

        if nxt_audio is not None:
            self._play_audio(nxt_audio[nxt_entry + layer_samples:], sr)

    def drum_swap(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        drums_a, _ = self._load_stem(cur_id, 'drums')
        melody_a, _ = self._load_stem(cur_id, 'other')
        vocals_a, _ = self._load_stem(cur_id, 'vocals')
        drums_b, _ = self._load_stem(nxt_id, 'drums')

        bpm_ratio = cur_ana.get('bpm', 120) / max(nxt_ana.get('bpm', 120), 1)
        if drums_b is not None and abs(bpm_ratio - 1.0) > 0.02:
            drums_b = self._time_stretch(drums_b, bpm_ratio)

        swap_samples = int(((60 / max(cur_ana.get('bpm', 120), 1)) * 4) * params.get('swap_bars', 8) * sr)
        swap = np.zeros(swap_samples)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        for stem, vol in [(melody_a, 0.8), (vocals_a, 0.85)]:
            if stem is not None:
                seg = self._fade_out(stem[trans_sample:trans_sample + swap_samples], swap_samples // 4)
                swap[:len(seg)] += seg * vol

        if drums_a is not None:
            seg = drums_a[trans_sample:trans_sample + swap_samples]
            fade = np.linspace(1, 0, min(len(seg), swap_samples))
            swap[:len(fade)] += seg[:len(fade)] * fade * 0.8

        if drums_b is not None:
            seg = drums_b[nxt_entry:nxt_entry + swap_samples]
            fade = np.linspace(0, 1, min(len(seg), swap_samples))
            swap[:len(fade)] += seg[:len(fade)] * fade * 0.8

        if np.max(np.abs(swap)) > 0:
            self._play_audio(swap / np.max(np.abs(swap)) * 0.85, sr)

        if nxt_audio is not None:
            self._play_audio(nxt_audio[nxt_entry + swap_samples:], sr)

    def bass_swap(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        bass_b, _ = self._load_stem(nxt_id, 'bass')
        drums_a, _ = self._load_stem(cur_id, 'drums')
        melody_a, _ = self._load_stem(cur_id, 'other')

        bpm_ratio = cur_ana.get('bpm', 120) / max(nxt_ana.get('bpm', 120), 1)
        swap_samples = int(((60 / max(cur_ana.get('bpm', 120), 1)) * 4) * params.get('swap_bars', 8) * sr)
        swap = np.zeros(swap_samples)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        if drums_a is not None:
            seg = drums_a[trans_sample:trans_sample + swap_samples]
            swap[:len(seg)] += seg * 0.8

        if melody_a is not None:
            seg = self._fade_out(melody_a[trans_sample:trans_sample + swap_samples], swap_samples // 3)
            swap[:len(seg)] += seg * 0.7

        if bass_b is not None:
            if abs(bpm_ratio - 1.0) > 0.02: bass_b = self._time_stretch(bass_b, bpm_ratio)
            seg = self._fade_in(bass_b[nxt_entry:nxt_entry + swap_samples], swap_samples // 4)
            swap[:len(seg)] += seg * 0.85

        if np.max(np.abs(swap)) > 0:
            self._play_audio(swap / np.max(np.abs(swap)) * 0.85, sr)

        if nxt_audio is not None:
            self._play_audio(nxt_audio[nxt_entry:], sr)

    def stutter_glitch(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        beat_samples = int((60 / max(cur_ana.get('bpm', 120), 1)) * sr)
        glitch_total = beat_samples * 4
        glitch_audio = cur_audio[trans_sample:trans_sample + glitch_total].copy()
        glitch_parts = []
        generated = 0

        for slice_size in [beat_samples // 2, beat_samples // 4, beat_samples // 8, beat_samples // 16]:
            for repeat in range(4):
                if generated >= glitch_total: break
                start = (repeat * slice_size) % max(len(glitch_audio) - slice_size, 1)
                chunk = glitch_audio[start:start + slice_size].copy()

                try: chunk = self._pitch_shift_semitones(chunk, np.random.choice([-2, 0, 2, 4, 7, 12]))
                except: pass

                env = np.ones(len(chunk))
                env[-len(env)//4:] = np.linspace(1, 0, len(env)//4)
                glitch_parts.append(chunk * env)
                generated += len(chunk)

        if glitch_parts:
            glitch = np.concatenate(glitch_parts)
            if np.max(np.abs(glitch)) > 0:
                self._play_audio(glitch / np.max(np.abs(glitch)) * 0.85, sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    def half_time_transition(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None: return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        half_dur = int(sr * 8)
        half_seg = nxt_audio[nxt_entry:nxt_entry + half_dur]

        if len(half_seg) > 100:
            self._play_audio(self._fade_in(self._time_stretch(half_seg, 0.5), fade_samples=int(sr * 2)), sr)

        ramp_dur = int(((60 / max(nxt_ana.get('bpm', 120), 1)) * 4) * 8 * sr)
        ramp_seg = nxt_audio[nxt_entry + half_dur:nxt_entry + half_dur + ramp_dur]

        chunks, chunk_size, ramp_parts = 8, len(ramp_seg) // 8, []
        for i in range(chunks):
            chunk = ramp_seg[i * chunk_size:(i + 1) * chunk_size]
            if len(chunk) < 10: continue
            try: ramp_parts.append(self._time_stretch(chunk, 0.5 + (0.5 * i / chunks)))
            except: ramp_parts.append(chunk)

        if ramp_parts: self._play_audio(np.concatenate(ramp_parts), sr)

    def wordplay_mashup(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        High-IQ transition:
        1. Find rhyming/matching word.
        2. Loop word from Song A.
        3. Bring in Instrumental from Song B.
        4. Drop Song B Vocals on matching word.
        """
        print("   🔍 Seeking Wordplay Connection...")
        connection = self.wordplay_agent.find_connection(cur_ana, nxt_ana)
        
        if not connection:
            print("   ⚠️ No connection found. Falling back to Echo Out.")
            return self.echo_out(cur_id, nxt_id, params, cur_ana, nxt_ana)
            
        print(f"   💡 FOUND LINK: '{connection.get('word', 'rhyme')}' ({connection.get('type', 'unknown')})")
        
        vocals_a, sr = self._load_stem(cur_id, 'vocals')
        drums_b, _ = self._load_stem(nxt_id, 'drums')
        other_b, _ = self._load_stem(nxt_id, 'other')
        vocals_b, _ = self._load_stem(nxt_id, 'vocals')
        
        if vocals_a is None or drums_b is None:
            return self.echo_out(cur_id, nxt_id, params, cur_ana, nxt_ana)

        cur_full, _ = self._load_audio(cur_id)
        word_start = connection.get('transition_time', 0)
        
        # FIXED: Safe dictionary access in case 'cur_entry' doesn't exist
        word_end = connection.get('cur_entry', {}).get('end_time', word_start + 0.5)
        
        self._play_audio(cur_full[:int(word_start * sr)], sr)
        
        word_clip = vocals_a[int(word_start * sr):int(word_end * sr)]
        if len(word_clip) == 0:
            return self.echo_out(cur_id, nxt_id, params, cur_ana, nxt_ana)
            
        word_loop = np.tile(word_clip, params.get('word_repeats', 4))
        
        bpm_ratio = cur_ana.get('bpm', 120) / max(nxt_ana.get('bpm', 120), 1)
        inst_b = self._mix(drums_b, other_b if other_b is not None else np.zeros_like(drums_b), 0.5, 0.5)
        
        if abs(bpm_ratio - 1.0) > 0.02:
            inst_b = self._time_stretch(inst_b, bpm_ratio)
            
        nxt_entry = int(connection.get('word_time_b', 0) * sr)
        loop_len = len(word_loop)
        
        inst_slice = inst_b[max(0, nxt_entry - loop_len):nxt_entry]
        mash = self._mix(word_loop, inst_slice, 0.7, 0.5)
        self._play_audio(mash, sr)
        
        nxt_full, _ = self._load_audio(nxt_id)
        if nxt_full is not None:
            self._play_audio(nxt_full[nxt_entry:], sr)

    def phrasal_interlace(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        TRUE INNOVATION: CSPI (Cross-Song Phrasal Interlacing)
        Alternates between Song A and B every 1/16th of a beat.
        Creates a 'shimmer' or 'interlaced' audio effect.
        """
        print("   ⚔️  Executing CSPI (Micro-Splicing)...")
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        bpm = cur_ana.get('bpm', 120)
        slice_samples = int(((60 / max(bpm, 1)) / 4) * sr)
        
        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
        
        self._play_audio(cur_audio[:trans_sample], sr)
        
        interlace_len = slice_samples * 64
        interlaced = np.zeros(interlace_len)
        
        for i in range(64):
            start = i * slice_samples
            if (i // 2) % 2 == 0:
                chunk_len = min(slice_samples, len(cur_audio) - (trans_sample + start))
                if chunk_len > 0:
                    interlaced[start:start+len(chunk)] = cur_audio[trans_sample + start:trans_sample + start + chunk_len]
            else:
                chunk_len = min(slice_samples, len(nxt_audio) - (nxt_entry + start))
                if chunk_len > 0:
                    interlaced[start:start+len(chunk)] = nxt_audio[nxt_entry + start:nxt_entry + start + chunk_len]
                
        fade = int(sr * 0.005) # 5ms
        for i in range(1, 64):
            idx =
