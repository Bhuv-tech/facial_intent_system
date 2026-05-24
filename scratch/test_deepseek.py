import sys
import os
from pathlib import Path

# Add backend to path
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent / "backend"
sys.path.append(str(backend_dir))

import logging
logging.basicConfig(level=logging.INFO)

from llm.local_llm import generate_suggestion

def test_deepseek():
    print("Testing DeepSeek Integration...")
    context = "teacher"
    emotion = "confused"
    intent = "Seeking clarification"
    risk = "low"
    
    suggestion = generate_suggestion(context, emotion, intent, risk)
    print(f"\nContext: {context}")
    print(f"Emotion: {emotion}")
    print(f"Suggestion: {suggestion}")

if __name__ == "__main__":
    test_deepseek()
