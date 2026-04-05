import logging
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import fastapi
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

BASE_PATH = Path(__file__).parent / "knowledge"

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
    "kill myself",
    "suicide",
    "end my life",
    "ending my life",
    "no reason to live",
    "hurt myself",
    "self harm",
    "die"
}


# ============ KNOWLEDGE FILE OPERATIONS ============

def load_topic_blocks(filename: str) -> list[dict]:
    """
    Load and parse topic knowledge file.
    Splits by '---' separator.
    Returns list of {header, body} dicts.
    """
    path = BASE_PATH / filename
    if not path.exists():
        logger.warning(f"Knowledge file missing: {filename}")
        return []

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read knowledge file {filename}: {e}")
        return []
    
    blocks = []
    for block_text in content.split("---"):
        block_text = block_text.strip()
        if not block_text:
            continue
        
        lines = block_text.splitlines()
        if len(lines) < 2:
            continue
        
        header = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        
        blocks.append({
            "header": header,
            "body": body
        })
    
    return blocks


# ============ LLM FUNCTIONS ============

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


def score_block_relevance(block_body: str, user_text: str) -> float:
    """
    Score block relevance to user text using LLM.
    Returns score 0-5.
    """
    escaped_user = user_text.replace('"', '\\"')
    escaped_block = block_body[:500].replace('"', '\\"')
    
    prompt = f"""Rate relevance from 0 to 5.
User: "{escaped_user}"
Guidance: "{escaped_block}"
Return only a number."""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0.0,
            max_tokens=5
        )
        
        score_text = response.choices[0].message.content.strip()
        score = float(score_text)
        return max(0, min(5, score))  # Clamp to 0-5
    
    except Exception as e:
        logger.error(f"Block scoring failed: {e}")
        return 0


def generate_response(user_text: str, fusion_emotion: str, language: str, 
                     chat_history: list = None, knowledge_block: dict = None,
                     max_sentences: int = 4) -> str:
    """
    Generate contextual response using LLM.
    Uses chat history, emotion, and optional knowledge block.
    Max 4 sentences.
    """
    if chat_history is None:
        chat_history = []
    
    # Format chat history for prompt
    history_str = ""
    for msg in chat_history[-6:]:  # Last 6 exchanges
        role = msg.get("role", "").title()
        content = msg.get("content", "")
        if role and content:
            history_str += f"{role}: {content}\n"
    
    knowledge_str = ""
    if knowledge_block:
        knowledge_str = f"Header: {knowledge_block.get('header', '')}\nGuidance: {knowledge_block.get('body', '')}"
    
    # Build system prompt
    system_prompt = f"""You are an empathetic mental health support assistant.

Rules:
- If greeting or casual, respond briefly.
- If distressed, validate briefly first.
- Use guidance only if relevant.
- Suggest at most ONE technique.
- Do NOT repeat previous techniques.
- Keep response under 4 sentences.
- Avoid excessive generic empathy.
- No diagnoses.
- No medication suggestions.
- Respond strictly in {language}."""
    
    user_prompt = f"""Conversation history:
{history_str or "(New conversation)"}

User emotion: {fusion_emotion}

Selected guidance:
{knowledge_str or "(No specific technique)"}

Generate supportive response:"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,
            max_tokens=90
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        # Fallback response in user's language
        fallback_phrases = {
            "en": "I'm here with you. What's on your mind?",
            "hi": "मैं आपके साथ हूं। आप क्या सोच रहे हैं?",
            "mr": "मी तुमच्या सोबत आहे. तुमचे काय विचार आहे?"
        }
        return fallback_phrases.get(language, fallback_phrases["en"])


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
    greeting_patterns = r'\b(hi|hello|hey|namaste|howdy|thanks|thank you)\b'
    if re.search(greeting_patterns, text_lower):
        return "greeting"
    
    # Introduction patterns
    intro_patterns = r"(i'm|i am|my name is|call me)"
    if re.search(intro_patterns, text_lower):
        return "introduction"
    
    # Goodbye patterns
    goodbye_patterns = r'\b(bye|goodbye|farewell|take care|see you|gotta go)\b'
    if re.search(goodbye_patterns, text_lower):
        return "goodbye"
    
    return None


def should_enforce_short_response(user_text: str) -> bool:
    """Check if user message is short (≤3 words)."""
    return len(user_text.split()) <= 3


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

    # ============ STEP 7: LOAD TOPIC KNOWLEDGE FILE ============
    filename = f"{topic}_{language}.txt"
    blocks = load_topic_blocks(filename)
    
    if not blocks:
        # Fallback to English if language variant not found
        filename = f"{topic}_en.txt"
        blocks = load_topic_blocks(filename)

    # ============ STEP 8: SCORE BLOCKS & SELECT ============
    selected_block = None
    last_technique = get_last_technique(session)
    block_scored = None
    
    if blocks:
        scored_blocks = []
        for block in blocks:
            score = score_block_relevance(block["body"], user_text)
            scored_blocks.append((score, block))
        
        # Sort by score descending
        scored_blocks.sort(key=lambda x: x[0], reverse=True)
        
        # Pick highest scoring block if >= 3
        if scored_blocks[0][0] >= 3:
            candidate = scored_blocks[0][1]
            block_scored = scored_blocks[0][0]
            
            # Check if equals last technique
            if candidate["header"] == last_technique:
                # Pick next highest
                if len(scored_blocks) > 1 and scored_blocks[1][0] >= 3:
                    selected_block = scored_blocks[1][1]
                    block_scored = scored_blocks[1][0]
            else:
                selected_block = candidate


    # Testing data extraction: topic, block_header, block_score, intent, emotion, language
    logger.info(
        f"Data extraction for {session_id}: "
        f"topic={topic}, block_header={selected_block['header'] if selected_block else 'None'}, "
        f"block_used={selected_block['body'] if selected_block else 'None'},"
        f"block_score={block_scored}, intent={intent}, "
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
    if short_count >= 3:
        selected_block = None  # Skip technique
        # Will trigger open-ended prompt in generate_response

    # ============ STEP 10: RESPONSE LENGTH ENFORCEMENT ============
    max_sentences = 2 if is_short else 4

    # ============ STEP 11: GENERATE RESPONSE ============
    chat_history = extract_chat_history(session)
    
    try:
        bot_reply = generate_response(
            user_text=user_text,
            fusion_emotion=fusion_emotion,
            language=language,
            chat_history=chat_history,
            knowledge_block=selected_block,
            max_sentences=max_sentences
        )
    except Exception as e:
        logger.error(f"Response generation failed entirely: {e}")
        # Fallback response
        fallback_phrases = {
            "en": "I'm here with you. What do you need right now?",
            "hi": "मैं आपके साथ हूं। आपको अभी क्या चाहिए?",
            "mr": "मी तुमच्या सोबत आहे. तुम्हाला अभी काय चाहिए?"
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
