def map_emotion_to_intent(emotion, context, confidence=1.0):
    healthcare_map = {
        "happy": [
            "Comfortable / Stable",
        ],
        "neutral": [
            "Comfortable / Stable",
            "Fatigue / Low Energy",
        ],
        "sad": [
            "Anxiety / Concern",
            "Mild Discomfort",
        ],
        "fear": [
            "Anxiety / Concern",
            "Pain / Distress",
        ],
        "angry": [
            "Pain / Distress",
            "Mild Discomfort",
        ],
        "disgust": [
            "Mild Discomfort",
            "Fatigue / Low Energy",
        ],
        "surprise": [
            "Pain / Distress",
            "Anxiety / Concern",
        ],
    }

    classroom_map = {
        "happy": [
            "understanding_the_concept",
            "agreement_with_explanation",
            "interest_in_topic",
            "enjoying_the_activity",
            "confidence_in_answer",
            "social_engagement",
            "positive_peer_interaction",
        ],
        "neutral": [
            "listening_attentively",
            "processing_information",
            "passive_engagement",
            "waiting_for_instruction",
            "mild_boredom",
            "emotional_control",
            "routine_participation",
        ],
        "sad": [
            "confusion",
            "feeling_left_behind",
            "lack_of_understanding",
            "low_confidence",
            "disappointment_wrong_answer",
            "social_withdrawal",
            "academic_stress",
        ],
        "fear": [
            "test_anxiety",
            "fear_of_being_questioned",
            "performance_pressure",
            "uncertainty_about_answer",
            "fear_of_making_mistakes",
            "public_speaking_anxiety",
            "evaluation_stress",
        ],
        "angry": [
            "frustration_with_difficulty",
            "cognitive_overload",
            "disagreement_with_explanation",
            "irritation_with_peers",
            "task_resistance",
            "perceived_unfairness",
            "mental_fatigue",
        ],
        "disgust": [
            "disinterest_in_topic",
            "aversion_to_activity",
            "negative_reaction_to_content",
            "social_discomfort",
            "rejection_of_group_task",
        ],
        "surprise": [
            "sudden_understanding",
            "confusion_due_to_unexpected_concept",
            "reaction_to_new_information",
            "being_suddenly_called",
            "realization_of_mistake",
        ],
    }

    corporate_map = {
        "happy": [
            "engaged_composure",
            "rapport_building",
            "clear_communication_flow",
            "positive_response",
            "confidence_signal",
            "steady_engagement",
            "constructive_tone",
            "comfort_in_conversation",
        ],
        "neutral": [
            "professional_composure",
            "active_listening",
            "measured_response_pace",
            "analytical_processing",
            "focused_attention",
            "controlled_communication",
            "stable_baseline",
        ],
        "sad": [
            "hesitation_signal",
            "confidence_drop",
            "difficulty_processing",
            "performance_pressure",
            "reduced_engagement",
            "self_doubt_signal",
            "response_fatigue",
        ],
        "fear": [
            "interview_anxiety_signal",
            "stress_spike",
            "evaluation_pressure_response",
            "answer_uncertainty",
            "nervousness_signal",
            "hesitation_under_pressure",
            "high_arousal_state",
        ],
        "angry": [
            "frustration_signal",
            "defensive_response",
            "disagreement_tension",
            "elevated_stress_response",
            "resistance_signal",
            "communication_friction",
        ],
        "disgust": [
            "disengagement_signal",
            "aversion_response",
            "social_discomfort_signal",
            "enthusiasm_drop",
            "negative_reaction_pattern",
        ],
        "surprise": [
            "processing_spike",
            "unexpected_prompt_reaction",
            "rapid_recalibration",
            "momentary_confusion",
            "attention_shift",
        ],
    }

    if context == "doctor":
        # Deterministic hierarchy for Clinical Intent
        if emotion in ["fear", "surprise"]:
            return "Pain / Distress" if confidence > 0.8 else "Anxiety / Concern"
        if emotion in ["angry", "sad"]:
            return "Pain / Distress" if confidence > 0.8 else "Mild Discomfort"
        if emotion == "disgust":
            return "Mild Discomfort" if confidence > 0.6 else "Fatigue / Low Energy"
        if emotion in ["happy", "neutral"]:
            return "Comfortable / Stable"
        
        return healthcare_map.get(emotion, ["Uncertain"])[0]

    if context == "teacher":
        intents = classroom_map.get(emotion, [])
        return intents[0] if intents else "unknown"

    if context == "hr":
        intents = corporate_map.get(emotion, [])
        return intents[0] if intents else "unknown"

    if context == "hr":
        # Deterministic hierarchy for Interview Intent (Normalized)
        if emotion == "fear":
             return "Stress" if confidence > 0.7 else "Hesitation"
        if emotion == "surprise":
             return "Hesitation"
        if emotion == "sad":
             return "Low Confidence"
        if emotion == "angry":
             return "Confusion"
        if emotion == "disgust":
             return "Confusion"
        if emotion == "neutral":
             return "Engaged"
        if emotion == "happy":
             return "Engaged"
             
        return "Uncertain"
