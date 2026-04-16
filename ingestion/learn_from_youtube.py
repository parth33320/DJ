import os
from main import DJApp
from ai_brain.agents.self_improve_agent import SelfImproveAgent

def trigger_learning():
    print("Initializing DJ App Configuration...")
    app = DJApp()
    
    print("\n" + "="*50)
    print("🚀 Forcing YouTube Learning Cycle...")
    print("Checking BestDJTransitions & other tutorial channels set in config.yaml...")
    print("="*50)
    
    improver = app.self_improver
    
    if not improver.use_openai:
        print("⚠️ NOTE: You don't have an OpenAI key set in config.yaml.")
        print("The agent will scrape tutorial URLs and transcribe them, but it")
        print("cannot generate new python code for transition techniques without the LLM.")
        print("Please ensure quota is available and API key is set before expecting new techniques.")
        
    improver.run_improvement_cycle()
    
    print("\n✅ Learning cycle finished!")
    print("Check transition_engine/ai_generated_techniques.py for new transitions!")

if __name__ == "__main__":
    trigger_learning()
