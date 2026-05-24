import cv2
from collections import deque

from config import LOW_CONFIDENCE_THRESHOLD
from core.realtime_emotion import predict_emotion, predict_emotions
from core.smoothing import EmotionSmoother
from core.context_logic import compute_risk
from core.mapping import map_emotion_to_intent
from logs.session_logger import log_emotion
from streaming.frame_store import upsert_participant_frame


class EmotionProcessor:
    """Handles all emotion processing logic separate from UI."""
    
    def __init__(self):
        self.smoothers = {}
    
    def process_single_frame(self, frame, session_id, context, user_id=None):
        """Process single frame for professional user."""
        emotions, confidences = predict_emotions(frame)
        
        if not emotions or not confidences:
            return None
        
        dominant_emotion = emotions[0]
        confidence = confidences[0]
        
        if confidence >= LOW_CONFIDENCE_THRESHOLD:
            smoother_key = f"single_{user_id or 'default'}"
            if smoother_key not in self.smoothers:
                self.smoothers[smoother_key] = EmotionSmoother(buffer_size=10)
            smoother = self.smoothers[smoother_key]
            smoother.update(dominant_emotion)
            display_emotion = smoother.get_stable_emotion() or dominant_emotion
        else:
            display_emotion = dominant_emotion
        
        intent = map_emotion_to_intent(display_emotion, context)
        risk = compute_risk(display_emotion, confidence, context)
        
        log_emotion(
            session_id, display_emotion, confidence, intent, risk,
            mode="single", face_count=len(emotions)
        )
        
        return {
            "emotion": display_emotion,
            "confidence": confidence,
            "intent": intent,
            "risk": risk,
            "face_count": len(emotions),
            "frame": frame
        }
    
    def process_remote_streams(self, session_id, context, remote_streams):
        """Process multiple remote participant streams."""
        results = []
        emotion_weights = {}
        no_face_participants = []
        
        for stream in remote_streams:
            frame = stream["frame"]
            emotion, confidence = predict_emotion(frame)
            display_emotion = None
            
            if emotion is None:
                no_face_participants.append(stream["name"])
            elif confidence < LOW_CONFIDENCE_THRESHOLD:
                # Low confidence - still process but mark
                display_emotion = emotion
            else:
                display_emotion = emotion
                emotion_weights[display_emotion] = emotion_weights.get(display_emotion, 0) + confidence
            
            intent = map_emotion_to_intent(display_emotion, context)
            risk = compute_risk(display_emotion, confidence, context)
            
            log_emotion(
                session_id, display_emotion, confidence, intent, risk,
                participant_id=stream["participant_id"], mode="remote_single", face_count=1
            )
            
            # Add emotion text to frame
            cv2.putText(
                frame, f"{display_emotion} ({confidence:.2f})", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )
            
            results.append({
                "participant_id": stream["participant_id"],
                "name": stream["name"],
                "emotion": display_emotion,
                "confidence": confidence,
                "intent": intent,
                "risk": risk,
                "frame": frame,
                "updated_at": stream["updated_at"]
            })
        
        return {
            "results": results,
            "emotion_weights": emotion_weights,
            "no_face_participants": no_face_participants
        }
    
    def process_participant_webcam(self, session_id, user_id):
        """Process participant webcam frame."""
        camera = cv2.VideoCapture(0)
        ret, frame = camera.read()
        camera.release()
        
        if ret:
            upsert_participant_frame(session_id, user_id, frame)
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            return None


# Global processor instance
emotion_processor = EmotionProcessor()
