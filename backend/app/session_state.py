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
