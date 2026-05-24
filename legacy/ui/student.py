import streamlit as st
import time
import cv2
from database.edu_actions import (
    send_nudge, get_break_status,
    get_student_focus_stats, update_student_focus
)
from streaming.frame_store import upsert_participant_frame, set_participant_stream_active
from utils.analysis_utils import render_rerun
from core.realtime_emotion import predict_emotion
from core.mapping import map_emotion_to_intent
from core.context_logic import compute_risk
from core.risk_engine import risk_engine

def show_student_dashboard(session_id, user_id, user_name):
    """Display the educational Student Dashboard."""
    
    # --- Check for Active Break ---
    break_info = get_break_status(session_id)
    if break_info["active"]:
        show_break_mode(break_info)
        return

    # --- Header ---
    st.subheader(f"Student Dashboard: {user_name}")
    st.caption(f"Session: {session_id}")

    # --- Focus Meter & Interaction ---
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 🎯 Your Focus Meter")
        stats = get_student_focus_stats(session_id, user_id)
        focus_score = stats["focus_score"]
        streak = stats["streak_count"]
        
        import random
        # Softened guidance based on focus
        if focus_score > 0.7:
            color = "green"
            message = random.choice([
                "Doing great, keep it up!",
                "Excellent engagement!",
                "Maintain this momentum"
            ])
        elif focus_score > 0.4:
            color = "orange"
            message = random.choice([
                "You're slightly losing focus — try to re-engage",
                "Let’s refocus on this part",
                "Stay with it, you're doing well"
            ])
        else:
            color = "red"
            message = random.choice([
                "Take a breath and gently bring your attention back",
                "This part is important — stay with it",
                "You might want to re-engage here",
                "A quick reset will help you refocus"
            ])

        st.markdown(
            f"""
            <div style="padding: 20px; border-radius: 10px; border: 2px solid {color}; text-align: center;">
                <h3 style="color: {color}; margin: 0;">{message}</h3>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown("#### 🤝 Interaction Tools")
        if st.button("🎤 Request Re-explanation", key="nudge_reexplain", use_container_width=True):
            send_nudge(session_id, user_id, "re-explanation")
            st.success("Teacher has been notified.")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("👍 Understood", key="feedback_up", use_container_width=True):
                st.toast("Feedback sent!")
        with c2:
            if st.button("👎 Confused", key="feedback_down", use_container_width=True):
                send_nudge(session_id, user_id, "confusion")
                st.toast("Feedback sent!")
        
        st.checkbox("Low Power Mode (Slower Scan)", key="student_low_power")

    st.markdown("---")

    # --- Webcam Sharing (Hidden/Small Preview) ---
    st.markdown("#### 📷 Live Feed Status")
    share_webcam = st.toggle("Share Webcam for Focus Analysis", value=True, key="share_webcam")
    
    if share_webcam:
        if "student_camera" not in st.session_state:
            st.session_state["student_camera"] = cv2.VideoCapture(0)
            
        camera = st.session_state["student_camera"]
        ret, frame = camera.read()
        
        if ret:
            # Upsert for teacher to see
            upsert_participant_frame(session_id, user_id, frame)

            # Show live preview for student (use bytes to avoid MediaFileStorageError)
            _, img_buf = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            st.image(img_buf.tobytes(), width=320, caption="Your live webcam feed")

            # Full analysis: emotion → intent → risk → focus
            emotion, confidence = predict_emotion(frame)
            if emotion and confidence and confidence > 0:
                intent = map_emotion_to_intent(emotion, "teacher")
                risk = compute_risk(emotion, confidence, "teacher")
                focus_score = risk_engine.compute_focus_score(emotion, confidence)

                # Persist focus so the Focus Meter above reflects real data
                update_student_focus(session_id, user_id, focus_score)

                # State label for plain-English feedback
                state_map = {
                    "happy": "😊 Engaged & Understanding",
                    "neutral": "🙂 Listening Attentively",
                    "sad": "😔 Possible Confusion",
                    "fear": "😟 Test Anxiety / Pressure",
                    "angry": "😤 Frustrated / Overloaded",
                    "disgust": "😑 Disinterested",
                    "surprise": "😲 Sudden Realization",
                }
                state = state_map.get(emotion, "🤔 Analysing...")
                st.markdown(
                    f"""
                    <div style="padding:10px; border-radius:8px; background:rgba(0,0,0,0.04); margin-top:8px;">
                        <p style="margin:0; font-size:1.1em; text-align:center;">{state}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        else:
            set_participant_stream_active(session_id, user_id, False)
            st.warning("⚠️ Camera occupied or disconnected. Close other apps using the camera and retry.")
            
        # Refresh logic — faster so UI stays responsive
        delay = 1.5 if st.session_state.get("student_low_power") else 0.5
        time.sleep(delay)
        render_rerun()
    else:
        if "student_camera" in st.session_state:
            st.session_state["student_camera"].release()
            del st.session_state["student_camera"]
        set_participant_stream_active(session_id, user_id, False)
        st.info("Webcam sharing is disabled.")

def show_break_mode(break_info):
    """Display a dedicated break screen for students."""
    st.balloons()
    st.markdown(
        """
        <div style="text-align: center; padding: 50px;">
            <h1>☕ Take a Break!</h1>
            <p>Your teacher has initiated a class-wide break.</p>
            <div style="font-size: 3em;">🧘‍♀️ 🍎 🥤</div>
            <p style="margin-top: 20px;">The session will resume automatically when the teacher ends the break.</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Placeholder for mini-games/quizzes
    with st.expander("🎮 Quick Brain Games (Optional)", expanded=True):
        st.write("Think of a number between 1 and 10...")
        if st.button("Reveal lucky number"):
            import random
            st.success(f"Your lucky number is {random.randint(1, 10)}!")
    
    time.sleep(5)
    render_rerun()
