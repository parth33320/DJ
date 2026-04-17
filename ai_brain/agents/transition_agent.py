"""
Transition Agent - Now with Tree of Thoughts!
"""

import os
from typing import Dict, Tuple

class TransitionAgent:
    def __init__(self, config):
        self.config = config
        self.tot_worker = None
        
        # Try to load Tree of Thoughts worker
        try:
            from ai_brain.local_swarm.local_llm_worker import LocalTreeOfThoughtsWorker
            self.tot_worker = LocalTreeOfThoughtsWorker()
            print("✅ TransitionAgent using Tree of Thoughts!")
        except Exception as e:
            print(f"⚠️ Tree of Thoughts not available: {e}")
            print("   Using rule-based fallback.")
    
    def decide(self, cur_id, nxt_id, cur_ana: Dict, nxt_ana: Dict) -> Tuple[str, Dict]:
        """
        Decide the best transition technique.
        Uses Tree of Thoughts if available, otherwise falls back to rules.
        """
        # Prepare track data
        track_a = {
            "name": cur_ana.get('title', cur_id),
            "bpm": cur_ana.get('bpm', 120),
            "key": cur_ana.get('camelot', ''),
            "energy": self._energy_to_string(cur_ana.get('energy_mean', 0.5)),
            "duration": cur_ana.get('duration', 180),
            "lyrics": cur_ana.get('lyrics', {}).get('text', ''),
            "phrases": str(cur_ana.get('phrases', []))
        }
        
        track_b = {
            "name": nxt_ana.get('title', nxt_id),
            "bpm": nxt_ana.get('bpm', 120),
            "key": nxt_ana.get('camelot', ''),
            "energy": self._energy_to_string(nxt_ana.get('energy_mean', 0.5)),
            "duration": nxt_ana.get('duration', 180),
            "lyrics": nxt_ana.get('lyrics', {}).get('text', ''),
            "phrases": str(nxt_ana.get('phrases', []))
        }
        
        # Use Tree of Thoughts if available
        if self.tot_worker and self.tot_worker.available:
            plan = self.tot_worker.generate_plan(track_a, track_b, task_type="transition")
            
            technique = plan.get('technique', 'beatmatch_crossfade')
            params = {
                'phrase_alignment': plan.get('phrase_alignment', ''),
                'entry_point_a': plan.get('entry_point_a', 0),
                'entry_point_b': plan.get('entry_point_b', 0),
                'confidence': plan.get('confidence', 0.5),
                'notes': plan.get('notes', ''),
                'is_experiment': plan.get('is_experiment', False)
            }
            
            return technique, params
        
        # Fallback to simple rules
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
        """Simple rule-based fallback"""
        bpm_diff = abs(cur_ana.get('bpm', 120) - nxt_ana.get('bpm', 120))
        
        if bpm_diff <= 5:
            technique = 'beatmatch_crossfade'
        elif bpm_diff <= 15:
            technique = 'tempo_ramp'
        else:
            technique = 'cut_transition'
        
        return technique, {'crossfade_bars': 8}
    
    def get_params(self, cur_ana: Dict, nxt_ana: Dict, technique: str) -> Dict:
        """Get default parameters for a technique"""
        bpm = cur_ana.get('bpm', 120)
        
        params = {
            'crossfade_bars': 8 if bpm < 140 else 4,
            'mashup_bars': 8,
            'swap_bars': 8,
        }
        
        return params
