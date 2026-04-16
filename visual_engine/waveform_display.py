import numpy as np
from PIL import Image, ImageDraw
import librosa

class WaveformDisplay:
    """
    DJ-style dual waveform display
    Shows current and incoming song waveforms
    with playhead position
    """
    def __init__(self, config):
        self.config = config
        self.width = config['visual']['width']
        self.height = config['visual']['height']
        self.waveform_height = 80
        self.waveform_a = None
        self.waveform_b = None

    def load_waveform(self, filepath, song_id):
        """Pre-compute waveform data for display"""
        try:
            y, sr = librosa.load(filepath, sr=8000, mono=True, duration=300)
            # Downsample to width pixels
            chunk_size = max(1, len(y) // self.width)
            waveform = []
            for i in range(0, len(y) - chunk_size, chunk_size):
                chunk = y[i:i + chunk_size]
                waveform.append(float(np.max(np.abs(chunk))))
            return waveform[:self.width]
        except Exception:
            return [0.1] * self.width

    def draw_waveforms(self, draw, waveform_a, waveform_b,
                       progress_a, bpm_a, bpm_b, technique):
        """
        Draw dual waveform display at bottom of screen
        """
        panel_y = self.height - 180
        panel_height = 170
        panel_color = (15, 15, 25)

        # Background panel
        draw.rectangle(
            [0, panel_y, self.width, self.height],
            fill=panel_color
        )

        # Divider line
        draw.line(
            [(0, panel_y), (self.width, panel_y)],
            fill=(60, 60, 80), width=1
        )

        # Waveform A (current song) - top half of panel
        wf_a_y = panel_y + 10
        self._draw_single_waveform(
            draw,
            waveform_a,
            wf_a_y,
            self.waveform_height,
            progress_a,
            color=(0, 200, 255),
            played_color=(0, 80, 120),
            label=f"NOW PLAYING | BPM: {bpm_a:.0f}"
        )

        # Waveform B (next song) - bottom half
        wf_b_y = panel_y + self.waveform_height + 25
        self._draw_single_waveform(
            draw,
            waveform_b,
            wf_b_y,
            self.waveform_height,
            0,  # Next song hasn't started
            color=(255, 100, 50),
            played_color=(100, 40, 20),
            label=f"NEXT UP | BPM: {bpm_b:.0f}"
        )

        # Technique indicator
        draw.text(
            (self.width // 2 - 150, panel_y + 65),
            f"▶ {technique.replace('_', ' ').upper()}",
            fill=(200, 200, 50)
        )

    def _draw_single_waveform(self, draw, waveform, y_start,
                               height, progress, color,
                               played_color, label):
        """Draw a single waveform"""
        if not waveform:
            waveform = [0.1] * self.width

        center_y = y_start + height // 2
        playhead_x = int(progress * self.width)

        for x, amp in enumerate(waveform[:self.width]):
            bar_height = int(amp * height * 0.9)
            bar_height = max(2, bar_height)

            c = played_color if x < playhead_x else color
            draw.rectangle(
                [x, center_y - bar_height // 2,
                 x + 1, center_y + bar_height // 2],
                fill=c
            )

        # Playhead line
        draw.line(
            [(playhead_x, y_start), (playhead_x, y_start + height)],
            fill=(255, 255, 0), width=2
        )

        # Label
        draw.text((10, y_start), label, fill=(180, 180, 180))
