"""
Risk assessment and context-specific state management.
"""

from config import LOW_CONFIDENCE_THRESHOLD
from logs.session_logger import get_participant_emotion_history
from utils.analysis_utils import (
    compute_doctor_risk_duration_seconds,
    compute_teacher_watchlist,
    doctor_state_label,
    hr_state_label,
    teacher_state_label,
)
from database.edu_actions import update_student_focus


class RiskEngine:
    """Handles all risk assessment and state calculations."""
    
    def compute_teacher_signals(self, emotion_results, session_id, participants):
        """Generate teacher-specific signals from emotion data."""
        from config import TEACHER_WATCHLIST_WINDOW_SECONDS
        
        teacher_signals = []
        engaged_states = {"engaged", "attentive"}
        confusion_states = {"confused_or_withdrawn", "test_anxiety", "frustrated", "disengaged"}
        
        for result in emotion_results:
            from core.mapping import map_emotion_to_intent
            from core.context_logic import compute_risk
            
            state = teacher_state_label(result["emotion"], result["confidence"])
            focus_score = self.compute_focus_score(result["emotion"], result["confidence"])
            intent = map_emotion_to_intent(result["emotion"], "teacher", result["confidence"])
            risk = compute_risk(result["emotion"], result["confidence"], "teacher")
            anomalies = self.detect_behavior_anomalies(result)
            
            # Update focus stats in DB
            update_student_focus(session_id, result["participant_id"], focus_score)
            
            teacher_signals.append({
                "participant_id": result["participant_id"],
                "student": result["name"],
                "state": state,
                "emotion": result["emotion"],
                "intent": intent,
                "risk": risk,
                "confidence": round(result["confidence"], 2),
                "focus_score": round(focus_score, 2),
                "anomalies": anomalies,
                "updated_at": result["updated_at"],
            })
        
        # Calculate metrics
        high_conf_signals = [row for row in teacher_signals if row["confidence"] >= LOW_CONFIDENCE_THRESHOLD]
        engaged_count = sum(1 for row in high_conf_signals if row["state"] in engaged_states)
        confusion_count = sum(1 for row in high_conf_signals if row["state"] in confusion_states)
        low_conf_count = sum(1 for row in teacher_signals if row["state"] == "insufficient_evidence")
        
        # Get priority students
        watchlist = compute_teacher_watchlist(session_id, participants)
        priority_students = self._get_priority_students(teacher_signals, watchlist, confusion_states)
        
        # Calculate engagement % and confusion %
        total = len(emotion_results) if emotion_results else 1
        avg_focus = sum(r["focus_score"] for r in teacher_signals) / total
        
        return {
            "signals": teacher_signals,
            "metrics": {
                "engaged_count": engaged_count,
                "confusion_count": confusion_count,
                "low_conf_count": low_conf_count,
                "total_students": len(emotion_results),
                "attention_needed": confusion_count + low_conf_count,
                "engagement_pct": round(engaged_count / total * 100, 1),
                "confusion_pct": round(confusion_count / total * 100, 1),
                "avg_focus_score": round(avg_focus, 2)
            },
            "priority_students": priority_students,
            "class_state": self._get_class_state(confusion_count + low_conf_count)
        }

    def compute_focus_score(self, emotion, confidence):
        """Calculate a focus score (0.0 to 1.0) based on emotion."""
        weights = {
            "happy": 0.8,    # Positive engagement
            "neutral": 1.0,  # Pure focus
            "surprise": 0.7, # Momentary interest
            "sad": 0.3,      # Disengaged/Low mood
            "fear": 0.4,      # Anxiety/Internal distress
            "angry": 0.2,    # Frustration/Conflict
            "disgust": 0.1   # Strong aversion/Boredom
        }
        base_score = weights.get(emotion, 0.5)
        # Adjust by confidence
        return (base_score * confidence) + (0.5 * (1 - confidence))

    def detect_behavior_anomalies(self, result):
        """Detect simple behavioral anomalies like looking away."""
        anomalies = []
        # In a real system, we'd check gaze/pose. 
        # Here we use 'low confidence' or specific 'sad/disgust' as a proxy for 'away/inactive'.
        if result["confidence"] < 0.4:
            anomalies.append("Looking Away / Blurred")
        if result["emotion"] in ["disgust", "angry"] and result["confidence"] > 0.8:
            anomalies.append("Extreme Disengagement")
        return anomalies
    
    def compute_doctor_signals(self, emotion_results, session_id):
        """Generate doctor-specific signals from emotion data."""
        from config import DOCTOR_SUSTAINED_ALERT_SECONDS
        
        doctor_signals = []
        
        for result in emotion_results:
            participant_risk_seconds = compute_doctor_risk_duration_seconds(
                session_id, result["participant_id"]
            )
            
            state = doctor_state_label(result["emotion"], result["confidence"])
            priority_score = round(
                (result["confidence"] * 100) + (participant_risk_seconds * 0.8) + 
                (30 if result["risk"] == "high" else 12 if result["risk"] == "medium" else 0), 2
            )
            
            doctor_signals.append({
                "participant_id": result["participant_id"],
                "patient": result["name"],
                "state": state,
                "emotion": result["emotion"],
                "confidence": round(result["confidence"], 2),
                "risk": result["risk"],
                "high_risk_duration_s": participant_risk_seconds,
                "priority_score": priority_score,
                "updated_at": result["updated_at"],
            })
        
        # Sort by priority
        doctor_signals.sort(key=lambda row: row["priority_score"], reverse=True)
        
        return {
            "signals": doctor_signals,
            "top_patient": doctor_signals[0] if doctor_signals else None,
            "high_risk_alerts": [
                row for row in doctor_signals 
                if row["high_risk_duration_s"] >= DOCTOR_SUSTAINED_ALERT_SECONDS
            ]
        }
    
    def compute_hr_signals(self, emotion_results, session_id):
        """Generate HR-specific signals from emotion data."""
        from utils.analysis_utils import hr_state_label
        if not emotion_results:
            return None
        
        # Get latest emotion data
        latest = emotion_results[0]
        state_label = hr_state_label(latest["emotion"], latest["confidence"])
        
        # Analyze patterns (e.g., response delay, technical issues)
        # Mocking technical issue detection for demonstration:
        # If frame count is low or confidence is consistently dropping
        tech_issue = False
        if latest["confidence"] < 0.3:
            tech_issue = True
            state_label = "Technical Issue Detected"

        # Signal Strength Labeling
        strength = "Low confidence"
        if latest["confidence"] > 0.8:
            strength = "High confidence"
        elif latest["confidence"] > 0.5:
            strength = "Moderate confidence"
            
        # Decision Safety: Review Recommended state
        review_recommended = tech_issue or latest["confidence"] < 0.6 or latest["risk"] == "high"

        return {
            "candidate_state": state_label,
            "latest_emotion": latest["emotion"],
            "confidence": round(latest["confidence"], 2),
            "intent": latest["intent"] if "intent" in latest else state_label,
            "risk": latest["risk"] if "risk" in latest else ("medium" if tech_issue else "low"),
            "tech_issue": tech_issue,
            "signal_strength": strength,
            "review_recommended": review_recommended,
            "explainability": f"{strength} ({round(latest['confidence']*100)}%)"
        }
    
    def _get_priority_students(self, teacher_signals, watchlist, confusion_states):
        """Extract priority students from signals and watchlist."""
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
                    priority_students.append({
                        "name": student_name, 
                        "issue": "Sustained Confusion", 
                        "duration": duration
                    })
                else:
                    priority_students.append({
                        "name": student_name, 
                        "issue": "Low Confidence", 
                        "duration": duration
                    })
        
        return priority_students
    
    def _get_class_state(self, attention_needed):
        """Determine overall class state."""
        if attention_needed == 0:
            return "🟢 Fully Engaged"
        elif attention_needed <= 2:
            return "🟡 Slightly Distracted"
        else:
            return "🔴 High Attention Needed"


# Global risk engine instance
risk_engine = RiskEngine()
