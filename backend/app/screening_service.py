# app/screening_service.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.session_state import get_session, update_session
from datetime import datetime, timezone

router = APIRouter()

# ---------------- Question Keys (frontend translates via i18n) ----------------

PHQ9_KEYS = [f"phq9_{i}" for i in range(9)]
GAD7_KEYS = [f"gad7_{i}" for i in range(7)]
ALL_QUESTION_KEYS = PHQ9_KEYS + GAD7_KEYS

# ---------------- Schemas ----------------

class StartScreeningRequest(BaseModel):
    session_id: str

class AnswerRequest(BaseModel):
    session_id: str
    answer: int  # 0–3

# ---------------- Helpers ----------------

def risk_level(score: int, scale: str) -> str:
    if scale == "phq9":
        if score <= 4: return "minimal"
        if score <= 9: return "mild"
        if score <= 14: return "moderate"
        if score <= 19: return "moderately_severe"
        return "severe"
    else:
        if score <= 4: return "minimal"
        if score <= 9: return "mild"
        if score <= 14: return "moderate"
        return "severe"

# ---------------- Endpoints ----------------

@router.post("/start")
def start_screening(req: StartScreeningRequest):
    session = get_session(req.session_id)

    # Allow screening if explicitly requested by support
    screening_request = session.get("screening_request", {}).get("value")

    if screening_request:
        update_session(req.session_id, "screening_request", None)

    update_session(req.session_id, "screening_active", True)
    update_session(req.session_id, "screening_index", 0)
    update_session(req.session_id, "screening_answers_phq9", [])
    update_session(req.session_id, "screening_answers_gad7", [])

    return {
        "session_id": req.session_id,
        "question_index": 1,
        "question": ALL_QUESTION_KEYS[0]
    }

@router.post("/answer")
def submit_answer(req: AnswerRequest):
    if req.answer not in (0, 1, 2, 3):
        raise HTTPException(status_code=400, detail="Answer must be 0–3")

    session = get_session(req.session_id)
    if not session or not session.get("screening_active", {}).get("value"):
        raise HTTPException(status_code=400, detail="Screening not active")

    index = session["screening_index"]["value"]

    if index < 9:
        answers = session["screening_answers_phq9"]["value"]
        answers.append(req.answer)
        update_session(req.session_id, "screening_answers_phq9", answers)
    else:
        answers = session["screening_answers_gad7"]["value"]
        answers.append(req.answer)
        update_session(req.session_id, "screening_answers_gad7", answers)

    index += 1
    update_session(req.session_id, "screening_index", index)

    if index < len(ALL_QUESTION_KEYS):
        return {
            "session_id": req.session_id,
            "question_index": index + 1,
            "question": ALL_QUESTION_KEYS[index]
        }

    # ---- Final scoring ----
    phq9_score = sum(session["screening_answers_phq9"]["value"])
    gad7_score = sum(session["screening_answers_gad7"]["value"])

    result = {
        "response_type": "screening_complete",
        "phq9_score": phq9_score,
        "phq9_risk": risk_level(phq9_score, "phq9"),
        "gad7_score": gad7_score,
        "gad7_risk": risk_level(gad7_score, "gad7")
    }

    update_session(req.session_id, "screening_result", result)
    update_session(req.session_id, "screening_active", False)

    update_session(
        req.session_id,
        "routing_ready",
        {
            "source": "screening_complete",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

    return result
