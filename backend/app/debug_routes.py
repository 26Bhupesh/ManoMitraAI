from fastapi import APIRouter, HTTPException
from app.session_state import get_session, get_all_sessions, clear_session, clear_all_sessions

router = APIRouter()

@router.get("/session/{session_id}")
def get_session_data(session_id: str):
    """Return session data for given session_id."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/all")
def get_all_sessions_data():
    """Return all stored sessions."""
    return get_all_sessions()


@router.delete("/session/{session_id}")
def delete_session(session_id: str):
    """Delete a specific session."""
    clear_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@router.delete("/all")
def delete_all_sessions():
    """Delete all sessions."""
    clear_all_sessions()
    return {"status": "all sessions cleared"}
