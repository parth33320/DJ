import json
import sys
from typing import Dict, TypedDict
from langchain_community.llms import Ollama
from langgraph.graph import StateGraph, END

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 1. Define the State for the LangGraph workflow
class DJTransitionState(TypedDict):
    track_a_name: str
    track_a_bpm: float
    track_b_name: str
    track_b_bpm: float
    raw_analysis: str
    final_plan: Dict

class LocalOllamaWorker:
    """
    LOCAL LLM WORKER
    Uses LangGraph to orchestrate a local Gemma/Ollama instance for zero-cost DJ analysis.
    """
    def __init__(self, model_name="gemma"):
        print(f"🧠 [LOCAL LLM] Booting LangGraph Worker attached to Ollama ({model_name})...")
        try:
            # Connects to default local Ollama port (http://localhost:11434)
            self.llm = Ollama(model=model_name, temperature=0.6)
        except Exception as e:
            print(f"❌ Failed to connect to Ollama. Is it running? Error: {e}")
            sys.exit(1)
            
        self.workflow = self._build_graph()

    def _analyze_tracks_node(self, state: DJTransitionState) -> DJTransitionState:
        """LangGraph Node: Ask the local LLM to analyze the vibe and BPM difference."""
        print(f"   [Node] Analyzing transition: {state['track_a_name']} -> {state['track_b_name']}")
        
        prompt = f"""
        You are an expert DJ. Analyze the transition between these two tracks:
        Track A: {state['track_a_name']} ({state['track_a_bpm']} BPM)
        Track B: {state['track_b_name']} ({state['track_b_bpm']} BPM)
        
        Provide a brief analysis of the energy shift and the best mixing technique (e.g., Echo Out, Mashup, EQ Fade).
        """
        response = self.llm.invoke(prompt)
        state["raw_analysis"] = response
        return state

    def _format_plan_node(self, state: DJTransitionState) -> DJTransitionState:
        """LangGraph Node: Convert the raw analysis into a structured JSON plan for the MasterTransitionEngine."""
        print("   [Node] Formatting plan into actionable JSON...")
        
        prompt = f"""
        Based on this analysis: "{state['raw_analysis']}"
        Extract the recommended technique and output ONLY a valid JSON object like this:
        {{"technique": "echo_out", "confidence": 0.85, "notes": "brief reason"}}
        """
        response = self.llm.invoke(prompt)
        
        try:
            # Clean up potential markdown formatting from the LLM
            clean_json = response.replace("```json", "").replace("```", "").strip()
            state["final_plan"] = json.loads(clean_json)
        except json.JSONDecodeError:
            state["final_plan"] = {"technique": "standard_fade", "confidence": 0.5, "notes": "Fallback due to parse error."}
            
        return state

    def _build_graph(self):
        """Construct the LangGraph state machine."""
        workflow = StateGraph(DJTransitionState)
        
        # Add nodes
        workflow.add_node("analyze", self._analyze_tracks_node)
        workflow.add_node("format", self._format_plan_node)
        
        # Define edges (Linear flow for this worker)
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "format")
        workflow.add_edge("format", END)
        
        # Compile the graph
        return workflow.compile()

    def generate_transition_plan(self, track_a: str, bpm_a: float, track_b: str, bpm_b: float) -> Dict:
        """Entry point for the DJ App to call."""
        initial_state = DJTransitionState(
            track_a_name=track_a,
            track_a_bpm=bpm_a,
            track_b_name=track_b,
            track_b_bpm=bpm_b,
            raw_analysis="",
            final_plan={}
        )
        
        print("\n🚀 Executing Local LLM Graph...")
        result = self.workflow.invoke(initial_state)
        return result["final_plan"]

if __name__ == "__main__":
    # Quick test execution
    worker = LocalOllamaWorker(model_name="gemma")
    plan = worker.generate_transition_plan(
        track_a="Dua Lipa - Training Season", bpm_a=122.0,
        track_b="The Weeknd - Blinding Lights", bpm_b=171.0
    )
    print("\n✅ Final Computed Plan:")
    print(json.dumps(plan, indent=2))
