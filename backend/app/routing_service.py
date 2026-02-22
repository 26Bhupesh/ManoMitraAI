"""
routing_service.py
------------------
Decision Routing Module

Purpose:
- Reads screening results (PHQ-9, GAD-7) + fused emotion
- Decides whether user goes to SUPPORT or CRISIS

This module contains ZERO ML.
Pure deterministic logic.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

from app.session_state import get_session, update_session

router = APIRouter()
logger = logging.getLogger("routing_service")
logger.setLevel(logging.INFO)

# ---------------- Schemas ----------------

class RoutingResponse(BaseModel):
    session_id: str
    route: str  # "support" | "crisis"
    reason: str
    phq9_score: int
    gad7_score: int
    fusion_emotion: str
    timestamp: str


# ---------------- Routing Logic ----------------

def decide_route(phq9: int, gad7: int, emotion: str) -> tuple[str, str]:
    """
    Core routing rules.
    Returns (route, reason)
    """

    # High-risk conditions
    if phq9 >= 15 and gad7 >= 10:
        return "crisis", "Based on screening scores"

    if emotion in ("sad", "fear") and phq9 >= 15:
        return "crisis", "High emotional distress with elevated PHQ-9"

    # Default path
    return "support", "No high-risk indicators"


# ---------------- Endpoint ----------------

@router.post("/decide", response_model=RoutingResponse)
def route_decision(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Extract screening scores
    phq9 = session.get("screening_result", {}).get("value", {}).get("phq9_score")
    gad7 = session.get("screening_result", {}).get("value", {}).get("gad7_score")

    if phq9 is None or gad7 is None:
        raise HTTPException(
            status_code=400,
            detail="Screening not completed (PHQ-9 / GAD-7 missing)",
        )

    # Extract fused emotion (optional)
    fusion_state = session.get("fusion_state", {})
    fusion_emotion = fusion_state.get("value", {}).get("fusion_emotion", "neutral")

    route, reason = decide_route(phq9, gad7, fusion_emotion)

    decision = {
        "route": route,
        "reason": reason,
        "phq9_score": phq9,
        "gad7_score": gad7,
        "fusion_emotion": fusion_emotion,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    update_session(session_id, "routing_decision", decision)

    logger.info(f"Routing decision for {session_id}: {route} | {reason}")

    return RoutingResponse(
        session_id=session_id,
        route=route,
        reason=reason,
        phq9_score=phq9,
        gad7_score=gad7,
        fusion_emotion=fusion_emotion,
        timestamp=decision["timestamp"],
    )
