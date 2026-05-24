import streamlit as st
import time
import cv2

from config import LOW_CONFIDENCE_THRESHOLD
from core.realtime_emotion import predict_emotion, predict_emotions
from core.smoothing import EmotionSmoother
from core.context_logic import compute_risk
from core.mapping import map_emotion_to_intent
from logs.session_logger import log_emotion
from utils.analysis_utils import render_rerun
from streaming.frame_store import upsert_participant_frame, set_participant_stream_active


def show_status_overview(session_id, context, session_status):
    """Display clean status overview header."""
    st.subheader("Live Monitoring Dashboard")
    st.caption(f"Session: {session_id} | Context: {context} | Status: {session_status}")


def show_auto_controls():
    """Display auto-refresh and TTS controls."""
    auto_refresh = st.checkbox("Enable Live Monitoring", key="auto_refresh_dashboard")
    enable_tts = st.checkbox("Enable Voice Output", key="enable_tts_dashboard")
    return auto_refresh, enable_tts


def show_system_status():
    """Display system status and stability information."""
    if st.session_state.get("latest_stream_issue"):
        st.warning(f"Stability Drop: {st.session_state['latest_stream_issue']}")
        st.session_state["latest_stream_issue"] = None
    st.caption(f"No-face events (stability drops): {st.session_state['no_face_events']}")


def show_live_camera():
    """Display live camera interface for professional users."""
    run = st.checkbox("Start Camera", key="start_camera")
    frame_placeholder = st.empty()
    result_placeholder = st.empty()

    if run:
        if "prof_camera" not in st.session_state:
            st.session_state["prof_camera"] = cv2.VideoCapture(0)
            
        camera = st.session_state["prof_camera"]
        ret, frame = camera.read()

        if not ret:
            st.warning("Unable to read from camera. Close other apps using the camera.")
            return

        results = predict_emotions(frame)
        if results:
            dominant_emotion = results[0]["emotion"]
            confidence = results[0]["confidence"]

            if confidence >= LOW_CONFIDENCE_THRESHOLD:
                smoother_key = f"single_{st.session_state.get('user_id', 'default')}"
                if smoother_key not in st.session_state["face_smoothers"]:
                    st.session_state["face_smoothers"][smoother_key] = EmotionSmoother(buffer_size=10)
                smoother = st.session_state["face_smoothers"][smoother_key]
                smoother.update(dominant_emotion)
                display_emotion = smoother.get_stable_emotion() or dominant_emotion
            else:
                display_emotion = dominant_emotion

            context = st.session_state.get("context", "teacher")
            intent = map_emotion_to_intent(display_emotion, context)
            risk = compute_risk(display_emotion, confidence, context)

            log_emotion(
                st.session_state["session_id"], display_emotion, confidence, intent, risk,
                mode="single", face_count=len(results)
            )

            # Overlay label on frame
            cv2.putText(
                frame, f"{display_emotion} ({confidence:.2f})", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )

            # Display intent + risk below the frame
            risk_color = "🔴" if risk == "high" else "🟡" if risk == "medium" else "🟢"
            result_placeholder.markdown(
                f"**Emotion:** `{display_emotion}` &nbsp;|&nbsp; "
                f"**Intent:** `{intent}` &nbsp;|&nbsp; "
                f"**Risk:** {risk_color} `{risk}` &nbsp;|&nbsp; "
                f"**Confidence:** `{confidence:.0%}`"
            )
        else:
            result_placeholder.caption("No face detected — align camera.")

        _, img_buf = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        frame_placeholder.image(img_buf.tobytes(), caption="Live Feed")

        time.sleep(0.5)
        render_rerun()
    else:
        if "prof_camera" in st.session_state:
            st.session_state["prof_camera"].release()
            del st.session_state["prof_camera"]
        st.info("Camera is disabled. Enable to start monitoring.")



