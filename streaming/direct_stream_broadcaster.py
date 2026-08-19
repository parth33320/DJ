import os
import sys
import time
import logging
import subprocess
import threading
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO, format='[DirectBroadcaster] %(asctime)s - %(message)s')

class DirectStreamBroadcaster:
    """
    Direct Python FFmpeg live stream broadcaster service.
    Streams output/continuous_stream_master.mp3 paired with background image/video
    directly to YouTube or Restream RTMP endpoints without needing OBS GUI.
    """
    def __init__(self, config: Dict, rtmp_url: Optional[str] = None):
        self.config = config
        streaming_cfg = config.get('streaming', {})
        self.rtmp_url = rtmp_url or streaming_cfg.get('rtmp_url', 'rtmp://a.rtmp.youtube.com/live2/x/stream-key')
        self.audio_source = os.path.abspath("output/current_pair.mp3")

        # Fallback background image
        self.bg_image = os.path.abspath("assets/bg.jpg")
        if not os.path.exists(self.bg_image):
            os.makedirs(os.path.dirname(self.bg_image), exist_ok=True)
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720',
                    '-vframes', '1', self.bg_image
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None

    def build_ffmpeg_command(self) -> list:
        """
        Builds FFmpeg CLI argument list for stable continuous RTMP broadcasting.
        """
        cmd = [
            'ffmpeg',
            '-y',
            '-re', # Read input at native frame rate
            '-loop', '1',
            '-i', self.bg_image,
            '-stream_loop', '-1',
            '-i', self.audio_source,
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-maxrate', '3000k',
            '-bufsize', '6000k',
            '-pix_fmt', 'yuv420p',
            '-g', '60', # Keyframe every 2 seconds at 30fps
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ac', '2',
            '-ar', '44100',
            '-shortest',
            '-f', 'flv',
            self.rtmp_url
        ]
        return cmd

    def start_stream(self) -> bool:
        """Starts streaming process in background."""
        if self.process and self.process.poll() is None:
            logging.info("⚠️ Streaming process is already running.")
            return True

        if not os.path.exists(self.audio_source):
            logging.warning(f"⚠️ Master audio source not found at {self.audio_source}. Generating dummy source...")
            os.makedirs(os.path.dirname(self.audio_source), exist_ok=True)
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=10',
                    '-c:a', 'libmp3lame', self.audio_source
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        cmd = self.build_ffmpeg_command()
        logging.info(f"🚀 Launching Direct FFmpeg Broadcaster: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            self.is_running = True

            # Start health monitor
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            return True
        except Exception as e:
            logging.error(f"❌ Failed to start FFmpeg broadcaster: {e}")
            return False

    def check_health(self) -> bool:
        return self.check_stream_health()

    def check_stream_health(self) -> bool:
        """Returns True if the FFmpeg streaming process is active."""
        if self.process is not None and self.process.poll() is None:
            return True
        return False

    def stop_stream(self):
        """Stops streaming process gracefully."""
        self.is_running = False
        if self.process and self.process.poll() is None:
            logging.info("🛑 Terminating FFmpeg broadcaster process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        logging.info("✅ FFmpeg broadcaster stopped.")

    def _monitor_loop(self):
        """Auto-restarts FFmpeg process if it dies unexpectedly."""
        while self.is_running:
            time.sleep(5)
            if self.is_running and not self.check_stream_health():
                logging.warning("⚠️ FFmpeg stream died unexpectedly! Auto-restarting stream...")
                self.start_stream()
