import json
import logging
import pandas as pd

from config import (
    DOCTOR_TREND_WINDOW_SECONDS,
    HR_TREND_WINDOW_SECONDS,
    LOW_CONFIDENCE_THRESHOLD,
    STRESS_EMOTIONS,
    TEACHER_WATCHLIST_WINDOW_SECONDS,
)

LOGGER = logging.getLogger(__name__)


def compute_stability_index(emotions):
    """Calculate emotional stability index from emotion sequence."""
    score_map = {"happy": 1, "neutral": 0, "sad": -1, "fear": -2, "angry": -3}
    scores = [score_map[e] for e in emotions if e in score_map]
    if len(scores) < 4:
        return "low"
    drift = sum(abs(scores[i] - scores[i - 1]) for i in range(1, len(scores)))
    avg_drift = drift / (len(scores) - 1)
    if avg_drift > 1.2:
        return "high"
    if avg_drift > 0.6:
        return "medium"
    return "low"


def parse_distribution(raw_distribution):
    """Parse emotion distribution from JSON string or dict."""
    if not raw_distribution:
        return {}
    if isinstance(raw_distribution, dict):
        return raw_distribution
    try:
        return json.loads(raw_distribution)
    except (TypeError, ValueError) as exc:
        LOGGER.warning("Failed to parse distribution payload: %s", exc)
        return {}


def render_rerun():
    """Trigger Streamlit rerun with compatibility."""
    import streamlit as st
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def compute_stress_duration_seconds(history_rows):
    """Calculate duration of continuous stress signals."""
    if not history_rows:
        return 0
    df = pd.DataFrame(history_rows, columns=["timestamp", "emotion", "confidence", "participant_id"])
    if df.empty:
        return 0
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return 0
    df = df.sort_values("timestamp")
    stress_df = df[df["emotion"].isin(STRESS_EMOTIONS)]
    if stress_df.empty:
        return 0
    contiguous = []
    for _, row in df[::-1].iterrows():
        if row["emotion"] in STRESS_EMOTIONS:
            contiguous.append(row["timestamp"])
        else:
            break
    if not contiguous:
        return 0
    return int((max(contiguous) - min(contiguous)).total_seconds())


def hr_state_label(emotion, confidence):
    """Generate HR-specific state labels for emotions."""
    if emotion is None or confidence < LOW_CONFIDENCE_THRESHOLD:
        return "insufficient_evidence"
    signal_map = {
        "happy": "engaged_composure",
        "neutral": "professional_composure",
        "sad": "hesitation_signal",
        "fear": "interview_anxiety_signal",
        "angry": "frustration_signal",
        "disgust": "disengagement_signal",
        "surprise": "processing_spike",
    }
    return signal_map.get(emotion, "insufficient_evidence")


def compute_hr_trend(history_rows, window_seconds=HR_TREND_WINDOW_SECONDS):
    """Calculate HR interview trend over time window."""
    if not history_rows:
        return "stable", "Not enough recent data"
    df = pd.DataFrame(history_rows, columns=["timestamp", "emotion", "confidence", "participant_id"])
    if df.empty:
        return "stable", "Not enough recent data"
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return "stable", "Not enough recent data"
    latest_ts = df["timestamp"].max()
    lower = latest_ts - pd.Timedelta(seconds=window_seconds)
    window_df = df[df["timestamp"] >= lower].copy()
    if window_df.empty:
        return "stable", "Not enough recent data"
    window_df = window_df[window_df["confidence"] >= LOW_CONFIDENCE_THRESHOLD]
    if len(window_df) < 3:
        return "stable", "Low-confidence or limited recent evidence"
    stress_emotions = {"fear", "sad", "angry", "disgust"}
    stress_ratio = (window_df["emotion"].isin(stress_emotions)).mean()
    if stress_ratio >= 0.6:
        return "rising_stress", "Stress signals increased over the last 60 seconds"
    if stress_ratio <= 0.25:
        return "settling", "Signals indicate stable or improving composure"
    return "mixed", "Signals are mixed in the last 60 seconds"


def teacher_state_label(emotion, confidence):
    """Generate teacher-specific state labels for emotions."""
    if emotion is None or confidence < LOW_CONFIDENCE_THRESHOLD:
        return "insufficient_evidence"
    state_map = {
        "happy": "engaged",
        "neutral": "attentive",
        "sad": "confused_or_withdrawn",
        "fear": "test_anxiety",
        "angry": "frustrated",
        "disgust": "disengaged",
        "surprise": "processing_shift",
    }
    return state_map.get(emotion, "insufficient_evidence")


