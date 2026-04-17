"""
Local LLM Worker - Tree of Thoughts + Phrase Matching
Uses DeepSeek-R1 for creative DJ transition planning.

Architecture:
1. Generator Node: Hallucinates 3 wildly different transition ideas (high temp)
2. Critic Node: Attacks ideas with music theory (Camelot wheel, phrase alignment)
3. Selector Node: Picks the mathematically superior transition

This makes the AI CREATIVE like a human DJ, not just a rule-follower!
"""

import sys
import os
import random
from typing import Dict, TypedDict, List, Optional

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Try to import LangGraph/Pydantic, fallback gracefully
LANGGRAPH_AVAILABLE = False
try:
    from pydantic import BaseModel, Field
    from langchain_ollama import ChatOllama
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("⚠️ LangGraph not installed. Run: pip install langchain-ollama langgraph pydantic")


# ═══════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS - Enforce Structured Output
# ═══════════════════════════════════════════════════════════════

if LANGGRAPH_AVAILABLE:
    class TransitionIdea(BaseModel):
        technique: str = Field(description="Name of transition technique (e.g., phrase_sync_drop, eq_fade, loop_roll, echo_out)")
        concept: str = Field(description="How it works musically - be specific about timing and layers")

    class IdeaGeneration(BaseModel):
        ideas: List[TransitionIdea] = Field(description="Exactly 3 different transition ideas")

    class FinalTransitionPlan(BaseModel):
        technique: str = Field(description="The winning technique name")
        confidence: float = Field(description="Score from 0.0 to 1.0 based on phrase and key compatibility")
        phrase_alignment: str = Field(description="Specific phrase alignment instruction (e.g., 'Start mix on Track B chorus at Track A breakdown, bar 64')")
        entry_point_a: float = Field(description="Timestamp in seconds to start transition on Track A")
        entry_point_b: float = Field(description="Timestamp in seconds to enter Track B")
        notes: str = Field(description="Why this technique won the critique")

    class WordplayConnection(BaseModel):
        found: bool = Field(description="True if a valid wordplay connection exists")
        word_a: str = Field(description="The target word or phrase from Song A")
        word_b: str = Field(description="The matching word or phrase from Song B")
        timestamp_a: float = Field(description="Timestamp in seconds where word appears in Song A")
        timestamp_b: float = Field(description="Timestamp in seconds where word appears in Song B")
        connection_type: str = Field(description="Type: exact, rhyme, phonetic, semantic, or none")
        explanation: str = Field(description="Brief explanation of the connection")


# ═══════════════════════════════════════════════════════════════
# LANGGRAPH STATE
# ═══════════════════════════════════════════════════════════════

class ToTState(TypedDict):
    track_a_data: Dict  # name, bpm, key, energy, phrases, lyrics
    track_b_data: Dict
    task_type: str  # 'transition' or 'wordplay'
    generated_ideas: List[Dict]
    critique_notes: str
    final_plan: Dict


# ═══════════════════════════════════════════════════════════════
# CAMELOT WHEEL - Harmonic Mixing Rules
# ═══════════════════════════════════════════════════════════════

CAMELOT_WHEEL = {
    '1A': ['1A', '1B', '12A', '2A'],
    '1B': ['1B', '1A', '12B', '2B'],
    '2A': ['2A', '2B', '1A', '3A'],
    '2B': ['2B', '2A', '1B', '3B'],
    '3A': ['3A', '3B', '2A', '4A'],
    '3B': ['3B', '3A', '2B', '4B'],
    '4A': ['4A', '4B', '3A', '5A'],
    '4B': ['4B', '4A', '3B', '5B'],
    '5A': ['5A', '5B', '4A', '6A'],
    '5B': ['5B', '5A', '4B', '6B'],
    '6A': ['6A', '6B', '5A', '7A'],
    '6B': ['6B', '6A', '5B', '7B'],
    '7A': ['7A', '7B', '6A', '8A'],
    '7B': ['7B', '7A', '6B', '8B'],
    '8A': ['8A', '8B', '7A', '9A'],
    '8B': ['8B', '8A', '7B', '9B'],
    '9A': ['9A', '9B', '8A', '10A'],
    '9B': ['9B', '9A', '8B', '10B'],
    '10A': ['10A', '10B', '9A', '11A'],
    '10B': ['10B', '10A', '9B', '11B'],
    '11A': ['11A', '11B', '10A', '12A'],
    '11B': ['11B', '11A', '10B', '12B'],
    '12A': ['12A', '12B', '11A', '1A'],
    '12B': ['12B', '12A', '11B', '1B'],
}

