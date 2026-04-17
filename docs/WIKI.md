# 📖 AI DJ Knowledge Wiki

Welcome to the internal knowledge base for the Autonomous AI DJ Project.

## 📂 Navigation Index
- [Architecture Diagram](../ARCHITECTURE.md)
- [README (Home)](../README.md)
- [Transition Techniques](#transition-techniques)
- [Innovation Batching](#innovation-batching)

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

## 🧪 Novel Techniques & Innovation

### Innovation Batching (Best of 10)
The system continuously generates experimental transitions. To ensure you only see high-quality inventions:
1. The **Transition Agent** creates 10 "Novel" candidates.
2. The **Validation Agent** scores each one.
3. Only the **highest scoring** mix is sent to you via **ntfy** for approval.
4. The remaining 9 are logged for training but kept out of your main queue.

## 📢 Developer Communication
- **Automatic Notifications**: The AI Agent (Antigravity) will send the latest mobile links to the `ntfy` topic `dj-agent-parth` every time a file is edited. This ensures real-time access to the testing UI without needing to check the terminal.

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
