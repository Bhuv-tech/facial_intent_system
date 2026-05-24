from collections import deque
from statistics import multimode

class EmotionSmoother:
    def __init__(self, buffer_size=10):
        self.buffer = deque(maxlen=buffer_size)

    def update(self, emotion):
        self.buffer.append(emotion)

    def get_stable_emotion(self):
        if len(self.buffer) == 0:
            return None
        modes = multimode(self.buffer)
        if not modes:
            return None
        if len(modes) == 1:
            return modes[0]
        for emotion in reversed(self.buffer):
            if emotion in modes:
                return emotion
        return modes[0]
