import logging
import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import fastapi
import chromadb # pyright: ignore[reportMissingImports]
from chromadb.utils import embedding_functions # pyright: ignore[reportMissingImports]
from pydantic import BaseModel
from app.session_state import get_session, update_session
from groq import Groq

# Initialize Groq client with API key from environment
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY environment variable not set")
client = Groq(api_key=groq_api_key)

router = fastapi.APIRouter()
logger = logging.getLogger("support_service")
logger.setLevel(logging.INFO)

# ============ SCHEMAS ============

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


# ============ CONFIGURATION ============

CHROMA_PATH = Path(__file__).parent / "chroma_support"
RAG_COLLECTION_NAME = "support_knowledge"
RAG_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

ALLOWED_TOPICS = {
    "anxiety",
    "low_mood",
    "anger",
    "stress",
    "sleep",
    "relationship",
    "academic",
    "general_support"
}

CRISIS_KEYWORDS = {
    # ── English ──────────────────────────────────────────────
    "kill myself", "kill yourself", "end my life", "end it all", "want to die", "wanna die",
    "gonna die", "should die", "don't want to live", "dont want to live", "not worth living",
    "better off dead", "hurt myself", "harm myself", "cut myself", "self harm", "self-harm",
    "no reason to live", "ending it all", "take my life", "take my own life", "overdose",

    # ── Hindi ─────────────────────────────────────────────────
    "मरना चाह", "मर जाऊ", "मर जाना", "मरने दो", "मर जाऊंगा", "मर जाऊंगी", "जीना नहीं", "जीने का मन नहीं", "जिंदगी खत्म",
    "सब खत्म कर", "खुद को नुकसान", "खुद को चोट", "खुद को hurt", "खुद को हर्ट", "आत्महत्या", "नहीं जीना", "जान दे दूं",
    "जान दे दूँ", "जान देना", "किसी को मारना", "किसी की जान", "जान लेना", "खून करना", "किसी को hurt",

    # ── Marathi ───────────────────────────────────────────────
    "मरायचं", "मरावं", "मरतो", "मरते", "जगायचं नाही", "जगणं नको", "जीव द्यायचा", "जीव द्यायची", "जीव संपवायचा", "संपवून टाक",
    "संपवतो", "संपवते", "सगळं संपव", "स्वतःला दुखव", "स्वतःला इजा", "आत्महत्या", "एखाद्याचा जीव", "कोणाचा जीव", "जीव घ्यायचा",
    "जीव घ्यावा", "कोणाला मारायचं", "कोणाला मारणे", "खून करायचा",
}

RELEVANCE_THRESHOLD = 30.0  # Distance threshold for RAG relevance (tuned empirically)

# Signals that mean "I don't want this technique" — clear and move on
REJECTION_PATTERNS = [
    r'^(नको|नाही|नको\s+नाही|नाही\s+नको)[\s.!]*$',
    r'^(नहीं|मत|बस)[\s.!]*$',
    r'^(no|nope|stop)[\s.!]*$',
    r'\b(वेगळं\s+सांग|दुसरं\s+काहीतरी|नवीन\s+टेक्निक|skip\s+this)\b',
    r'\b(बस\s+करो|कुछ\s+और|दूसरा\s+तरीका)\b',

    # sentence-level rejection (Marathi)
    r'(कोणतेही\s+तंत्र\s+नको|आता\s+काही\s+नको|तंत्र\s+नको)',
    r'(नको\s+आता|आता\s+नको)',

    # sentence-level rejection (Hindi)
    r'(कोई\s+भी\s+तकनीक\s+नहीं|अब\s+कुछ\s+नहीं\s+चाहिए|तकनीक\s+नहीं\s+चाहिए)',

    # English sentence-level
    r"\b(don't\s+want\s+(any|a)\s+technique|no\s+more\s+techniques?|stop\s+suggesting)\b",
]

# Signals that mean "I'm confused, explain better" — STAY on technique, clarify
CONFUSION_PATTERNS = [
    r'\b(कळाल\s+नाही|समजलं\s+नाही|नक्की\s+काय|म्हणजे\s+काय|स्पष्ट\s+सांग)\b',
    r'\b(समझ\s+नहीं|क्या\s+मतलब|ठीक\s+से\s+बताओ|और\s+बताओ)\b',
    r"\b(don't\s+understand|what\s+do\s+you\s+mean|explain|be\s+more\s+specific|unclear)\b",
]

