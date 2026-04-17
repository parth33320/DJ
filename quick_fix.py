import os

fixes = {
    'ai_brain/agents/research_agent.py': [
        ('import os\nimport json', 'import os\nimport json\nimport random')
    ],
    'ai_brain/agents/self_improve_agent.py': [
        ('self.whisper_model = whisper.load_model("base")',
         'if whisper is None:\n            print("Whisper missing")\n            return None\n        self.whisper_model = whisper.load_model("base")')
    ],
    'ai_brain/agents/wordplay_agent.py': [
        ('phones = pronouncing.phones_for_word(word)',
         'if pronouncing is None: return None\n        phones = pronouncing.phones_for_word(word)')
    ]
}

for path, changes in fixes.items():
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
        for old, new in changes:
            if old in data:
                data = data.replace(old, new)
                print(f"✅ Fixed bug in {path}")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
