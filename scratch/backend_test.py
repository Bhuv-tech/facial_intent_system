import sys
import os
import json
import base64
import numpy as np
import cv2
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from core.realtime_emotion import predict_emotion
from llm.local_llm import generate_suggestion
from database.db import get_db

def test_db_health():
    print("[1/4] DB Health Check...")
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM users LIMIT 1")
            row = cursor.fetchone()
            print(f"  [PASS] DB reachable. Sample user: {row['name'] if row else 'None'}")
            return True
    except Exception as e:
        print(f"  [FAIL] DB unreachable: {e}")
        return False

def test_ai_inference():
    print("[2/4] AI Inference Check...")
    try:
        # Create a blank image
        test_img = np.zeros((300, 300, 3), dtype=np.uint8)
        cv2.putText(test_img, "Test Face", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        emotion, confidence = predict_emotion(test_img)
        print(f"  [PASS] AI pipeline active. Result: {emotion or 'No Face'} ({confidence:.2f})")
        return True
    except Exception as e:
        print(f"  [FAIL] AI Inference error: {e}")
        return False

def test_llm_logic():
    print("[3/4] LLM Suggestion Check...")
    try:
        suggestion = generate_suggestion("teacher", "happy", "engaged", "low")
        print(f"  [PASS] LLM reachable. Suggestion: {suggestion[:50]}...")
        return True
    except Exception as e:
        print(f"  [FAIL] LLM logic error: {e}")
        return False

def test_api_config():
    print("[4/4] Config Integrity...")
    from config import DATA_DIR, DB_PATH, MODEL_PATH
    folders = [DATA_DIR, DATA_DIR / "models"]
    for f in folders:
        if not f.exists():
             print(f"  [WARN] Path missing: {f}")
    
    files = [DB_PATH, MODEL_PATH]
    for f in files:
        if not f.exists():
             print(f"  [FAIL] File missing: {f}")
             return False
    print("  [PASS] All critical paths verified.")
    return True

if __name__ == "__main__":
    print("=== BACKEND HEALTH CHECK ===\n")
    results = [
        test_db_health(),
        test_ai_inference(),
        test_llm_logic(),
        test_api_config()
    ]
    
    print("\n" + "="*28)
    if all(results):
        print("FINAL STATUS: BACKEND HEALTHY")
    else:
        print("FINAL STATUS: ISSUES DETECTED")
    print("="*28)