# How many turns to keep a technique active before auto-closing
TECHNIQUE_MAX_TURNS = 4

TECHNIQUE_COOLDOWN_TURNS = 2  # turns to stay technique-free after closing/rejection

FORBIDDEN_RESPONSE_PATTERNS = """
STRICTLY FORBIDDEN phrases and behaviors:
- Telling user they are "ready to talk" or "opening up" when they said no/nothing
- "तू आता बोलायला तयार झाला आहेस" or any variant when user said नाही/नको
- "तुझ्या X ची भावना मला पूर्णपणे समजते, आणि ती योग्य आहे" (same opener every time)
- "तू या प्रवासात खूप पुढे गेला आहेस" (hollow filler praise)
- "तुला अभिमान वाटायला पाहिजे" or "you should be proud" (telling user how to feel)
- "तयार आहेस का?" as a repetitive closing
- "I'm here to support you" repeated more than once
- Introducing a new technique when user said no or wants to leave
- Interpreting silence or refusal as willingness to engage
- Any phrase that sounds like a motivational poster
"""

SESSION_END_PATTERNS = [
    r'\b(मला\s+काही\s+नको|काही\s+नको\s+आता|आता\s+काही\s+नको)\b',
    r'\b(मदत\s+मिळाली|गरज\s+नाही\s+आता|आता\s+गरज\s+नाही)\b',
    r'\b(मुझे\s+कुछ\s+नहीं\s+चाहिए|काफी\s+है\s+अब|अब\s+ज़रूरत\s+नहीं)\b',
    r"\b(i('m|\s+am)\s+(okay|fine|good)\s+now|that'?s\s+(all|enough)|i\s+don't\s+need)\b",
]

CRISIS_RESPONSE = {
    "en": (
        "Thank you for trusting me with something so painful. "
        "You're not alone, and I'm taking this seriously. "
        "To understand how to best support you, "
        "I'd like to ask a few short questions — PHQ-9 and GAD-7."
    ),
    "hi": (
        "इतनी दर्दनाक बात मुझसे साझा करने के लिए शुक्रिया। "
        "आप अकेले नहीं हैं, और मैं इसे गंभीरता से ले रहा हूँ। "
        "आपकी बेहतर मदद करने के लिए मैं कुछ छोटे सवाल पूछना चाहता हूँ — "
        "इन्हें PHQ-9 और GAD-7 कहते हैं।"
    ),
    "mr": (
        "इतकी जड गोष्ट माझ्याशी शेअर केल्याबद्दल आभारी आहे. "
        "तुम्ही एकटे नाही आहात, आणि मी हे गांभीर्याने घेतो आहे. "
        "तुम्हाला अधिक चांगल्या प्रकारे मदत करण्यासाठी "
        "मला काही छोटे प्रश्न विचारायचे आहेत — PHQ-9 आणि GAD-7."
    ),
}


# ============ VECTOR RAG (ChromaDB) ============

@lru_cache(maxsize=1)
def _get_support_collection():
    """Persistent Chroma collection with multilingual sentence embeddings."""
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=RAG_EMBEDDING_MODEL
    )
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return chroma_client.get_collection(name=RAG_COLLECTION_NAME, embedding_function=ef)


def retrieve_knowledge_block(
    user_text: str,
    topic: str,
    language: str,
    last_technique: str,
) -> tuple[dict | None, float | None]:
    """
    Query ChromaDB with topic + language metadata filters.
    Returns ({header, content} or None, distance or None for logging).
    Skips blocks whose header matches last_technique when alternatives exist.
    Only called when a NEW technique is needed (not during follow-through turns).
    """
    try:
        collection = _get_support_collection()
    except Exception as e:
        logger.error("ChromaDB collection unavailable (run ingest_data.py): %s", e)
        return None, None

    if collection.count() == 0:
        logger.warning("ChromaDB collection %r is empty", RAG_COLLECTION_NAME)
        return None, None

    def query_lang(lang: str):
        return collection.query(
            query_texts=[user_text],
            n_results=5,
            where={"$and": [{"topic": topic}, {"language": lang}]},
        )

    def pick_block(result: dict) -> tuple[dict | None, float | None]:
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for meta, dist in zip(metas, dists):
            if not meta:
                continue
            header = meta.get("header", "")
            if header == last_technique:
                continue
            if dist is not None and float(dist) > RELEVANCE_THRESHOLD:
                logger.info(f"RAG block rejected (distance {dist:.2f} > threshold): {header}")
                return None, float(dist)
            return (
                {"header": header, "content": meta.get("content", "")},
                float(dist) if dist is not None else None,
            )
        return None, None

    try:
        res = query_lang(language)
        if not res.get("metadatas") or not res["metadatas"][0]:
            res = collection.query(query_texts=[user_text], n_results=3, where={"language": language})

        if (not res.get("metadatas") or not res["metadatas"][0]) and language != "en":
            res = collection.query(query_texts=[user_text], n_results=3, where={"language": "en"})

        return pick_block(res)
    except Exception as e:
        logger.error("ChromaDB query failed: %s", e)
        return None, None


