"""
Local LLM Worker - LangGraph + Pydantic for structured AI responses
Uses Ollama (FREE local AI) for DJ transition decisions and wordplay.
"""

import sys
import os
from typing import Dict, TypedDict, Optional

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Try to import LangGraph/Pydantic, fallback gracefully
try:
    from pydantic import BaseModel, Field
    from langchain_ollama import ChatOllama
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("⚠️ LangGraph not installed. Run: pip install langchain-ollama langgraph pydantic")


# Pydantic Schemas for Strict Output Enforcement
if LANGGRAPH_AVAILABLE:
    class TransitionPlan(BaseModel):
        technique: str = Field(description="The DJ transition technique to use (e.g., echo_out, beatmatch_crossfade)")
        confidence: float = Field(description="Confidence score between 0.0 and 1.0")
        notes: str = Field(description="Brief reasoning for the transition")

    class WordplayPlan(BaseModel):
        found: bool = Field(description="True if a valid wordplay connection exists, False otherwise")
        word_a: str = Field(description="The target word or phrase from Song A")
        word_b: str = Field(description="The target word or phrase from Song B")
        connection_type: str = Field(description="Type of connection: exact, rhyme, phonetic, thematic, or none")
        explanation: str = Field(description="Brief explanation of why this connects")


# LangGraph State
class DJTransitionState(TypedDict):
    track_a_name: str
    track_a_bpm: float
    track_a_lyrics: str
    track_b_name: str
    track_b_bpm: float
    track_b_lyrics: str
    task_type: str  # 'transition' or 'wordplay'
    final_plan: Dict


