from database.db import get_connection, get_db
from datetime import datetime
import uuid
import sqlite3

def create_user(name, email, role, user_type, password=""):
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT id, user_type FROM users WHERE email = ?", (email,))
        existing = cursor.fetchone()
        if existing:
            # If user exists but as a different type, we could update it or just return ID
            # For now, let's just return the existing ID to allow multi-role use
            return existing['id']

        cursor.execute("""
            INSERT INTO users (name, email, role, user_type, password, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, role, user_type, password, datetime.now()))
        conn.commit()
        user_id = cursor.lastrowid

    return user_id

def verify_user(email, password, preferred_type=None):
    """Verifies email and password. Returns user data if valid.
    If multiple accounts exist, prioritizes preferred_type.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, role, user_type FROM users 
            WHERE email = ? AND password = ?
        """, (email, password))
        
        users = [dict(u) for u in cursor.fetchall()]
        if not users:
            return None
            
        if preferred_type:
            for u in users:
                if u['user_type'] == preferred_type:
                    return u
                    
        return users[0]

def generate_custom_session_id(context):
    """Generates a 6-character session ID like T00001"""
    prefix = context[0].upper() if context else 'S'
    with get_db() as conn:
        cursor = conn.cursor()
        # Count sessions with this prefix
        cursor.execute("SELECT COUNT(*) as count FROM sessions WHERE session_id LIKE ?", (f"{prefix}%",))
        count = cursor.fetchone()['count']
        
    session_id = f"{prefix}{str(count + 1).zfill(5)}"
    return session_id

def create_session(professional_id, context, session_id=None):
    with get_db() as conn:
        cursor = conn.cursor()

        if session_id:
            # Resuming session? Check if it exists
            cursor.execute("SELECT session_id, professional_id FROM sessions WHERE session_id = ?", (session_id,))
            existing = cursor.fetchone()
            if existing:
                if str(existing['professional_id']) == str(professional_id):
                    return session_id
                else:
                    raise ValueError("This session ID belongs to another professional.")
        else:
            session_id = generate_custom_session_id(context)

        try:
            cursor.execute("""
                INSERT INTO sessions 
                (session_id, professional_id, context, start_time, status)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, professional_id, context, datetime.now(), "active"))
            conn.commit()
        except sqlite3.IntegrityError as exc:
            # Handle collision if count was inaccurate
            if not session_id.startswith(context[0].upper()):
                 raise ValueError("Session code already exists.") from exc
            # Try once more with a random suffix if needed, but per requirement we use the count
            session_id = f"{session_id}_2" 
            cursor.execute("""
                INSERT INTO sessions 
                (session_id, professional_id, context, start_time, status)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, professional_id, context, datetime.now(), "active"))
            conn.commit()

    return session_id

def attach_participant_to_session(session_id, participant_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions
            SET participant_id = ?
            WHERE session_id = ? AND status = 'active'
        """, (participant_id, session_id))

        cursor.execute("""
            SELECT 1
            FROM session_participants
            WHERE session_id = ? AND participant_id = ?
            LIMIT 1
        """, (session_id, participant_id))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("""
                INSERT INTO session_participants (session_id, participant_id, joined_at)
                VALUES (?, ?, ?)
            """, (session_id, participant_id, datetime.now()))
        conn.commit()

def get_session_participants(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.name, u.role, sp.joined_at
            FROM session_participants sp
            JOIN users u ON u.id = sp.participant_id
            WHERE sp.session_id = ?
            ORDER BY sp.joined_at ASC
        """, (session_id,))

        rows = [dict(row) for row in cursor.fetchall()]

    return rows

def get_session(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, professional_id, participant_id, context, start_time, end_time, status
            FROM sessions
            WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
    return None

def end_session(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions
            SET status = 'completed',
                end_time = ?
            WHERE session_id = ? AND status = 'active'
        """, (datetime.now(), session_id))
        conn.commit()