def compute_teacher_watchlist(session_id, participants, window_seconds=TEACHER_WATCHLIST_WINDOW_SECONDS):
    """Identify students needing attention based on stress signals."""
    from logs.session_logger import get_participant_emotion_history
    
    watch_rows = []
    now = pd.Timestamp.now()
    stress_emotions = {"sad", "fear", "angry", "disgust"}
    for participant in participants:
        history = get_participant_emotion_history(session_id, participant["id"])
        if not history:
            continue
        df = pd.DataFrame(history, columns=["timestamp", "emotion", "confidence"])
        if df.empty:
            continue
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])
        if df.empty:
            continue
        df = df[df["timestamp"] >= now - pd.Timedelta(seconds=window_seconds)]
        if df.empty:
            continue
        df = df[df["confidence"] >= LOW_CONFIDENCE_THRESHOLD]
        if len(df) < 3:
            continue
        stress_ratio = float(df["emotion"].isin(stress_emotions).mean())
        avg_conf = float(df["confidence"].mean())
        if stress_ratio >= 0.45:
            watch_rows.append(
                {
                    "student": participant["name"],
                    "stress_ratio": round(stress_ratio, 2),
                    "avg_confidence": round(avg_conf, 2),
                    "samples": int(len(df)),
                }
            )
    watch_rows.sort(key=lambda row: (row["stress_ratio"], row["avg_confidence"]), reverse=True)
    return watch_rows


def doctor_state_label(emotion, confidence):
    """Generate doctor-specific clinical intent labels."""
    from core.mapping import map_emotion_to_intent
    
    if emotion is None:
         return "Uncertain (low data)"
    if confidence < LOW_CONFIDENCE_THRESHOLD:
         return "Uncertain (low confidence)"
    
    return map_emotion_to_intent(emotion, "doctor", confidence)


def hr_state_label(emotion, confidence):
    """Generate HR-specific interview intent labels."""
    from core.mapping import map_emotion_to_intent

    if emotion is None:
         return "Uncertain (low data)"
    if confidence < LOW_CONFIDENCE_THRESHOLD:
         return "Uncertain (low confidence)"

    return map_emotion_to_intent(emotion, "hr", confidence)


def compute_doctor_risk_duration_seconds(session_id, participant_id):
    """Calculate duration of high-risk patient signals."""
    from logs.session_logger import get_participant_emotion_history
    
    rows = get_participant_emotion_history(session_id, participant_id)
    if not rows:
        return 0
    df = pd.DataFrame(rows, columns=["timestamp", "emotion", "confidence"])
    if df.empty:
        return 0
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return 0
    df = df.sort_values("timestamp")
    high_risk = {"fear", "angry"}
    contiguous = []
    for _, row in df[::-1].iterrows():
        if row["emotion"] in high_risk and float(row["confidence"]) >= LOW_CONFIDENCE_THRESHOLD:
            contiguous.append(row["timestamp"])
        else:
            break
    if len(contiguous) < 2:
        return 0
    return int((max(contiguous) - min(contiguous)).total_seconds())


def compute_doctor_trend(history_rows, window_seconds=DOCTOR_TREND_WINDOW_SECONDS):
    """Calculate doctor clinical trend over time window."""
    if not history_rows:
        return "stable", "Not enough recent clinical signal data"
    df = pd.DataFrame(history_rows, columns=["timestamp", "emotion", "confidence", "participant_id"])
    if df.empty:
        return "stable", "Not enough recent clinical signal data"
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return "stable", "Not enough recent clinical signal data"
    latest_ts = df["timestamp"].max()
    lower = latest_ts - pd.Timedelta(seconds=window_seconds)
    window_df = df[df["timestamp"] >= lower]
    window_df = window_df[window_df["confidence"] >= LOW_CONFIDENCE_THRESHOLD]
    if len(window_df) < 3:
        return "stable", "Low-confidence or limited recent evidence"
    high_risk = {"fear", "angry"}
    high_ratio = float(window_df["emotion"].isin(high_risk).mean())
    if high_ratio >= 0.55:
        return "distress_rising", "High-risk distress signals rising over the last 2 minutes"
    if high_ratio <= 0.2:
        return "stable", "Clinical signals indicate a comfortable and stable state"
    return "mixed", "Patient state has been fluctuating over the last 2 minutes"
