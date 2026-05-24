import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress info and warning logs
import tensorflow as tf
tf.get_logger().setLevel('ERROR')  # Only show error logs
import cv2
import numpy as np
import logging
from tensorflow.keras.models import load_model
from config import MODEL_PATH

LOGGER = logging.getLogger(__name__)

model = None
MODEL_AVAILABLE = False
if not MODEL_PATH.exists():
    LOGGER.warning(
        "Emotion model file not found at %s. Emotion inference disabled until model is added.",
        MODEL_PATH,
    )
else:
    try:
        model = load_model(str(MODEL_PATH))
        MODEL_AVAILABLE = True
    except Exception as exc:
        LOGGER.warning("Failed to load emotion model: %s. Inference disabled.", exc)

emotion_labels = [
    "angry",
    "disgust",
    "fear",
    "happy",
    "sad",
    "surprise",
    "neutral"
]

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

def predict_emotion(frame):
    results = predict_emotions(frame)
    if results:
        top = results[0]
        return top["emotion"], top["confidence"]
    return None, 0.0


def predict_emotions(frame):
    if not MODEL_AVAILABLE:
        return []

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    if len(faces) == 0:
        LOGGER.debug("No faces detected in current frame.")
    else:
        LOGGER.debug(f"Detected {len(faces)} faces.")

    results = []

    for (x, y, w, h) in faces:
        face = gray[y:y+h, x:x+w]
        face = cv2.resize(face, (48, 48))
        face = face / 255.0
        face = np.reshape(face, (1, 48, 48, 1))

        preds = model.predict(face, verbose=0)[0]
        confidence = np.max(preds)
        emotion = emotion_labels[np.argmax(preds)]

        results.append({
            "emotion": emotion,
            "confidence": float(confidence),
            "bbox": (int(x), int(y), int(w), int(h)),
        })

    return results