class LocalOllamaWorker:
    """
    LOCAL LLM WORKER
    Uses LangGraph and Pydantic to orchestrate local Gemma/Llama 
    for modular, error-free DJ analysis.
    
    Falls back to simple HTTP if LangGraph not installed.
    """
    
    def __init__(self, model_name="llama3.2"):
        self.model_name = model_name
        self.available = False
        self.llm = None
        self.transition_llm = None
        self.wordplay_llm = None
        self.workflow = None
        
        if not LANGGRAPH_AVAILABLE:
            print("⚠️ LangGraph not available. Using fallback mode.")
            self._init_fallback()
            return
        
        print(f"🧠 [LOCAL LLM] Booting LangGraph Worker with Ollama ({model_name})...")
        
        try:
            # Check if Ollama is running
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code != 200:
                raise Exception("Ollama not responding")
            
            self.llm = ChatOllama(model=model_name, temperature=0.6)
            self.transition_llm = self.llm.with_structured_output(TransitionPlan)
            self.wordplay_llm = self.llm.with_structured_output(WordplayPlan)
            self.workflow = self._build_graph()
            self.available = True
            print("✅ LangGraph Worker ready!")
            
        except Exception as e:
            print(f"⚠️ LangGraph init failed: {e}")
            print("   Falling back to simple mode.")
            self._init_fallback()
    
    def _init_fallback(self):
        """Initialize fallback mode using raw HTTP to Ollama"""
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                self.available = True
                print("✅ Fallback mode: Raw Ollama HTTP ready")
            else:
                self.available = False
        except:
            self.available = False
            print("❌ Ollama not running. Local AI disabled.")
    
    def _route_task_node(self, state: DJTransitionState) -> str:
        """Conditional routing based on task type."""
        return state["task_type"]

    def _analyze_transition_node(self, state: DJTransitionState) -> DJTransitionState:
        """LangGraph Node: Generate standard transition plan."""
        print(f"   [Node] Processing Transition: {state['track_a_name']} -> {state['track_b_name']}")
        
        prompt = f"""
        Analyze this DJ transition:
        Track A: {state['track_a_name']} ({state['track_a_bpm']} BPM)
        Track B: {state['track_b_name']} ({state['track_b_bpm']} BPM)
        
        Choose the best transition technique and explain why.
        """
        
        try:
            response = self.transition_llm.invoke(prompt)
            state["final_plan"] = response.model_dump()
        except Exception as e:
            print(f"   ⚠️ Transition analysis failed: {e}")
            state["final_plan"] = {
                "technique": "beatmatch_crossfade",
                "confidence": 0.5,
                "notes": "Fallback due to error"
            }
        return state

    def _analyze_wordplay_node(self, state: DJTransitionState) -> DJTransitionState:
        """LangGraph Node: Generate creative semantic bridges."""
        print(f"   [Node] Processing Wordplay/Semantic Bridge...")
        
        prompt = f"""
        Find a creative wordplay connection between these songs:
        
        Song A: "{state['track_a_name']}"
        Lyrics: {state['track_a_lyrics'][:300]}
        
        Song B: "{state['track_b_name']}"
        Lyrics: {state['track_b_lyrics'][:300]}
        
        Look for matching words, rhymes, phonetic similarities, or thematic connections.
        """
        
        try:
            response = self.wordplay_llm.invoke(prompt)
            state["final_plan"] = response.model_dump()
        except Exception as e:
            print(f"   ⚠️ Wordplay analysis failed: {e}")
            state["final_plan"] = {
                "found": False,
                "word_a": "",
                "word_b": "",
                "connection_type": "none",
                "explanation": "Analysis failed"
            }
        return state

    def _build_graph(self):
        """Construct Directed Acyclic Graph."""
        workflow = StateGraph(DJTransitionState)
        
        workflow.add_node("transition_analyzer", self._analyze_transition_node)
        workflow.add_node("wordplay_analyzer", self._analyze_wordplay_node)
        
        workflow.set_conditional_entry_point(
            self._route_task_node,
            {
                "transition": "transition_analyzer",
                "wordplay": "wordplay_analyzer"
            }
        )
        
        workflow.add_edge("transition_analyzer", END)
        workflow.add_edge("wordplay_analyzer", END)
        
        return workflow.compile()

    def generate_plan(self, task: str, **kwargs) -> Dict:
        """
        Entry point for DJ App.
        
        Args:
            task: 'transition' or 'wordplay'
            track_a: Name of first track
            track_b: Name of second track
            bpm_a: BPM of first track
            bpm_b: BPM of second track
            lyrics_a: Lyrics of first track (for wordplay)
            lyrics_b: Lyrics of second track (for wordplay)
        
        Returns:
            Dict with plan details
        """
        if not self.available:
            return self._fallback_plan(task, **kwargs)
        
        if self.workflow is None:
            return self._fallback_plan(task, **kwargs)
        
        initial_state = DJTransitionState(
            track_a_name=kwargs.get("track_a", "Unknown"),
            track_a_bpm=kwargs.get("bpm_a", 120.0),
            track_a_lyrics=kwargs.get("lyrics_a", ""),
            track_b_name=kwargs.get("track_b", "Unknown"),
            track_b_bpm=kwargs.get("bpm_b", 120.0),
            track_b_lyrics=kwargs.get("lyrics_b", ""),
            task_type=task,
            final_plan={}
        )
        
        try:
            result = self.workflow.invoke(initial_state)
            return result["final_plan"]
        except Exception as e:
            print(f"⚠️ Workflow error: {e}")
            return self._fallback_plan(task, **kwargs)
    
    def _fallback_plan(self, task: str, **kwargs) -> Dict:
        """Simple fallback when LangGraph fails"""
        if task == "wordplay":
            return {
                "found": False,
                "word_a": "",
                "word_b": "",
                "connection_type": "none",
                "explanation": "Local AI unavailable"
            }
        else:
            # Use simple BPM-based logic
            bpm_a = kwargs.get("bpm_a", 120)
            bpm_b = kwargs.get("bpm_b", 120)
            diff = abs(bpm_a - bpm_b)
            
            if diff <= 5:
                technique = "beatmatch_crossfade"
            elif diff <= 15:
                technique = "tempo_ramp"
            else:
                technique = "cut_transition"
            
            return {
                "technique": technique,
                "confidence": 0.6,
                "notes": f"BPM difference: {diff}"
            }


if __name__ == "__main__":
    # Test boot
    worker = LocalOllamaWorker()
    
    if worker.available:
        print("\n🧪 Testing transition analysis...")
        result = worker.generate_plan(
            task="transition",
            track_a="Drake - Hotline Bling",
            track_b="The Weeknd - Blinding Lights",
            bpm_a=135,
            bpm_b=171
        )
        print(f"   Result: {result}")
    else:
        print("\n⚠️ Ollama not running. Start it with: ollama serve")
