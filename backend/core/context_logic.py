def compute_risk(emotion, confidence, context):
    multipliers = {
        "fear": 1.35,
        "angry": 1.3,
        "sad": 1.2,
        "neutral": 1.0,
        "happy": 0.8,
        "disgust": 1.1,
        "surprise": 1.05,
    }

    context_scale = {
        "doctor": 1.0,
        "teacher": 0.9,
        "hr": 0.95,
    }

    score = confidence * multipliers.get(emotion, 1.0) * context_scale.get(context, 0.9)

    if score > 0.9:
        return "high"
    elif score > 0.7:
        return "medium"
    else:
        return "low"
