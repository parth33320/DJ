#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import logging

try:
    import imageio_ffmpeg
    FFMPEG_BIN = shutil.which('ffmpeg') or imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_BIN = shutil.which('ffmpeg') or 'ffmpeg'

logging.basicConfig(level=logging.INFO, format='[GenerateDemo] %(asctime)s - %(message)s')

def generate_demo_video():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    output_dir = os.path.join(root_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)

    audio_path = os.path.join(output_dir, 'latest_mix.wav')
    video_path = os.path.join(root_dir, 'docs', 'demo_video.webm')
    output_demo_path = os.path.join(output_dir, 'demo_with_audio.mp4')

    # 1. Fallback Audio check
    if not os.path.exists(audio_path):
        logging.warning(f"Audio file missing at {audio_path}. Generating dummy audio...")
        try:
            subprocess.run([
                FFMPEG_BIN, '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=10',
                '-c:a', 'pcm_s16le', audio_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logging.error(f"Failed to generate dummy audio: {e}")

    # 2. Fallback Video check
    if not os.path.exists(video_path):
        logging.warning(f"Video file missing at {video_path}. Generating dummy video...")
        os.makedirs(os.path.dirname(video_path), exist_ok=True)
        try:
            subprocess.run([
                FFMPEG_BIN, '-y', '-f', 'lavfi', '-i', 'testsrc=size=1280x720:rate=30',
                '-t', '10', '-c:v', 'libvpx-vp9', video_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logging.error(f"Failed to generate dummy video: {e}")

    # 3. Mux Video + Audio using FFmpeg
    logging.info(f"🎬 Muxing {video_path} with {audio_path} into {output_demo_path}...")
    cmd = [
        FFMPEG_BIN,
        '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_demo_path
    ]

    try:
        res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"✅ Demo video successfully created at: {output_demo_path}")
        return output_demo_path
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ FFmpeg muxing failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return None

if __name__ == '__main__':
    generate_demo_video()
