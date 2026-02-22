import os
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from transformers import pipeline
from pydub import AudioSegment
from app.session_state import update_session
from datetime import datetime

# ---------------- Router & Logging ----------------
router = APIRouter()
logger = logging.getLogger("emotion_voice_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(ch)

# ---------------- Model config / cache ----------------
MODEL_NAME = "superb/wav2vec2-base-superb-er"

# Pipeline cache (load once)
_emotion_audio_pipeline = None
_model_loaded = False

def get_audio_pipeline():
    """
    Lazy-load the audio-classification pipeline and return it.
    Uses GPU if available (torch.cuda.is_available()).
    """
    global _emotion_audio_pipeline, _model_loaded
    if _emotion_audio_pipeline is None:
        try:
            import torch
            device = 0 if torch.cuda.is_available() else -1
        except Exception:
            device = -1

        logger.info("Loading audio classification pipeline for model: %s (device=%s)", MODEL_NAME, device)
        try:
            _emotion_audio_pipeline = pipeline("audio-classification", model=MODEL_NAME, device=device)
            _model_loaded = True
            logger.info("Audio emotion pipeline loaded successfully.")
        except Exception as e:
            logger.exception("Failed to load audio pipeline: %s", e)
            raise
    return _emotion_audio_pipeline

# ---------------- Request / Response models ----------------
class VoiceEmotionRequest(BaseModel):
    session_id: str

class VoiceEmotionResponse(BaseModel):
    session_id: str
    voice_emotion: str
    confidence: float

# ---------------- Label Mapping ----------------
LABEL_MAP = {
    "ang": "angry",
    "hap": "happy",
    "sad": "sad",
    "neu": "neutral",
}

# ---------------- Helpers ----------------
def convert_path_to_16k_mono_wav(input_path: str) -> str:
    """
    Convert an audio file at path to 16kHz mono WAV.
    Returns path to temp WAV file (caller must remove).
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(input_path)[-1] or ".wav") as tmp_in:
        with open(input_path, "rb") as f:
            tmp_in.write(f.read())
        tmp_in.flush()
        tmp_in_path = tmp_in.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_out:
        tmp_out_path = tmp_out.name
    audio = AudioSegment.from_file(tmp_in_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(tmp_out_path, format="wav")
    try:
        os.remove(tmp_in_path)
    except Exception:
        pass
    return tmp_out_path


def convert_to_16k_mono_wav(upload_file: UploadFile) -> str:
    """
    Convert an UploadFile (any reasonable audio format) into a 16kHz mono WAV file.
    Returns the path to the temp WAV file (caller must remove it).
    Uses pydub (ffmpeg recommended for many formats).
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(upload_file.filename or "")[-1] or ".wav") as tmp_in:
            tmp_in.write(upload_file.file.read())
            tmp_in.flush()
            tmp_in_path = tmp_in.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_out:
            tmp_out_path = tmp_out.name

        audio = AudioSegment.from_file(tmp_in_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(tmp_out_path, format="wav")

        try:
            os.remove(tmp_in_path)
        except Exception:
            pass

        return tmp_out_path

    except Exception as e:
        logger.exception("Audio conversion failed: %s", e)
        raise


def run_voice_emotion(session_id: str, audio_path: str) -> dict:
    """
    Core voice emotion logic: convert path to wav, run model, update session.
    Callable from orchestrator. Returns dict with session_id, voice_emotion, confidence.
    """
    wav_path = convert_path_to_16k_mono_wav(audio_path)
    try:
        pipeline_model = get_audio_pipeline()
        predictions = pipeline_model(wav_path, top_k=1)
        if not predictions:
            raise RuntimeError("No predictions returned by model")
        pred = predictions[0]
        if isinstance(pred, list):
            pred = pred[0]
        label = pred.get("label")
        score = round(float(pred.get("score", 0.0)), 2)
        label = LABEL_MAP.get(label.lower(), label) if label else "unknown"
    finally:
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass
    result = {
        "session_id": session_id,
        "voice_emotion": label or "unknown",
        "confidence": score,
    }
    update_session(
        session_id,
        "voice_emotion",
        {"value": result["voice_emotion"], "confidence": result["confidence"]},
    )
    logger.info("Session=%s VoiceEmotion=%s Confidence=%.2f", session_id, label, score)
    return result


# ---------------- Endpoints ----------------
@router.post("/voice", response_model=VoiceEmotionResponse)
async def analyze_voice_emotion(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    Accepts multipart/form-data:
      - session_id: str
      - audio: file (wav/m4a/mp3/...)
    Returns: JSON with predicted emotion and confidence (0..1 rounded to 2 decimals)
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    if not audio:
        raise HTTPException(status_code=400, detail="Missing audio file")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename or "")[-1] or ".wav") as tmp:
            tmp.write(await audio.read())
            tmp.flush()
            tmp_path = tmp.name
        try:
            return run_voice_emotion(session_id, tmp_path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        logger.exception("Voice emotion failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def health():
    """Return model status"""
    loaded = bool(_model_loaded)
    return {
        "status": "ok" if loaded else "loading",
        "model_name": MODEL_NAME,
        "loaded": loaded,
    }
