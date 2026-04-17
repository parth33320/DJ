import os
from typing import Dict, Tuple

class TransitionAgent:
    def __init__(self, config):
        self.config = config
        self.history = []
        self.tot_worker = None
        
        # Try to load Tree of Thoughts worker safely
        try:
            from ai_brain.local_swarm.local_llm_worker import LocalTreeOfThoughtsWorker
            self.tot_worker = LocalTreeOfThoughtsWorker(model_name="deepseek-r1:8b")
            print("✅ TransitionAgent using Tree of Thoughts!")
        except Exception as e:
            print(f"⚠️ Tree of Thoughts not available: {e}")

    def decide_transition(self, current_song: str, next_song: str, cur_ana: Dict, nxt_ana: Dict) -> Tuple[str, Dict]:
        """
        Decide the best transition technique.
        Uses Tree of Thoughts if available and alive, otherwise falls back to fast rules.
        """
        # 1. Prepare rich metadata for the Tree of Thoughts LLM
        track_a = {
            "name": current_song,
            "bpm": cur_ana.get('bpm', 120),
            "key": cur_ana.get('camelot', ''),
            "energy": self._energy_to_string(cur_ana.get('energy_mean', 0.5)),
            "duration": cur_ana.get('duration', 180),
            "phrases": str(cur_ana.get('phrases', []))
        }
        
        track_b = {
            "name": next_song,
            "bpm": nxt_ana.get('bpm', 120),
            "key": nxt_ana.get('camelot', ''),
            "energy": self._energy_to_string(nxt_ana.get('energy_mean', 0.5)),
            "duration": nxt_ana.get('duration', 180),
            "phrases": str(nxt_ana.get('phrases', []))
        }
        
        print("🎧 Checking if Local LLM is awake...")
        
        # 2. Check if brain is alive and execute
        # Using getattr to safely check is_brain_alive just in case worker failed to boot
        if self.tot_worker and getattr(self.tot_worker, 'is_brain_alive', lambda: False)():
            print("🧠 Brain active. Routing to Tree of Thoughts.")
            try:
                # Ask Ollama for the master plan
                plan = self.tot_worker.generate_plan(track_a=track_a, track_b=track_b)
                
                technique = plan.get('technique', 'crossfade').lower()
                print(f"🎯 Local Agent selected technique: {technique.upper()}")
                
                params = {
                    "duration": 16,
                    "curve": "exponential",
                    "reasoning": plan.get('notes', 'ToT inference complete.'),
                    "phrase_alignment": plan.get('phrase_alignment', '')
                }
                return technique, params
                
            except Exception as e:
                print(f"⚠️ LangGraph Failed: {e}. Falling back to rules.")
        else:
            print("⚠️ Brain dead (Connection Refused). Falling back to heuristic rules immediately.")
            
        # 3. Rule-based Fallback
        return self._fallback_decide(cur_ana, nxt_ana)

    def _energy_to_string(self, energy: float) -> str:
        """Convert energy float to descriptive string"""
        if energy < 0.3:
            return "Low"
        elif energy < 0.6:
            return "Medium"
        elif energy < 0.8:
            return "High"
        else:
            return "Maximum"

    def _fallback_decide(self, cur_ana: Dict, nxt_ana: Dict) -> Tuple[str, Dict]:
        """Simple rule-based fallback if LLM is offline or crashes"""
        bpm_diff = abs(cur_ana.get('bpm', 120) - nxt_ana.get('bpm', 120))
        
        if bpm_diff <= 5:
            technique = 'beatmatch_crossfade'
        elif bpm_diff <= 15:
            technique = 'tempo_ramp'
        else:
            technique = 'cut_transition'
            
        return technique, {'duration': 16, 'curve': 'linear'}

    def get_params(self, cur_ana: Dict, nxt_ana: Dict, technique: str) -> Dict:
        """Get default parameters for a technique (Used by older scripts)"""
        bpm = cur_ana.get('bpm', 120)
        
        return {
            'crossfade_bars': 8 if bpm < 140 else 4,
            'mashup_bars': 8,
            'swap_bars': 8,
            'duration': 16
        }
