from database.db import get_connection, get_db
from datetime import datetime
import json


def log_emotion(
    session_id,
    emotion,
    confidence,
    intent,
    risk_level,
    participant_id=None,
    face_index=None,
    mode="single",
    distribution=None,
    face_count=None,
    stability_index=None,
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO emotion_logs 
        (session_id, participant_id, face_index, timestamp, emotion, confidence, intent, risk_level, mode, distribution, face_count, stability_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        participant_id,
        face_index,
        datetime.now(),
        emotion,
        confidence,
        intent,
        risk_level,
        mode,
        json.dumps(distribution) if distribution else None,
        face_count,
        stability_index,
    ))



def get_latest_emotion(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT emotion, confidence, intent, risk_level, timestamp, mode, distribution, face_count, stability_index
            FROM emotion_logs
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (session_id,))

        row = cursor.fetchone()
    return row


def get_emotion_history(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, emotion
            FROM emotion_logs
            WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,))

        rows = cursor.fetchall()
    return rows


def get_session_emotion_history(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.timestamp, e.emotion, e.confidence, e.participant_id, u.name, e.risk_level
            FROM emotion_logs e
            JOIN users u ON e.participant_id = u.id
            WHERE e.session_id = ?
            ORDER BY e.timestamp DESC
        """, (session_id,))

        rows = cursor.fetchall()
    return [
        {
            "timestamp": r["timestamp"],
            "updated_at": r["timestamp"],
            "emotion": r["emotion"],
            "confidence": r["confidence"],
            "participant_id": r["participant_id"],
            "name": r["name"],
            "risk": r["risk_level"]
        }
        for r in rows
    ]


def get_participant_emotion_history(session_id, participant_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, emotion, confidence
            FROM emotion_logs
            WHERE session_id = ?
              AND participant_id = ?
            ORDER BY timestamp ASC
        """, (session_id, participant_id))

        rows = cursor.fetchall()
    return rows


def log_suggestion(session_id, emotion, intent, risk_level, suggestion, trigger_details=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO suggestion_logs
            (session_id, timestamp, emotion, intent, risk_level, suggestion, trigger_details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.now(),
            emotion,
            intent,
            risk_level,
            suggestion,
            json.dumps(trigger_details) if trigger_details else None,
        ))

        conn.commit()
        suggestion_id = cursor.lastrowid
    return suggestion_id


def get_suggestion_history(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, emotion, intent, risk_level, suggestion, trigger_details
            FROM suggestion_logs
            WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,))

        rows = cursor.fetchall()
    return rows


def get_export_rows(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.timestamp, e.emotion, e.confidence, e.intent, e.risk_level, e.mode, e.distribution, e.face_count, e.stability_index, s.suggestion
            FROM emotion_logs e
            LEFT JOIN suggestion_logs s
              ON s.session_id = e.session_id
             AND s.timestamp = (
                SELECT MAX(s2.timestamp)
                FROM suggestion_logs s2
                WHERE s2.session_id = e.session_id
                  AND s2.timestamp <= e.timestamp
             )
            WHERE e.session_id = ?
            ORDER BY e.timestamp ASC
        """, (session_id,))

        rows = cursor.fetchall()
    return rows


def log_suggestion_feedback(session_id, suggestion_log_id, feedback):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO suggestion_feedback (session_id, suggestion_log_id, feedback, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(suggestion_log_id)
        DO UPDATE SET
            feedback = excluded.feedback,
            created_at = excluded.created_at
    """, (session_id, suggestion_log_id, feedback, datetime.now()))


def get_feedback_for_suggestion(suggestion_log_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT feedback
            FROM suggestion_feedback
            WHERE suggestion_log_id = ?
            LIMIT 1
        """, (suggestion_log_id,))
        row = cursor.fetchone()

    if not row:
        return None
    return row["feedback"]


def upsert_doctor_handover(session_id, delegate_name, handover_note):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute(
            """
            INSERT INTO doctor_handover (session_id, delegate_name, handover_note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id)
            DO UPDATE SET
                delegate_name = excluded.delegate_name,
                handover_note = excluded.handover_note,
                updated_at = excluded.updated_at
            """,
            (session_id, delegate_name, handover_note, now, now),
        )


def get_doctor_handover(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT delegate_name, handover_note, created_at, updated_at
            FROM doctor_handover
            WHERE session_id = ?
            LIMIT 1
            """,
            (session_id,),
        )
        row = cursor.fetchone()
    return row


def log_doctor_alert_action(
    session_id,
    participant_id,
    participant_name,
    action,
    actor="doctor",
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO doctor_alert_actions
            (session_id, participant_id, participant_name, action, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, participant_id, participant_name, action, actor, datetime.now()),
        )


def get_doctor_alert_actions(session_id, limit=100):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT participant_name, action, actor, created_at
            FROM doctor_alert_actions
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = cursor.fetchall()
    return rows
