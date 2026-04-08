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
    "kill myself", "suicide", "end my life", "end it", "want to die", 
    "hurt myself", "self harm", "no reason to live", "ending it all", 
    "मरने", "आत्महत्या", "संपवून"
}

RELEVANCE_THRESHOLD = 50.0  # Distance threshold for considering a retrieved block relevant (tuned empirically)


# ============ VECTOR RAG (ChromaDB) ============

@lru_cache(maxsize=1)
def _get_support_collection():
    """Persistent Chroma collection with multilingual sentence embeddings."""
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=RAG_EMBEDDING_MODEL
    )
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_collection(name=RAG_COLLECTION_NAME, embedding_function=ef)


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

def detect_crisis_llm(user_text: str) -> bool:
    """
    Uses LLM to detect if the user is in immediate danger (self-harm or suicide).
    Returns True if a crisis is detected.
    """
    prompt = """Analyze the user message for any intent of self-harm, suicide, or deep hopelessness.
Return strictly JSON:
{
  "is_crisis": <boolean>,
  "confidence": <float>
}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": f"{prompt}\n\nUser message: {user_text}"}],
            temperature=0.0,
            max_tokens=40
        )
        result = json.loads(response.choices[0].message.content.strip())
        # Trigger crisis if boolean is true and confidence is reasonably high
        return result.get("is_crisis", False) and result.get("confidence", 0) > 0.7
    except Exception as e:
        logger.error(f"LLM Crisis check failed: {e}")
        # Fallback to keyword check if LLM fails
        return contains_crisis_keywords(user_text)


def detect_topic_llm(user_text: str, language: str = "en") -> dict:
    """
    Classify user message into ONE of the allowed topics using LLM.
    
    Returns: {topic: str, confidence: float}
    Fallback to general_support if invalid or low confidence.
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
        
        # Validate
        if topic not in ALLOWED_TOPICS or confidence < 0.6:
            logger.info(f"Topic validation failed: topic={topic}, conf={confidence}")
            return {"topic": "general_support", "confidence": 0.6}
        
        return {"topic": topic, "confidence": confidence}
    
    except Exception as e:
        logger.error(f"Topic classification failed: {e}")
        return {"topic": "general_support", "confidence": 0.6}


