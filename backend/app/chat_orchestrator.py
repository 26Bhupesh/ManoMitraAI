"""
Chat Orchestrator – single entry point for multimodal chat.

POST /chat/message orchestrates:
  preprocess → modality-specific emotion → fusion → crisis check (inside support) → support response.
No internal HTTP calls; uses direct Python imports.
"""

import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.emotion_fusion_service import run_fusion
from app.emotion_service import EmotionTextRequest, analyze_text_emotion
from app.emotion_voice_service import run_voice_emotion
from app.preprocess_service import run_preprocess
from app.session_state import update_session
from app.support_service import SupportRequest, generate_support_response

logger = logging.getLogger("chat_orchestrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(ch)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatMessageResponse(BaseModel):
    session_id: str
    bot_reply: str
    emotion_used: str
    response_type: str  # "guided_support" | "screening_suggestion"
    language: str
    timestamp: str


# ---------------------------------------------------------------------------
# Pipeline steps (internal)
# ---------------------------------------------------------------------------


def _ensure_fusion_state(session_id: str) -> None:
    """If fusion returned None, set a minimal fusion_state so support can read emotion."""
    update_session(
        session_id,
        "fusion_state",
        {
            "fusion_emotion": "neutral",
            "confidence": 0.0,
            "fusion_method": "no_valid_data",
            "timestamp": "",
            "weights": {},
            "component_emotions": {},
        },
    )
    logger.debug("Set default fusion_state for session %s", session_id)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(
    session_id: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
):
    """
    Multimodal chat: exactly one of text or audio.
    Internally runs: preprocess → emotion (text or voice) → fusion → support.
    Crisis check and screening_suggestion are handled inside support.
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    if text is not None and audio is not None:
        raise HTTPException(status_code=400, detail="Provide either text or audio, not both")
    if text is None and audio is None:
        raise HTTPException(status_code=400, detail="Provide text or audio")

    is_audio = audio is not None
    user_text_for_support: str

    try:
        # ---- STEP 1: Preprocess ----
        audio_path: Optional[str] = None
        if is_audio:
            audio_bytes = await audio.read()
            if not audio_bytes:
                raise HTTPException(status_code=400, detail="Uploaded audio file is empty")
            suffix = os.path.splitext(audio.filename or "")[-1] or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                audio_path = tmp.name
            try:
                preprocess_result = run_preprocess(session_id, audio_path=audio_path)
                user_text_for_support = (preprocess_result.transcript or "").strip() or " "
            finally:
                pass  # keep audio_path for step 2
        else:
            preprocess_result = run_preprocess(session_id, text=text or "")
            user_text_for_support = (text or "").strip() or " "

        # ---- STEP 2: Modality-specific emotion ----
        if is_audio:
            if audio_path and os.path.exists(audio_path):
                try:
                    run_voice_emotion(session_id, audio_path)
                finally:
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass
        else:
            analyze_text_emotion(EmotionTextRequest(session_id=session_id, text=text or ""))

        # ---- STEP 3: Fusion ----
        fusion_response = run_fusion(session_id)
        if fusion_response is None:
            _ensure_fusion_state(session_id)

        # ---- STEP 4 & 5: Crisis check + Support (inside generate_support_response) ----
        req = SupportRequest(session_id=session_id, user_text=user_text_for_support or " ")
        support_response = generate_support_response(req)
        return ChatMessageResponse(
            session_id=support_response.session_id,
            bot_reply=support_response.bot_reply,
            emotion_used=support_response.emotion_used,
            response_type=support_response.response_type,
            language=support_response.language,
            timestamp=support_response.timestamp,
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("Validation error in chat_message: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Chat pipeline error: %s", e)
        raise HTTPException(status_code=500, detail="Chat pipeline failed")
