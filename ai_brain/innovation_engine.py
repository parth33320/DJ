"""
Innovation Engine - AI That Learns and Invents New DJ Techniques!

This engine:
1. Stores every transition you rate (pass/fail) on Google Drive
2. Analyzes patterns in successful vs failed transitions
3. Mutates and combines techniques to create NEW ones
4. Tests innovations and keeps the winners

This is how AI becomes BETTER than human DJs - it experiments 24/7!
"""

import os
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

class InnovationEngine:
    """
    The brain that never sleeps. Always learning. Always inventing.
    """
    
    def __init__(self, config, drive_manager=None):
        self.config = config
        self.drive = drive_manager
        self.local_feedback_path = 'data/logs/feedback_log.jsonl'
        self.local_innovations_path = 'data/logs/innovations.json'
        self.innovations = self._load_innovations()
        
        # Known base techniques that can be mutated/combined
        self.base_techniques = [
            'beatmatch_crossfade', 'cut_transition', 'echo_out',
            'filter_sweep', 'loop_roll', 'reverb_wash', 'spinback',
            'tempo_ramp', 'white_noise_sweep', 'vinyl_scratch_flourish',
            'tone_play', 'wordplay', 'mashup_short', 'mashup_extended',
            'acapella_layer', 'drum_swap', 'bass_swap', 'stutter_glitch',
            'half_time_transition', 'wordplay_mashup', 'phrasal_interlace'
        ]
        
        # Parameters that can be mutated
        self.mutable_params = {
            'crossfade_bars': [2, 4, 8, 16, 32],
            'mashup_bars': [4, 8, 16, 32],
            'echo_feedback': [0.3, 0.5, 0.7, 0.9],
            'echo_delay_ms': [125, 250, 375, 500],
            'filter_sweep_duration': [4, 8, 12, 16],
            'reverb_room_size': [0.3, 0.5, 0.7, 0.9],
            'pitch_shift_semitones': [-5, -3, -2, 2, 3, 5, 7, 12],
            'interlace_slice_divisions': [4, 8, 16, 32, 64],
            'glitch_density': [4, 8, 16, 32],
            'half_time_ramp_bars': [4, 8, 16],
            'word_repeats': [2, 3, 4, 6, 8],
            'layer_bars': [8, 16, 32],
            'pitch_interpolation_steps': [4, 8, 12, 24],
            'spectral_freeze_duration_ms': [250, 500, 1000, 2000],
        }
    
    def _load_innovations(self) -> Dict:
        """Load existing innovations from disk"""
        if os.path.exists(self.local_innovations_path):
            try:
                with open(self.local_innovations_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'techniques': [], 'experiments': [], 'hall_of_fame': []}
    
    def _save_innovations(self):
        """Save innovations to disk and optionally to Drive"""
        os.makedirs(os.path.dirname(self.local_innovations_path), exist_ok=True)
        with open(self.local_innovations_path, 'w') as f:
            json.dump(self.innovations, f, indent=2)
        
        # Upload to Drive for backup
        if self.drive:
            try:
                self.drive.upload_file('account_1', self.local_innovations_path, 'DJ_Agent_Innovations')
            except:
                pass
    
    def record_feedback(self, technique: str, passed: bool, params: Dict, 
                        song_a: Dict, song_b: Dict, text_feedback: str = ""):
        """
        Record user feedback for AI learning.
        Every pass/fail teaches the AI what works!
        """
        record = {
            'timestamp': time.time(),
            'datetime': datetime.now().isoformat(),
            'technique': technique,
            'passed': passed,
            'params': params,
            'song_a': {
                'title': song_a.get('title', 'Unknown'),
                'bpm': song_a.get('bpm'),
                'key': song_a.get('camelot'),
                'energy': song_a.get('energy_mean'),
                'genre': song_a.get('genre_hint'),
            },
            'song_b': {
                'title': song_b.get('title', 'Unknown'),
                'bpm': song_b.get('bpm'),
                'key': song_b.get('camelot'),
                'energy': song_b.get('energy_mean'),
                'genre': song_b.get('genre_hint'),
            },
            'bpm_diff': abs((song_a.get('bpm') or 120) - (song_b.get('bpm') or 120)),
            'text_feedback': text_feedback,
        }
        
        # Append to local log
        os.makedirs(os.path.dirname(self.local_feedback_path), exist_ok=True)
        with open(self.local_feedback_path, 'a') as f:
            f.write(json.dumps(record) + '\n')
        
        # Upload to Drive for long-term storage
        if self.drive:
            try:
                self.drive.upload_file('account_1', self.local_feedback_path, 'DJ_Agent_Feedback')
            except:
                pass
        
        print(f"   📝 Feedback recorded: {technique} = {'✅ PASS' if passed else '❌ FAIL'}")
    
    def analyze_patterns(self) -> Dict:
        """
        Analyze all feedback to find patterns.
        What techniques work? When do they fail?
        """
        if not os.path.exists(self.local_feedback_path):
            return {'total': 0, 'patterns': []}
        
        # Load all feedback
        records = []
        with open(self.local_feedback_path, 'r') as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except:
                    continue
        
        if not records:
            return {'total': 0, 'patterns': []}
        
        # Analyze by technique
        technique_stats = {}
        for r in records:
            tech = r['technique']
            if tech not in technique_stats:
                technique_stats[tech] = {'passes': 0, 'fails': 0, 'contexts': []}
            
            if r['passed']:
                technique_stats[tech]['passes'] += 1
            else:
                technique_stats[tech]['fails'] += 1
            
            technique_stats[tech]['contexts'].append({
                'bpm_diff': r.get('bpm_diff', 0),
                'passed': r['passed'],
            })
        
        # Find patterns
        patterns = []
        for tech, stats in technique_stats.items():
            total = stats['passes'] + stats['fails']
            if total >= 3:  # Need at least 3 samples
                success_rate = stats['passes'] / total
                
                # Analyze when technique works vs fails
                pass_bpm_diffs = [c['bpm_diff'] for c in stats['contexts'] if c['passed']]
                fail_bpm_diffs = [c['bpm_diff'] for c in stats['contexts'] if not c['passed']]
                
                avg_pass_bpm = sum(pass_bpm_diffs) / len(pass_bpm_diffs) if pass_bpm_diffs else 0
                avg_fail_bpm = sum(fail_bpm_diffs) / len(fail_bpm_diffs) if fail_bpm_diffs else 0
                
                patterns.append({
                    'technique': tech,
                    'success_rate': success_rate,
                    'total_uses': total,
                    'avg_pass_bpm_diff': avg_pass_bpm,
                    'avg_fail_bpm_diff': avg_fail_bpm,
                    'insight': self._generate_insight(tech, success_rate, avg_pass_bpm, avg_fail_bpm),
                })
        
        return {
            'total': len(records),
            'patterns': sorted(patterns, key=lambda x: x['success_rate'], reverse=True),
        }
    
    def _generate_insight(self, technique: str, success_rate: float, 
                          avg_pass_bpm: float, avg_fail_bpm: float) -> str:
        """Generate human-readable insight about a technique"""
        if success_rate >= 0.8:
            insight = f"🌟 {technique} is a WINNER! Use it often."
        elif success_rate >= 0.5:
            insight = f"👍 {technique} works OK."
        else:
            insight = f"⚠️ {technique} often fails."
        
        if avg_pass_bpm < avg_fail_bpm and avg_fail_bpm - avg_pass_bpm > 5:
            insight += f" Works better when BPM diff is small (<{int(avg_pass_bpm + 5)})."
        elif avg_pass_bpm > avg_fail_bpm and avg_pass_bpm - avg_fail_bpm > 5:
            insight += f" Works better when BPM diff is large (>{int(avg_fail_bpm)})."
        
        return insight
    
    def invent_new_technique(self) -> Optional[Dict]:
        """
        🧬 MUTATION ENGINE 🧬
        Combines and mutates existing techniques to create NEW ones!
        This is how AI goes beyond human DJ knowledge!
        """
        # Strategy 1: Combine two successful techniques
        patterns = self.analyze_patterns()
        top_techniques = [p['technique'] for p in patterns.get('patterns', [])[:5] if p['success_rate'] >= 0.6]
        
        if len(top_techniques) >= 2:
            # Combine two techniques
            tech_a, tech_b = random.sample(top_techniques, 2)
            
            innovation = {
                'name': f"hybrid_{tech_a[:4]}_{tech_b[:4]}_{random.randint(100,999)}",
                'type': 'hybrid',
                'parents': [tech_a, tech_b],
                'description': f"Start with {tech_a}, blend into {tech_b}",
                'created_at': datetime.now().isoformat(),
                'test_count': 0,
                'pass_count': 0,
                'status': 'experimental',
            }
            
            self.innovations['techniques'].append(innovation)
            self._save_innovations()
            
            print(f"   🧬 INVENTED NEW TECHNIQUE: {innovation['name']}")
            print(f"      Parents: {tech_a} + {tech_b}")
            
            return innovation
        
        # Strategy 2: Mutate parameters of a successful technique
        if top_techniques:
            base_tech = random.choice(top_techniques)
            param_key = random.choice(list(self.mutable_params.keys()))
            param_value = random.choice(self.mutable_params[param_key])
            
            innovation = {
                'name': f"mutant_{base_tech[:6]}_{param_key[:3]}{param_value}",
                'type': 'mutation',
                'base': base_tech,
                'mutation': {param_key: param_value},
                'description': f"{base_tech} with {param_key}={param_value}",
                'created_at': datetime.now().isoformat(),
                'test_count': 0,
                'pass_count': 0,
                'status': 'experimental',
            }
            
            self.innovations['techniques'].append(innovation)
            self._save_innovations()
            
            print(f"   🧬 MUTATED TECHNIQUE: {innovation['name']}")
            print(f"      Base: {base_tech}, Mutation: {param_key}={param_value}")
            
            return innovation
        
        # Strategy 3: Random combination
        tech_a, tech_b = random.sample(self.base_techniques, 2)
        innovation = {
            'name': f"experiment_{random.randint(1000,9999)}",
            'type': 'random_experiment',
            'parents': [tech_a, tech_b],
            'description': f"Wild experiment: {tech_a} meets {tech_b}",
            'created_at': datetime.now().isoformat(),
            'test_count': 0,
            'pass_count': 0,
            'status': 'experimental',
        }
        
        self.innovations['techniques'].append(innovation)
        self._save_innovations()
        
        print(f"   🎲 RANDOM EXPERIMENT: {innovation['name']}")
        
        return innovation
    
    def get_experimental_technique(self) -> Optional[Dict]:
        """
        Get an experimental technique to test.
        AI wants to know if its invention works!
        """
        experiments = [t for t in self.innovations.get('techniques', []) 
                       if t.get('status') == 'experimental' and t.get('test_count', 0) < 5]
        
        if experiments:
            return random.choice(experiments)
        return None
    
    def record_experiment_result(self, technique_name: str, passed: bool):
        """Record result of an experimental technique"""
        for tech in self.innovations.get('techniques', []):
            if tech['name'] == technique_name:
                tech['test_count'] = tech.get('test_count', 0) + 1
                if passed:
                    tech['pass_count'] = tech.get('pass_count', 0) + 1
                
                # Promote to hall of fame if it's proven!
                if tech['test_count'] >= 5:
                    success_rate = tech['pass_count'] / tech['test_count']
                    if success_rate >= 0.7:
                        tech['status'] = 'proven'
                        self.innovations['hall_of_fame'].append(tech)
                        print(f"   🏆 TECHNIQUE PROVEN: {technique_name} ({success_rate*100:.0f}% success)")
                    else:
                        tech['status'] = 'failed'
                        print(f"   ❌ TECHNIQUE FAILED: {technique_name} ({success_rate*100:.0f}% success)")
                
                self._save_innovations()
                return
    
    def get_hall_of_fame(self) -> List[Dict]:
        """Get all proven AI-invented techniques"""
        return self.innovations.get('hall_of_fame', [])
    
    def print_report(self):
        """Print a report of AI learning progress"""
        patterns = self.analyze_patterns()
        
        print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║              🧠 AI LEARNING REPORT 🧠                      ║
    ╚═══════════════════════════════════════════════════════════╝
        """)
        
        print(f"   📊 Total transitions rated: {patterns['total']}")
        print()
        
        if patterns['patterns']:
            print("   🏆 TOP TECHNIQUES:")
            for p in patterns['patterns'][:5]:
                bar = "█" * int(p['success_rate'] * 10) + "░" * (10 - int(p['success_rate'] * 10))
                print(f"      {p['technique'][:20]:<20} [{bar}] {p['success_rate']*100:.0f}%")
                print(f"         {p['insight']}")
            print()
        
        innovations = self.innovations.get('techniques', [])
        experiments = [t for t in innovations if t.get('status') == 'experimental']
        proven = self.innovations.get('hall_of_fame', [])
        
        print(f"   🧬 INNOVATIONS:")
        print(f"      Experiments in progress: {len(experiments)}")
        print(f"      Proven techniques: {len(proven)}")
        
        if proven:
            print("\n   🏆 HALL OF FAME (AI-Invented Techniques):")
            for t in proven:
                print(f"      ⭐ {t['name']}: {t['description']}")
        
        print()