def are_keys_compatible(key_a: str, key_b: str) -> bool:
    """Check if two Camelot keys are harmonically compatible"""
    if not key_a or not key_b:
        return True  # Unknown = assume compatible
    return key_b in CAMELOT_WHEEL.get(key_a, [key_a])


# ═══════════════════════════════════════════════════════════════
# TREE OF THOUGHTS WORKER
# ═══════════════════════════════════════════════════════════════

class LocalTreeOfThoughtsWorker:
    """
    LOCAL TREE OF THOUGHTS (ToT) WORKER
    
    Instead of asking the LLM for ONE answer, we:
    1. Generate 3 wildly different ideas (high creativity)
    2. Critique them with music theory (cold logic)
    3. Select the mathematically best one
    
    This makes AI think like a HUMAN DJ who considers multiple options!
    
    Also includes Epsilon-Greedy exploration:
    - 80% of time: Use the best technique from experience
    - 20% of time: Try something random to discover new tricks!
    """
    
    def __init__(self, model_name="deepseek-r1:8b"):
        self.model_name = model_name
        self.available = False
        self.generator_llm = None
        self.critic_llm = None
        self.selector_llm = None
        self.wordplay_llm = None
        self.workflow = None
        
        # Epsilon-greedy: 20% chance to explore random technique
        self.epsilon = 0.2
        
        # All known techniques for random exploration
        self.all_techniques = [
            'beatmatch_crossfade', 'cut_transition', 'echo_out',
            'filter_sweep', 'loop_roll', 'reverb_wash', 'spinback',
            'tempo_ramp', 'white_noise_sweep', 'vinyl_scratch_flourish',
            'tone_play', 'wordplay', 'mashup_short', 'mashup_extended',
            'acapella_layer', 'drum_swap', 'bass_swap', 'stutter_glitch',
            'half_time_transition', 'wordplay_mashup', 'phrasal_interlace'
        ]
        
        if not LANGGRAPH_AVAILABLE:
            print("⚠️ LangGraph not available. Using fallback mode.")
            self._init_fallback()
            return
        
        print(f"🌳 [TREE OF THOUGHTS] Booting local reasoning engine ({model_name})...")
        
        try:
            # Check if Ollama is running
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code != 200:
                raise Exception("Ollama not responding")
            
            # Check if model is available
            models = r.json().get('models', [])
            model_names = [m.get('name', '') for m in models]
            
            if not any(model_name in name for name in model_names):
                print(f"⚠️ Model {model_name} not found. Trying llama3.2...")
                model_name = "llama3.2"
            
            # Generator: High temperature for creative divergence
            self.generator_llm = ChatOllama(model=model_name, temperature=0.85)
            
            # Critic: Low temperature for strict music theory logic
            self.critic_llm = ChatOllama(model=model_name, temperature=0.1)
            
            # Selector: Strict Pydantic output
            self.selector_llm = ChatOllama(model=model_name, temperature=0.1).with_structured_output(FinalTransitionPlan)
            
            # Wordplay: Medium temperature for creative connections
            self.wordplay_llm = ChatOllama(model=model_name, temperature=0.6).with_structured_output(WordplayConnection)
            
            self.workflow = self._build_transition_graph()
            self.wordplay_workflow = self._build_wordplay_graph()
            self.available = True
            
            print("✅ Tree of Thoughts Worker ready!")
            print(f"   🎲 Epsilon-greedy exploration: {int(self.epsilon * 100)}% random experiments")
            
        except Exception as e:
            print(f"⚠️ LangGraph init failed: {e}")
            print("   Falling back to rule-based mode.")
            self._init_fallback()
    
    def _init_fallback(self):
        """Initialize fallback mode using simple rules"""
        self.available = True  # Fallback is always "available"
        print("✅ Fallback mode: Rule-based transitions ready")
    
    # ═══════════════════════════════════════════════════════════
    # TRANSITION PLANNING NODES
    # ═══════════════════════════════════════════════════════════
    
    def _generator_node(self, state: ToTState) -> ToTState:
        """Step 1: Hallucinate 3 distinct transition strategies."""
        print(f"   [ToT 1/3] 🎨 Generating 3 creative hypotheses...")
        
        track_a = state['track_a_data']
        track_b = state['track_b_data']
        
        prompt = f"""You are an elite DJ with 20 years of experience. Brainstorm 3 COMPLETELY DIFFERENT transition techniques between these tracks.

TRACK A: "{track_a.get('name', 'Unknown')}"
- BPM: {track_a.get('bpm', 120)}
- Key: {track_a.get('key', 'Unknown')} (Camelot)
- Energy: {track_a.get('energy', 'Medium')}
- Phrases: {track_a.get('phrases', 'Standard 32-beat')}

TRACK B: "{track_b.get('name', 'Unknown')}"
- BPM: {track_b.get('bpm', 120)}
- Key: {track_b.get('key', 'Unknown')} (Camelot)
- Energy: {track_b.get('energy', 'Medium')}
- Phrases: {track_b.get('phrases', 'Standard 32-beat')}

RULES:
1. IDEA 1 (Safe): A reliable technique that almost always works (e.g., EQ fade, beatmatch crossfade)
2. IDEA 2 (Phrase-based): Focus on 32-beat phrase alignment, drop-swaps, or structural mixing
3. IDEA 3 (Creative/Risky): Something bold - vinyl brake, echo out into acapella, tempo ramp, stutter glitch

For each idea, specify:
- Technique name
- Exactly HOW it works (timing, layers, what elements to isolate)

Format your response as:
IDEA 1 (Safe): [technique name]
Concept: [detailed explanation]

IDEA 2 (Phrase-based): [technique name]
Concept: [detailed explanation]

IDEA 3 (Creative): [technique name]
Concept: [detailed explanation]
"""
        
        try:
            response = self.generator_llm.invoke([HumanMessage(content=prompt)])
            
            # Parse the response into structured ideas
            ideas = self._parse_ideas(response.content)
            state["generated_ideas"] = ideas
            
        except Exception as e:
            print(f"   ⚠️ Generator failed: {e}")
            # Fallback ideas
            state["generated_ideas"] = [
                {"technique": "beatmatch_crossfade", "concept": "Safe 8-bar crossfade"},
                {"technique": "filter_sweep", "concept": "High-pass sweep out, low-pass sweep in"},
                {"technique": "echo_out", "concept": "Echo current track, fade in next"},
            ]
        
        return state
    
    def _parse_ideas(self, text: str) -> List[Dict]:
        """Parse generator output into structured ideas"""
        ideas = []
        
        # Try to extract ideas from the text
        lines = text.split('\n')
        current_technique = None
        current_concept = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if 'IDEA' in line.upper() and ':' in line:
                # Save previous idea if exists
                if current_technique:
                    ideas.append({"technique": current_technique, "concept": current_concept.strip()})
                
                # Extract technique name
                parts = line.split(':')
                if len(parts) >= 2:
                    current_technique = parts[1].strip().lower().replace(' ', '_')
                    current_concept = ""
            elif line.lower().startswith('concept:'):
                current_concept = line[8:].strip()
            elif current_technique:
                current_concept += " " + line
        
        # Save last idea
        if current_technique:
            ideas.append({"technique": current_technique, "concept": current_concept.strip()})
        
        # Ensure we have at least 3 ideas
        while len(ideas) < 3:
            fallback_techniques = ['beatmatch_crossfade', 'echo_out', 'filter_sweep']
            ideas.append({
                "technique": fallback_techniques[len(ideas) % 3],
                "concept": "Fallback technique"
            })
        
        return ideas[:3]
    
    def _critic_node(self, state: ToTState) -> ToTState:
        """Step 2: Apply music theory logic to destroy bad ideas."""
        print(f"   [ToT 2/3] 🔬 Critiquing with music theory...")
        
        track_a = state['track_a_data']
        track_b = state['track_b_data']
        ideas = state['generated_ideas']
        
        key_a = track_a.get('key', '')
        key_b = track_b.get('key', '')
        keys_compatible = are_keys_compatible(key_a, key_b)
        
        bpm_a = track_a.get('bpm', 120)
        bpm_b = track_b.get('bpm', 120)
        bpm_diff = abs(bpm_a - bpm_b)
        
        ideas_str = "\n".join([f"- {i['technique']}: {i['concept']}" for i in ideas])
        
        prompt = f"""You are a music theory professor and professional DJ. Critically evaluate these 3 transition ideas.

MUSICAL CONTEXT:
- Track A Key: {key_a} | Track B Key: {key_b}
- Keys Compatible on Camelot Wheel: {'YES' if keys_compatible else 'NO - DANGER!'}
- Track A BPM: {bpm_a} | Track B BPM: {bpm_b}
- BPM Difference: {bpm_diff} ({'Easy to mix' if bpm_diff <= 5 else 'Moderate' if bpm_diff <= 15 else 'CHALLENGING'})
- Energy A: {track_a.get('energy', '?')} | Energy B: {track_b.get('energy', '?')}

IDEAS TO CRITIQUE:
{ideas_str}

EVALUATE EACH IDEA ON:
1. PHRASE MATCHING: Will 32-beat phrases align properly? Will vocals clash?
2. HARMONIC MIX: Are melodic elements safe to overlap given the keys? If keys clash, can we isolate drums only?
3. BPM COMPATIBILITY: Is tempo adjustment needed? Will time-stretching sound bad?
4. ENERGY FLOW: Does energy transition feel natural or jarring?

Write a harsh critique. Identify the FATAL FLAWS in bad ideas. Highlight why ONE idea is mathematically superior.
End with: "WINNER: [technique name] because [reason]"
"""
        
        try:
            response = self.critic_llm.invoke([HumanMessage(content=prompt)])
            state["critique_notes"] = response.content
        except Exception as e:
            print(f"   ⚠️ Critic failed: {e}")
            # Fallback: pick based on simple rules
            if bpm_diff <= 5 and keys_compatible:
                winner = "beatmatch_crossfade"
            elif bpm_diff > 15:
                winner = "cut_transition"
            else:
                winner = "filter_sweep"
            state["critique_notes"] = f"WINNER: {winner} because it's safest for this BPM/key combination."
        
        return state
    
    def _selector_node(self, state: ToTState) -> ToTState:
        """Step 3: Output structured plan based on critique survival."""
        print(f"   [ToT 3/3] 📋 Finalizing optimal transition...")
        
        track_a = state['track_a_data']
        track_b = state['track_b_data']
        ideas = state['generated_ideas']
        critique = state['critique_notes']
        
        ideas_str = ", ".join([i['technique'] for i in ideas])
        
        prompt = f"""Based on this music theory critique:
---
{critique}
---

Select the WINNING transition from: {ideas_str}

Create the final execution plan with SPECIFIC timing:
- technique: The winning technique name (use snake_case like 'echo_out' or 'beatmatch_crossfade')
- confidence: Score from 0.0 to 1.0
- phrase_alignment: SPECIFIC instruction like "Start mixing at Track A bar 64, bring in Track B at bar 1 of chorus"
- entry_point_a: Timestamp in seconds where transition starts on Track A (estimate based on typical song structure)
- entry_point_b: Timestamp in seconds where Track B enters
- notes: Why this technique won

Track A duration estimate: {track_a.get('duration', 180)} seconds
Track B duration estimate: {track_b.get('duration', 180)} seconds
"""
        
        try:
            if self.selector_llm:
                response = self.selector_llm.invoke([HumanMessage(content=prompt)])
                state["final_plan"] = response.model_dump()
            else:
                raise Exception("Selector LLM not available")
        except Exception as e:
            print(f"   ⚠️ Selector failed: {e}")
            
            # Extract winner from critique
            winner = "beatmatch_crossfade"
            if "WINNER:" in critique:
                try:
                    winner_line = critique.split("WINNER:")[1].split('\n')[0]
                    winner = winner_line.split()[0].lower().replace(' ', '_')
                except:
                    pass
            
            state["final_plan"] = {
                "technique": winner,
                "confidence": 0.7,
                "phrase_alignment": "Start mix at Track A outro, bring in Track B at intro",
                "entry_point_a": track_a.get('duration', 180) * 0.75,
                "entry_point_b": 0.0,
                "notes": "Selected based on music theory critique"
            }
        
        return state
    
    # ═══════════════════════════════════════════════════════════
    # WORDPLAY NODES
    # ═══════════════════════════════════════════════════════════
    
    def _wordplay_node(self, state: ToTState) -> ToTState:
        """Find creative wordplay connections between lyrics"""
        print(f"   [Wordplay] 🎤 Searching for lyrical connections...")
        
        track_a = state['track_a_data']
        track_b = state['track_b_data']
        
        lyrics_a = track_a.get('lyrics', '')[:500]
        lyrics_b = track_b.get('lyrics', '')[:500]
        
        if not lyrics_a or not lyrics_b:
            state["final_plan"] = {
                "found": False,
                "word_a": "",
                "word_b": "",
                "timestamp_a": 0,
                "timestamp_b": 0,
                "connection_type": "none",
                "explanation": "No lyrics available"
            }
            return state
        
        prompt = f"""You are a creative DJ known for clever wordplay transitions. Find a connection between these songs' lyrics.

SONG A: "{track_a.get('name', 'Unknown')}"
Lyrics: {lyrics_a}

SONG B: "{track_b.get('name', 'Unknown')}"
Lyrics: {lyrics_b}

Look for:
1. EXACT MATCH: Same word appears in both (e.g., "love" in both songs)
2. RHYME: Words that rhyme (e.g., "night" and "light")
3. PHONETIC: Words that sound similar (e.g., "heart" and "hard")
4. SEMANTIC: Words with related meaning (e.g., "fire" and "burning")

Find the BEST connection that would create a smooth DJ transition where one word echoes into the other.
"""
        
        try:
            if self.wordplay_llm:
                response = self.wordplay_llm.invoke([HumanMessage(content=prompt)])
                state["final_plan"] = response.model_dump()
            else:
                raise Exception("Wordplay LLM not available")
        except Exception as e:
            print(f"   ⚠️ Wordplay analysis failed: {e}")
            state["final_plan"] = {
                "found": False,
                "word_a": "",
                "word_b": "",
                "timestamp_a": 0,
                "timestamp_b": 0,
                "connection_type": "none",
                "explanation": f"Analysis failed: {str(e)[:50]}"
            }
        
        return state
    
    # ═══════════════════════════════════════════════════════════
    # GRAPH BUILDERS
    # ═══════════════════════════════════════════════════════════
    
    def _build_transition_graph(self):
        """Build the transition planning DAG"""
        workflow = StateGraph(ToTState)
        
        workflow.add_node("generator", self._generator_node)
        workflow.add_node("critic", self._critic_node)
        workflow.add_node("selector", self._selector_node)
        
        workflow.set_entry_point("generator")
        workflow.add_edge("generator", "critic")
        workflow.add_edge("critic", "selector")
        workflow.add_edge("selector", END)
        
        return workflow.compile()
    
    def _build_wordplay_graph(self):
        """Build the wordplay analysis DAG"""
        workflow = StateGraph(ToTState)
        workflow.add_node("wordplay", self._wordplay_node)
        workflow.set_entry_point("wordplay")
        workflow.add_edge("wordplay", END)
        return workflow.compile()
    
    # ═══════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════
    
    def generate_plan(self, track_a: Dict, track_b: Dict, task_type: str = "transition") -> Dict:
        """
        Main entry point for DJ App.
        
        Args:
            track_a: Dict with keys: name, bpm, key, energy, phrases, lyrics, duration
            track_b: Same structure as track_a
            task_type: 'transition' or 'wordplay'
        
        Returns:
            Dict with the optimal plan
        """
        # Epsilon-greedy exploration: 20% chance to try random technique
        if task_type == "transition" and random.random() < self.epsilon:
            print(f"   🎲 EXPLORATION MODE: Trying random technique!")
            random_technique = random.choice(self.all_techniques)
            return {
                "technique": random_technique,
                "confidence": 0.5,
                "phrase_alignment": "Experimental - let AI learn from your feedback!",
                "entry_point_a": track_a.get('duration', 180) * 0.75,
                "entry_point_b": 0.0,
                "notes": f"EXPLORATION: Randomly selected {random_technique} to test. Rate it to help AI learn!",
                "is_experiment": True
            }
        
        # Check if we have the full LangGraph workflow
        if not LANGGRAPH_AVAILABLE or self.workflow is None:
            return self._fallback_plan(track_a, track_b, task_type)
        
        initial_state = ToTState(
            track_a_data=track_a,
            track_b_data=track_b,
            task_type=task_type,
            generated_ideas=[],
            critique_notes="",
            final_plan={}
        )
        
        try:
            if task_type == "wordplay" and self.wordplay_workflow:
                result = self.wordplay_workflow.invoke(initial_state)
            else:
                result = self.workflow.invoke(initial_state)
            
            return result["final_plan"]
            
        except Exception as e:
            print(f"⚠️ Workflow error: {e}")
            return self._fallback_plan(track_a, track_b, task_type)
    
    def _fallback_plan(self, track_a: Dict, track_b: Dict, task_type: str) -> Dict:
        """Simple fallback when LangGraph fails"""
        if task_type == "wordplay":
            return {
                "found": False,
                "word_a": "",
                "word_b": "",
                "timestamp_a": 0,
                "timestamp_b": 0,
                "connection_type": "none",
                "explanation": "Local AI unavailable"
            }
        
        # Use simple BPM/key-based logic
        bpm_a = track_a.get('bpm', 120)
        bpm_b = track_b.get('bpm', 120)
        diff = abs(bpm_a - bpm_b)
        
        key_a = track_a.get('key', '')
        key_b = track_b.get('key', '')
        keys_ok = are_keys_compatible(key_a, key_b)
        
        if diff <= 5 and keys_ok:
            technique = "beatmatch_crossfade"
            confidence = 0.9
        elif diff <= 5:
            technique = "filter_sweep"  # Safe when keys clash
            confidence = 0.7
        elif diff <= 15:
            technique = "tempo_ramp"
            confidence = 0.6
        else:
            technique = "cut_transition"
            confidence = 0.5
        
        return {
            "technique": technique,
            "confidence": confidence,
            "phrase_alignment": "Start at Track A outro",
            "entry_point_a": track_a.get('duration', 180) * 0.75,
            "entry_point_b": 0.0,
            "notes": f"Fallback: BPM diff={diff}, Keys compatible={keys_ok}"
        }
    
    def set_exploration_rate(self, epsilon: float):
        """Set the exploration rate (0.0 to 1.0)"""
        self.epsilon = max(0.0, min(1.0, epsilon))
        print(f"   🎲 Exploration rate set to {int(self.epsilon * 100)}%")