def generate_response(user_text: str, fusion_emotion: str, language: str, 
                      chat_history: list = None, knowledge_block: dict = None, max_sentences: int = 4,
                      disengage_prompt_override: str = None) -> str:
    if chat_history is None:
        chat_history = []
    
    # Mapping for LLM clarity
    lang_map = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
    target_lang = lang_map.get(language, "English")

    # Standardize guidance extraction
    knowledge_str = ""
    if knowledge_block:
        header = knowledge_block.get('header', '')
        body = knowledge_block.get('content') or knowledge_block.get('body') or ""
        knowledge_str = f"Technique: {header}\nSteps: {body}"
    
    # SYSTEM PROMPT: Dynamic and Persona-focused
    # The language rule is now dynamic to prevent the 'English-exclusion' bug.
    system_prompt = f"""You are 'ManoMitra', a compassionate and grounded mental health assistant. 
Your goal is to provide a safe space and practical coping tools.

CORE INSTRUCTIONS:
1. LANGUAGE: Respond strictly and exclusively in {target_lang}. 
2. STRUCTURE: 
   - Start with a brief, warm validation of the user's '{fusion_emotion}' emotion.
   - If 'Guidance' is provided below, explain it simply.
   - End with a supportive closing or a gentle question to keep the conversation open.
3. CONSTRAINTS: 
   - Length: Not more than {max_sentences} sentences. 
   - Tone: Empathetic, non-clinical, and calm.
   - Safety: No medical diagnoses or prescriptions.
4. STYLE: Use natural, spoken {target_lang}. Avoid overly formal or robotic "textbook" phrasing."""

    user_prompt = f"""[Context]
User Emotion: {fusion_emotion}
Target Language: {target_lang}

[Recent History]
{chat_history[-3:]}

[Guidance to Incorporate]
{knowledge_str or disengage_prompt_override or "No specific technique today. Focus on active listening and emotional support."}

[Action]
Write around {max_sentences} sentence supportive response in {target_lang}:"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",# if language == "mr" or language == "hi" else "llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5, # Balanced for creativity and consistency
            max_tokens=450,   # Safe buffer for Devanagari scripts
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
    """
    Lightweight intent detection for greeting, introduction, goodbye.
    Returns: 'greeting', 'introduction', 'goodbye', or None
    """
    text_lower = text.lower().strip()
    
    # Greeting patterns
    greeting_patterns = r'\b(hi|hello|hey|namaste|thanks|thank you)\b'
    if re.search(greeting_patterns, text_lower):
        return "greeting"
    
    # Introduction patterns
    intro_patterns = r"(?i)^\s*(?:i'm|i am|my name is|call me)\b\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)([.!]*)$"
    if re.search(intro_patterns, text_lower):
        return "introduction"
    
    # Goodbye patterns
    goodbye_patterns = r'\b(bye|goodbye|farewell|take care|see you|gotta go)\b'
    if re.search(goodbye_patterns, text_lower):
        return "goodbye"
    
    return None


def should_enforce_short_response(user_text: str) -> bool:
    """Check if user message is short (≤4 words)."""
    return len(user_text.split()) <= 4


def get_language_from_session(session: dict) -> str:
    """Get detected language from session, default to English."""
    return session.get("last_preprocess", {}).get("value", {}).get("language", "en")


def extract_chat_history(session: dict) -> list:
    """Extract chat history from session."""
    history = session.get("chat_history", {}).get("value", [])
    return history if isinstance(history, list) else []


def update_chat_history(session_id: str, user_text: str, bot_reply: str):
    """Add exchange to chat history, keep last 6."""
    history = extract_chat_history(get_session(session_id))
    
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": bot_reply})
    
    # Keep only last 6 exchanges (12 messages)
    if len(history) > 12:
        history = history[-12:]
    
    update_session(session_id, "chat_history", history)


def handle_language_switch(text: str, session_id: str) -> str:
    """
    Check if text contains explicit language switch command.
    Format: /lang en, /language hi, /lang mr
    Returns: language code if match found, None otherwise
    """
    match = re.match(r'^/lang(?:uage)?\s+(en|hi|mr)\s*$', text.strip(), re.IGNORECASE)
    if match:
        lang = match.group(1).lower()
        return lang
    return None


def get_last_technique(session: dict) -> str:
    """Get the last technique used from session."""
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


# ============ MAIN ENDPOINT ============

@router.post("/respond", response_model=SupportResponse)
def generate_support_response(req: SupportRequest):
    """
    Main support response generation endpoint.
    Implements V2 logic with topic classification, context awareness, and technique tracking.
    """
    session_id = req.session_id
    user_text = req.user_text.strip()

    if not user_text:
        raise fastapi.HTTPException(status_code=400, detail="Empty user_text")

    session = get_session(session_id)
    if not session:
        raise fastapi.HTTPException(status_code=404, detail="Session not found")

    # Get language
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
            bot_reply=(
                "I'm really glad you shared this with me. "
                "Before we go further, it would help me understand how best to support you "
                "if you could answer a few short questions. "
                "They're called PHQ-9 and GAD-7, and they help measure stress and low mood."
            ),
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
        response_text = {
            "en": f"Language switched to English.",
            "hi": f"भाषा हिंदी में बदल दी गई है।",
            "mr": f"भाषा मराठीत बदली गेली आहे."
        }.get(language, "Language switched.")
        
        bot_reply = response_text
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
    intent = detect_intent(user_text)
    if intent:
        # For greetings, introductions, goodbyes - brief conversational response only
        intent_responses = {
            "greeting": {
                "en": "Hello! I'm here to listen and support you. How are you feeling today?",
                "hi": "नमस्ते! मैं आपकी सुनने और समर्थन करने के लिए यहाँ हूँ। आप आज कैसा महसूस कर रहे हैं?",
                "mr": "नमस्कार! मैं तुमची ऐकण्यास आणि समर्थन करण्यास येथे आहे. तुम्ही आज कसा महसूस करत आहात?"
            },
            "introduction": {
                "en": "Nice to meet you. I'm here to support your well-being. What brings you here today?",
                "hi": "आपसे मिलकर खुशी हुई। मैं आपके कल्याण के लिए यहाँ हूँ। आज आप यहाँ क्यों आए हैं?",
                "mr": "तुमच्या मिळण्यास आनंद झाला. मैं तुमच्या कल्याणासाठी येथे आहे. आज तुम्ही येथे का आहात?"
            },
            "goodbye": {
                "en": "Take care of yourself. Feel free to come back anytime you need support.",
                "hi": "अपना ख्याल रखिये। जब भी आपको समर्थन की जरूरत हो, बेझिझक वापस आएं।",
                "mr": "अपनी काळजी घ्या. जेव्हा तुम्हाला समर्थन आवश्यक असेल तेव्हा परत या."
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
        
        # Update history
        update_chat_history(session_id, user_text, bot_reply)
        update_session(session_id, "last_bot_reply", response.model_dump())
        
        return response

    # ============ STEP 5: GET FUSION EMOTION ============
    fusion_state = session.get("fusion_state", {})
    fusion_emotion = fusion_state.get("value", {}).get("fusion_emotion", "neutral")

    # ============ STEP 6: TOPIC CLASSIFICATION ============
    topic_result = detect_topic_llm(user_text, language)
    topic = topic_result["topic"]

    # ============ STEP 7–8: VECTOR RETRIEVAL (ChromaDB) ============
    last_technique = get_last_technique(session)
    selected_block, rag_distance = retrieve_knowledge_block(
        user_text=user_text,
        topic=topic,
        language=language,
        last_technique=last_technique,
    )

    # Testing data extraction: topic, block_header, RAG distance, intent, emotion, language
    logger.info(
        f"Data extraction for {session_id}: "
        f"topic={topic}, block_header={selected_block['header'] if selected_block else 'None'}, "
        f"block_used={selected_block['content'] if selected_block else 'None'},"
        f"rag_distance={rag_distance}, intent={intent}, "
        f"emotion={fusion_emotion}, language={language}"
    )


    # ============ STEP 9: CHECK SHORT REPLY COOLDOWN ============
    is_short = should_enforce_short_response(user_text)
    short_count = get_consecutive_short_replies(session)
    
    if is_short:
        short_count += 1
    else:
        short_count = 0
    
    # If 3 consecutive short replies, ask open-ended question instead
    disengage_prompt_override = ""
    if short_count >= 3:
        selected_block = None  # Skip technique
        disengage_prompt_override = (
            "The user has given very short responses several times. "
            "Ask ONE simple, concrete, specific question to gently re-engage them "
            "(e.g. about something they mentioned, or what they're doing today). "
            "Do NOT ask about how they feel about the conversation itself."
        )
        # Will trigger open-ended prompt in generate_response

    # ============ STEP 10: RESPONSE LENGTH ENFORCEMENT ============
    max_sentences = 2 if is_short else 4

    # ============ STEP 11: GENERATE RESPONSE ============
    chat_history = extract_chat_history(session)
    
    TOPIC_EMOTION_GUARD = {
        "sleep": ["tired", "restless", "frustrated", "anxious", "neutral"],
        "stress": ["anxious", "overwhelmed", "frustrated", "neutral"],
        "anxiety": ["fear", "anxious", "nervous", "neutral"],
    }
    # If emotion seems mismatched, soften the label
    if topic in TOPIC_EMOTION_GUARD and fusion_emotion not in TOPIC_EMOTION_GUARD[topic]:
        fusion_emotion = "overwhelmed"  # safe fallback

    try:
        bot_reply = generate_response(
            user_text=user_text,
            fusion_emotion=fusion_emotion,
            language=language,
            chat_history=chat_history,
            knowledge_block=selected_block,
            max_sentences=max_sentences,
            disengage_prompt_override=disengage_prompt_override
        )
    except Exception as e:
        logger.error(f"Response generation failed entirely: {e}")
        # Fallback response
        fallback_phrases = {
            "en": "I'm here with you. What do you need right now?",
            "hi": "मैं आपके साथ हूं। आपको अभी क्या चाहिए?",
            "mr": "मी तुमच्या सोबत आहे. तुम्हाला आत्ता काय हवं आहे?"
        }
        bot_reply = fallback_phrases.get(language, fallback_phrases["en"])

    # ============ STEP 12: UPDATE SESSION STATE ============
    update_chat_history(session_id, user_text, bot_reply)
    update_consecutive_short_replies(session_id, short_count)
    
    if selected_block:
        update_last_technique(session_id, selected_block["header"])

    timestamp = datetime.now(timezone.utc).isoformat()
    response = SupportResponse(
        session_id=session_id,
        bot_reply=bot_reply,
        emotion_used=fusion_emotion,
        response_type="guided_support",
        language=language,
        timestamp=timestamp
    )

    update_session(session_id, "last_bot_reply", response.model_dump())

    logger.info(
        f"Support reply generated for {session_id}: "
        f"topic={topic}, emotion={fusion_emotion}, lang={language}"
    )

    return response
