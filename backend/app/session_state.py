import json
from datetime import datetime
from pathlib import Path
from threading import Lock
import logging

# ---------------- Configuration ----------------
SESSION_FILE = Path("session_store.json")
lock = Lock()
logger = logging.getLogger("session_state")

# ---------------- Helpers ----------------
def _load_store() -> dict:
    """Load the session data from file."""
    if not SESSION_FILE.exists():
        return {}
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load session_store.json: {e}")
        return {}

def _save_store(store: dict):
    """Save session data to file safely."""
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write session_store.json: {e}")

# ---------------- Core Session Functions ----------------
def update_session(session_id: str, key: str, value):
    """Update or insert a key in session data."""
    with lock:
        store = _load_store()
        if session_id not in store:
            store[session_id] = {}
        store[session_id][key] = {
            "value": value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        _save_store(store)
        logger.info(f"Session updated: {session_id} -> {key}={value}")

def get_session(session_id: str):
    """Get session dictionary for a specific session_id."""
    store = _load_store()
    return store.get(session_id, {})

def get_all_sessions():
    """Return all session data."""
    return _load_store()

def clear_session(session_id: str):
    """Delete a specific session."""
    with lock:
        store = _load_store()
        if session_id in store:
            del store[session_id]
            _save_store(store)

def clear_all_sessions():
    """Wipe all stored sessions."""
    with lock:
        _save_store({})
        logger.warning("All sessions cleared.")

def authenticate_session(session_id: str, user_id: str, preferred_language: str):
    """Mark a session as authenticated and link to a user."""
    with lock:
        store = _load_store()
        if session_id not in store:
            store[session_id] = {}
        store[session_id]["user_id"] = {
            "value": user_id,
            "updated_at": datetime.utcnow().isoformat(),
        }
        store[session_id]["is_authenticated"] = {
            "value": True,
            "updated_at": datetime.utcnow().isoformat(),
        }
        store[session_id]["preferred_language"] = {
            "value": preferred_language,
            "updated_at": datetime.utcnow().isoformat(),
        }
        _save_store(store)
        logger.info(f"Session authenticated: {session_id} -> user_id={user_id}")

def is_session_authenticated(session_id: str) -> bool:
    """Check if a session is authenticated."""
    store = _load_store()
    session = store.get(session_id, {})
    auth_data = session.get("is_authenticated", {})
    return auth_data.get("value", False)

def get_session_user_id(session_id: str) -> str:
    """Get the user_id associated with a session."""
    store = _load_store()
    session = store.get(session_id, {})
    user_id_data = session.get("user_id", {})
    return user_id_data.get("value", None)

def get_user_preferred_language(session_id: str) -> str:
    """Get the user's preferred language for a session."""
    store = _load_store()
    session = store.get(session_id, {})
    lang_data = session.get("preferred_language", {})
    return lang_data.get("value", "en")


def get_chat_history(session_id: str) -> list:
    """Retrieve chat history list for a session (may be empty)."""
    store = _load_store()
    session = store.get(session_id, {})
    hist = session.get("chat_history", {}).get("value", [])
    return hist if isinstance(hist, list) else []


def get_last_technique(session_id: str) -> str:
    """Get the header of the last technique used in this session."""
    store = _load_store()
    session = store.get(session_id, {})
    last = session.get("last_technique", {}).get("value", "")
    return last if isinstance(last, str) else ""


def get_consecutive_short_replies(session_id: str) -> int:
    """Get the counter of consecutive short replies."""
    store = _load_store()
    session = store.get(session_id, {})
    cnt = session.get("consecutive_short_replies", {}).get("value", 0)
    return cnt if isinstance(cnt, int) else 0



def logout_session(session_id: str):
    """Clear authentication from a session."""
    with lock:
        store = _load_store()
        if session_id in store:
            store[session_id]["is_authenticated"] = {
                "value": False,
                "updated_at": datetime.utcnow().isoformat(),
            }
            _save_store(store)
            logger.info(f"Session logged out: {session_id}")
