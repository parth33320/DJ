import os, json, requests
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from typing import Dict, List, TypedDict, Optional
from langgraph.graph import StateGraph, END

class IdeaGeneration(BaseModel):
    ideas: List[Dict] = Field(description="3 transition ideas")

class FinalTransitionPlan(BaseModel):
    technique: str; confidence: float; notes: str

# 🎯 NEW: Added mode and target_technique so State know if it is punishing itself
class ToTState(TypedDict):
    track_a_data: Dict; track_b_data: Dict; human_feedback: str; 
    generated_ideas: List; critique_notes: str; final_plan: Dict;
    mode: str; target_technique: Optional[str]

class LocalTreeOfThoughtsWorker:
    def __init__(self, model_name="deepseek-r1:8b"):
        self.generator_llm = ChatOllama(model=model_name, temperature=0.7).with_structured_output(IdeaGeneration)
        self.critic_llm = ChatOllama(model=model_name, temperature=0.2)
        self.selector_llm = ChatOllama(model=model_name, temperature=0.1).with_structured_output(FinalTransitionPlan)
        self.workflow = self._build_graph()

    def _get_memory(self):
        mem = load_json_safe('data/logs/critic_memory.json', [])[-5:]
        return f"PAST FAILURES AND CRITICISM: {mem}\n"

    def _generator_node(self, state):
        # 🎯 NEW: Branch logic! If Remediation, FORCE the new recipe!
        if state.get('mode') == 'REMEDIATION':
            tech = state['target_technique']
            recipe = load_json_safe(f"data/knowledge/{tech.lower()}_recipe.json", {})
            prompt = f"""
            🚨 REMEDIATION MODE: You recently FAILED a {tech} transition!
            Tracks: {state['track_a_data']['title']} -> {state['track_b_data']['title']}
            
            You went to school. Here are the exact steps you just learned to fix it:
            {json.dumps(recipe.get('steps', []), indent=2)}
            
            Generate 3 variations of how to apply THESE SPECIFIC STEPS to these two tracks.
            Do not do anything else. Just follow the newly learned steps.
            """
        else:
            prompt = f"Tracks: {state['track_a_data']['title']} -> {state['track_b_data']['title']}\n{state['human_feedback']}\nSuggest 3 DJ techniques."
            
        state["generated_ideas"] = self.generator_llm.invoke([HumanMessage(content=prompt)]).ideas
        return state

    def _critic_node(self, state):
        mode_text = f"Ensure they follow the newly learned {state['target_technique']} recipe exactly." if state.get('mode') == 'REMEDIATION' else ""
        prompt = f"Critique these ideas based on human feedback: {state['generated_ideas']}. {mode_text}"
        state["critique_notes"] = self.critic_llm.invoke([HumanMessage(content=prompt)]).content
        return state

    def _selector_node(self, state):
        prompt = f"Pick the best idea based on this critique: {state['critique_notes']}"
        res = self.selector_llm.invoke([HumanMessage(content=prompt)])
        state["final_plan"] = res.model_dump()
        
        # 🎯 NEW: Loud, visible Remediation Monologue
        print(f"\n   ========================================")
        if state.get('mode') == 'REMEDIATION':
            print(f"   🗣️ AI INTERNAL MONOLOGUE (Remediation Report):")
            print(f"   🎯 STATUS: ATTEMPTING FIX FOR {state['target_technique']}")
            print(f"   🧠 LOGIC: 'The previous attempt failed. I ingested tutorial steps.")
            print(f"   The new approach: {res.notes}. Applying now.'")
        else:
            print(f"   🗣️ AI INTERNAL MONOLOGUE:")
            print(f"   🎯 STATUS: NEW EXPLORATION")
            print(f"   🧠 LOGIC: {res.notes}")
        print(f"   ========================================\n")
        
        return state

    def _build_graph(self):
        builder = StateGraph(ToTState)
        builder.add_node("gen", self._generator_node); builder.add_node("crit", self._critic_node); builder.add_node("sel", self._selector_node)
        builder.set_entry_point("gen"); builder.add_edge("gen", "crit"); builder.add_edge("crit", "sel"); builder.add_edge("sel", END)
        return builder.compile()

    # 🎯 NEW: Updated to accept mode and technique from main engine
    def generate_plan(self, a, b, mode='NORMAL', target_technique=None):
        return self.workflow.invoke({
            "track_a_data": a, 
            "track_b_data": b, 
            "human_feedback": self._get_memory(),
            "mode": mode,
            "target_technique": target_technique
        })["final_plan"]

def load_json_safe(fp, default):
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f: return json.load(f)
    return default
