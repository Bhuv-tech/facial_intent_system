from collections import deque, Counter
from backend.config import LOW_CONFIDENCE_THRESHOLD, SMOOTHING_WINDOW_SIZE

class SignalProcessor:
    """Handles temporal smoothing and signal validation."""
    
    def __init__(self):
        # session_id -> user_id -> deque of recent emotions
        self.buffers = {}

    def process_signal(self, session_id, user_id, emotion, confidence):
        """
        Apply confidence floor and temporal smoothing.
        Returns (smoothed_emotion, is_reliable)
        """
        # 1. Confidence Floor
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            return "uncertain", False

        # Ensure buffer exists
        if session_id not in self.buffers:
            self.buffers[session_id] = {}
        if user_id not in self.buffers[session_id]:
            self.buffers[session_id][user_id] = deque(maxlen=SMOOTHING_WINDOW_SIZE)

        # 2. Update buffer
        self.buffers[session_id][user_id].append(emotion)
        
        # 3. Temporal Smoothing (Majority Vote)
        recent = self.buffers[session_id][user_id]
        if len(recent) < 3: # Not enough data yet
            return emotion, True
            
        counts = Counter(recent)
        smoothed_emotion, count = counts.most_common(1)[0]
        
        # Only switch if there is a clear trend (e.g. at least 3/5 frames or 2/3)
        if count >= (SMOOTHING_WINDOW_SIZE // 2 + 1):
             return smoothed_emotion, True
        
        return recent[-1], True # Fallback to latest but keep reliable flag

    def clear_session(self, session_id):
        self.buffers.pop(session_id, None)

signal_processor = SignalProcessor()