def show_participant_webcam():
    """Display participant webcam sharing interface."""
    st.subheader("Participant Webcam")
    share_webcam = st.checkbox("Share Webcam to Professional", key="share_webcam")
    participant_preview = st.image([])
    
    if share_webcam and st.session_state.get("session_status") == "active":
        if "part_camera" not in st.session_state:
            st.session_state["part_camera"] = cv2.VideoCapture(0)
            
        camera = st.session_state["part_camera"]
        ret, frame = camera.read()
        
        if ret:
            upsert_participant_frame(st.session_state["session_id"], st.session_state["user_id"], frame)
            _, img_buf = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            participant_preview.image(img_buf.tobytes())
        else:
            set_participant_stream_active(st.session_state["session_id"], st.session_state["user_id"], False)
            st.warning("Webcam frame capture failed. Stream paused.")
        
        time.sleep(0.25)
        render_rerun()
    else:
        if "part_camera" in st.session_state:
            st.session_state["part_camera"].release()
            del st.session_state["part_camera"]
        set_participant_stream_active(st.session_state["session_id"], st.session_state["user_id"], False)


def show_analytics_section():
    """Display analytics section with charts and history."""
    import streamlit as st
    
    # Only run if we have a valid session
    if "session_id" not in st.session_state:
        return
        
    from logs.session_logger import get_emotion_history, get_suggestion_history, get_export_rows
    from utils.analysis_utils import compute_stress_duration_seconds, parse_distribution
    import pandas as pd
    
    # Emotion history chart
    history = get_emotion_history(st.session_state["session_id"])
    if history:
        st.markdown("#### Emotion Timeline")
        df = pd.DataFrame(history, columns=["timestamp", "emotion"])
        emotion_to_score = {"happy": 1, "neutral": 0, "sad": -1, "fear": -2, "angry": -3}
        df["emotion_score"] = df["emotion"].map(emotion_to_score)
        df = df.dropna(subset=["emotion_score"])
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            st.line_chart(df["emotion_score"])
    
    # Context-specific metrics
    if st.session_state.get("context") == "hr":
        from logs.session_logger import get_emotion_history_with_confidence
        from utils.analysis_utils import compute_hr_trend
        
        emotion_conf_history = get_emotion_history_with_confidence(st.session_state["session_id"])
        if emotion_conf_history:
            stress_duration = compute_stress_duration_seconds(emotion_conf_history)
            st.metric("High-Stress Signal Duration (s)", stress_duration)
    
    if st.session_state.get("context") == "doctor":
        from logs.session_logger import get_emotion_history_with_confidence
        
        emotion_conf_history = get_emotion_history_with_confidence(st.session_state["session_id"])
        if emotion_conf_history:
            distress_duration = compute_stress_duration_seconds(emotion_conf_history)
            st.metric("Distress Signal Duration (s)", distress_duration)
    
    # Suggestion history
    suggestion_rows = get_suggestion_history(st.session_state["session_id"])
    if suggestion_rows:
        st.markdown("#### Suggestion History")
        suggestion_df = pd.DataFrame(
            suggestion_rows,
            columns=["id", "timestamp", "emotion", "intent", "risk_level", "suggestion", "trigger_details"]
        )
        suggestion_df["timestamp"] = pd.to_datetime(suggestion_df["timestamp"], errors="coerce")
        parsed_trigger_details = suggestion_df["trigger_details"].apply(parse_distribution)
        suggestion_df["trigger_summary"] = parsed_trigger_details.apply(
            lambda details: (
                f"conf={details.get('confidence')} | mode={details.get('mode')} | "
                f"trend={details.get('hr_trend') or details.get('doctor_trend')}"
                if isinstance(details, dict) and details
                else ""
            )
        )
        st.dataframe(
            suggestion_df[["timestamp", "emotion", "intent", "suggestion", "trigger_summary"]],
            use_container_width=True
        )
    
    # Export functionality
    export_rows = get_export_rows(st.session_state["session_id"])
    if export_rows:
        export_df = pd.DataFrame(
            export_rows,
            columns=[
                "timestamp", "emotion", "confidence", "intent", "risk_level",
                "mode", "distribution", "face_count", "stability_index", "suggestion"
            ]
        )
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export Session Report (CSV)",
            data=csv_bytes,
            file_name=f"{st.session_state['session_id']}_report.csv",
            mime="text/csv",
        )
