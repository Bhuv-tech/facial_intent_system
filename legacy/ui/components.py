import streamlit as st
import pandas as pd
import cv2

from config import LOW_CONFIDENCE_THRESHOLD
from core.realtime_emotion import predict_emotion, predict_emotions
from core.smoothing import EmotionSmoother
from core.context_logic import compute_risk
from core.mapping import map_emotion_to_intent
from llm.local_llm import generate_suggestion
from logs.session_logger import (
    log_emotion,
    log_suggestion,
    log_suggestion_feedback,
    get_emotion_history,
    get_suggestion_history,
)
from streaming.frame_store import (
    get_active_participant_streams,
    set_participant_stream_active,
    upsert_participant_frame,
)
from utils.analysis_utils import (
    compute_stability_index,
    parse_distribution,
    render_rerun,
    compute_stress_duration_seconds,
    hr_state_label,
    compute_hr_trend,
    teacher_state_label,
    compute_teacher_watchlist,
    doctor_state_label,
    compute_doctor_risk_duration_seconds,
    compute_doctor_trend,
)


def show_teacher_dashboard(session_id, context, session_status, participants, remote_streams):
    """Display teacher-specific dashboard with clean UI layers."""
    from config import TEACHER_WATCHLIST_WINDOW_SECONDS
    
    if not remote_streams:
        st.warning("No active participant webcams. Check participant connections.")
        return
    
    # Process emotions and generate signals
    teacher_signals = []
    remote_emotion_weights = {}
    remote_conf_by_emotion = {}
    no_face_students = []
    
    for stream in remote_streams:
        frame = stream["frame"]
        emotion, confidence = predict_emotion(frame)
        display_emotion = None
        
        if emotion is None:
            st.warning(f"No face detected for {stream['name']}. Align camera.")
            no_face_students.append(stream["name"])
        elif confidence < LOW_CONFIDENCE_THRESHOLD:
            st.info(f"Low confidence prediction ({confidence:.2f}) for {stream['name']}. Monitoring...")
        else:
            smoother_key = f"remote_{stream['participant_id']}"
            if smoother_key not in st.session_state["face_smoothers"]:
                st.session_state["face_smoothers"][smoother_key] = EmotionSmoother(buffer_size=10)
            smoother = st.session_state["face_smoothers"][smoother_key]
            smoother.update(emotion)
            display_emotion = smoother.get_stable_emotion() or emotion
            remote_emotion_weights[display_emotion] = remote_emotion_weights.get(display_emotion, 0) + confidence
            remote_conf_by_emotion[display_emotion] = remote_conf_by_emotion.get(display_emotion, []) + [confidence]
            
            intent = map_emotion_to_intent(display_emotion, context)
            risk = compute_risk(display_emotion, confidence, context)
            log_emotion(
                session_id, display_emotion, confidence, intent, risk,
                participant_id=stream["participant_id"], mode="remote_single", face_count=1
            )
            
            cv2.putText(
                frame, f"{display_emotion} ({confidence:.2f})", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )
        
        teacher_signals.append({
            "student": stream["name"],
            "state": teacher_state_label(display_emotion or emotion, confidence),
            "emotion": display_emotion or emotion or "none",
            "confidence": round(confidence, 2),
            "updated_at": stream["updated_at"],
        })
    
    # Layer 1: Status Overview
    high_conf_signals = [row for row in teacher_signals if row["confidence"] >= LOW_CONFIDENCE_THRESHOLD]
    engaged_states = {"engaged", "attentive"}
    confusion_states = {"confused_or_withdrawn", "test_anxiety", "frustrated", "disengaged"}
    engaged_count = sum(1 for row in high_conf_signals if row["state"] in engaged_states)
    confusion_count = sum(1 for row in high_conf_signals if row["state"] in confusion_states)
    low_conf_count = sum(1 for row in teacher_signals if row["state"] == "insufficient_evidence")
    
    total_students = len(remote_streams)
    attention_needed = confusion_count + low_conf_count
    
    if attention_needed == 0:
        class_state = "🟢 Fully Engaged"
    elif attention_needed <= 2:
        class_state = "🟡 Slightly Distracted"
    else:
        class_state = "🔴 High Attention Needed"
    
    st.markdown(f"### {class_state}")
    st.markdown(f"**{attention_needed} Students Need Attention**")
    st.markdown(f"Test Mode: {'ON' if 'Test Mode' in str(st.session_state.get('teacher_mode', '')) else 'OFF'} | Active Cameras: {total_students}/{len(participants) if participants else total_students}")
    st.markdown("---")
    
    # Layer 2: Priority Alerts
    watchlist = compute_teacher_watchlist(session_id, participants)
    priority_students = []
    
    for signal in teacher_signals:
        if signal["state"] in confusion_states or signal["state"] == "insufficient_evidence":
            student_name = signal["student"]
            duration = 0
            for watch in watchlist:
                if watch["name"] == student_name:
                    duration = watch.get("duration_seconds", 0)
                    break
            
            if signal["state"] in confusion_states:
                priority_students.append({"name": student_name, "issue": "Sustained Confusion", "duration": duration})
            else:
                priority_students.append({"name": student_name, "issue": "Low Confidence", "duration": duration})
    
    if priority_students:
        st.markdown("### ⚠️ Priority Students")
        for student in priority_students[:3]:
            duration_min = student["duration"] // 60 if student["duration"] > 0 else 1
            st.markdown(f"⚠️ **{student['name']}** – {student['issue']} ({duration_min} min)")
        
        if len(priority_students) > 3:
            st.markdown(f"*...and {len(priority_students) - 3} more students*")
    
    if st.button("View All Students", key="view_all_students"):
        st.session_state["show_all_students"] = not st.session_state.get("show_all_students", False)
    
    if st.session_state.get("show_all_students", False):
        st.subheader("All Student States")
        signal_df = pd.DataFrame(teacher_signals)
        if not signal_df.empty:
            st.dataframe(signal_df, use_container_width=True)
    
    st.markdown("---")
    
    # Layer 3: Smart Action Panel
    st.markdown("### 🎯 Smart Actions")
    action_cols = st.columns(3)
    
    with action_cols[0]:
        if confusion_count > 0:
            if st.button("🎤 Repeat Last Explanation", key="action_repeat"):
                st.session_state["teacher_action"] = "Repeated last explanation for confused students."
        else:
            st.button("🎤 Repeat Last Explanation", key="action_repeat", disabled=True, help="No confused students detected")
    
    with action_cols[1]:
        if attention_needed > 0:
            if st.button("📝 Ask Comprehension Question", key="action_comprehension"):
                st.session_state["teacher_action"] = "Asked comprehension check question."
        else:
            st.button("📝 Ask Comprehension Question", key="action_comprehension", disabled=True, help="All students engaged")
    
    with action_cols[2]:
        if engaged_count > 2 and attention_needed == 0:
            if st.button("🎯 Switch to Interactive Poll", key="action_poll"):
                st.session_state["teacher_action"] = "Started interactive poll to maintain engagement."
        else:
            st.button("🎯 Switch to Interactive Poll", key="action_poll", disabled=True, help="Need higher engagement first")
    
    if st.session_state.get("teacher_action"):
        st.success(f"Action: {st.session_state['teacher_action']}")
    
    st.markdown("---")
    
    # Layer 4: Analytics (collapsed)
    with st.expander("📊 Deep Analytics", expanded=False):
        if remote_emotion_weights:
            st.markdown("#### Emotion Distribution")
            total_weight = sum(remote_emotion_weights.values())
            distribution = {
                emotion: round((weight / total_weight) * 100, 2)
                for emotion, weight in remote_emotion_weights.items()
            }
            dist_series = pd.Series(distribution).sort_values(ascending=False)
            st.bar_chart(dist_series)
        
        history = get_emotion_history(session_id)
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
        
        latest = get_latest_emotion(session_id)
        if latest and latest.get("stability_index"):
            st.markdown("#### Stability Index")
            st.metric("Current Stability", latest["stability_index"])
        
        if teacher_signals:
            st.markdown("#### Full Student Table")
            signal_df = pd.DataFrame(teacher_signals)
            st.dataframe(signal_df, use_container_width=True)


