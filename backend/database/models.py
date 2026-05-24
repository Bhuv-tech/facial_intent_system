from database.db import get_connection, get_db


def _ensure_column(cursor, table_name, column_name, column_type):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    if column_name not in existing:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


def create_tables():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                role TEXT,
                user_type TEXT,
                created_at TIMESTAMP
            )
        """)
        _ensure_column(cursor, "users", "password", "TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                professional_id INTEGER,
                participant_id INTEGER,
                context TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emotion_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                participant_id INTEGER,
                face_index INTEGER,
                timestamp TIMESTAMP,
                emotion TEXT,
                confidence REAL,
                intent TEXT,
                risk_level TEXT,
                mode TEXT,
                distribution TEXT,
                face_count INTEGER,
                stability_index TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                participant_id INTEGER,
                joined_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TIMESTAMP,
                emotion TEXT,
                intent TEXT,
                risk_level TEXT,
                suggestion TEXT,
                trigger_details TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                suggestion_log_id INTEGER UNIQUE,
                feedback TEXT,
                created_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS participant_streams (
                session_id TEXT,
                participant_id INTEGER,
                frame BLOB,
                updated_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                PRIMARY KEY (session_id, participant_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctor_handover (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                delegate_name TEXT,
                handover_note TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctor_alert_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                participant_id INTEGER,
                participant_name TEXT,
                action TEXT,
                actor TEXT,
                created_at TIMESTAMP
            )
        """)

        # New Teacher/Student Interaction Tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_phase_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                phase TEXT,
                created_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_nudges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                participant_id INTEGER,
                nudge_type TEXT,
                created_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_breaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                status TEXT,
                started_at TIMESTAMP,
                ended_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_focus_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                participant_id INTEGER,
                focus_score REAL,
                streak_count INTEGER,
                updated_at TIMESTAMP,
                UNIQUE(session_id, participant_id)
            )
        """)

        # Lightweight migrations for older databases.
        _ensure_column(cursor, "users", "email", "TEXT")
        _ensure_column(cursor, "sessions", "participant_id", "INTEGER")
        _ensure_column(cursor, "emotion_logs", "participant_id", "INTEGER")
        _ensure_column(cursor, "emotion_logs", "face_index", "INTEGER")
        _ensure_column(cursor, "emotion_logs", "mode", "TEXT")
        _ensure_column(cursor, "emotion_logs", "distribution", "TEXT")
        _ensure_column(cursor, "emotion_logs", "face_count", "INTEGER")
        _ensure_column(cursor, "emotion_logs", "stability_index", "TEXT")
        _ensure_column(cursor, "participant_streams", "is_active", "INTEGER DEFAULT 1")
        _ensure_column(cursor, "suggestion_logs", "trigger_details", "TEXT")

        cursor.execute("""
            DELETE FROM session_participants
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM session_participants
                GROUP BY session_id, participant_id
            )
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_session_participants_unique
            ON session_participants (session_id, participant_id)
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_suggestion_feedback_unique
            ON suggestion_feedback (suggestion_log_id)
        """)


