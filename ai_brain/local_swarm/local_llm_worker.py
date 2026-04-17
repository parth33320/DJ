import os, json, requests
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END

class IdeaGeneration(BaseModel):
    ideas: List[Dict] = Field(description="3 transition ideas")

class FinalTransitionPlan(BaseModel):
    technique: str; confidence: float; notes: str

class ToTState(TypedDict):
    track_a_data: Dict; track_b_data: Dict; human_feedback: str; generated_ideas: List; critique_notes: str; final_plan: Dict

class LocalTreeOfThoughtsWorker:
    def __init__(self, model_name="deepseek-r1:8b"):
        self.generator_llm = ChatOllama(model=model_name, temperature=0.7).with_structured_output(IdeaGeneration)
        self.critic_llm = ChatOllama(model=model_name, temperature=0.2)
        self.selector_llm = ChatOllama(model=model_name, temperature=0.1).with_structured_output(FinalTransitionPlan)
        self.workflow = self._build_graph()

    def _get_memory(self):
        mem = load_json_safe('data/logs/critic_memory.json', [])[-5:]
        recipes = load_json_safe('data/logs/dj_knowledge_base.json', [])
        return f"FEEDBACK: {mem}\nRECIPES: {recipes}"

    def _generator_node(self, state):
        prompt = f"Tracks: {state['track_a_data']['title']} -> {state['track_b_data']['title']}\n{state['human_feedback']}\nSuggest 3 DJ techniques."
        state["generated_ideas"] = self.generator_llm.invoke([HumanMessage(content=prompt)]).ideas
        return state

    def _critic_node(self, state):
        prompt = f"Critique these ideas based on human feedback: {state['generated_ideas']}"
        state["critique_notes"] = self.critic_llm.invoke([HumanMessage(content=prompt)]).content
        return state

    def _selector_node(self, state):
        prompt = f"Pick the best idea based on this critique: {state['critique_notes']}"
        res = self.selector_llm.invoke([HumanMessage(content=prompt)])
        state["final_plan"] = res.model_dump()
        print(f"\n   🗣️ AI INTERNAL MONOLOGUE: {res.notes}\n")
        return state

    def _build_graph(self):
        builder = StateGraph(ToTState)
        builder.add_node("gen", self._generator_node); builder.add_node("crit", self._critic_node); builder.add_node("sel", self._selector_node)
        builder.set_entry_point("gen"); builder.add_edge("gen", "crit"); builder.add_edge("crit", "sel"); builder.add_edge("sel", END)
        return builder.compile()

    def generate_plan(self, a, b):
        return self.workflow.invoke({"track_a_data": a, "track_b_data": b, "human_feedback": self._get_memory()})["final_plan"]

def load_json_safe(fp, default):
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f: return json.load(f)
    return default
