import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import json
import math

class StickFigureGen:
    """
    Generates stick figure animations based on
    lyric sentiment and song story
    Switches to equalizer for instrumentals
    """
    def __init__(self, config):
        self.config = config
        self.width = config['visual']['width']
        self.height = config['visual']['height']
        self.frame_count = 0
        self.bg_color = (10, 10, 20)
        self.figure_color = (255, 255, 255)

    def generate_frame(self, lyrics_data, beat_time,
                       energy, sentiment, current_word=None):
        """
        Generate a single animation frame
        Returns PIL Image
        """
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        has_lyrics = (
            lyrics_data is not None and
            lyrics_data.get('text', '').strip() != ''
        )

        if has_lyrics:
            self._draw_stick_scene(
                draw, sentiment, energy, beat_time, current_word
            )
        else:
            self._draw_equalizer(draw, energy, beat_time)

        # Always draw beat pulse overlay
        self._draw_beat_pulse(draw, energy, beat_time)

        self.frame_count += 1
        return img

    def _draw_stick_scene(self, draw, sentiment, energy,
                           beat_time, current_word):
        """Draw scene based on song sentiment"""

        if sentiment == 'happy':
            self.bg_color = (20, 15, 5)
            self.figure_color = (255, 220, 50)
        elif sentiment == 'sad':
            self.bg_color = (5, 10, 25)
            self.figure_color = (150, 180, 255)
        elif sentiment == 'angry':
            self.bg_color = (25, 5, 5)
            self.figure_color = (255, 80, 50)
        elif sentiment == 'hype':
            self.bg_color = (15, 5, 25)
            self.figure_color = (200, 50, 255)
        elif sentiment == 'love':
            self.bg_color = (20, 5, 15)
            self.figure_color = (255, 100, 180)
        else:
            self.bg_color = (10, 10, 20)
            self.figure_color = (255, 255, 255)

        # Redraw background with new color
        draw.rectangle(
            [0, 0, self.width, self.height],
            fill=self.bg_color
        )

        # Draw ground line
        ground_y = int(self.height * 0.75)
        draw.line(
            [(0, ground_y), (self.width, ground_y)],
            fill=(80, 80, 80), width=2
        )

        # Beat-synced bounce
        bounce = int(
            math.sin(beat_time * math.pi * 2) * 10 * energy * 5
        )

        if sentiment == 'happy':
            self._draw_dancing_figure(
                draw, self.width // 3,
                ground_y + bounce,
                self.figure_color, beat_time
            )
            self._draw_dancing_figure(
                draw, 2 * self.width // 3,
                ground_y + bounce,
                self.figure_color, beat_time + 0.5
            )

        elif sentiment == 'sad':
            self._draw_sad_figure(
                draw, self.width // 2,
                ground_y, self.figure_color
            )
            self._draw_rain(draw)

        elif sentiment == 'love':
            self._draw_dancing_figure(
                draw, self.width // 2 - 80,
                ground_y, self.figure_color, beat_time
            )
            self._draw_dancing_figure(
                draw, self.width // 2 + 80,
                ground_y, (255, 150, 200), beat_time
            )
            self._draw_hearts(draw, beat_time)

        elif sentiment == 'hype':
            for i, x in enumerate([
                self.width // 5,
                2 * self.width // 5,
                3 * self.width // 5,
                4 * self.width // 5
            ]):
                jump = int(abs(math.sin(
                    beat_time * math.pi * 2 + i * 0.5
                )) * 80 * energy * 3)
                self._draw_dancing_figure(
                    draw, x, ground_y - jump,
                    self.figure_color,
                    beat_time + i * 0.25
                )
        else:
            self._draw_dancing_figure(
                draw, self.width // 2,
                ground_y + bounce,
                self.figure_color, beat_time
            )

    def _draw_stick_figure(self, draw, cx, ground_y, color,
                            arm_angle=0, leg_angle=0):
        """Draw a basic stick figure at position cx, ground_y"""
        scale = 60

        # Head
        head_r = scale // 3
        head_cx = cx
        head_cy = ground_y - scale * 2 - head_r
        draw.ellipse(
            [head_cx - head_r, head_cy - head_r,
             head_cx + head_r, head_cy + head_r],
            outline=color, width=3
        )

        # Body
        body_top = head_cy + head_r
        body_bot = ground_y - scale
        draw.line(
            [(cx, body_top), (cx, body_bot)],
            fill=color, width=3
        )

        # Arms
        arm_y = body_top + scale // 2
        arm_len = scale * 0.8
        draw.line([
            (int(cx - arm_len * math.cos(arm_angle)),
             int(arm_y - arm_len * math.sin(arm_angle))),
            (cx, arm_y),
            (int(cx + arm_len * math.cos(arm_angle)),
             int(arm_y + arm_len * math.sin(arm_angle)))
        ], fill=color, width=3)

        # Legs
        draw.line([
            (cx, body_bot),
            (int(cx - scale * 0.6 * math.sin(leg_angle)),
             ground_y)
        ], fill=color, width=3)
        draw.line([
            (cx, body_bot),
            (int(cx + scale * 0.6 * math.sin(leg_angle)),
             ground_y)
        ], fill=color, width=3)

    def _draw_dancing_figure(self, draw, cx, ground_y,
                              color, beat_time):
        """Stick figure dancing with beat"""
        arm_angle = (
            0.5 + math.sin(beat_time * math.pi * 4) * 0.8
        )
        leg_angle = (
            0.3 + abs(math.sin(beat_time * math.pi * 2)) * 0.6
        )
        self._draw_stick_figure(
            draw, cx, ground_y, color, arm_angle, leg_angle
        )

    def _draw_sad_figure(self, draw, cx, ground_y, color):
        """Sad drooping stick figure"""
        self._draw_stick_figure(
            draw, cx, ground_y, color,
            arm_angle=-0.3,
            leg_angle=0.1
        )

    def _draw_rain(self, draw):
        """Draw rain drops"""
        import random
        random.seed(self.frame_count // 3)
        for _ in range(50):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            draw.line(
                [(x, y), (x - 2, y + 15)],
                fill=(100, 150, 255), width=1
            )

    def _draw_hearts(self, draw, beat_time):
        """Draw floating hearts between figures"""
        pulse = abs(math.sin(beat_time * math.pi * 2))
        size = int(20 + pulse * 15)
        cx = self.width // 2
        cy = int(self.height * 0.5)

        for dx in range(-size, size):
            for dy in range(-size, size):
                if (dx*dx + dy*dy) < size*size // 2:
                    draw.point(
                        (cx + dx, cy + dy),
                        fill=(255, 50, 100)
                    )

    def _draw_equalizer(self, draw, energy, beat_time):
        """Draw frequency equalizer bars for instrumentals"""
        draw.rectangle(
            [0, 0, self.width, self.height],
            fill=self.bg_color
        )

        bar_count = 64
        bar_width = self.width // bar_count
        center_y = self.height // 2

        for i in range(bar_count):
            freq_factor = math.sin(
                i * 0.3 + beat_time * 5
            ) * 0.5 + 0.5
            height = int(energy * freq_factor * self.height * 0.8)

            r = int(50 + (i / bar_count) * 200)
            g = int(20)
            b = int(200 - (i / bar_count) * 100)
            color = (r, g, b)

            x = i * bar_width
            draw.rectangle(
                [x, center_y - height // 2,
                 x + bar_width - 2, center_y + height // 2],
                fill=color
            )

    def _draw_beat_pulse(self, draw, energy, beat_time):
        """Subtle beat pulse overlay on edges"""
        pulse = abs(math.sin(beat_time * math.pi * 2))
        alpha = int(pulse * energy * 100)
        if alpha > 10:
            draw.rectangle(
                [0, 0, self.width, 5],
                fill=(alpha, alpha // 2, alpha * 2)
            )
            draw.rectangle(
                [0, self.height - 5, self.width, self.height],
                fill=(alpha, alpha // 2, alpha * 2)
            )