# ============ LLM FUNCTIONS ============

def detect_topic_llm(user_text: str, language: str = "en") -> dict:
    """
    Classify user message into ONE of the allowed topics using LLM.
    Returns: {topic: str, confidence: float}
    Fallback to general_support if invalid or low confidence.
    Only called when a new technique is needed.
    """
    prompt = """You are a classification system.

Classify the user's message into exactly ONE of:
- anxiety
- low_mood
- anger
- stress
- sleep
- relationship
- academic
- general_support

Return strictly JSON:
{
  "topic": "<value>",
  "confidence": <float between 0 and 1>
}

Do not explain."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": f"{prompt}\n\nUser message: {user_text}"
            }],
            temperature=0.0,
            max_tokens=40
        )

        response_text = response.choices[0].message.content.strip()
        result = json.loads(response_text)

        topic = result.get("topic", "").lower()
        confidence = float(result.get("confidence", 0))

        if topic not in ALLOWED_TOPICS or confidence < 0.6:
            logger.info(f"Topic validation failed: topic={topic}, conf={confidence}")
            return {"topic": "general_support", "confidence": 0.6}

        return {"topic": topic, "confidence": confidence}

    except Exception as e:
        logger.error(f"Topic classification failed: {e}")
        return {"topic": "general_support", "confidence": 0.6}


def generate_response(
    user_text: str,
    fusion_emotion: str,
    language: str,
    chat_history: list = None,
    knowledge_block: dict = None,
    max_sentences: int = 4,
    disengage_prompt_override: str = None,
    technique_phase: str = "new",   # "new" | "followthrough" | "closing"
    active_turn: int = 1,          # which turn we're on within the current technique (1-based)
) -> str:
    if chat_history is None:
        chat_history = []

    lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
    target_lang = lang_map.get(language, "English")

    # Override guidance if a special instruction was passed (e.g. short reply re-engagement)
    if disengage_prompt_override:
        guidance_section = disengage_prompt_override
    else:
        guidance_section = build_guidance_for_phase(knowledge_block, technique_phase, active_turn)

    formatted_history = format_chat_history_for_prompt(chat_history)

    system_prompt = f"""You are ManoMitra, a warm mental health companion.
Respond in {target_lang} only. Max {max_sentences} sentences.
Be natural and human — like a caring friend, not a therapist.
Do NOT repeat what you said before. Do NOT add filler sentences.
Do NOT tell the user how they should feel.
Follow the [Instruction] below exactly — it tells you precisely what to say."""

    user_prompt = f"""[Recent Conversation]
{formatted_history}

[What user just said]
{user_text}

[Instruction — follow this exactly]
{guidance_section}

Write {max_sentences} sentences in {target_lang}:"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=450,
            top_p=0.85
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        fallback = {
            "en": "I'm here with you. Please, tell me more about how you're feeling.",
            "hi": "मैं आपके साथ हूँ। कृपया मुझे और बताइये कि आप कैसा महसूस कर रहे हैं।",
            "mr": "मी तुमच्या सोबत आहे. तुम्हाला नक्की कसं वाटतंय त्याबद्दल अधिक सांगा."
        }
        return fallback.get(language, fallback["en"])


# ============ UTILITY FUNCTIONS ============

