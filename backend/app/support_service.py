import random
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langdetect import detect
from app.session_state import get_session, update_session
from groq import Groq
import os

client = Groq(api_key='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')

router = APIRouter()
logger = logging.getLogger("support_service")
logger.setLevel(logging.INFO)

# ---------------- Schemas ----------------

class SupportRequest(BaseModel):
    session_id: str
    user_text: str


class SupportResponse(BaseModel):
    session_id: str
    bot_reply: str
    emotion_used: str
    response_type: str
    language: str
    timestamp: str


# ---------------- Knowledge Mapping ----------------

BASE_PATH = Path(__file__).parent / "knowledge"

EMOTION_TO_FILE = {
    "fear": {
        "en": "anxiety_en.txt",
        "hi": "anxiety_hi.txt",
        "mr": "anxiety_mr.txt",
    },
    "sad": {
        "en": "depression_en.txt",
        "hi": "depression_hi.txt",
        "mr": "depression_mr.txt",
    },
    "angry": {
        "en": "anger_en.txt",
        "hi": "anger_hi.txt",
        "mr": "anger_mr.txt",
    },
    "neutral": {
        "en": "grounding_en.txt",
        "hi": "grounding_hi.txt",
        "mr": "grounding_mr.txt",
    },
}
SUPPORTED_EMOTIONS = set(EMOTION_TO_FILE.keys())

CRISIS_KEYWORDS = {
    "kill myself",
    "suicide",
    "end my life",
    "no reason to live",
    "hurt myself",
    "self harm",
    "die"
}

# ---------------- Helpers ----------------

def detect_language_safe(text: str) -> str:
    try:
        lang = detect(text)
        return lang if lang in ("hi", "mr") else "en"
    except Exception:
        return "en"


def load_knowledge_blocks(filename: str) -> list[str]:
    path = BASE_PATH / filename
    if not path.exists():
        logger.warning(f"Knowledge file missing: {filename}")
        return []

    content = path.read_text(encoding="utf-8")
    return [block.strip() for block in content.split("---") if block.strip()]


def build_reply_from_block(block: str) -> str:
    lines = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip internal tags
        if line.startswith("[") and line.endswith("]"):
            continue
        lines.append(line)
    return " ".join(lines)


def score_block_relevance(block: str, user_text: str) -> int:
    """
    Simple relevance scoring:
    counts overlap between user words and block words
    """
    user_words = set(user_text.lower().split())
    block_words = set(block.lower().split())
    return len(user_words & block_words)


def contains_crisis_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CRISIS_KEYWORDS)


def rewrite_with_llm(block: str, user_text: str, emotion: str, language: str) -> str:
    """
    LLM is used ONLY to rewrite retrieved content.
    It must NOT invent advice or override safety logic.
    """

    prompt = f"""
        You are a mental health support assistant.

        Rewrite the content below so it sounds natural and empathetic.

        Rules:
        - Do NOT add new advice
        - Do NOT mention diagnoses
        - Do NOT suggest medication
        - Keep it supportive, not clinical
        - Write ONLY in this language: {language}
        - Do NOT translate from another language
        - User emotion: {emotion}

        User said:
        {user_text}

        Source content:
        {block}

        Rewrite:
        """

    return call_llm(prompt)


def call_llm(prompt: str) -> str:
    """
    Calls LLM ONLY for rewriting retrieved mental-health content.
    No decision making. No safety logic.
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a mental health support assistant. "
                        "Rewrite content empathetically. "
                        "Do NOT give medical advice. "
                        "Do NOT mention diagnoses. "
                        "Do NOT add new techniques."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.4,
            max_tokens=180,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"LLM rewrite failed: {e}")
        return "I’m here with you. You don’t have to go through this alone."

# ---------------- Endpoint ----------------

@router.post("/respond", response_model=SupportResponse)
def generate_support_response(req: SupportRequest):
    session_id = req.session_id
    user_text = req.user_text.strip()

    if not user_text:
        raise HTTPException(status_code=400, detail="Empty user_text")

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # ---------------- CRISIS INTERCEPT ----------------

    if contains_crisis_keywords(user_text):
        update_session(
            session_id,
            "screening_request",
            {
                "reason": "self_harm_language_detected",
                "triggered_at": datetime.now(timezone.utc).isoformat()
            }
        )

        return SupportResponse(
            session_id=session_id,
            bot_reply=(
                "I’m really glad you shared this with me. "
                "Before we go further, it would help me understand how best to support you "
                "if you could answer a few short questions. "
                "They’re called PHQ-9 and GAD-7, and they help measure stress and low mood."
            ),
            emotion_used="concern",
            response_type="immediate_screening",
            language=detect_language_safe(user_text),
            timestamp=datetime.now(timezone.utc).isoformat()
        )


    # Get fused emotion only (do not rely on raw text emotion)
    fusion_state = session.get("fusion_state", {})
    emotion = fusion_state.get("value", {}).get("fusion_emotion")

    if not emotion:
        emotion = "neutral"

    if emotion not in SUPPORTED_EMOTIONS:
        emotion = "neutral"

    language = detect_language_safe(user_text)

    emotion_files = EMOTION_TO_FILE.get(emotion)
    filename = None

    if isinstance(emotion_files, dict):
        filename = emotion_files.get(language) or emotion_files.get("en")

    blocks = load_knowledge_blocks(filename) if filename else []

    if not blocks:
        bot_reply = "I’m here with you. You can take your time and share what you’re feeling."
    else:
        # Rank blocks by relevance to user_text
        scored_blocks = [
            (score_block_relevance(block, user_text), block)
            for block in blocks
        ]

        # Sort by score (highest first)
        scored_blocks.sort(key=lambda x: x[0], reverse=True)

        # Pick best match, fallback to random if all scores are zero
        best_score, best_block = scored_blocks[0]
        selected_block = best_block if best_score > 0 else random.choice(blocks)

        raw_block = build_reply_from_block(selected_block)
        bot_reply = rewrite_with_llm(raw_block, user_text, emotion, language)


    timestamp = datetime.now(timezone.utc).isoformat()

    response = SupportResponse(
        session_id=session_id,
        bot_reply=bot_reply,
        emotion_used=emotion,
        response_type="guided_support",
        language=language,
        timestamp=timestamp,
    )

    update_session(session_id, "last_bot_reply", response.model_dump())

    logger.info(
        f"Support reply generated for {session_id}: emotion={emotion}, lang={language}"
    )

    return response
