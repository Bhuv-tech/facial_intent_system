from datetime import datetime

import cv2
import numpy as np

from database.db import get_connection, get_db


def upsert_participant_frame(session_id, participant_id, frame):
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        return

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
        """
        INSERT INTO participant_streams (session_id, participant_id, frame, updated_at, is_active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(session_id, participant_id)
        DO UPDATE SET
            frame = excluded.frame,
            updated_at = excluded.updated_at,
            is_active = 1
        """,
        (session_id, participant_id, encoded.tobytes(), datetime.now().isoformat()),
    )


def set_participant_stream_active(session_id, participant_id, is_active):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
        """
        UPDATE participant_streams
        SET is_active = ?, updated_at = ?
        WHERE session_id = ? AND participant_id = ?
        """,
        (1 if is_active else 0, datetime.now().isoformat(), session_id, participant_id),
    )


def get_active_participant_streams(session_id, max_age_seconds=3):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ps.participant_id, u.name, ps.frame, ps.updated_at
            FROM participant_streams ps
            JOIN users u ON u.id = ps.participant_id
            WHERE ps.session_id = ? AND ps.is_active = 1
            ORDER BY u.name ASC
            """,
            (session_id,),
        )
        rows = cursor.fetchall()

    now = datetime.now()
    streams = []
    for row in rows:
        frame_blob = row["frame"]
        if not frame_blob:
            continue
        try:
            updated_at = datetime.fromisoformat(row["updated_at"])
        except (TypeError, ValueError):
            continue
        age_seconds = (now - updated_at).total_seconds()
        if age_seconds > max_age_seconds:
            continue
        nparr = np.frombuffer(frame_blob, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            continue
        streams.append(
            {
                "participant_id": row["participant_id"],
                "name": row["name"],
                "frame": frame,
                "updated_at": row["updated_at"],
            }
        )
    return streams
