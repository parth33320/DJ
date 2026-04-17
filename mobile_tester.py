# Add this import at the top of mobile_tester.py:
from ai_brain.innovation_engine import InnovationEngine

# In the init section, add:
innovation_engine = None

# In factory_loop(), after dj is initialized, add:
global innovation_engine
try:
    from utils.drive_manager import DriveManager
    dm = DriveManager(dj.config)
    innovation_engine = InnovationEngine(dj.config, dm)
except:
    innovation_engine = InnovationEngine(dj.config, None)

# Replace the feedback() function with this:
@app.route('/feedback', methods=['POST'])
def feedback():
    global innovation_engine
    data = request.json
    is_pass = data.get('pass', False)
    text = data.get('text_feedback', '')
    
    state = current_task.get()
    technique = state.get('technique', '')
    
    # Record feedback for AI learning!
    if technique and innovation_engine:
        try:
            innovation_engine.record_feedback(
                technique=technique,
                passed=is_pass,
                params={},
                song_a={'title': state.get('cur_title', '')},
                song_b={'title': state.get('nxt_title', '')},
                text_feedback=text
            )
        except Exception as e:
            print(f"Learning error: {e}")
    
    # Save feedback weights
    if technique:
        try:
            os.makedirs('data/logs', exist_ok=True)
            weight_file = 'data/logs/feedback_weights.json'
            weights = {}
            if os.path.exists(weight_file):
                with open(weight_file, 'r') as f:
                    weights = json.load(f)
            weights[technique] = weights.get(technique, 1.0) + (0.3 if is_pass else -0.2)
            with open(weight_file, 'w') as f:
                json.dump(weights, f, indent=2)
        except Exception as e:
            print(f"Weight save error: {e}")
    
    current_task.update(audio_ready=False, status='idle')
    return jsonify({'status': 'ok'})
