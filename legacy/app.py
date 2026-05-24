import json
import logging
import time
from collections import defaultdict, deque

import cv2
import pandas as pd
import streamlit as st

from config import (
    DOCTOR_SUSTAINED_ALERT_SECONDS,
    LOW_CONFIDENCE_THRESHOLD,
    REMOTE_STREAM_MAX_AGE_SECONDS,
    STRESS_EMOTIONS,
)
from auth.login import (
    create_session,
    create_user,
    end_session,
    get_session,
    get_session_participants,
)
from logs.session_logger import (
    get_doctor_handover,
    upsert_doctor_handover,
)
from streaming.frame_store import (
    get_active_participant_streams,
)
from utils.analysis_utils import (
    render_rerun,
)

from database.models import create_tables
from ui.session_manager import initialize_session_state, show_login_interface, check_session_access
from ui.teacher import show_teacher_dashboard
from ui.student import show_student_dashboard
from ui.doctor import show_doctor_dashboard
from ui.hr import show_hr_dashboard
from ui.layouts import show_status_overview, show_auto_controls, show_system_status, show_live_camera, show_analytics_section
from core.emotion_engine import emotion_processor
from core.risk_engine import risk_engine

create_tables()

st.title("AI Assistive Communication System")

try:
    # Initialize session state FIRST
    initialize_session_state()
    
    # Show login interface if not logged in
    if "session_id" not in st.session_state:
        show_login_interface()
        st.stop()
    
    # Check session access AFTER initialization
    session_id = check_session_access()
    context = st.session_state.get("context", "teacher")
    user_type = st.session_state.get("user_type", "professional")
    session_row = get_session(session_id)
    session_status = session_row["status"] if session_row else "completed"
    
    # Show status overview
    show_status_overview(session_id, context, session_status)
    
    # Professional dashboard based on context
    if user_type == "professional":
        # Doctor-specific features
        if context == "doctor":
            st.subheader("Doctor Handover")
            existing_handover = get_doctor_handover(session_id)
            default_delegate = existing_handover["delegate_name"] if existing_handover else ""
            default_note = existing_handover["handover_note"] if existing_handover else ""
            delegate_name = st.text_input(
                "Delegate Caregiver",
                value=default_delegate or "",
                key="doctor_delegate_name",
                disabled=session_status != "active",
            )
            handover_note = st.text_area(
                "Handover Note",
                value=default_note or "",
                key="doctor_handover_note",
                help="Include red flags, medication timing and escalation instructions.",
                disabled=session_status != "active",
            )
            if st.button("Save Handover", key="doctor_save_handover", disabled=session_status != "active"):
                upsert_doctor_handover(session_id, delegate_name.strip(), handover_note.strip())
                st.success("Handover saved for delegate caregiver.")
            if existing_handover:
                st.caption(
                    f"Last updated: {existing_handover['updated_at']} | Delegate: {existing_handover['delegate_name'] or 'Not set'}"
                )
        
        # End session button
        if session_status == "active":
            if st.button("End Session", key="end_session"):
                end_session(session_id)
                st.success("Session marked as completed.")
                render_rerun()
    
    # Get participants
    participants = get_session_participants(session_id)
    if participants:
        participant_names = [row["name"] for row in participants]
        st.write("Participants:", ", ".join(participant_names))
    
    # Participant dashboard setup
    if user_type == "participant":
        if context == "teacher":
            show_student_dashboard(session_id, st.session_state["user_id"], st.session_state["display_name"])
        else:
            from ui.layouts import show_participant_webcam
            show_participant_webcam()
    
    # Professional remote monitoring + dashboard
    if user_type == "professional":
        st.subheader("Pulled Participant Views")
        pull_remote = st.checkbox("Pull Participant Webcams", key="pull_remote_webcams")

        # Default empty data so dashboard always renders
        emotion_data = {"results": [], "emotion_weights": {}, "no_face_participants": []}
        risk_summary = {
            "signals": [],
            "metrics": {
                "engaged_count": 0, "confusion_count": 0, "low_conf_count": 0,
                "total_students": 0, "attention_needed": 0,
                "engagement_pct": 0.0, "confusion_pct": 0.0, "avg_focus_score": 0.0
            },
            "priority_students": [],
            "class_state": "🟡 Waiting for data"
        }

        if pull_remote and session_status == "active":
            try:
                remote_streams = get_active_participant_streams(
                    session_id, max_age_seconds=REMOTE_STREAM_MAX_AGE_SECONDS
                )
                if not remote_streams:
                    st.info("No active participant webcam streams yet. Ask participants to share their webcam.")
                    st.session_state["no_face_events"] += 1
                else:
                    emotion_data = emotion_processor.process_remote_streams(session_id, context, remote_streams)
                    if context == "teacher":
                        risk_summary = risk_engine.compute_teacher_signals(
                            emotion_data["results"], session_id, participants
                        )
                    elif context == "doctor":
                        risk_summary = risk_engine.compute_doctor_signals(emotion_data["results"], session_id)
                    elif context == "hr":
                        risk_summary = risk_engine.compute_hr_signals(emotion_data["results"])
            except Exception as e:
                st.error(f"Error pulling participant video stream: {str(e)}")
                logging.error(f"Stream error: {e}")
        elif pull_remote and session_status != "active":
            st.info("Session is completed. Pulling is disabled.")

        # Always render the context-specific dashboard
        if context == "teacher":
            show_teacher_dashboard(session_id, context, session_status, participants, emotion_data, risk_summary)
        elif context == "doctor":
            show_doctor_dashboard(session_id, context, session_status, participants, emotion_data, risk_summary)
        elif context == "hr":
            show_hr_dashboard(session_id, context, session_status, emotion_data, risk_summary)

    
    # Professional live camera
    if user_type == "professional":
        show_live_camera()
    
    # Auto controls and system status
    auto_refresh, enable_tts = show_auto_controls()
    show_system_status()
    
    # Analytics section
    if user_type == "professional":
        show_analytics_section()

except Exception as e:
    st.error(f"A critical error occurred: {str(e)}")
    logging.exception("Critical error in main app execution.")
    st.info("Please refresh the page or contact support if the issue persists.")
