import json
import time
import threading
try:
    import obsws_python as obs
except:
    obs = None

class OBSBridge:
    """
    Controls OBS Studio for YouTube livestream
    Updates overlays in real-time
    """
    def __init__(self, config):
        self.config = config
        self.ws = None
        self.connected = False
        self.port = config['visual']['obs_websocket_port']
        self.password = config['visual']['obs_websocket_password']

    def connect(self):
        """Connect to OBS WebSocket"""
        try:
            self.ws = obs.ReqClient(
                host='localhost',
                port=self.port,
                password=self.password,
                timeout=3
            )
            self.connected = True
            print("✅ Connected to OBS")
        except Exception as e:
            print(f"⚠️  OBS not connected: {e}")
            print("   App will run without OBS integration")
            self.connected = False

    def update_display(self, current_analysis, next_analysis, technique):
        """Update all OBS overlays"""
        if not self.connected:
            return

        try:
            # Update song info text
            self._update_text_source(
                'current_song',
                f"NOW: {current_analysis.get('title', 'Unknown')[:40]}"
            )

            self._update_text_source(
                'next_song',
                f"NEXT: {next_analysis.get('title', 'Unknown')[:40]}"
            )

            self._update_text_source(
                'bpm_display',
                f"BPM: {current_analysis.get('bpm', 0):.0f}"
            )

            self._update_text_source(
                'key_display',
                f"KEY: {current_analysis.get('camelot', 'N/A')}"
            )

            self._update_text_source(
                'technique_display',
                f"TECHNIQUE: {technique.replace('_', ' ').upper()}"
            )

        except Exception as e:
            print(f"⚠️  OBS update error: {e}")

    def _update_text_source(self, source_name, text):
        """Update a text source in OBS"""
        if not self.connected:
            return
        try:
            self.ws.set_input_settings(
                name=source_name,
                settings={'text': text},
                overlay=True
            )
        except Exception:
            pass

    def trigger_scene_change(self, scene_name):
        """Switch OBS scene"""
        if not self.connected:
            return
        try:
            self.ws.set_current_program_scene(scene_name)
        except Exception as e:
            print(f"⚠️  Scene change failed: {e}")
