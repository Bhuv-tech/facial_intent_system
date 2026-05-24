import streamlit as st
from collections import deque


def initialize_session_state():
    """Initialize default session state values."""
    defaults = {
        "multi_face_mode": False,
        "input_mode": "Webcam",
        "emotion_buffer": deque(maxlen=30),
        "face_smoothers": {},
        "last_suggestion_signature": None,
        "no_face_events": 0,
        "latest_stream_issue": None,
        "last_generated_suggestion_signature": None,
        "last_suggestion_text": None,
        "last_suggestion_log_id": None,
        "last_spoken_signature": None,
        "face_track_smoothers": {},
        "hr_last_action": None,
        "doctor_last_action": None,
        "show_all_students": False,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_login_interface():
    """Display login interface for professionals and participants."""
    login_type = st.radio("Select Login Type", ["Professional", "Participant"])
    
    if login_type == "Professional":
        return show_professional_login()
    elif login_type == "Participant":
        return show_participant_login()
    
    return None


def show_professional_login():
    """Handle professional user login and session creation."""
    from auth.login import create_user, create_session, get_session
    from config import LOW_CONFIDENCE_THRESHOLD
    
    role = st.selectbox("Select Role", ["Teacher", "Doctor", "HR"])
    name = st.text_input("Enter Name (Optional)")
    input_mode = st.selectbox("Input Mode", ["Webcam"])
    multi_face_mode = st.checkbox(
        "Multi-Face Mode", value=st.session_state.get("multi_face_mode", False)
    )
    custom_session_code = st.text_input("Session Code (Optional)")

    if st.button("Login", key="professional_login"):
        desired_session_code = custom_session_code.strip() or None
        if desired_session_code and get_session(desired_session_code):
            st.error("Session code already exists. Use a different code.")
            st.stop()
        if not name:
            name = f"{role}_Auto"
        user_id = create_user(name, role.lower(), "professional")
        context = role.lower()
        try:
            session_id = create_session(user_id, context, desired_session_code)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
        
        # Update session state
        st.session_state["session_id"] = session_id
        st.session_state["user_id"] = user_id
        st.session_state["context"] = context
        st.session_state["input_mode"] = input_mode
        st.session_state["multi_face_mode"] = multi_face_mode
        st.session_state["user_type"] = "professional"
        st.session_state["display_name"] = name
        
        st.success(f"Session Created: {session_id}")
        st.rerun()
    
    return None


def show_participant_login():
    """Handle participant login to existing sessions."""
    from auth.login import create_user, attach_participant_to_session, get_session
    
    role = st.selectbox("Select Role", ["Student", "Patient", "Candidate"])
    name = st.text_input("Enter Name (Required)")
    session_code = st.text_input("Enter Session Code")

    if st.button("Login", key="participant_login"):
        if not name:
            st.error("Name is required")
        elif not session_code:
            st.error("Session Code required")
        else:
            session = get_session(session_code)
            if not session or session["status"] != "active":
                st.error("Invalid or inactive session code")
            else:
                user_id = create_user(name, role.lower(), "participant")
                attach_participant_to_session(session_code, user_id)
                
                # Update session state
                st.session_state["session_id"] = session_code
                st.session_state["user_id"] = user_id
                st.session_state["context"] = session["context"]
                st.session_state["user_type"] = "participant"
                st.session_state["display_name"] = name
                
                st.success("Connected to Session")
                st.rerun()
    
    return None


def check_session_access():
    """Check if user is logged in and redirect if not."""
    if "session_id" not in st.session_state:
        st.stop()
    return st.session_state.get("session_id")