# ═══════════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🧪 Testing Tree of Thoughts Worker...\n")
    
    worker = LocalTreeOfThoughtsWorker()
    
    if worker.available:
        print("\n" + "="*50)
        print("TEST 1: Transition Planning")
        print("="*50)
        
        plan = worker.generate_plan(
            track_a={
                "name": "Dua Lipa - Levitating",
                "bpm": 103,
                "key": "6B",
                "energy": "High",
                "duration": 210,
                "phrases": "Verse-Chorus-Verse-Chorus-Bridge-Chorus"
            },
            track_b={
                "name": "The Weeknd - Blinding Lights",
                "bpm": 171,
                "key": "11B",
                "energy": "Maximum",
                "duration": 200,
                "phrases": "Intro-Verse-Chorus-Verse-Chorus-Bridge-Outro"
            },
            task_type="transition"
        )
        
        print("\n✅ WINNING PLAN:")
        for key, value in plan.items():
            print(f"   {key}: {value}")
        
        print("\n" + "="*50)
        print("TEST 2: Wordplay Detection")
        print("="*50)
        
        wordplay = worker.generate_plan(
            track_a={
                "name": "Drake - Hotline Bling",
                "lyrics": "You used to call me on my cell phone, late night when you need my love"
            },
            track_b={
                "name": "Hindi Song",
                "lyrics": "Tujhe dekha to ye jaana sanam, pyar hota hai deewana sanam"
            },
            task_type="wordplay"
        )
        
        print("\n✅ WORDPLAY RESULT:")
        for key, value in wordplay.items():
            print(f"   {key}: {value}")
    
    else:
        print("⚠️ Ollama not running. Start it with: ollama serve")
