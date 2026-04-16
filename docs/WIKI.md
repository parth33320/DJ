# 📖 AI DJ Knowledge Wiki

Welcome to the internal knowledge base for the Autonomous AI DJ Project.

## 🚀 Getting Started

### Running the Mobile Tester
1. Connect your phone to the same Wi-Fi or use the Public Cloudflare link.
2. Run `python mobile_tester.py`.
3. Open the link provided in the console.

### Adding Music
- Place `.mp3` files in the `data/library` directory.
- Ensure filenames are clean (Artist - Title.mp3).
- The system requires at least **2 songs** to start generating transitions.

## 🧠 The AI Brain

### Transition Agent
The brain uses logic to pick between:
- **Beatmatching**: Matching rhythms for smooth flow.
- **Filter Sweeps**: Using HPF/LPF for energy shifts.
- **Innovation Mode**: Creating new hybrid techniques by mutating existing rules.

### Validation Agent
Every mix is pre-checked. If the judge sees:
- Long silence
- Terrible beat-match
- Clipping audio
...It will **delete** the mix and try again automatically.

## 🛠️ Maintenance & Tools

### Synchronizing Code
Use `tools/sync_github.py` to push your latest changes to the remote repository.

### Troubleshooting
- **No Sound**: Check if `ffmpeg` is installed and in your System PATH.
- **503 Error**: Restart the `mobile_tester.py` to refresh the Cloudflare tunnel.
- **Brain Freeze**: If generation hangs, check `data/logs/error.log`.

## 📈 Improving the System
The Agent learns from your **Pass/Fail** ratings. 
- **Pass**: Increases the probability of the used technique.
- **Fail**: Decreases probability and triggers a retry.
- **Text Feedback**: Read by the developer (and eventually the agent) to fine-tune specific behaviors.
