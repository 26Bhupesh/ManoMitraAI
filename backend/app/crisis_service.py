# app/crisis_service.py
"""
Crisis Handling Module

Purpose:
- Activated ONLY after routing sends user to "crisis"
- Classifies crisis level: MODERATE or HIGH
- Provides appropriate actions:
    - Moderate: Helpline suggestion
    - High: Helpline + family contact escalation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

from app.session_state import get_session, update_session

router = APIRouter()
logger = logging.getLogger("crisis_service")
logger.setLevel(logging.INFO)

# ---------------- Schemas ----------------

class CrisisResponse(BaseModel):
    session_id: str
    crisis_level: str          # "moderate" | "high"
    action: str                # "helpline" | "helpline_and_family"
    reason: str
    timestamp: str


# ---------------- Crisis Logic ----------------

def classify_crisis(phq9: int, gad7: int, emotion: str) -> tuple[str, str, str]:
    """
    Returns (crisis_level, action, reason)
    """

    # HIGH CRISIS
    if phq9 >= 20 or gad7 >= 15:
        return (
            "high",
            "helpline_and_family",
            "Severe screening scores"
        )

    if emotion in ("sad", "fear") and phq9 >= 20:
        return (
            "high",
            "helpline_and_family",
            "Severe emotional distress with high PHQ-9"
        )

    # MODERATE CRISIS
    return (
        "moderate",
        "helpline",
        "Moderate psychological distress detected"
    )


# ---------------- Endpoint ----------------

@router.post("/handle", response_model=CrisisResponse)
def handle_crisis(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Ensure routing already decided crisis
    routing = session.get("routing_decision", {}).get("value")
    if not routing or routing.get("route") != "crisis":
        raise HTTPException(
            status_code=400,
            detail="Session is not routed to crisis"
        )

    screening = session.get("screening_result", {}).get("value")
    if not screening:
        raise HTTPException(
            status_code=400,
            detail="Screening results missing"
        )

    phq9 = screening.get("phq9_score")
    gad7 = screening.get("gad7_score")

    fusion_state = session.get("fusion_state", {}).get("value", {})
    emotion = fusion_state.get("fusion_emotion", "neutral")

    crisis_level, action, reason = classify_crisis(phq9, gad7, emotion)

    result = {
        "crisis_level": crisis_level,
        "action": action,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    update_session(session_id, "crisis_state", result)

    logger.info(
        f"Crisis handled for {session_id}: level={crisis_level}, action={action}"
    )

    return CrisisResponse(
        session_id=session_id,
        crisis_level=crisis_level,
        action=action,
        reason=reason,
        timestamp=result["timestamp"]
    )
