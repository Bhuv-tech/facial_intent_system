import streamlit as st
import pandas as pd
import time

from ui.layouts import show_auto_controls, show_system_status
from database.edu_actions import (
    log_class_phase, get_latest_class_phase, 
    get_active_nudges, set_break_status, get_break_status
)


def show_teacher_dashboard(session_id, context, session_status, participants, emotion_data, risk_summary):
    """Display the restructured educational Teacher Dashboard."""
    
    # --- Top Control Bar: Class Phase & Break ---
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        current_phase = get_latest_class_phase(session_id)
        phase = st.radio(
            "Class Phase",
            ["Lecture", "Revision", "Test"],
            index=["Lecture", "Revision", "Test"].index(current_phase),
            key="teacher_class_phase",
            horizontal=True,
        )
        if phase != current_phase:
            log_class_phase(session_id, phase)
            st.rerun()

    with col2:
        break_info = get_break_status(session_id)
        if break_info["active"]:
            if st.button("⏹️ End Break", key="end_break", use_container_width=True):
                set_break_status(session_id, "completed")
                st.rerun()
        else:
            if st.button("⏸️ Start Break", key="trigger_break", use_container_width=True):
                set_break_status(session_id, "active")
                st.rerun()
    
    with col3:
        if "start_time" not in st.session_state:
            st.session_state["start_time"] = time.time()
        elapsed = int(time.time() - st.session_state["start_time"])
        mins, secs = divmod(elapsed, 60)
        st.metric("Session Timer", f"{mins:02d}:{secs:02d}")

    st.markdown("---")

    # --- Panel 1: Class Overview ---
    metrics = risk_summary["metrics"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Engagement %", f"{metrics['engagement_pct']}%")
    m2.metric("Confusion %", f"{metrics['confusion_pct']}%")
    m3.metric("Active Students", f"{metrics['total_students']}")
    m4.metric("Avg Focus Score", f"{metrics['avg_focus_score']}")

    # --- Panel 2: Live Emotion/Engagement Chart ---
    if emotion_data["emotion_weights"]:
        st.markdown("#### Live Engagement Distribution")
        total_weight = sum(emotion_data["emotion_weights"].values())
        distribution = {
            emotion: round((weight / total_weight) * 100, 1)
            for emotion, weight in emotion_data["emotion_weights"].items()
        }
        # Sort so positive is first
        sorted_dist = dict(sorted(distribution.items(), key=lambda item: item[1], reverse=True))
        st.bar_chart(pd.Series(sorted_dist), horizontal=True)

    st.markdown("---")

    # --- Panel 3: Student Status Grid & Alerts ---
    grid_col, alert_col = st.columns([2, 1])

    with grid_col:
        st.markdown("#### Student Status Grid")
        if risk_summary["signals"]:
            # Display students in a grid of 3 columns
            student_cols = st.columns(3)
            for i, student in enumerate(risk_summary["signals"]):
                with student_cols[i % 3]:
                    # Color coding based on state
                    color = "green" if student["focus_score"] > 0.7 else "orange" if student["focus_score"] > 0.4 else "red"
                    status_text = "Attentive" if color == "green" else "Low Focus" if color == "orange" else "Away/Distracted"
                    
                    st.markdown(
                        f"""
                        <div style="border: 1px solid {color}; padding: 10px; border-radius: 5px; margin-bottom: 10px; background-color: rgba(0,0,0,0.05);">
                            <p style="margin:0; font-weight:bold;">{student['student']}</p>
                            <p style="margin:0; font-size:0.8em; color:{color};">{status_text}</p>
                            <p style="margin:0; font-size:0.7em;">
                                <b>Intent:</b> {student.get('intent', 'unknown').replace('_', ' ')}<br>
                                <b>Risk:</b> {student.get('risk', 'low')}<br>
                                <b>Focus:</b> {int(student['focus_score']*100)}% (Conf: {int(student.get('confidence', 0)*100)}%)
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        else:
            st.info("No active students detected.")

    with alert_col:
        st.markdown("#### 🔔 Alerts Panel")
        
        # Nudges (Re-explanation requests)
        nudges = get_active_nudges(session_id)
        if nudges:
            st.error("❗ Re-explanation Requested")
            for nudge in nudges:
                time_str = nudge['created_at'].split()[1] if nudge.get('created_at') else "recently"
                st.caption(f"• **{nudge['name']}** requested help {time_str}")
        
        # Confusion Spikes Priority Logic (sustained > 20s and multiple, or very sustained > 40s)
        priority_students = risk_summary["priority_students"]
        sustained_issues = [s for s in priority_students if s.get("duration", 0) >= 20]
        show_confusion = len(sustained_issues) >= 2 or any(s.get("duration", 0) >= 40 for s in sustained_issues)
        
        if show_confusion:
            st.warning("⚠️ Sustained Confusion Detected")
            for student in sustained_issues[:3]:
                st.caption(f"• **{student['name']}** ({student.get('duration', 0)}s)")
        
        if not nudges and not show_confusion:
            st.success("Internal class state is stable.")

    st.markdown("---")

    # --- Panel 4: Smart Actions ---
    st.markdown("#### 🎯 Smart Actions")
    
    # Priority Logic: Calculate top 2 contextually relevant actions
    actions_to_show = []
    
    if break_info["active"]:
        actions_to_show.append(("⏸️ End Break", "action_end_break", "Break ended."))
    else:
        if metrics["confusion_pct"] > 20 or nudges:
            actions_to_show.append(("🎤 Repeat Last Explanation", "action_repeat", "Paused to re-explain concepts."))
        
        if metrics["engagement_pct"] < 50:
            actions_to_show.append(("📝 Start Quiz/Activity", "action_quiz", "Triggered interaction mode."))
            
        if "start_time" in st.session_state and (time.time() - st.session_state["start_time"] > 1800):
            actions_to_show.append(("⏸️ Suggest Short Break", "action_break", "Break initiated."))
            
        if not actions_to_show:
            actions_to_show.append(("🏁 Continue Lesson Plan", "action_continue", "Continuing smoothly."))
            
    # Show only the top 1 or 2
    actions_to_show = actions_to_show[:2]
    
    cols = st.columns(len(actions_to_show))
    for i, (label, key, action_text) in enumerate(actions_to_show):
        with cols[i]:
            if st.button(label, key=key, use_container_width=True):
                st.session_state["teacher_action"] = action_text
                if key == "action_break":
                    set_break_status(session_id, "active")
                    st.rerun()
                elif key == "action_end_break":
                    set_break_status(session_id, "completed")
                    st.rerun()

    if "teacher_action" in st.session_state:
        st.info(f"Last Action: {st.session_state['teacher_action']}")

    # --- Layer 5: Analytics & Timeline ---
    with st.expander("📊 Post-Class Analytics Preview", expanded=False):
        # Attention Timeline (Mocked for now since we need persistent historical query)
        st.markdown("#### Engagement Timeline")
        st.caption("Attention levels over the last 10 minutes")
        # In a real implementation, we'd fetch emotion_logs over time
        st.line_chart(pd.DataFrame({"Attention": [metrics['engagement_pct']] * 10}))
        
        st.markdown("#### Full Participation Table")
        if risk_summary["signals"]:
            st.table(pd.DataFrame(risk_summary["signals"])[["student", "focus_score", "emotion", "confidence"]])
