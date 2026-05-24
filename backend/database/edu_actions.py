import sqlite3
import time
from database.db import get_db

def log_class_phase(session_id, phase):
    """Log a class phase change (Lecture, Revision, Test)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO class_phase_logs (session_id, phase, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (session_id, phase)
        )
        conn.commit()

def get_latest_class_phase(session_id):
    """Retrieve the current class phase for a session."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT phase FROM class_phase_logs WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else "Lecture"

def send_nudge(session_id, participant_id, nudge_type="re-explanation"):
    """Record a student nudge (e.g., request for re-explanation)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO student_nudges (session_id, participant_id, nudge_type, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (session_id, participant_id, nudge_type)
        )
        conn.commit()

def get_active_nudges(session_id, minutes_ago=5):
    """Get nudges sent within the last X minutes."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT n.participant_id, u.name, n.nudge_type, n.created_at 
            FROM student_nudges n
            JOIN users u ON n.participant_id = u.id
            WHERE n.session_id = ? AND n.created_at >= datetime('now', ?)
            ORDER BY n.id DESC
            """,
            (session_id, f"-{minutes_ago} minutes")
        )
        return [
            {"participant_id": r[0], "name": r[1], "nudge_type": r[2], "created_at": r[3]}
            for r in cursor.fetchall()
        ]

def set_break_status(session_id, status):
    """Set the break status for a session (active/completed)."""
    with get_db() as conn:
        cursor = conn.cursor()
        if status == "active":
            cursor.execute(
                "INSERT INTO session_breaks (session_id, status, started_at) VALUES (?, 'active', CURRENT_TIMESTAMP)",
                (session_id,)
            )
        else:
            cursor.execute(
                "UPDATE session_breaks SET status = 'completed', ended_at = CURRENT_TIMESTAMP WHERE session_id = ? AND status = 'active'",
                (session_id,)
            )
        conn.commit()

def get_break_status(session_id):
    """Check if a session is currently in break mode."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, started_at FROM session_breaks WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,)
        )
        row = cursor.fetchone()
        if row and row[0] == "active":
            return {"active": True, "started_at": row[1]}
        return {"active": False, "started_at": None}

def update_student_focus(session_id, participant_id, focus_score):
    """Update or insert student focus stats and streaks."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Get existing streak
        cursor.execute(
            "SELECT streak_count FROM student_focus_stats WHERE session_id = ? AND participant_id = ?",
            (session_id, participant_id)
        )
        row = cursor.fetchone()
        
        if row:
            # Update streak based on focus score
            new_streak = row[0] + 1 if focus_score > 0.7 else (row[0] // 2 if focus_score < 0.3 else row[0])
            cursor.execute(
                "UPDATE student_focus_stats SET focus_score = ?, streak_count = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ? AND participant_id = ?",
                (focus_score, new_streak, session_id, participant_id)
            )
        else:
            cursor.execute(
                "INSERT INTO student_focus_stats (session_id, participant_id, focus_score, streak_count, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (session_id, participant_id, focus_score, 1 if focus_score > 0.7 else 0)
            )
        conn.commit()

def get_student_focus_stats(session_id, participant_id):
    """Get current focus stats for a student."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT focus_score, streak_count FROM student_focus_stats WHERE session_id = ? AND participant_id = ?",
            (session_id, participant_id)
        )
        row = cursor.fetchone()
        return {"focus_score": row[0], "streak_count": row[1]} if row else {"focus_score": 0.0, "streak_count": 0}
