import streamlit as st
import pandas as pd

from ui.layouts import show_auto_controls, show_system_status


def show_hr_dashboard(session_id, context, session_status, emotion_data, risk_summary):
    """Display HR-specific dashboard with subtle interface."""
    from logs.session_logger import get_emotion_history_with_confidence
    from utils.analysis_utils import compute_hr_trend, parse_distribution
    
    st.write(f"Active participant webcams: {len(emotion_data['results'])}")
    
    if not emotion_data["results"]:
        st.warning("No active candidate webcams. Check candidate connection.")
        return
    
    # Subtle status card
    state_label = risk_summary["candidate_state"]
    confidence_value = risk_summary["confidence"]
    
    st.markdown(f"### Candidate State: {state_label}")
    
    # Generate subtle suggestion
    from llm.local_llm import generate_suggestion
    
    if confidence_value >= 0.5:  # LOW_CONFIDENCE_THRESHOLD
        latest_data = emotion_data["results"][0]  # Get first result
        signature = (latest_data["updated_at"], latest_data["emotion"], latest_data["intent"], latest_data["risk"])
        if st.session_state["last_generated_suggestion_signature"] != signature:
            suggestion = generate_suggestion(
                context=context, emotion=latest_data["emotion"], 
                intent=latest_data["intent"], risk=latest_data["risk"]
            )
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
        latest_data = emotion_data["results"][0]
        st.metric("Interview Signal", latest_data["intent"])
        st.metric("Confidence", confidence_value)
        
        emotion_conf_history = get_emotion_history_with_confidence(session_id)
        hr_trend = compute_hr_trend(emotion_conf_history)
        st.caption(f"60s Trend: {hr_trend[0]} | {hr_trend[1]}")
        
        # Emotion distribution
        if emotion_data["emotion_weights"]:
            st.markdown("#### Emotion Distribution")
            total_weight = sum(emotion_data["emotion_weights"].values())
            distribution = {
                emotion: round((weight / total_weight) * 100, 2)
                for emotion, weight in emotion_data["emotion_weights"].items()
            }
            dist_series = pd.Series(distribution).sort_values(ascending=False)
            st.bar_chart(dist_series)
        
        # Suggestion history
        from logs.session_logger import get_suggestion_history
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
