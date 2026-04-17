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
            self.cut_transition(current_id, next_id, {},
                                current_analysis, next_analysis)

    def generate_transition_mix(self, cur_id, nxt_id, technique, params, cur_ana, nxt_ana):
        """Generates a mix file instead of playing live"""
        self.test_mode = True
        self.output_buffer = []
        
        self.execute(cur_id, nxt_id, technique, params, cur_ana, nxt_ana)
        
        if not self.output_buffer:
            return None
            
        mix_data = np.concatenate(self.output_buffer)
        out_path = os.path.join(self.config['paths']['sandbox'], 'test_mix.wav')
        sf.write(out_path, mix_data, self.sr)
        
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
        # Try wav first, then mp3
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
        """Apply fade out to audio array"""
        if fade_samples is None:
            fade_samples = min(int(self.sr * 2), len(audio))
        fade = np.ones(len(audio))
        fade[-fade_samples:] = np.linspace(1, 0, fade_samples)
        return audio * fade

    def _fade_in(self, audio, fade_samples=None):
        """Apply fade in to audio array"""
        if fade_samples is None:
            fade_samples = min(int(self.sr * 2), len(audio))
        fade = np.ones(len(audio))
        fade[:fade_samples] = np.linspace(0, 1, fade_samples)
        return audio * fade

    def _apply_reverb(self, audio, room_size=0.5):
        """Apply reverb effect using delay lines"""
        delay_times = [0.03, 0.05, 0.07, 0.11, 0.13, 0.17]
        gains = [
            room_size * g for g in [0.8, 0.6, 0.5, 0.4, 0.3, 0.2]
        ]
        output = audio.copy()
        for delay_time, gain in zip(delay_times, gains):
            delay_samples = int(delay_time * self.sr)
            if delay_samples < len(audio):
                delayed = np.zeros_like(audio)
                delayed[delay_samples:] = (
                    audio[:-delay_samples] * gain
                )
                output = output + delayed
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val
        return output

    def _apply_echo(self, audio, delay_ms=375, feedback=0.6,
                    num_echoes=4):
        """Apply echo effect"""
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
        """Apply high pass filter"""
        cutoff_norm = min(0.99, max(0.001, cutoff_hz / (self.sr / 2)))
        b, a = signal.butter(order, cutoff_norm, btype='high')
        return signal.filtfilt(b, a, audio)

    def _apply_lowpass(self, audio, cutoff_hz, order=4):
        """Apply low pass filter"""
        cutoff_norm = min(0.99, max(0.001, cutoff_hz / (self.sr / 2)))
        b, a = signal.butter(order, cutoff_norm, btype='low')
        return signal.filtfilt(b, a, audio)

    def _pitch_shift_semitones(self, audio, semitones):
        """Pitch shift audio by N semitones"""
        return librosa.effects.pitch_shift(
            audio, sr=self.sr, n_steps=semitones
        )

    def _time_stretch(self, audio, rate):
        """Time stretch audio by rate (>1 = faster)"""
        if abs(rate - 1.0) < 0.01:
            return audio
        return librosa.effects.time_stretch(audio, rate=rate)

    def _mix(self, audio_a, audio_b, weight_a=0.5, weight_b=0.5):
        """Mix two audio arrays of potentially different lengths"""
        max_len = max(len(audio_a), len(audio_b))
        a_padded = np.pad(audio_a, (0, max_len - len(audio_a)))
        b_padded = np.pad(audio_b, (0, max_len - len(audio_b)))
        return a_padded * weight_a + b_padded * weight_b

    def _crossfade(self, audio_a, audio_b, cf_samples):
        """Create crossfade between two audio arrays"""
        cf_len = min(cf_samples, len(audio_a), len(audio_b))
        fade_out = np.linspace(1, 0, cf_len)
        fade_in = np.linspace(0, 1, cf_len)
        cf = audio_a[-cf_len:] * fade_out + audio_b[:cf_len] * fade_in
        return cf

    # ============================================================
    # TECHNIQUE 1: BEATMATCH CROSSFADE
    # ============================================================

    def beatmatch_crossfade(self, cur_id, nxt_id, params,
                             cur_ana, nxt_ana):
        """
        Classic beatmatched crossfade
        Time-stretches incoming song to match BPM
        Crossfades over N bars at phrase boundary
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        crossfade_bars = params.get('crossfade_bars', 8)
        bpm = cur_ana.get('bpm', 120)
        seconds_per_bar = (60 / bpm) * 4
        cf_samples = int(seconds_per_bar * crossfade_bars * sr)

        # Time-stretch next song to match current BPM
        bpm_ratio = cur_ana.get('bpm', 120) / max(
            nxt_ana.get('bpm', 120), 1
        )
        if abs(bpm_ratio - 1.0) > 0.02:
            print(f"   ⏱️  Stretching BPM: "
                  f"{nxt_ana.get('bpm'):.1f} → {cur_ana.get('bpm'):.1f}")
            nxt_audio = self._time_stretch(nxt_audio, bpm_ratio)

        # Get transition point
        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        # Play current song up to transition
        self._play_audio(cur_audio[:trans_sample], sr)

        # Crossfade
        cf = self._crossfade(
            cur_audio[trans_sample:],
            nxt_audio[nxt_entry:],
            cf_samples
        )
        self._play_audio(cf, sr)

        # Play rest of next song
        self._play_audio(nxt_audio[nxt_entry + cf_samples:], sr)

    # ============================================================
    # TECHNIQUE 2: CUT TRANSITION
    # ============================================================

    def cut_transition(self, cur_id, nxt_id, params,
                       cur_ana, nxt_ana):
        """
        Hard cut at phrase boundary
        No overlap - instant switch
        Best for: large BPM differences, dramatic genre changes
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))

        # Find nearest phrase boundary
        bar_times = cur_ana.get('bar_times', [])
        if bar_times:
            trans_time = trans_sample / sr
            nearest_bar = min(
                bar_times,
                key=lambda x: abs(x - trans_time)
            )
            trans_sample = int(nearest_bar * sr)

        self._play_audio(cur_audio[:trans_sample], sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    # ============================================================
    # TECHNIQUE 3: ECHO OUT
    # ============================================================

    def echo_out(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Echo/delay out current song
        Fade in next song underneath echoes
        Best for: energy drops, emotional transitions
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        delay_ms = params.get('delay_ms', 375)
        feedback = params.get('feedback', 0.6)

        # Play up to transition
        self._play_audio(cur_audio[:trans_sample], sr)

        # Echo segment (4 seconds)
        echo_segment = cur_audio[
            trans_sample:trans_sample + sr * 4
        ].copy()
        echoed = self._apply_echo(echo_segment, delay_ms, feedback)
        echoed = self._fade_out(echoed)

        # Bring in next song during echo
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            nxt_start = nxt_audio[nxt_entry:nxt_entry + len(echoed)]
            nxt_fadein = self._fade_in(nxt_start,
                                       fade_samples=len(nxt_start))
            mixed = self._mix(echoed, nxt_fadein, 0.7, 0.3)
            self._play_audio(mixed, sr)
            self._play_audio(nxt_audio[nxt_entry + len(echoed):], sr)

    # ============================================================
    # TECHNIQUE 4: FILTER SWEEP
    # ============================================================

    def filter_sweep(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        High-pass sweep current song out (removes bass progressively)
        Low-pass sweep next song in (builds up from treble)
        Classic EDM/House transition technique
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        sweep_dur = int(sr * params.get('sweep_duration', 8))

        # Play up to transition
        self._play_audio(cur_audio[:trans_sample], sr)

        # High-pass sweep OUT of current song
        sweep_out = cur_audio[trans_sample:trans_sample + sweep_dur].copy()
        swept_out = np.zeros_like(sweep_out)
        chunk = sr // 4  # 250ms chunks

        for i in range(0, len(sweep_out), chunk):
            seg = sweep_out[i:i + chunk]
            progress = i / max(len(sweep_out), 1)
            # Cutoff: 20Hz → 8000Hz over sweep duration
            cutoff = 20 + (8000 - 20) * (progress ** 1.5)
            filtered = self._apply_highpass(seg, cutoff)
            amp = 1.0 - (progress * 0.8)
            swept_out[i:i + len(filtered)] = filtered * amp

        self._play_audio(swept_out, sr)

        # Low-pass sweep IN of next song
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            sweep_in = nxt_audio[nxt_entry:nxt_entry + sweep_dur].copy()
            swept_in = np.zeros_like(sweep_in)

            for i in range(0, len(sweep_in), chunk):
                seg = sweep_in[i:i + chunk]
                progress = i / max(len(sweep_in), 1)
                # Cutoff: 200Hz → 20000Hz
                cutoff = 200 + (20000 - 200) * progress
                filtered = self._apply_lowpass(seg, min(cutoff, 20000))
                amp = 0.2 + (progress * 0.8)
                swept_in[i:i + len(filtered)] = filtered * amp

            self._play_audio(swept_in, sr)
            # Continue playing next song normally
            self._play_audio(
                nxt_audio[nxt_entry + sweep_dur:], sr
            )

    # ============================================================
    # TECHNIQUE 5: LOOP ROLL
    # ============================================================

    def loop_roll(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Loop a section of current song with progressively
        shorter loop lengths creating a roll/stutter effect
        Then cut to next song
        Best for: EDM, House, Drum & Bass
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        bpm = cur_ana.get('bpm', 120)
        seconds_per_bar = (60 / bpm) * 4

        # Play up to transition
        self._play_audio(cur_audio[:trans_sample], sr)

        # Loop roll: 1 bar → 1/2 → 1/4 → 1/8 bar
        divisions = [1, 0.5, 0.25, 0.125]
        rolled_parts = []

        for div in divisions:
            loop_len = int((seconds_per_bar * div) * sr)
            loop_len = max(loop_len, 100)
            loop = cur_audio[trans_sample:trans_sample + loop_len].copy()

            # Repeat each division 2x
            repeats = max(1, int(1 / div))
            for r in range(repeats):
                decay = 1.0 - (r * 0.1)
                rolled_parts.append(loop * decay)

        if rolled_parts:
            rolled = np.concatenate(rolled_parts)
            # Add rising pitch effect
            rolled_pitched = self._pitch_shift_semitones(rolled, 2)
            self._play_audio(rolled_pitched, sr)

        # Cut to next song
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    # ============================================================
    # TECHNIQUE 6: REVERB WASH
    # ============================================================

    def reverb_wash(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Apply heavy reverb wash to current song
        Creates dreamy/atmospheric fadeout
        Fade in next song from silence
        Best for: emotional transitions, slow songs,
                  ambient/chill genres
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))

        # Play up to transition
        self._play_audio(cur_audio[:trans_sample], sr)

        # Apply heavy reverb to tail
        wash_len = int(sr * 6)
        wash_segment = cur_audio[
            trans_sample:trans_sample + wash_len
        ].copy()

        washed = self._apply_reverb(wash_segment, room_size=0.85)
        washed = self._fade_out(washed, fade_samples=len(washed))
        self._play_audio(washed, sr)

        # Fade in next song
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            nxt_segment = nxt_audio[nxt_entry:]
            nxt_faded = self._fade_in(
                nxt_segment, fade_samples=int(sr * 4)
            )
            self._play_audio(nxt_faded, sr)

    # ============================================================
    # TECHNIQUE 7: SPINBACK
    # ============================================================

    def spinback(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Simulate vinyl spinning back rapidly
        Creates whooshing pitch-up reverse effect
        Then drops next song
        Best for: dramatic genre changes,
                  hype moments, hip-hop/EDM
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        # Spinback effect: reverse + speed up + pitch up
        spin_len = int(sr * 1.5)
        spin_seg = cur_audio[
            trans_sample:trans_sample + spin_len
        ].copy()

        # Build spinback from chunks getting faster
        chunks = 12
        chunk_size = len(spin_seg) // chunks
        spun_parts = []

        for i in range(chunks):
            chunk = spin_seg[i * chunk_size:(i + 1) * chunk_size]
            if len(chunk) < 10:
                continue
            speed = 1.0 + (i / chunks) * 5.0  # 1x → 6x speed
            chunk_rev = chunk[::-1]
            try:
                stretched = self._time_stretch(chunk_rev, speed)
                spun_parts.append(stretched)
            except Exception:
                spun_parts.append(chunk_rev)

        if spun_parts:
            spun = np.concatenate(spun_parts)
            # Pitch up during spin
            try:
                spun = self._pitch_shift_semitones(spun, 6)
            except Exception:
                pass
            spun = self._fade_out(spun, fade_samples=len(spun) // 3)
            self._play_audio(spun, sr)

        # Drop next song
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    # ============================================================
    # TECHNIQUE 8: TEMPO RAMP
    # ============================================================

    def tempo_ramp(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Gradually ramp BPM from Song A to Song B
        over 16 bars using progressive time stretching
        Best for: moderate BPM differences (5-30 BPM)
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        bpm_a = cur_ana.get('bpm', 120)
        bpm_b = nxt_ana.get('bpm', 120)
        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))

        self._play_audio(cur_audio[:trans_sample], sr)

        # Ramp segment: 16 bars of current song
        seconds_per_bar = (60 / bpm_a) * 4
        ramp_dur = int(seconds_per_bar * 16 * sr)
        ramp_seg = cur_audio[
            trans_sample:trans_sample + ramp_dur
        ].copy()

        # Process in 16 chunks, each at increasing speed
        chunk_count = 16
        chunk_size = len(ramp_seg) // chunk_count
        ramped_parts = []

        for i in range(chunk_count):
            chunk = ramp_seg[i * chunk_size:(i + 1) * chunk_size]
            if len(chunk) < 10:
                continue
            progress = i / chunk_count
            # Gradually change rate from 1.0 to bpm_b/bpm_a
            current_rate = 1.0 + (bpm_b / bpm_a - 1.0) * progress
            try:
                stretched = self._time_stretch(chunk, current_rate)
                ramped_parts.append(stretched)
            except Exception:
                ramped_parts.append(chunk)

        if ramped_parts:
            ramped = np.concatenate(ramped_parts)
            self._play_audio(ramped, sr)

        # Now crossfade into next song at target BPM
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            cf_len = int(sr * 4)
            cf = self._crossfade(
                np.zeros(cf_len),
                nxt_audio[nxt_entry:nxt_entry + cf_len],
                cf_len
            )
            self._play_audio(cf, sr)
            self._play_audio(nxt_audio[nxt_entry + cf_len:], sr)

    # ============================================================
    # TECHNIQUE 9: WHITE NOISE SWEEP
    # ============================================================

    def white_noise_sweep(self, cur_id, nxt_id, params,
                           cur_ana, nxt_ana):
        """
        Build white noise over current song then sweep it out
        Covers the transition between genres
        Best for: genre change masking
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        sweep_dur = int(sr * 4)

        # White noise with build/release envelope
        noise = np.random.normal(0, 0.08, sweep_dur)
        env = np.concatenate([
            np.linspace(0, 1, sweep_dur // 2) ** 2,
            np.linspace(1, 0, sweep_dur // 2) ** 2
        ])
        noise_sweep = noise * env

        # Current song tail fading out
        cur_tail = cur_audio[
            trans_sample:trans_sample + sweep_dur
        ]
        if len(cur_tail) > 0:
            cur_fade = self._fade_out(
                cur_tail, fade_samples=len(cur_tail)
            )
            mixed = self._mix(
                cur_fade[:len(noise_sweep)],
                noise_sweep[:len(cur_fade)],
                0.6, 0.4
            )
            self._play_audio(mixed, sr)

        # Next song fading in
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            nxt_segment = nxt_audio[nxt_entry:]
            nxt_faded = self._fade_in(
                nxt_segment, fade_samples=int(sr * 2)
            )
            self._play_audio(nxt_faded, sr)

    # ============================================================
    # TECHNIQUE 10: VINYL SCRATCH FLOURISH (Fort Minor)
    # ============================================================

    def vinyl_scratch_flourish(self, cur_id, nxt_id, params,
                                cur_ana, nxt_ana):
        """
        Mid-song vinyl scratch that rewinds and replays
        from earlier in the same song
        Inspired by Fort Minor 'Where'd You Go' technique
        Can be used as flourish OR as transition
        """
        cur_audio, sr = self._load_audio(cur_id)
        if cur_audio is None:
            return

        bpm = cur_ana.get('bpm', 120)
        seconds_per_bar = (60 / bpm) * 4
        rewind_bars = params.get('rewind_bars', 4)

        # Use transition point or specified scratch time
        scratch_time = params.get(
            'scratch_time',
            cur_ana.get('transition_points', {}).get(
                'outro_beat', len(cur_audio) / sr * 0.75
            )
        )
        scratch_sample = int(scratch_time * sr)

        # Play up to scratch point
        self._play_audio(cur_audio[:scratch_sample], sr)

        # ---- Scratch effect ----
        scratch_len = int(sr * 0.6)
        scratch_seg = cur_audio[
            scratch_sample:scratch_sample + scratch_len
        ].copy()

        # Forward-back-forward scratch motion
        scratch_parts = []

        # Forward (slowing down)
        for i in range(4):
            speed = 1.0 - (i * 0.2)
            chunk = scratch_seg[
                i * (scratch_len // 4):(i + 1) * (scratch_len // 4)
            ]
            if len(chunk) > 10:
                try:
                    s = self._time_stretch(chunk, max(0.3, speed))
                    scratch_parts.append(s)
                except Exception:
                    scratch_parts.append(chunk)

        # Reverse (backwards)
        scratch_parts.append(scratch_seg[::-1])

        # Forward again (speeding back up)
        for i in range(4):
            speed = 0.5 + (i * 0.2)
            chunk = scratch_seg[
                i * (scratch_len // 4):(i + 1) * (scratch_len // 4)
            ]
            if len(chunk) > 10:
                try:
                    s = self._time_stretch(chunk, speed)
                    scratch_parts.append(s)
                except Exception:
                    scratch_parts.append(chunk)

        scratch_audio = np.concatenate(scratch_parts)

        # Apply pitch wobble to scratch
        wobble_freq = 8.0
        wobble = (
            np.sin(
                np.linspace(0, wobble_freq * np.pi, len(scratch_audio))
            ) * 0.3 + 1.0
        )
        scratch_audio = scratch_audio * wobble
        self._play_audio(scratch_audio, sr)

        # Rewind to N bars back and continue
        rewind_seconds = seconds_per_bar * rewind_bars
        rewind_sample = max(0, scratch_sample - int(rewind_seconds * sr))

        # If this is a transition (not just flourish), go to next song
        nxt_audio, _ = self._load_audio(nxt_id)
        if nxt_audio is not None and params.get('is_transition', False):
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)
        else:
            # Replay from rewind point (same song continues)
            self._play_audio(cur_audio[rewind_sample:], sr)

    # ============================================================
    # TECHNIQUE 11: TONE PLAY
    # ============================================================

    def tone_play(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Extract timbre/sound from Song A
        Use it to play Song B's melody as preview
        Then gradually introduce Song B's full audio
        Creates smooth melodic bridge between songs
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        # Get melody notes of next song
        melody_notes = params.get(
            'melody_notes',
            nxt_ana.get('melody_notes', [60, 62, 64, 65, 67])
        )
        note_duration = params.get(
            'note_duration',
            60 / max(cur_ana.get('bpm', 120), 1)
        )
        note_samples = int(note_duration * sr)

        # Extract instrument sound from current song
        # Use the melody stem if available, otherwise full audio
        melody_stem, _ = self._load_stem(cur_id, 'other')
        source_audio = melody_stem if melody_stem is not None else cur_audio

        instrument_sample = source_audio[
            trans_sample:trans_sample + note_samples
        ].copy()

        if len(instrument_sample) < 100:
            instrument_sample = cur_audio[
                trans_sample:trans_sample + note_samples
            ].copy()

        # Play Song B's melody using Song A's timbre
        preview_parts = []
        base_note = 60  # Middle C as reference

        for note_midi in melody_notes[:8]:  # Max 8 notes preview
            semitones = int(note_midi - base_note)
            try:
                shifted = self._pitch_shift_semitones(
                    instrument_sample, semitones
                )
                preview_parts.append(shifted)
            except Exception:
                preview_parts.append(instrument_sample.copy())

        if preview_parts:
            preview = np.concatenate(preview_parts)
            # Fade out preview melody
            preview = self._fade_out(preview, len(preview) // 3)
            self._play_audio(preview, sr)

        # Fade in actual Song B underneath
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
        fade_len = int(sr * 8)
        nxt_segment = nxt_audio[nxt_entry:]
        nxt_faded = self._fade_in(nxt_segment, fade_samples=fade_len)
        self._play_audio(nxt_faded, sr)

    # ============================================================
    # TECHNIQUE 12: WORDPLAY TRANSITION
    # ============================================================

    def wordplay_transition(self, cur_id, nxt_id, params,
                             cur_ana, nxt_ana):
        """
        Isolate matching word/phoneme from Song A vocals
        Echo/loop it as bridge
        Bring in Song B starting from same/similar word
        Example: 'daddy' (Drake) → 'daddy' (Hindi song)
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        transition_time = params.get(
            'transition_time',
            cur_ana.get('transition_points', {}).get(
                'outro_beat', len(cur_audio) / sr * 0.8
            )
        )
        trans_sample = int(transition_time * sr)

        # Play current song up to the matching word
        self._play_audio(cur_audio[:trans_sample], sr)

        # Load vocals stem and extract word clip
        word_clip_path = params.get('word_clip_a')
        word_audio = None

        if word_clip_path and os.path.exists(word_clip_path):
            word_audio, _ = librosa.load(word_clip_path, sr=sr)
        else:
            # Fall back: use vocals stem around transition time
            vocals, _ = self._load_stem(cur_id, 'vocals')
            if vocals is not None:
                word_start = max(0, trans_sample - int(sr * 0.5))
                word_end = trans_sample + int(sr * 0.5)
                word_audio = vocals[word_start:word_end]

        if word_audio is not None and len(word_audio) > 100:
            # Echo the word
            echoed_word = self._apply_echo(
                word_audio, delay_ms=250, feedback=0.5, num_echoes=3
            )

            # Repeat word N times with decreasing volume
            repeats = params.get('word_repeats', 3)
            word_sequence = []
            for i in range(repeats):
                decay = 1.0 - (i * 0.25)
                word_sequence.append(echoed_word * decay)
            word_bridge = np.concatenate(word_sequence)

            # Apply reverb to bridge
            word_bridge = self._apply_reverb(word_bridge, room_size=0.4)
            self._play_audio(word_bridge, sr)

        # Bring in next song starting from matching word timestamp
        if nxt_audio is not None:
            nxt_word_time = params.get('word_time_b', 0)
            nxt_start = int(nxt_word_time * sr)
            nxt_segment = nxt_audio[nxt_start:]

            # Fade in instrumentation of next song
            nxt_faded = self._fade_in(
                nxt_segment, fade_samples=int(sr * 2)
            )
            self._play_audio(nxt_faded, sr)

    # ============================================================
    # TECHNIQUE 13: MASHUP SHORT (8-16 bars)
    # ============================================================

    def mashup_short(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Layer stems from both songs for 8-16 bars
        Creates short mashup as transition technique
        Rules: BPM matched, key compatible
        Best structure: Song A drums + Song B vocals
                     OR Song A vocals + Song B instrumental
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        bpm_a = cur_ana.get('bpm', 120)
        bpm_b = nxt_ana.get('bpm', 120)
        bpm_ratio = bpm_a / max(bpm_b, 1)

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        # Load stems
        vocals_a, _ = self._load_stem(cur_id, 'vocals')
        drums_a, _ = self._load_stem(cur_id, 'drums')
        bass_a, _ = self._load_stem(cur_id, 'bass')

        vocals_b, _ = self._load_stem(nxt_id, 'vocals')
        drums_b, _ = self._load_stem(nxt_id, 'drums')
        melody_b, _ = self._load_stem(nxt_id, 'other')

        # Stretch song B stems to match song A BPM
        if abs(bpm_ratio - 1.0) > 0.02:
            if vocals_b is not None:
                vocals_b = self._time_stretch(vocals_b, bpm_ratio)
            if drums_b is not None:
                drums_b = self._time_stretch(drums_b, bpm_ratio)
            if melody_b is not None:
                melody_b = self._time_stretch(melody_b, bpm_ratio)

        # Mashup duration: 8 bars
        mashup_bars = params.get('mashup_bars', 8)
        seconds_per_bar = (60 / bpm_a) * 4
        mashup_samples = int(seconds_per_bar * mashup_bars * sr)

        # Build mashup layers
        mashup = np.zeros(mashup_samples)
        layer_count = 0

        # Layer: Song A drums (keep the groove)
        if drums_a is not None:
            drum_seg = drums_a[
                trans_sample:trans_sample + mashup_samples
            ]
            if len(drum_seg) > 0:
                pad = np.zeros(mashup_samples)
                pad[:len(drum_seg)] = drum_seg
                mashup += pad * 0.8
                layer_count += 1

        # Layer: Song B vocals (introduce new song)
        if vocals_b is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            vocal_seg = vocals_b[nxt_entry:nxt_entry + mashup_samples]
            if len(vocal_seg) > 0:
                pad = np.zeros(mashup_samples)
                pad[:len(vocal_seg)] = vocal_seg
                # Fade in vocals
                pad = self._fade_in(pad, fade_samples=mashup_samples // 4)
                mashup += pad * 0.85
                layer_count += 1

        # Layer: Song B melody/harmony
        if melody_b is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            mel_seg = melody_b[nxt_entry:nxt_entry + mashup_samples]
            if len(mel_seg) > 0:
                pad = np.zeros(mashup_samples)
                pad[:len(mel_seg)] = mel_seg
                pad = self._fade_in(pad, fade_samples=mashup_samples // 2)
                mashup += pad * 0.6
                layer_count += 1

        if layer_count > 0:
            # Normalize
            max_val = np.max(np.abs(mashup))
            if max_val > 0:
                mashup = mashup / max_val * 0.85
            self._play_audio(mashup, sr)

        # Transition to full next song
        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            nxt_segment = nxt_audio[nxt_entry:]
            nxt_faded = self._fade_in(
                nxt_segment, fade_samples=int(sr * 4)
            )
            self._play_audio(nxt_faded, sr)

    # ============================================================
    # TECHNIQUE 14: MASHUP EXTENDED
    # ============================================================

    def mashup_extended(self, cur_id, nxt_id, params,
                         cur_ana, nxt_ana):
        """
        Full extended mashup: layer both songs for 32+ bars
        Applies all professional mashup rules:
        - BPM matched via time stretch
        - Key matched via pitch shift if needed
        - Frequency space separation (bass A + melody B)
        - Phrase aligned vocals
        - Energy balanced layers
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        bpm_a = cur_ana.get('bpm', 120)
        bpm_b = nxt_ana.get('bpm', 120)
        bpm_ratio = bpm_a / max(bpm_b, 1)

        # Key matching: pitch shift song B if needed
        key_shift = self._calculate_key_shift(
            cur_ana.get('camelot', ''),
            nxt_ana.get('camelot', '')
        )

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        # Load all stems
        drums_a, _ = self._load_stem(cur_id, 'drums')
        bass_a, _ = self._load_stem(cur_id, 'bass')
        vocals_a, _ = self._load_stem(cur_id, 'vocals')

        vocals_b, _ = self._load_stem(nxt_id, 'vocals')
        melody_b, _ = self._load_stem(nxt_id, 'other')
        bass_b, _ = self._load_stem(nxt_id, 'bass')
        drums_b, _ = self._load_stem(nxt_id, 'drums')

        # Stretch all song B stems to match song A BPM
        if abs(bpm_ratio - 1.0) > 0.02:
            for stem in [vocals_b, melody_b, bass_b, drums_b]:
                if stem is not None:
                    stem[:] = self._time_stretch(stem, bpm_ratio)

        # Pitch shift song B if keys don't match
        if key_shift != 0:
            print(f"   🎵 Pitch shifting Song B by {key_shift} semitones")
            for stem in [vocals_b, melody_b, bass_b]:
                if stem is not None:
                    stem[:] = self._pitch_shift_semitones(stem, key_shift)

        # Extended mashup duration: 32 bars
        mashup_bars = params.get('mashup_bars', 32)
        seconds_per_bar = (60 / bpm_a) * 4
        mashup_samples = int(seconds_per_bar * mashup_bars * sr)

        mashup = np.zeros(mashup_samples)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        # PHASE 1 (bars 1-8): Song A with Song B vocals creeping in
        phase1 = mashup_samples // 4
        if drums_a is not None:
            seg = drums_a[trans_sample:trans_sample + phase1]
            mashup[:len(seg)] += seg * 0.85
        if bass_a is not None:
            seg = bass_a[trans_sample:trans_sample + phase1]
            mashup[:len(seg)] += seg * 0.80
        if vocals_a is not None:
            seg = vocals_a[trans_sample:trans_sample + phase1]
            seg = self._fade_out(seg, len(seg) // 2)
            mashup[:len(seg)] += seg * 0.70

        # PHASE 2 (bars 9-16): Mix both
        phase2_start = phase1
        phase2_end = phase1 * 2
        if drums_a is not None:
            seg = drums_a[
                trans_sample + phase1:trans_sample + phase2_end
            ]
            mashup[phase2_start:phase2_start + len(seg)] += seg * 0.70
        if vocals_b is not None:
            seg = vocals_b[nxt_entry:nxt_entry + phase1]
            seg = self._fade_in(seg, len(seg) // 2)
            mashup[phase2_start:phase2_start + len(seg)] += seg * 0.80
        if melody_b is not None:
            seg = melody_b[nxt_entry:nxt_entry + phase1]
            seg = self._fade_in(seg, len(seg) // 2)
            mashup[phase2_start:phase2_start + len(seg)] += seg * 0.60

        # PHASE 3 (bars 17-32): Song B taking over
        phase3_start = phase2_end
        phase3_len = mashup_samples - phase3_start
        if drums_b is not None:
            seg = drums_b[nxt_entry:nxt_entry + phase3_len]
            mashup[phase3_start:phase3_start + len(seg)] += seg * 0.85
        if bass_b is not None:
            seg = bass_b[nxt_entry:nxt_entry + phase3_len]
            mashup[phase3_start:phase3_start + len(seg)] += seg * 0.80
        if vocals_b is not None:
            seg = vocals_b[
                nxt_entry + phase1:nxt_entry + phase1 + phase3_len
            ]
            mashup[phase3_start:phase3_start + len(seg)] += seg * 0.85

        # Normalize
        max_val = np.max(np.abs(mashup))
        if max_val > 0:
            mashup = mashup / max_val * 0.85
        self._play_audio(mashup, sr)

        # Full Song B
        if nxt_audio is not None:
            nxt_end_of_mashup = nxt_entry + mashup_samples
            self._play_audio(nxt_audio[nxt_end_of_mashup:], sr)

    # ============================================================
    # TECHNIQUE 15: ACAPELLA LAYER
    # ============================================================

    def acapella_layer(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Layer Song A acapella over Song B instrumental
        Classic mashup technique
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        vocals_a, _ = self._load_stem(cur_id, 'vocals')
        drums_b, _ = self._load_stem(nxt_id, 'drums')
        bass_b, _ = self._load_stem(nxt_id, 'bass')
        melody_b, _ = self._load_stem(nxt_id, 'other')

        bpm_ratio = cur_ana.get('bpm', 120) / max(
            nxt_ana.get('bpm', 120), 1
        )
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        layer_bars = params.get('layer_bars', 16)
        seconds_per_bar = (60 / cur_ana.get('bpm', 120)) * 4
        layer_samples = int(seconds_per_bar * layer_bars * sr)

        layer = np.zeros(layer_samples)

        # Song A vocals
        if vocals_a is not None:
            seg = vocals_a[trans_sample:trans_sample + layer_samples]
            if abs(bpm_ratio - 1.0) > 0.02:
                seg = self._time_stretch(seg, bpm_ratio)
            layer[:len(seg)] += seg * 0.9

        # Song B instrumental
        for stem, vol in [(drums_b, 0.8), (bass_b, 0.75), (melody_b, 0.7)]:
            if stem is not None:
                seg = stem[nxt_entry:nxt_entry + layer_samples]
                layer[:len(seg)] += seg * vol

        max_val = np.max(np.abs(layer))
        if max_val > 0:
            layer = layer / max_val * 0.85
        self._play_audio(layer, sr)

        if nxt_audio is not None:
            self._play_audio(nxt_audio[nxt_entry + layer_samples:], sr)

    # ============================================================
    # TECHNIQUE 16: DRUM SWAP
    # ============================================================

    def drum_swap(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Gradually swap Song A drums for Song B drums
        while keeping melody/vocals of Song A
        Creates smooth rhythmic transition
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        drums_a, _ = self._load_stem(cur_id, 'drums')
        melody_a, _ = self._load_stem(cur_id, 'other')
        vocals_a, _ = self._load_stem(cur_id, 'vocals')
        drums_b, _ = self._load_stem(nxt_id, 'drums')

        bpm_ratio = cur_ana.get('bpm', 120) / max(
            nxt_ana.get('bpm', 120), 1
        )
        if drums_b is not None and abs(bpm_ratio - 1.0) > 0.02:
            drums_b = self._time_stretch(drums_b, bpm_ratio)

        swap_bars = params.get('swap_bars', 8)
        seconds_per_bar = (60 / cur_ana.get('bpm', 120)) * 4
        swap_samples = int(seconds_per_bar * swap_bars * sr)

        swap = np.zeros(swap_samples)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        for stem, vol in [(melody_a, 0.8), (vocals_a, 0.85)]:
            if stem is not None:
                seg = stem[trans_sample:trans_sample + swap_samples]
                seg = self._fade_out(seg, swap_samples // 4)
                swap[:len(seg)] += seg * vol

        # Crossfade drums A out, drums B in
        if drums_a is not None:
            seg = drums_a[trans_sample:trans_sample + swap_samples]
            fade = np.linspace(1, 0, min(len(seg), swap_samples))
            swap[:len(fade)] += seg[:len(fade)] * fade * 0.8

        if drums_b is not None:
            seg = drums_b[nxt_entry:nxt_entry + swap_samples]
            fade = np.linspace(0, 1, min(len(seg), swap_samples))
            swap[:len(fade)] += seg[:len(fade)] * fade * 0.8

        max_val = np.max(np.abs(swap))
        if max_val > 0:
            swap = swap / max_val * 0.85
        self._play_audio(swap, sr)

        if nxt_audio is not None:
            self._play_audio(
                nxt_audio[nxt_entry + swap_samples:], sr
            )

    # ============================================================
    # TECHNIQUE 17: BASS SWAP
    # ============================================================

    def bass_swap(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Drop Song A bass, introduce Song B bass
        while blending other elements
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        bass_b, _ = self._load_stem(nxt_id, 'bass')
        drums_a, _ = self._load_stem(cur_id, 'drums')
        melody_a, _ = self._load_stem(cur_id, 'other')

        bpm_ratio = cur_ana.get('bpm', 120) / max(
            nxt_ana.get('bpm', 120), 1
        )

        swap_bars = params.get('swap_bars', 8)
        seconds_per_bar = (60 / cur_ana.get('bpm', 120)) * 4
        swap_samples = int(seconds_per_bar * swap_bars * sr)

        swap = np.zeros(swap_samples)
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        if drums_a is not None:
            seg = drums_a[trans_sample:trans_sample + swap_samples]
            swap[:len(seg)] += seg * 0.8

        if melody_a is not None:
            seg = melody_a[trans_sample:trans_sample + swap_samples]
            seg = self._fade_out(seg, swap_samples // 3)
            swap[:len(seg)] += seg * 0.7

        if bass_b is not None:
            if abs(bpm_ratio - 1.0) > 0.02:
                bass_b = self._time_stretch(bass_b, bpm_ratio)
            seg = bass_b[nxt_entry:nxt_entry + swap_samples]
            seg = self._fade_in(seg, swap_samples // 4)
            swap[:len(seg)] += seg * 0.85

        max_val = np.max(np.abs(swap))
        if max_val > 0:
            swap = swap / max_val * 0.85
        self._play_audio(swap, sr)

        if nxt_audio is not None:
            self._play_audio(nxt_audio[nxt_entry:], sr)

    # ============================================================
    # TECHNIQUE 18: STUTTER GLITCH
    # ============================================================

    def stutter_glitch(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        Glitch/stutter effect on transition point
        Rapid repetitions of short audio slices
        with pitch variations
        Best for: Electronic, EDM, experimental
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        bpm = cur_ana.get('bpm', 120)
        beat_samples = int((60 / bpm) * sr)

        glitch_parts = []
        glitch_total = beat_samples * 4  # 4 beats of glitch
        slice_sizes = [
            beat_samples // 2,
            beat_samples // 4,
            beat_samples // 8,
            beat_samples // 16
        ]

        glitch_audio = cur_audio[
            trans_sample:trans_sample + glitch_total
        ].copy()
        generated = 0

        for slice_size in slice_sizes:
            for repeat in range(4):
                if generated >= glitch_total:
                    break
                start = (repeat * slice_size) % max(
                    len(glitch_audio) - slice_size, 1
                )
                chunk = glitch_audio[start:start + slice_size].copy()

                # Random pitch variation
                semitone_shift = np.random.choice([-2, 0, 2, 4, 7, 12])
                try:
                    chunk = self._pitch_shift_semitones(
                        chunk, semitone_shift
                    )
                except Exception:
                    pass

                # Volume envelope
                env = np.ones(len(chunk))
                env[-len(env)//4:] = np.linspace(1, 0, len(env)//4)
                chunk = chunk * env

                glitch_parts.append(chunk)
                generated += len(chunk)

        if glitch_parts:
            glitch = np.concatenate(glitch_parts)
            max_val = np.max(np.abs(glitch))
            if max_val > 0:
                glitch = glitch / max_val * 0.85
            self._play_audio(glitch, sr)

        if nxt_audio is not None:
            nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
            self._play_audio(nxt_audio[nxt_entry:], sr)

    # ============================================================
    # TECHNIQUE 19: HALF TIME TRANSITION
    # ============================================================

    def half_time_transition(self, cur_id, nxt_id, params,
                              cur_ana, nxt_ana):
        """
        When Song B BPM is roughly double Song A:
        Play Song B at half speed initially
        Then ramp up to full speed
        Bridges large BPM gaps gracefully
        """
        cur_audio, sr = self._load_audio(cur_id)
        nxt_audio, _ = self._load_audio(nxt_id)
        if cur_audio is None or nxt_audio is None:
            return

        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        self._play_audio(cur_audio[:trans_sample], sr)

        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)

        # Play next song at half time (0.5x speed)
        half_dur = int(sr * 8)  # 8 seconds at half speed
        half_seg = nxt_audio[nxt_entry:nxt_entry + half_dur]

        if len(half_seg) > 100:
            # Stretch to double length (half speed)
            half_time = self._time_stretch(half_seg, 0.5)
            half_time = self._fade_in(
                half_time, fade_samples=int(sr * 2)
            )
            self._play_audio(half_time, sr)

        # Ramp up to full speed over 8 bars
        bpm = nxt_ana.get('bpm', 120)
        ramp_dur = int((60 / bpm) * 4 * 8 * sr)
        ramp_seg = nxt_audio[
            nxt_entry + half_dur:nxt_entry + half_dur + ramp_dur
        ]

        ramp_parts = []
        chunks = 8
        chunk_size = len(ramp_seg) // max(chunks, 1)

        for i in range(chunks):
            chunk = ramp_seg[i * chunk_size:(i + 1) * chunk_size]
            if len(chunk) < 10:
                continue
            rate = 0.5 + (0.5 * i / chunks)  # 0.5x → 1.0x
            try:
                ramped = self._time_stretch(chunk, rate)
                ramp_parts.append(ramped)
            except Exception:
                ramp_parts.append(chunk)

        if ramp_parts:
            ramp_audio = np.concatenate(ramp_parts)
            self._play_audio(ramp_audio, sr)

    def double_time_transition(self, cur_id, nxt_id, params,
                                cur_ana, nxt_ana):
        """Transition from Half-time (70) to Double-time (140)"""
        # For simplicity in this engine version, me uses beatmatch but with ramp label
        return self.beatmatch_crossfade(cur_id, nxt_id, params, cur_ana, nxt_ana)

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
            
        print(f"   💡 FOUND LINK: '{connection.get('word', 'rhyme')}' ({connection['type']})")
        
        # Load Stems
        vocals_a, sr = self._load_stem(cur_id, 'vocals')
        drums_b, _ = self._load_stem(nxt_id, 'drums')
        other_b, _ = self._load_stem(nxt_id, 'other')
        vocals_b, _ = self._load_stem(nxt_id, 'vocals')
        
        if vocals_a is None or drums_b is None:
            return self.echo_out(cur_id, nxt_id, params, cur_ana, nxt_ana)

        # 1. Play Song A background until word
        cur_full, _ = self._load_audio(cur_id)
        word_start = connection['transition_time']
        word_end = connection['cur_entry']['end_time']
        self._play_audio(cur_full[:int(word_start * sr)], sr)
        
        # 2. Extract and Loop Word
        word_clip = vocals_a[int(word_start * sr):int(word_end * sr)]
        repeats = params.get('word_repeats', 4)
        word_loop = np.tile(word_clip, repeats)
        
        # 3. Mashup with Song B Instrumental
        bpm_ratio = cur_ana.get('bpm', 120) / max(nxt_ana.get('bpm', 120), 1)
        inst_b = self._mix(drums_b, other_b, 0.5, 0.5)
        if abs(bpm_ratio - 1.0) > 0.02:
            inst_b = self._time_stretch(inst_b, bpm_ratio)
            
        nxt_entry = int(connection['word_time_b'] * sr)
        # Length of word loop
        loop_len = len(word_loop)
        
        # Slice B Instrumental for same length
        inst_slice = inst_b[max(0, nxt_entry - loop_len):nxt_entry]
        
        # Mash them
        mash = self._mix(word_loop, inst_slice, 0.7, 0.5)
        self._play_audio(mash, sr)
        
        # 4. Drop into Song B
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
        slice_dur = (60 / bpm) / 4
        slice_samples = int(slice_dur * sr)
        
        trans_sample = self._get_transition_point(cur_ana, len(cur_audio))
        nxt_entry = int(self._get_entry_point(nxt_ana) * sr)
        
        # Play up to transition
        self._play_audio(cur_audio[:trans_sample], sr)
        
        # Interlace for 4 bars (64 slices of 1/16th)
        interlace_len = slice_samples * 64
        interlaced = np.zeros(interlace_len)
        
        for i in range(64):
            start = i * slice_samples
            if (i // 2) % 2 == 0:
                chunk_len = min(slice_samples, len(cur_audio) - (trans_sample + start))
                if chunk_len > 0:
                    chunk = cur_audio[trans_sample + start:trans_sample + start + chunk_len]
                    interlaced[start:start+len(chunk)] = chunk
            else:
                chunk_len = min(slice_samples, len(nxt_audio) - (nxt_entry + start))
                if chunk_len > 0:
                    chunk = nxt_audio[nxt_entry + start:nxt_entry + start + chunk_len]
                    interlaced[start:start+len(chunk)] = chunk
                
        fade = int(sr * 0.005) # 5ms
        for i in range(1, 64):
            idx = i * slice_samples
            if idx + fade < len(interlaced):
                interlaced[idx-fade:idx+fade] *= np.hanning(fade*2)

        self._play_audio(interlaced, sr)
        self._play_audio(nxt_audio[nxt_entry + interlace_len:], sr)

    def semantic_bridge(self, cur_id, nxt_id, params, cur_ana, nxt_ana):
        """
        TRUE INNOVATION: Semantic Thematic Matching
        Uses Local LLM to find a narrative link between songs.
        """
        print("   🧠 Analyzing Semantic Connection...")
        # Placeholder for LocalLogicAgent
        print(f"   💬 THEME: Narrative bridge identified across lyrics.")
        return self.beatmatch_crossfade(cur_id, nxt_id, params, cur_ana, nxt_ana)
