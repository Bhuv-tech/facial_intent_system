import sys
import os
import cv2
import json
import base64
import numpy as np
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any

# Ensure internal modules can be imported after reorganization
sys.path.append(str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth.login import create_user, create_session, attach_participant_to_session, get_session, get_session_participants, verify_user
from core.realtime_emotion import predict_emotion
from core.mapping import map_emotion_to_intent
from core.context_logic import compute_risk
from core.risk_engine import risk_engine
from core.signal_processor import signal_processor
from config import ENABLE_PRIVACY_MODE
from database.edu_actions import send_nudge, get_active_nudges, update_student_focus
from streaming.frame_store import upsert_participant_frame
from database.db import get_db
from database.models import create_tables

app = FastAPI(title="Facial Intent API")

@app.on_event("startup")
async def startup_event():
    create_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.error(f"Global error: {exc}", exc_info=True)
    return HTTPException(status_code=500, detail="Internal Server Error: Check backend logs")

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        # session_id -> { user_id -> websocket }
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str, user_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = {}
        
        # If no user_id, use a fallback
        uid = str(user_id) if user_id else str(id(websocket))
        self.active_connections[session_id][uid] = websocket
        logging.info(f"WS Connect: session={session_id} user_id={uid}")
        return uid

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            # Find and remove the websocket
            uid_to_remove = None
            for uid, ws in self.active_connections[session_id].items():
                if ws == websocket:
                    uid_to_remove = uid
                    break
            if uid_to_remove:
                del self.active_connections[session_id][uid_to_remove]
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_personal_message(self, message: dict, session_id: str, user_id: str):
        if session_id in self.active_connections:
            ws = self.active_connections[session_id].get(str(user_id))
            if ws:
                await ws.send_json(message)

    async def broadcast(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            count = len(self.active_connections[session_id])
            logging.info(f"WS Broadcast to {count} users in {session_id}: type={message.get('type')}")
            for ws in self.active_connections[session_id].values():
                await ws.send_json(message)
        else:
            logging.warning(f"WS Broadcast failed: No active connections for {session_id}")

manager = ConnectionManager()

# --- Models ---
class LoginRequest(BaseModel):
    name: str
    email: str
    password: str = ""
    is_signup: bool = False
    role: str
    user_type: str
    context: str = "teacher"
    session_id: Optional[str] = None

class FrameRequest(BaseModel):
    user_id: int
    session_id: str
    context: str
    image_b64: str

class NudgeRequest(BaseModel):
    session_id: str
    user_id: int
    nudge_type: str

class ChatMessage(BaseModel):
    session_id: str
    user_name: str
    message: str

class BreakRequest(BaseModel):
    status: str # 'active' or 'ended'

class QuizRequest(BaseModel):
    title: str
    action: str # 'start' or 'stop'

class ModeratorActionRequest(BaseModel):
    action: str # 'mute', 'unmute', 'kick', 'report'

# --- Endpoints ---

@app.get("/health")
async def health():
    """Service health check."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "db_connected": True # Simplified
    }

@app.post("/login")
async def login(req: LoginRequest):
    if req.is_signup:
        user_id = create_user(req.name, req.email, req.role, req.user_type, req.password)
        user_name = req.name
    else:
        # verifying user returns user data if email/password matches
        # we pass the requested user_type to prioritize it in case of duplicates
        user_data = verify_user(req.email, req.password, req.user_type)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        user_id = user_data['id']
        # Use the name from DB to keep it consistent
        user_name = user_data['name']
            
    if req.user_type == "professional":
        try:
            # req.session_id might be provided if they want to resume
            session_id = create_session(user_id, req.context, req.session_id)
            from database.edu_actions import get_break_status
            break_info = get_break_status(session_id)
            return {
                "session_id": session_id, 
                "user_id": user_id, 
                "name": user_name, 
                "context": req.context, 
                "user_type": "professional",
                "role": req.role,
                "is_break": break_info["active"]
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        if not req.session_id:
            raise HTTPException(status_code=400, detail="Missing session_id for participant")
            
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        attach_participant_to_session(req.session_id, user_id)
        from database.edu_actions import get_break_status
        break_info = get_break_status(req.session_id)
        
        # Broadcast that a student joined to the teacher
        import asyncio
        asyncio.create_task(manager.broadcast(req.session_id, {
            "type": "student_joined",
            "data": {"user_id": user_id, "user_name": user_name, "role": req.role}
        }))
        
        return {
            "session_id": req.session_id, 
            "user_id": user_id, 
            "name": user_name, 
            "context": session["context"], 
            "user_type": "student",
            "role": req.role,
            "is_break": break_info["active"]
        }

@app.get("/session/{session_id}/participants")
async def get_participants(session_id: str):
    # Fetch real participants from DB
    participants = get_session_participants(session_id)
    return [
        {"id": p["id"], "name": p["name"], "role": p["role"], "connected": True}
        for p in participants
    ]

@app.post("/session/{session_id}/participants/{user_id}/action")
async def moderate_participant(session_id: str, user_id: int, req: ModeratorActionRequest):
    if req.action == 'report':
        get_db().execute("INSERT INTO session_logs (session_id, event_type, details) VALUES (?, ?, ?)",
                     (session_id, "user_reported", f"User {user_id} reported by host"))
        return {"success": True}
        
    # Broadcast the action targeting the specific user
    await manager.broadcast(session_id, {
        "type": "moderator_action",
        "target_user_id": user_id,
        "action": req.action
    })
    return {"success": True}

@app.post("/session/{session_id}/break")
async def toggle_break(session_id: str, req: BreakRequest):
    from database.edu_actions import set_break_status
    # Log to database
    set_break_status(session_id, req.status)
    # Broadcast to all connected clients
    await manager.broadcast(session_id, {"type": "break_toggle", "status": req.status})
    return {"success": True, "status": req.status}

@app.post("/session/{session_id}/quiz")
async def toggle_quiz(session_id: str, req: QuizRequest):
    get_db().execute("INSERT INTO session_logs (session_id, event_type, details) VALUES (?, ?, ?)",
                     (session_id, f"quiz_{req.action}", req.title))
    await manager.broadcast(session_id, {"type": "quiz_event", "action": req.action, "title": req.title})
    return {"success": True}

@app.get("/session/{session_id}/suggestions")
async def get_ai_suggestions(session_id: str, context: str = "teacher"):
    from llm.local_llm import generate_suggestion
    from logs.session_logger import get_session_emotion_history
    
    history = get_session_emotion_history(session_id)
    if not history:
        return {"suggestion": "Awaiting interaction data...", "metrics": None, "priority_students": []}
    
    participants = get_session_participants(session_id)
    
    if context == "doctor":
        signals = risk_engine.compute_doctor_signals(history, session_id)
        target = signals.get("top_patient")
        if not target:
            return {"suggestion": "No active patient data detected.", "metrics": None}
        suggestion = generate_suggestion("doctor", target["emotion"], target["state"], target["risk"])
        return {
            "suggestion": f"{suggestion} ({round(target['confidence'] * 100)}% confidence)",
            "metrics": signals,
            "priority_students": signals.get("high_risk_alerts", [])
        }
    elif context == "hr":
        signals = risk_engine.compute_hr_signals(history, session_id)
        if not signals:
            return {"suggestion": "Awaiting candidate interaction...", "metrics": None}
        suggestion = generate_suggestion("hr", signals["latest_emotion"], signals["candidate_state"], signals["risk"])
        return {
            "suggestion": f"{suggestion} [{signals['explainability']}]",
            "metrics": signals,
            "priority_students": []
        }
    else:
        # Teacher context
        signals = risk_engine.compute_teacher_signals(history, session_id, participants)
        metrics = signals.get("metrics", {})
        
        if signals.get("priority_students"):
            top = signals["priority_students"][0]
            suggestion = generate_suggestion("teacher", "mixed", top["issue"], "medium")
        else:
            suggestion = generate_suggestion("teacher", "neutral", "attentive", "low")

        return {
            "suggestion": suggestion,
            "metrics": metrics,
            "priority_students": signals.get("priority_students", [])
        }

@app.get("/session/{session_id}/student_advice")
async def get_student_advice(session_id: str, user_id: str):
    from llm.local_llm import generate_suggestion
    from logs.session_logger import get_participant_emotion_history
    
    history = get_participant_emotion_history(session_id, user_id)
    if not history:
        return {"advice": "I'm still learning your communication style. Keep participating!"}
    
    latest = history[-1]
    # Use a special 'student' context for personalized coaching
    suggestion = generate_suggestion("student", latest["emotion"], "self_improvement", "low")
    return {"advice": suggestion}

@app.post("/nudge")
async def create_nudge(req: NudgeRequest):
    send_nudge(req.session_id, req.user_id, req.nudge_type)
    
    # Fetch user name for display
    name = f"Student #{req.user_id}"
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM users WHERE id = ?", (req.user_id,))
            row = cursor.fetchone()
            if row:
                name = row["name"]
            else:
                logging.warning(f"Nudge: User ID {req.user_id} not found in database.")
    except Exception as e:
        logging.error(f"Nudge DB error: {e}")

    # Broadcast to teacher with name
    await manager.broadcast(req.session_id, {
        "type": "nudge",
        "data": {"user_id": req.user_id, "user_name": name, "nudge_type": req.nudge_type}
    })
    return {"status": "ok"}

@app.post("/chat")
async def send_chat(req: ChatMessage):
    # Broadcast to all
    await manager.broadcast(req.session_id, {
        "type": "chat",
        "data": {"user_name": req.user_name, "message": req.message}
    })
    return {"status": "ok"}


@app.post("/process_frame")
async def process_frame(req: FrameRequest):
    try:
        header, encoded = req.image_b64.split(",", 1) if "," in req.image_b64 else ("", req.image_b64)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return {"error": "Invalid frame"}

        # Upsert generic frame for grid
        upsert_participant_frame(req.session_id, req.user_id, frame)

        # ML Inference
        import time
        start_time = time.time()
        emotion, confidence = predict_emotion(frame)
        latency = (time.time() - start_time) * 1000
        
        if emotion is None:
            logging.warning(f"Frame processing: No face detected for user {req.user_id} in {req.session_id}")

        # Apply Safety Guards (Smoothing & Confidence Floor)
        stable_emotion, is_reliable = signal_processor.process_signal(req.session_id, req.user_id, emotion, confidence)
        
        result = {
            "emotion": stable_emotion if is_reliable else "uncertain", 
            "confidence": float(round(confidence, 2)), 
            "intent": "Uncertain", 
            "risk": "low", 
            "focus": 0, 
            "latency_ms": float(round(latency, 2)),
            "is_reliable": is_reliable
        }

        if is_reliable and stable_emotion != "uncertain":
            result["intent"] = map_emotion_to_intent(stable_emotion, req.context, confidence)
            result["risk"] = compute_risk(stable_emotion, confidence, req.context)
            result["focus"] = risk_engine.compute_focus_score(stable_emotion, confidence)
            if not ENABLE_PRIVACY_MODE:
                update_student_focus(req.session_id, req.user_id, result["focus"])

        if not ENABLE_PRIVACY_MODE:
             logging.info(f"Frame processed: session={req.session_id} user={req.user_id} intent={result['intent']} latency={result['latency_ms']}ms")

        # Broadcast update to professional so UI reacts instantly
        await manager.broadcast(req.session_id, {
            "type": "student_update",
            "data": {
                "user_id": req.user_id,
                "metrics": result
            }
        })

        return result
    except Exception as e:
        logging.error(f"Frame error: {e}")
        return {"error": str(e)}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, user_id: Optional[str] = Query(None)):
    uid = await manager.connect(websocket, session_id, user_id)
    
    # If the joining user is the Host, notify others so they can re-negotiate WebRTC
    from auth.login import get_session
    sess = get_session(session_id)
    if sess and str(sess["professional_id"]) == str(uid):
        import asyncio
        asyncio.create_task(manager.broadcast(session_id, {"type": "host_ready", "host_id": uid}))
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            # WebRTC Signaling & Routing 
            if msg.get("type") in ["offer", "answer", "candidate"]:
                target_id = msg.get("target")
                
                # Special cases for routing
                if target_id == "host":
                    from auth.login import get_session
                    sess = get_session(session_id)
                    if sess:
                        target_id = str(sess["professional_id"])

                if target_id:
                    # Forward to the specific target
                    msg["from"] = uid
                    await manager.send_personal_message(msg, session_id, target_id)
            elif msg.get("type") == "reaction":
                await manager.broadcast(session_id, msg)
            elif msg.get("type") == "chat":
                # Ensure sender is correctly identified
                await manager.broadcast(session_id, msg)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
