import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime
from pydantic import BaseModel
import json
from pathlib import Path
import uuid

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
from app.session_state import (
    update_session,
    get_all_sessions,
    get_session,
    authenticate_session,
    is_session_authenticated,
    get_session_user_id,
    get_user_preferred_language,
    logout_session,
)

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

# ============ AUTHENTICATION MODELS ============
class RegisterRequest(BaseModel):
    name: str
    username: str
    password: str
    date_of_birth: str  # YYYY-MM-DD format
    preferred_language: str  # "en", "hi", or "mr"
    emergency_contact_name: str
    emergency_contact_number: str
    emergency_contact_relation: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    session_id: str = None
    user_id: str = None
    username: str = None
    preferred_language: str = None

# ============ USER MANAGEMENT ============
USERS_FILE = Path("users.json")
from threading import Lock

user_lock = Lock()

def _load_users() -> dict:
    """Load users from file."""
    if not USERS_FILE.exists():
        return {"users": []}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load users.json: {e}")
        return {"users": []}

def _save_users(data: dict):
    """Save users to file."""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write users.json: {e}")

def _user_exists(username: str) -> bool:
    """Check if user already exists."""
    users_data = _load_users()
    return any(u["username"] == username for u in users_data.get("users", []))

def _get_user_by_username(username: str):
    """Retrieve user by username."""
    users_data = _load_users()
    for user in users_data.get("users", []):
        if user["username"] == username:
            return user
    return None

def _create_user(user_info: RegisterRequest) -> dict:
    """Create and store a new user."""
    with user_lock:
        if _user_exists(user_info.username):
            return None
        
        new_user = {
            "id": str(uuid.uuid4()),
            "username": user_info.username,
            "password": user_info.password,
            "name": user_info.name,
            "date_of_birth": user_info.date_of_birth,
            "preferred_language": user_info.preferred_language,
            "emergency_contact_name": user_info.emergency_contact_name,
            "emergency_contact_number": user_info.emergency_contact_number,
            "emergency_contact_relation": user_info.emergency_contact_relation,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        users_data = _load_users()
        users_data["users"].append(new_user)
        _save_users(users_data)
        logger.info(f"User created: {user_info.username}")
        return new_user

# ============ AUTH ROUTES ============
@app.post("/auth/register", response_model=AuthResponse)
async def register(user_data: RegisterRequest):
    """Register a new user."""
    try:
        # Validate language choice
        if user_data.preferred_language not in ["en", "hi", "mr"]:
            raise HTTPException(status_code=400, detail="Invalid language. Must be 'en', 'hi', or 'mr'.")
        
        # Check if user exists
        if _user_exists(user_data.username):
            raise HTTPException(status_code=400, detail="Username already exists.")
        
        # Create user
        new_user = _create_user(user_data)
        if not new_user:
            raise HTTPException(status_code=400, detail="Failed to create user.")
        
        # Create authenticated session
        session_id = str(uuid.uuid4())
        authenticate_session(session_id, new_user["id"], new_user["preferred_language"])
        
        return AuthResponse(
            success=True,
            message="User registered successfully.",
            session_id=session_id,
            user_id=new_user["id"],
            username=new_user["username"],
            preferred_language=new_user["preferred_language"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed.")

@app.post("/auth/login", response_model=AuthResponse)
async def login(credentials: LoginRequest):
    """Login with username and password."""
    try:
        user = _get_user_by_username(credentials.username)
        
        if not user or user["password"] != credentials.password:
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        
        # Create authenticated session
        session_id = str(uuid.uuid4())
        authenticate_session(session_id, user["id"], user["preferred_language"])
        
        return AuthResponse(
            success=True,
            message="Login successful.",
            session_id=session_id,
            user_id=user["id"],
            username=user["username"],
            preferred_language=user["preferred_language"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed.")

@app.post("/auth/logout", response_model=AuthResponse)
async def logout(request: Request):
    """Logout the user."""
    try:
        body = await request.json()
        session_id = body.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required.")
        
        logout_session(session_id)
        
        return AuthResponse(
            success=True,
            message="Logout successful.",
            session_id=session_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed.")

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