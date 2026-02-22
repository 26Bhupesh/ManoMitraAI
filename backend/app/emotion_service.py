from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit.processor import IndicProcessor
from langdetect import detect
import torch
import logging
import traceback
from app.session_state import update_session
from datetime import datetime

router = APIRouter()

# ---------------- Logging ----------------
logger = logging.getLogger("emotion_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(ch)

# ---------------- Model setup ----------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 🔹 English emotion classifier
EMOTION_MODEL_NAME = "j-hartmann/emotion-english-distilroberta-base"
emotion_analyzer = pipeline(
    "text-classification",
    model=EMOTION_MODEL_NAME,
    device=0 if DEVICE == "cuda" else -1
)

# 🔹 IndicTrans2 Model (Hindi/Marathi → English)
TRANS_MODEL_NAME = "ai4bharat/indictrans2-indic-en-dist-200M"

trans_tokenizer = AutoTokenizer.from_pretrained(TRANS_MODEL_NAME, trust_remote_code=True)
trans_model = AutoModelForSeq2SeqLM.from_pretrained(
    TRANS_MODEL_NAME,
    trust_remote_code=True,
    attn_implementation="eager"  # CPU-safe
).to("cpu")

ip = IndicProcessor(inference=True)

# ---------------- Schemas ----------------
class EmotionTextRequest(BaseModel):
    session_id: str
    text: str

class EmotionResponse(BaseModel):
    session_id: str
    text_emotion: str
    confidence: float

# ---------------- Helpers ----------------
def safe_detect_language(text: str) -> str:
    try:
        return detect(text)
    except Exception as e:
        logger.warning("Language detection failed: %s", e)
        return "unknown"

def translate_hi_mr_to_en(text: str, lang_code: str) -> str:
    """Translate Hindi/Marathi → English using IndicTrans2."""
    if lang_code not in ("hi", "mr"):
        return text

    src_lang = "hin_Deva" if lang_code == "hi" else "mar_Deva"
    tgt_lang = "eng_Latn"
    text = text.strip()

    if not text:
        raise ValueError("Empty text")

    logger.info(f"Translating {src_lang} → {tgt_lang}")

    batch = ip.preprocess_batch([text], src_lang=src_lang, tgt_lang=tgt_lang)
    inputs = trans_tokenizer(
        batch,
        return_tensors="pt",
        truncation=True,
        padding="longest",
        return_attention_mask=True,
    ).to("cpu")

    with torch.no_grad():
        generated_tokens = trans_model.generate(
            **inputs,
            use_cache=False,
            num_beams=3,
            max_length=256,
            do_sample=False,
        )

    decoded = trans_tokenizer.batch_decode(
        generated_tokens,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )

    translations = ip.postprocess_batch(decoded, lang=tgt_lang)
    if not translations or not translations[0]:
        raise RuntimeError("Empty translation output")

    translated_text = translations[0]
    logger.info(f"Translation OK: {text[:25]} → {translated_text[:25]}")
    return translated_text

# ---------------- Endpoint ----------------
@router.post("/text", response_model=EmotionResponse)
def analyze_text_emotion(req: EmotionTextRequest):
    session_id = req.session_id
    original_text = req.text or ""

    lang = safe_detect_language(original_text)
    logger.info(f"Session={session_id} detected_language={lang}")

    translated = original_text
    if lang in ("hi", "mr"):
        try:
            translated = translate_hi_mr_to_en(original_text, lang)
        except Exception as e:
            logger.warning(f"Translation failed for session={session_id}: {e}\n{traceback.format_exc()}")

    try:
        result = emotion_analyzer(translated)[0]
        emotion = result.get("label", "unknown")
        confidence = round(float(result.get("score", 0.0)), 2)  # ✅ Rounded to 2 decimals
        logger.info(f"Session={session_id} Emotion={emotion} Confidence={confidence}")
    except Exception as e:
        logger.exception("Emotion model inference failed")
        raise HTTPException(status_code=500, detail=f"Emotion inference failed: {e}")

    try:
        update_session(
            session_id,
            "text_emotion",
            {
                "value": emotion,
                "confidence": confidence,
            }
        )
        logger.info(f"Session store updated for {session_id} (text_emotion={emotion})")
    except Exception as e:
        logger.warning(f"Session store update failed for {session_id}: {e}")
        
    return {
        "session_id": session_id,
        "text_emotion": emotion,
        "confidence": confidence,
    }

@router.get("/health")
def health():
    return {
        "status": "ok",
        "translation_model": TRANS_MODEL_NAME,
        "emotion_model": EMOTION_MODEL_NAME
    }
