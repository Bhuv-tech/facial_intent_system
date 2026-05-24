import sys
import os
from pathlib import Path

# Add backend to path so we can import database modules
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from database.db import get_db

def clear_logs():
    tables_to_clear = [
        "emotion_logs",
        "suggestion_logs",
        "suggestion_feedback",
        "sessions",
        "session_participants",
        "participant_streams",
        "doctor_handover",
        "doctor_alert_actions",
        "class_phase_logs",
        "student_nudges",
        "student_focus_stats",
        "session_breaks"
    ]
    
    with get_db() as conn:
        cursor = conn.cursor()
        for table in tables_to_clear:
            try:
                cursor.execute(f"DELETE FROM {table}")
                print(f"Cleared table: {table}")
            except Exception as e:
                print(f"Could not clear table {table}: {e}")
        conn.commit()
    print("\nDatabase logs cleared successfully (Users table preserved).")

if __name__ == "__main__":
    clear_logs()