def contains_crisis_keywords(text: str) -> bool:
    """Check if text contains crisis keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CRISIS_KEYWORDS)

def detect_intent(text: str) -> str:
    text_lower = text.lower().strip()

    # Thank-you — handle BEFORE greeting so धन्यवाद/शुक्रिया don't 
    # get swallowed by the greeting branch
    thanks_patterns = (
        r'\b(thanks|thank\s+you|thank\s+u)\b'
        r'|\b(धन्यवाद|शुक्रिया|आभारी\s+आहे|आभार)\b'
    )
    if re.search(thanks_patterns, text_lower, re.UNICODE):
        return "thanks"

    greeting_patterns = (
        r'\b(hi|hello|hey)\b'
        r'|\b(namaste|namaskar|नमस्ते|नमस्कार)\b'
    )
    if re.search(greeting_patterns, text_lower, re.UNICODE):
        return "greeting"

    intro_patterns = (
        r"(?i)^\s*(?:i'm|i\s+am|my\s+name\s+is|call\s+me)\s+[A-Za-z]+"
        r"|माझं\s+नाव|मेरा\s+नाम"
    )
    if re.search(intro_patterns, text_lower, re.UNICODE):
        return "introduction"

    goodbye_patterns = (
        r'\b(bye|goodbye|farewell|see\s+you|gotta\s+go)\b'
        r'|\b(निघतो|निघते|जातो|जाते|बाय|भेटू\s+परत|येतो|येते)\b'
        r'|\b(चलता\s+हूँ|चलती\s+हूँ|जा\s+रहा\s+हूँ|अलविदा|बाय)\b'
    )
    if re.search(goodbye_patterns, text_lower, re.UNICODE):
        return "goodbye"

    return None

def should_enforce_short_response(user_text: str) -> bool:
    """Check if user message is short (≤4 words)."""
    return len(user_text.split()) <= 4

def get_language_from_session(session: dict) -> str:
    # Prefer the explicitly locked chat_language over the per-turn preprocessor output
    locked = session.get("chat_language", {}).get("value")
    if locked:
        return locked
    return session.get("last_preprocess", {}).get("value", {}).get("language", "en")

def extract_chat_history(session: dict) -> list:
    """Extract chat history from session."""
    history = session.get("chat_history", {}).get("value", [])
    return history if isinstance(history, list) else []

def update_chat_history(session_id: str, user_text: str, bot_reply: str):
    """Add exchange to chat history, keep last 12 messages (6 exchanges)."""
    history = extract_chat_history(get_session(session_id))

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": bot_reply})

    if len(history) > 12:
        history = history[-12:]

    update_session(session_id, "chat_history", history)

def handle_language_switch(text: str, session_id: str) -> str:
    match = re.match(
        r'^/?lang(?:uage)?\s+(en|hi|mr)\s*$',
        text.strip(),
        re.IGNORECASE
    )
    if match:
        return match.group(1).lower()
    return None

def get_last_technique(session: dict) -> str:
    """Get the last technique header from session."""
    last_tech = session.get("last_technique", {}).get("value", "")
    return last_tech if isinstance(last_tech, str) else ""

def update_last_technique(session_id: str, technique_header: str):
    """Update last technique in session."""
    update_session(session_id, "last_technique", technique_header)

def get_consecutive_short_replies(session: dict) -> int:
    """Get count of consecutive short replies."""
    count = session.get("consecutive_short_replies", {}).get("value", 0)
    return count if isinstance(count, int) else 0

def update_consecutive_short_replies(session_id: str, count: int):
    """Update consecutive short replies counter."""
    update_session(session_id, "consecutive_short_replies", count)

def format_chat_history_for_prompt(history: list) -> str:
    """Format chat history as readable dialogue for LLM context."""
    if not history:
        return "No prior conversation."
    lines = []
    for msg in history[-6:]:  # last 3 exchanges = 6 messages
        role = "User" if msg.get("role") == "user" else "ManoMitra"
        lines.append(f"{role}: {msg.get('content', '').strip()}")
    return "\n".join(lines)

def user_is_rejecting(user_text: str) -> bool:
    """User wants to stop this technique entirely."""
    text_lower = user_text.lower()
    return any(re.search(p, text_lower, re.UNICODE) for p in REJECTION_PATTERNS)

def user_is_confused(user_text: str) -> bool:
    """User wants clarification on the current technique."""
    text_lower = user_text.lower()
    return any(re.search(p, text_lower, re.UNICODE) for p in CONFUSION_PATTERNS)

def build_guidance_for_phase(
    knowledge_block: dict | None,
    technique_phase: str,
    active_turn: int,
) -> str:
    """
    Build a precise, phase-specific instruction for the LLM.
    The LLM's only job is to translate this into warm, natural language.
    """
    if technique_phase == "listening":
        return (
            "Do NOT mention any technique. "
            "Acknowledge what the user shared. "
            "Ask ONE clarifying question about what specifically is bothering them."
        )

    if not knowledge_block:
        return "Listen carefully. Reflect back what the user said. Ask one open question."

    header = knowledge_block.get("header", "")
    steps_raw = knowledge_block.get("content") or knowledge_block.get("body") or ""

    # Parse steps into a list if they're newline-separated
    steps = [s.strip() for s in steps_raw.split("\n") if s.strip()]
    # Which step to focus on this turn
    step_index = max(0, min(active_turn - 1, len(steps) - 1))
    current_step = steps[step_index] if steps else steps_raw

    if technique_phase == "new":
        return (
            f"Introduce '{header}' in ONE sentence — just its name and purpose. "
            f"Then give ONLY this first step: {current_step}. "
            f"Ask the user to try just this one step."
        )

    if technique_phase == "followthrough":
        next_step = steps[step_index] if steps else ""
        return (
            f"Do NOT re-introduce '{header}'. "
            f"Acknowledge what the user just said in one sentence. "
            f"Then guide them to this next step: {next_step}. "
            f"Ask if they can try it."
        )

    if technique_phase == "clarifying":
        return (
            f"The user is confused about this step: {current_step}. "
            f"Explain it differently — use a concrete real-life example. "
            f"Do NOT move to the next step yet."
        )

    if technique_phase == "closing":
        return (
            f"The user finished '{header}'. "
            f"Acknowledge their effort in one warm sentence. "
            f"Ask how they feel right now — nothing else."
        )

    return "Focus on listening and emotional support."

# ============ ACTIVE TECHNIQUE HELPERS ============

def get_active_technique(session: dict) -> dict | None:
    """
    Returns the currently active technique block being worked through, or None.
    Shape: {"header": str, "content": str}
    """
    active = session.get("active_technique", {}).get("value")
    if active and isinstance(active, dict) and active.get("header"):
        return active
    return None


def get_active_technique_turn(session: dict) -> int:
    """How many follow-through turns have elapsed on the active technique."""
    val = session.get("active_technique_turn", {}).get("value", 0)
    return val if isinstance(val, int) else 0


def set_active_technique(session_id: str, block: dict | None):
    """Lock in a new active technique, or pass None to clear it."""
    update_session(session_id, "active_technique", block)


def clear_active_technique(session_id: str):
    """Clear the active technique and reset its turn counter."""
    update_session(session_id, "active_technique", None)
    update_session(session_id, "active_technique_turn", 0)


def get_last_bot_reply_text(session: dict) -> str:
    last = session.get("last_bot_reply", {}).get("value", {})
    return last.get("bot_reply", "") if isinstance(last, dict) else ""


def increment_active_technique_turn(session_id: str, session: dict):
    """Advance the turn counter for the active technique."""
    current = get_active_technique_turn(session)
    update_session(session_id, "active_technique_turn", current + 1)


def user_completed_technique(user_text: str, active_turn: int) -> bool:
    """
    Heuristic: technique is considered complete after TECHNIQUE_MAX_TURNS turns,
    or if the user sends an explicit completion signal.
    """
    if active_turn >= TECHNIQUE_MAX_TURNS:
        return True
    # In user_completed_technique():
    completion_signals = (
        r'\b('
        # English
        r'done|finished|better|good|helped|thank\s+you|thanks|okay\s+now|feel\s+better'
        r'|'
        # Marathi
        r'ठीक|झालं|झाल|केलं|केल'
        r'|बर[ं]?\s+वाट[तं]*'
        r'|मदत\s+झाली|मदत\s+मिळाली'
        r'|धन्यवाद|बर[ं]?\s+आह[े]?'
        r'|चांगलं?\s+वाट[तं]*|पुरे|आता\s+ठीक|गरज\s+नाही'
        # Hindi
        r'|ठीक\s+है|ठीक\s+हूँ|बेहतर|अच्छा\s+लग\s+रहा|शुक्रिया|धन्यवाद'
        r'|मदद\s+हुई|अब\s+ठीक|अच्छा\s+है|काफी\s+है|बस\s+यही\s+चाहिए\s+था'
        r')\b'
    )
    return bool(re.search(completion_signals, user_text.lower(), re.UNICODE))

def get_technique_cooldown(session: dict) -> int:
    val = session.get("technique_cooldown", {}).get("value", 0)
    return val if isinstance(val, int) else 0

def set_technique_cooldown(session_id: str, turns: int):
    update_session(session_id, "technique_cooldown", turns)

def decrement_technique_cooldown(session_id: str, session: dict):
    current = get_technique_cooldown(session)
    update_session(session_id, "technique_cooldown", max(0, current - 1))

def user_is_ending_session(user_text: str) -> bool:
    text_lower = user_text.lower()
    return any(re.search(p, text_lower, re.UNICODE) for p in SESSION_END_PATTERNS)


# ============ MAIN ENDPOINT ============

@router.post("/respond", response_model=SupportResponse)
def generate_support_response(req: SupportRequest):
    """
    Main support response generation endpoint.
    Implements phase-aware technique tracking so the bot stays with one
    technique across multiple turns instead of introducing a new one each time.
    """
    session_id = req.session_id
    user_text = req.user_text.strip()

    if not user_text:
        raise fastapi.HTTPException(status_code=400, detail="Empty user_text")

    session = get_session(session_id)
    if not session:
        raise fastapi.HTTPException(status_code=404, detail="Session not found")

    language = get_language_from_session(session)

    # ============ STEP 1: CRISIS CHECK (PRIORITY) ============
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
            bot_reply=CRISIS_RESPONSE.get(language, CRISIS_RESPONSE["en"]),
            emotion_used="concern",
            response_type="immediate_screening",
            language=language,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    # ============ STEP 2: LANGUAGE SWITCH CHECK ============
    lang_switch = handle_language_switch(user_text, session_id)
    if lang_switch:
        language = lang_switch
        update_session(session_id, "chat_language", language)
        bot_reply = {
            "en": "Language switched to English.",
            "hi": "भाषा हिंदी में बदल दी गई है।",
            "mr": "भाषा मराठीत बदली गेली आहे."
        }.get(language, "Language switched.")
        return SupportResponse(
            session_id=session_id,
            bot_reply=bot_reply,
            emotion_used="neutral",
            response_type="language_switch",
            language=language,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    # ============ STEP 3: FIRST TIME - SET LANGUAGE LOCK ============
    if "chat_language" not in session:
        update_session(session_id, "chat_language", language)
    
    # ============ STEP 4: INTENT DETECTION ============
    if user_is_ending_session(user_text):
        bot_reply = {
            "en": "Really glad you're feeling better. Come back whenever you need — take care.",
            "hi": "अच्छा लगा कि आप बेहतर महसूस कर रहे हैं। जब भी ज़रूरत हो, वापस आएं।",
            "mr": "बरं वाटलं की तुम्हाला बरं वाटतंय. कधीही गरज लागली तर या."
        }.get(language, "Glad you're feeling better. Take care.")
        
        # Clear all technique state cleanly
        clear_active_technique(session_id)
        set_technique_cooldown(session_id, 0)
        
        response = SupportResponse(
            session_id=session_id,
            bot_reply=bot_reply,
            emotion_used="neutral",
            response_type="session_end",
            language=language,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        update_chat_history(session_id, user_text, bot_reply)
        update_session(session_id, "last_bot_reply", response.model_dump())
        return response

    intent = detect_intent(user_text)
    if intent:
        intent_responses = {
            "greeting": {
                "en": "Hello! I'm here to listen and support you. How are you feeling today?",
                "hi": "नमस्ते! मैं आपको सुनने और समर्थन करने के लिए यहाँ हूँ। आप आज कैसा महसूस कर रहे हैं?",
                "mr": "नमस्कार! मी तुमच ऐकण्यास आणि समर्थन करण्यास येथे आहे. तुम्हाला आज कसे वाटत आहे?"
            },
            "introduction": {
                "en": "Nice to meet you. I'm here to support your well-being. What brings you here today?",
                "hi": "आपसे मिलकर खुशी हुई। आज आप यहाँ क्यों आए हैं?",
                "mr": "तुमच्याशी भेटून आनंद झाला. आज तुम्ही येथे का आलात?"
            },
            "goodbye": {
                "en": "Take care of yourself. Feel free to come back anytime you need support.",
                "hi": "अपना ख्याल रखिये। जब भी आपको समर्थन की जरूरत हो, बेझिझक वापस आएं।",
                "mr": "स्वतःची काळजी घ्या. जेव्हा तुम्हाला समर्थन आवश्यक असेल तेव्हा परत या."
            },
            "thanks": {
                "en": "Really glad that helped. Take care of yourself.",
                "hi": "खुशी हुई कि मदद हो पाई। अपना ख्याल रखें।",
                "mr": "बरं वाटलं की मदत झाली. स्वतःची काळजी घ्या."
            }
        }

        bot_reply = intent_responses[intent].get(language, intent_responses[intent]["en"])
        response = SupportResponse(
            session_id=session_id,
            bot_reply=bot_reply,
            emotion_used="neutral",
            response_type="conversational",
            language=language,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        update_chat_history(session_id, user_text, bot_reply)
        update_session(session_id, "last_bot_reply", response.model_dump())
        return response

    # ============ STEP 5: GET FUSION EMOTION ============
    fusion_state = session.get("fusion_state", {})
    fusion_emotion = fusion_state.get("value", {}).get("fusion_emotion", "neutral")

    # ============ STEP 6: PHASE-AWARE TECHNIQUE SELECTION ============
    # Read active technique state ONCE at the start of this block
    active_technique = get_active_technique(session)
    active_turn = get_active_technique_turn(session)
    cooldown = get_technique_cooldown(session)

    logger.info(
        f"Step6 entry {session_id}: "
        f"active={'yes:'+active_technique['header'] if active_technique else 'no'}, "
        f"turn={active_turn}, cooldown={cooldown}"
    )

    selected_block = None
    technique_phase = "new"
    topic = "general_support"  # default; overwritten if we do topic classification
    rag_distance = None

    if active_technique:
        if active_turn == 0:
            technique_phase = "new"
            selected_block = active_technique
            topic = "followthrough"
            increment_active_technique_turn(session_id, session)

        elif user_is_confused(user_text):
            # Stay on same technique, explain the CURRENT step more concretely
            technique_phase = "clarifying"
            selected_block = active_technique
            topic = "followthrough"
            # Do NOT increment turn — they haven't moved forward yet

        elif user_is_rejecting(user_text):
            clear_active_technique(session_id)
            set_technique_cooldown(session_id, TECHNIQUE_COOLDOWN_TURNS)
            active_technique = None
            # Now falls through to new-technique logic — this is correct

        elif user_completed_technique(user_text, active_turn):
            technique_phase = "closing"
            selected_block = active_technique
            topic = "followthrough"
            clear_active_technique(session_id)
            set_technique_cooldown(session_id, TECHNIQUE_COOLDOWN_TURNS)

        else:
            technique_phase = "followthrough"
            selected_block = active_technique
            topic = "followthrough"
            increment_active_technique_turn(session_id, session)

    if active_technique is None and technique_phase == "new":
        if user_is_rejecting(user_text):
            # User doesn't want anything — just listen this turn, no technique
            selected_block = None
            technique_phase = "listening"
            logger.info(f"Global rejection detected for {session_id}, skipping RAG")
        elif cooldown > 0:
            selected_block = None
            decrement_technique_cooldown(session_id, session)
            logger.info(f"Technique cooldown active for {session_id}: {cooldown} turns remaining")
        else:
            # Normal new-technique flow
            topic_result = detect_topic_llm(user_text, language)
            topic = topic_result["topic"]
            last_technique = get_last_technique(session)
            selected_block, rag_distance = retrieve_knowledge_block(
                user_text=user_text,
                topic=topic,
                language=language,
                last_technique=last_technique,
            )
            # Count prior exchanges to decide if we should listen first
            prior_exchanges = len(extract_chat_history(session)) // 2  # each exchange = 2 messages

            if selected_block and prior_exchanges == 0:
                # First message in conversation — listen and empathize before suggesting anything
                set_active_technique(session_id, selected_block)   # lock it for next turn
                update_session(session_id, "active_technique_turn", 0)  # not introduced yet
                selected_block = None   # don't pass to LLM this turn
                technique_phase = "listening"  # new phase

    logger.info(
        f"Data extraction for {session_id}: "
        f"topic={topic}, phase={technique_phase}, "
        f"block_header={selected_block['header'] if selected_block else 'None'}, "
        f"rag_distance={rag_distance}, intent={intent}, "
        f"emotion={fusion_emotion}, language={language}"
    )

    # ============ STEP 7: SHORT REPLY COOLDOWN ============
    is_short = should_enforce_short_response(user_text)
    short_count = get_consecutive_short_replies(session)

    if is_short:
        short_count += 1
    else:
        short_count = 0

    disengage_prompt_override = ""
    if short_count >= 3:
        # Too many one-word replies — pause technique and re-engage
        selected_block = None
        technique_phase = "new"  # reset phase so prompt doesn't say "follow-through"
        disengage_prompt_override = (
            "The user has given very short responses several times. "
            "Ask ONE simple, concrete, specific question to gently re-engage them "
            "(e.g. about something they mentioned, or what they're doing today). "
            "Do NOT ask about how they feel about the conversation itself."
        )

    # ============ STEP 8: RESPONSE LENGTH ============
    max_sentences = 2 if is_short else 3

    # ============ STEP 9: EMOTION GUARD ============
    chat_history = extract_chat_history(session)

    TOPIC_EMOTION_GUARD = {
        "sleep": ["tired", "restless", "frustrated", "anxious", "neutral"],
        "stress": ["anxious", "overwhelmed", "frustrated", "neutral"],
        "anxiety": ["fear", "anxious", "nervous", "neutral"],
    }
    if topic in TOPIC_EMOTION_GUARD and fusion_emotion not in TOPIC_EMOTION_GUARD[topic]:
        fusion_emotion = "overwhelmed"

    # ============ STEP 10: GENERATE RESPONSE ============
    last_reply_text = get_last_bot_reply_text(session)
    anti_repeat_instruction = ""
    if last_reply_text and is_short:
        anti_repeat_instruction = (
            f"\n\nCRITICAL: Your previous reply was: \"{last_reply_text[:80]}...\"\n"
            "You MUST NOT repeat or closely paraphrase this. "
            "Respond differently — acknowledge the silence, change approach, "
            "or simply say it's okay not to talk right now."
        )

    # Pass it into generate_response as an addition to disengage_prompt_override:
    if anti_repeat_instruction:
        disengage_prompt_override = (disengage_prompt_override or "") + anti_repeat_instruction
    
    try:
        bot_reply = generate_response(
            user_text=user_text,
            fusion_emotion=fusion_emotion,
            language=language,
            chat_history=chat_history,
            knowledge_block=selected_block,
            max_sentences=max_sentences,
            disengage_prompt_override=disengage_prompt_override,
            technique_phase=technique_phase,
            active_turn=active_turn
        )
    except Exception as e:
        logger.error(f"Response generation failed entirely: {e}")
        fallback_phrases = {
            "en": "I'm here with you. What do you need right now?",
            "hi": "मैं आपके साथ हूं। आपको अभी क्या चाहिए?",
            "mr": "मी तुमच्या सोबत आहे. तुम्हाला आत्ता काय हवं आहे?"
        }
        bot_reply = fallback_phrases.get(language, fallback_phrases["en"])

    # ============ STEP 11: UPDATE SESSION STATE ============
    update_chat_history(session_id, user_text, bot_reply)
    update_consecutive_short_replies(session_id, short_count)

    # Only update last_technique when a genuinely new technique was introduced
    if technique_phase == "new" and selected_block:
        update_last_technique(session_id, selected_block["header"])

    timestamp = datetime.now(timezone.utc).isoformat()
    response = SupportResponse(
        session_id=session_id,
        bot_reply=bot_reply,
        emotion_used=fusion_emotion,
        response_type=f"guided_support_{technique_phase}",
        language=language,
        timestamp=timestamp
    )

    update_session(session_id, "last_bot_reply", response.model_dump())

    logger.info(
        f"Support reply generated for {session_id}: "
        f"topic={topic}, phase={technique_phase}, emotion={fusion_emotion}, lang={language}"
    )

    return response