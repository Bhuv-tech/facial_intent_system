import os
import sqlite3
import requests
from config import DB_PATH, DEEPSEEK_API_KEY, DEEPSEEK_URL, LLM_PROVIDER

def check_db():
    print(f"Checking Database: {DB_PATH}...")
    if not os.path.exists(DB_PATH):
        print("[ERROR] Database file not found!")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        required = ['users', 'sessions', 'emotion_logs', 'student_nudges', 'student_focus_stats']
        missing = [r for r in required if r not in tables]
        
        if missing:
            print(f"[ERROR] Missing tables: {', '.join(missing)}")
            return False
        print("[OK] Database tables verified.")
        return True
    except Exception as e:
        print(f"[ERROR] Database error: {e}")
        return False

def check_llm():
    print(f"Checking LLM Provider: {LLM_PROVIDER}...")
    if LLM_PROVIDER == 'deepseek':
        if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_key_here":
            print("[ERROR] DeepSeek API key missing in .env")
            return False
        
        try:
            # Simple health check if the provider supports it, or just notify key presence
            print(f"[OK] DeepSeek key detected and URL set to {DEEPSEEK_URL}")
            return True
        except Exception as e:
            print(f"[ERROR] LLM error: {e}")
            return False
    else:
        print(f"[OK] Using local provider: {LLM_PROVIDER}")
        return True

if __name__ == "__main__":
    print("=== Facial Intent System: Health Check ===\n")
    db_ok = check_db()
    llm_ok = check_llm()
    
    if db_ok and llm_ok:
        print("\n[SUCCESS] SYSTEM STATUS: PERFECT")
    else:
        print("\n[WARNING] SYSTEM STATUS: ISSUES DETECTED")
