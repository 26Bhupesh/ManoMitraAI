import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

# Import routers from the microservices
from app.preprocess_service import router as preprocess_router
from app.video_service import router as video_router
from app.emotion_service import router as emotion_router
from app.emotion_voice_service import router as emotion_router_voice
from app.debug_routes import router as debug_router
from app.emotion_fusion_service import router as fusion_router
from app.support_service import router as support_router
from app.screening_service import router as screening_router
from app.routing_service import router as routing_router
from app.crisis_service import router as crisis_router
from app.chat_orchestrator import router as chat_router

# Import session state (shared memory)
from app.session_state import update_session
from app.session_state import get_all_sessions, get_session

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unified_app")

# ---------------- App Setup ----------------
app = FastAPI(title="🧠Unified Mental Health Support API")

# Allow CORS for frontend (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8080", "http://127.0.0.1:8080", "http://10.16.90.42:8080/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log all requests with session_id (if available)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    session_id = None
    try:
        content_type = (request.headers.get("content-type") or "").lower()

        # If JSON content, safely peek the body *and reattach it* so the route can still read it.
        if content_type.startswith("application/json"):
            body_bytes = await request.body()  # read once
            if body_bytes:
                try:
                    import json
                    body_json = json.loads(body_bytes.decode("utf-8"))
                    session_id = body_json.get("session_id")
                except Exception:
                    session_id = None
            # put body back so downstream can read it
            request._body = body_bytes

        # For form/multipart (including file uploads) **do not** call await request.form()
        # Instead, fall back to query params — the route will parse form fields properly.
        else:
            session_id = request.query_params.get("session_id") or None

        logger.info(f"[{datetime.utcnow().isoformat()}] {request.method} {request.url.path} | session_id={session_id}")
        # if session_id:
        #     update_session(session_id, "last_request", request.url.path)
    except Exception:
        # Never fail the request because logging failed
        logger.exception("Logging middleware error (ignored)")

    response = await call_next(request)
    return response

# Include routers
app.include_router(preprocess_router, prefix="", tags=["Preprocess"])
app.include_router(video_router, prefix="/video", tags=["Video"])
app.include_router(emotion_router, prefix="/emotion", tags=["Text Emotion Detection"])
app.include_router(emotion_router_voice, prefix="/emotion_voice", tags=["Voice Emotion Detection"])
app.include_router(debug_router, prefix="/debug", tags=["Debug"])
app.include_router(fusion_router, prefix="/fusion", tags=["Fusion"])
app.include_router(support_router, prefix="/support", tags=["Support"])
app.include_router(screening_router, prefix="/screening", tags=["Screening"])
app.include_router(routing_router, prefix="/route", tags=["Routing"])
app.include_router(crisis_router, prefix="/crisis", tags=["Crisis"])
app.include_router(chat_router, prefix="/chat", tags=["Chat"])

# ---------------- Root Endpoint ----------------
@app.get("/")
def root():
    return {
        "message": "Unified Mental Health Support API",
        "endpoints": ["/chat/message", "/video/video_frame", "/preprocess", "/debug/all", "/debug/session/{session_id}", "/emotion/text", "/emotion_voice/voice", "/fusion/{session_id}", "/screening/*", "/route/decide", "/crisis/handle"],
        "timestamp": datetime.utcnow().isoformat()
    }