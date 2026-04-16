"""
Standalone self-improvement runner
Can be called from main app or run independently
"""
from ai_brain.agents.self_improve_agent import SelfImproveAgent
import yaml
import schedule
import time

def main():
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    agent = SelfImproveAgent(config)
    print("🤖 Self-Improver running...")
    agent.run_improvement_cycle()

if __name__ == "__main__":
    main()
