import time
import cv2
import numpy as np
import threading
import requests
import pyttsx3
from tensorflow.keras.models import load_model

# ==========================
# Intent Setup
# ==========================

intent_labels = [
    "agreement",
    "help_needed",
    "discomfort",
    "clarification",
    "neutral_state"
]

emotion_to_intent = {
    "happy": "agreement",
    "neutral": "neutral_state",
    "sad": "help_needed",
    "fear": "help_needed",
    "angry": "discomfort",
    "disgust": "discomfort",
    "surprise": "clarification"
}

# ==========================
# Configuration
# ==========================

MODEL_PATH = "models/emotion_model.h5"
CONFIDENCE_THRESHOLD = 0.60
SPEECH_COOLDOWN = 4  # seconds

# ==========================
# Load Emotion Model
# ==========================

model = load_model(MODEL_PATH)

emotion_labels = [
    'angry', 'disgust', 'fear',
    'happy', 'neutral', 'sad', 'surprise'
]

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

# ==========================
# Text To Speech Setup
# ==========================

engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)

voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)  # female voice (optional)

def speak(text):
    engine.stop()
    engine.say(text)
    engine.runAndWait()

# ==========================
# LLM Response Generator
# ==========================

def generate_response(intent, emotion, confidence):

    prompt = f"""
You convert detected user intent into one spoken sentence.

Detected facial emotion: {emotion}
Emotion confidence: {confidence:.2f}
Detected intent: {intent}

Rules:
- Output exactly one short sentence (max 10 words).
- Write in first person.
- Match emotion tone.
- Do not greet.
- Ask a question only if clarification.
- Return only the sentence.
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3
                }
            },
            timeout=5
        )

        raw = response.json().get("response", "").strip()

        if not raw:
            return "I need help."

        return raw.splitlines()[0].strip().strip('"')

    except Exception:
        fallback = {
            "agreement": "I agree with that.",
            "help_needed": "I need help.",
            "discomfort": "I feel uncomfortable.",
            "clarification": "Can you explain that again?",
            "neutral_state": "I am okay."
        }
        return fallback.get(intent, "I am okay.")

# ==========================
# Webcam Setup
# ==========================

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

previous_intent = None
response_text = ""
intent_response_cache = {}
last_spoken_time = 0

# ==========================
# Real-Time Loop
# ==========================

while True:

    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) > 0:

        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])

        face = gray[y:y+h, x:x+w]
        face = cv2.resize(face, (48, 48))
        face = face / 255.0
        face = np.reshape(face, (1, 48, 48, 1))

        preds = model.predict(face, verbose=0)[0]
        max_index = np.argmax(preds)
        confidence = preds[max_index]

        if confidence > CONFIDENCE_THRESHOLD:

            emotion = emotion_labels[max_index]
            intent = emotion_to_intent.get(emotion, "neutral_state")

            current_time = time.time()

            # If intent changed → generate once
            if intent != previous_intent:

                if intent in intent_response_cache:
                    response_text = intent_response_cache[intent]
                else:
                    response_text = generate_response(intent, emotion, confidence)
                    intent_response_cache[intent] = response_text

                previous_intent = intent
                last_spoken_time = current_time - SPEECH_COOLDOWN

            # Speak every cooldown seconds
            if response_text and (current_time - last_spoken_time >= SPEECH_COOLDOWN):
                last_spoken_time = current_time
                threading.Thread(
                    target=speak,
                    args=(response_text,),
                    daemon=True
                ).start()

            # Draw UI
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)

            cv2.putText(frame,
                        f"{emotion} ({confidence:.2f})",
                        (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0,255,0),
                        2)

            cv2.putText(frame,
                        f"Intent: {intent}",
                        (x, y-40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255,0,0),
                        2)

    else:
        cv2.putText(frame,
                    "No face detected",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0,0,255),
                    2)

    # Display sentence
    if response_text:
        cv2.putText(frame,
                    response_text[:60],
                    (10, 450),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0,255,255),
                    2)

    cv2.imshow("Assistive Emotion-Based Communication System", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