def show_doctor_dashboard(session_id, context, session_status, participants, remote_streams):
    """Display doctor-specific dashboard with risk card and actions."""
    from config import DOCTOR_SUSTAINED_ALERT_SECONDS
    
    if not remote_streams:
        st.warning("No active patient webcams. Check patient connections.")
        return
    
    # Process patient signals
    doctor_signals = []
    remote_emotion_weights = {}
    no_face_patients = []
    
    for stream in remote_streams:
        frame = stream["frame"]
        emotion, confidence = predict_emotion(frame)
        display_emotion = None
        
        if emotion is None:
            no_face_patients.append(stream["name"])
        elif confidence < LOW_CONFIDENCE_THRESHOLD:
            st.info(f"Low confidence prediction ({confidence:.2f}) for {stream['name']}. Monitoring...")
        else:
            display_emotion = emotion
            remote_emotion_weights[display_emotion] = remote_emotion_weights.get(display_emotion, 0) + confidence
            
            intent = map_emotion_to_intent(display_emotion, context)
            risk = compute_risk(display_emotion, confidence, context)
            log_emotion(
                session_id, display_emotion, confidence, intent, risk,
                participant_id=stream["participant_id"], mode="remote_single", face_count=1
            )
            
            cv2.putText(
                frame, f"{display_emotion} ({confidence:.2f})", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )
        
        participant_risk_seconds = compute_doctor_risk_duration_seconds(session_id, stream["participant_id"])
        effective_emotion = display_emotion or emotion
        risk = compute_risk(effective_emotion if effective_emotion else "neutral", confidence, context)
        priority_score = round(
            (confidence * 100) + (participant_risk_seconds * 0.8) + 
            (30 if risk == "high" else 12 if risk == "medium" else 0), 2
        )
        
        doctor_signals.append({
            "participant_id": stream["participant_id"],
            "patient": stream["name"],
            "state": doctor_state_label(effective_emotion, confidence),
            "emotion": effective_emotion or "none",
            "confidence": round(confidence, 2),
            "risk": risk,
            "high_risk_duration_s": participant_risk_seconds,
            "priority_score": priority_score,
            "updated_at": stream["updated_at"],
        })
    
    # Sort by priority
    doctor_signals = sorted(doctor_signals, key=lambda row: row["priority_score"], reverse=True)
    
    # Dominant Risk Card
    top_patient = doctor_signals[0]
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
        if remote_emotion_weights:
            st.markdown("#### Emotion Distribution")
            total_weight = sum(remote_emotion_weights.values())
            distribution = {
                emotion: round((weight / total_weight) * 100, 2)
                for emotion, weight in remote_emotion_weights.items()
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
        doctor_df = pd.DataFrame(doctor_signals)
        st.dataframe(doctor_df, use_container_width=True)


def show_hr_dashboard(session_id, context, session_status, remote_streams):
    """Display HR-specific dashboard with subtle interface."""
    from logs.session_logger import get_emotion_history_with_confidence
    
    if not remote_streams:
        st.warning("No active candidate webcams. Check candidate connection.")
        return
    
    # Get latest emotion data
    latest = get_latest_emotion(session_id)
    if not latest:
        st.info("No emotion data available yet.")
        return
    
    # Subtle status card
    state_label = hr_state_label(latest["emotion"], latest["confidence"])
    confidence_value = round(latest["confidence"], 2)
    
    st.markdown(f"### Candidate State: {state_label}")
    
    # Generate subtle suggestion
    if confidence_value >= LOW_CONFIDENCE_THRESHOLD:
        signature = (latest["timestamp"], latest["emotion"], latest["intent"], latest["risk_level"])
        if st.session_state["last_generated_suggestion_signature"] != signature:
            try:
                suggestion = generate_suggestion(
                    context=context, emotion=latest["emotion"], 
                    intent=latest["intent"], risk=latest["risk_level"]
                )
            except Exception as e:
                import logging
                logging.error(f"LLM suggestion error: {e}")
                suggestion = "Connection to AI assistant failed. Interview proceeding normally."
            # Make suggestion more subtle for HR
            if "high risk" in suggestion.lower() or "alert" in suggestion.lower():
                suggestion = "Consider offering a brief pause to help the candidate feel more comfortable."
            st.session_state["last_generated_suggestion_signature"] = signature
            st.session_state["last_suggestion_text"] = suggestion
        else:
            suggestion = st.session_state.get("last_suggestion_text") or "Interview proceeding normally."
        
        st.markdown(f"**Suggested:** {suggestion}")
    
    # Quick actions (subtle)
    st.markdown("---")
    action_cols = st.columns(3)
    
    with action_cols[0]:
        if st.button("🔄 Rephrase Question", key="hr_action_rephrase", use_container_width=True):
            st.session_state["hr_last_action"] = "Question rephrased for clarity."
    
    with action_cols[1]:
        if st.button("⏸️ Offer Pause", key="hr_action_pause", use_container_width=True):
            st.session_state["hr_last_action"] = "Offered 20-second pause to candidate."
    
    with action_cols[2]:
        if st.button("💬 Follow-up Example", key="hr_action_example", use_container_width=True):
            st.session_state["hr_last_action"] = "Requested specific example from candidate."
    
    if st.session_state.get("hr_last_action"):
        st.caption(f"Last action: {st.session_state['hr_last_action']}")
    
    # Advanced Analytics (collapsed)
    with st.expander("📊 Advanced Analytics", expanded=False):
        # Original metrics hidden here
        st.metric("Interview Signal", latest["intent"])
        st.metric("Confidence", confidence_value)
        
        emotion_conf_history = get_emotion_history_with_confidence(session_id)
        hr_trend = compute_hr_trend(emotion_conf_history)
        st.caption(f"60s Trend: {hr_trend[0]} | {hr_trend[1]}")
        
        # Emotion distribution
        distribution = parse_distribution(latest["distribution"])
        if distribution:
            st.markdown("#### Emotion Distribution")
            dist_series = pd.Series(distribution).sort_values(ascending=False)
            st.bar_chart(dist_series)
        
        # Suggestion history
        suggestion_rows = get_suggestion_history(session_id)
        if suggestion_rows:
            st.markdown("#### Suggestion History")
            suggestion_df = pd.DataFrame(
                suggestion_rows,
                columns=["id", "timestamp", "emotion", "intent", "risk_level", "suggestion", "trigger_details"]
            )
            suggestion_df["timestamp"] = pd.to_datetime(suggestion_df["timestamp"], errors="coerce")
            st.dataframe(
                suggestion_df[["timestamp", "emotion", "intent", "suggestion"]],
                use_container_width=True
            )
