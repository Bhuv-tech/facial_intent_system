import streamlit as st
import pandas as pd

from ui.layouts import show_auto_controls, show_system_status


def show_doctor_dashboard(session_id, context, session_status, participants, emotion_data, risk_summary):
    """Display doctor-specific dashboard with risk card and actions."""
    if emotion_data["results"]:
        patient_names = [result["name"] for result in emotion_data["results"]]
        spotlight_options = ["None"] + patient_names
        spotlight_name = st.selectbox(
            "Spotlight Patient Camera",
            spotlight_options,
            key="doctor_spotlight_patient",
        )
    
    st.write(f"Active participant webcams: {len(emotion_data['results'])}")
    st.caption("Weighted by confidence score")
    
    if not emotion_data["results"]:
        st.warning("No face detected. Align camera.")
        st.session_state["latest_stream_issue"] = "No active participant webcam stream."
        st.session_state["no_face_events"] += 1
        return
    
    # Dominant Risk Card
    top_patient = risk_summary["top_patient"]
    if top_patient["risk"] == "high":
        risk_emoji = "🔴"
        risk_text = "High Risk"
    elif top_patient["risk"] == "medium":
        risk_emoji = "🟡"
        risk_text = "Medium Risk"
    else:
        risk_emoji = "🟢"
        risk_text = "Low Risk"
    
    stress_percent = int(top_patient["confidence"] * 100)
    duration_min = top_patient["high_risk_duration_s"] // 60
    
    # Large centered risk card
    st.markdown(f"<div style='text-align: center; padding: 2rem; border: 2px solid #ff4444; border-radius: 10px; margin: 1rem 0;'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color: #ff4444; margin: 0;'>{risk_emoji} {risk_text}: {top_patient['patient']}</h2>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin: 0.5rem 0;'>Stress: {stress_percent}%</h3>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='margin: 0.5rem 0;'>Duration: {duration_min} min</h3>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Action Panel
    st.markdown("### 🚨 Action Panel")
    action_cols = st.columns(3)
    
    with action_cols[0]:
        if st.button("📢 Send Calming Prompt", key="doctor_action_calm", use_container_width=True):
            from logs.session_logger import log_doctor_alert_action
            log_doctor_alert_action(session_id, top_patient["participant_id"], top_patient["patient"], "send_calming_prompt")
            st.session_state["doctor_last_action"] = "Sent calming prompt."
    
    with action_cols[1]:
        if st.button("🩺 Ask Vitals", key="doctor_action_vitals", use_container_width=True):
            from logs.session_logger import log_doctor_alert_action
            log_doctor_alert_action(session_id, top_patient["participant_id"], top_patient["patient"], "ask_caregiver_check_vitals")
            st.session_state["doctor_last_action"] = "Requested caregiver vitals check."
    
    with action_cols[2]:
        if st.button("🚨 Escalate Emergency", key="doctor_action_escalate", use_container_width=True):
            from logs.session_logger import log_doctor_alert_action
            log_doctor_alert_action(session_id, top_patient["participant_id"], top_patient["patient"], "escalate_emergency_protocol")
            st.session_state["doctor_last_action"] = "Emergency escalation logged."
    
    if st.session_state.get("doctor_last_action"):
        st.success(f"Action: {st.session_state['doctor_last_action']}")
    
    st.markdown("---")
    
    # Secondary Data (Collapsed)
    with st.expander("📊 Secondary Data", expanded=False):
        # Risk Timeline
        st.markdown("#### Risk Timeline")
        from logs.session_logger import get_emotion_history_with_confidence
        emotion_conf_history = get_emotion_history_with_confidence(session_id)
        if emotion_conf_history:
            df = pd.DataFrame(emotion_conf_history, columns=["timestamp", "emotion", "confidence"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            st.line_chart(df["confidence"])
        
        # Emotion Distribution
        if emotion_data["emotion_weights"]:
            st.markdown("#### Emotion Distribution")
            total_weight = sum(emotion_data["emotion_weights"].values())
            distribution = {
                emotion: round((weight / total_weight) * 100, 2)
                for emotion, weight in emotion_data["emotion_weights"].items()
            }
            dist_series = pd.Series(distribution).sort_values(ascending=False)
            st.bar_chart(dist_series)
        
        # Audit Logs
        st.markdown("#### Audit Logs")
        from logs.session_logger import get_doctor_alert_actions
        actions = get_doctor_alert_actions(session_id, limit=20)
        if actions:
            action_df = pd.DataFrame(actions, columns=["patient", "action", "actor", "timestamp"])
            st.dataframe(action_df, use_container_width=True)
        
        # Full Patient Queue
        st.markdown("#### Full Patient Queue")
        doctor_df = pd.DataFrame(risk_summary["signals"])
        st.dataframe(doctor_df, use_container_width=True)
