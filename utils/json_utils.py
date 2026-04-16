import numpy as np

def make_serializable(obj):
    """
    Recursively convert any non-serializable objects (like numpy types) 
    into standard Python types for JSON serialization.
    """
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_serializable(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, '__dict__'):
        return make_serializable(obj.__dict__)
    return obj
