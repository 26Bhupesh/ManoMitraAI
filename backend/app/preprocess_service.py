from fastapi import APIRouter, UploadFile, Form, File, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os
import tempfile
import numpy as np
import librosa
import soundfile as sf
from faster_whisper import WhisperModel
import fasttext
from pydub import AudioSegment
from app.session_state import update_session

router = APIRouter()

# ---------------- Models ----------------
class PreprocessResponse(BaseModel):
    session_id: str
    language: str
    clean_text: Optional[str] = None
    transcript: Optional[str] = None
    voice_features: Optional[dict] = None

# ---------------- Setup ----------------
FASTTEXT_MODEL = "lid.176.bin"

if not os.path.exists(FASTTEXT_MODEL):
    import urllib.request
    print("Downloading FastText model...")
    urllib.request.urlretrieve(
        "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin",
        FASTTEXT_MODEL,
    )

language_model = fasttext.load_model(FASTTEXT_MODEL)
whisper_model = WhisperModel("base", device="cpu")

# ---------------- Helpers ----------------
def detect_language(text: str) -> str:
    try:
        pred = language_model.predict(text)
        return pred[0][0].replace("__label__", "")
    except Exception:
        return "unknown"

def extract_features(audio_path: str) -> dict:
    try:
        y, sr = librosa.load(audio_path, sr=16000)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13).mean(axis=1).tolist()
        rms = float(np.mean(librosa.feature.rms(y=y)))
        duration = float(librosa.get_duration(y=y, sr=sr))
        return {"mfcc_mean": mfcc, "rms_mean": rms, "duration_secs": duration}
    except Exception:
        return {}

def convert_to_wav(upload: UploadFile) -> str:
    """Convert any audio file to 16kHz mono WAV"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        audio = AudioSegment.from_file(upload.file)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(tmp_wav.name, format="wav")
        return tmp_wav.name


def convert_file_to_wav(input_path: str) -> str:
    """Convert an audio file at path to 16kHz mono WAV. Returns path to temp WAV."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(tmp_wav.name, format="wav")
        return tmp_wav.name


def run_preprocess(
    session_id: str,
    *,
    text: Optional[str] = None,
    audio_path: Optional[str] = None,
) -> PreprocessResponse:
    """
    Core preprocess logic: text branch (clean text + language) or audio branch (transcript + language + voice_features).
    Callable from orchestrator. Exactly one of text or audio_path must be set.
    """
    if (text is None) == (audio_path is None):
        raise ValueError("Exactly one of text or audio_path must be provided")

    language = "unknown"
    transcript = None
    voice_features = None
    clean_text = None

    if text:
        clean_text = text.strip()
        language = detect_language(clean_text)
        update_session(session_id, "text_input", clean_text)
    else:
        wav_path = convert_file_to_wav(audio_path)
        try:
            segments, _ = whisper_model.transcribe(wav_path)
            transcript = " ".join([seg.text.strip() for seg in segments])
            language = detect_language(transcript)
            voice_features = extract_features(wav_path)
            update_session(session_id, "audio_transcript", transcript)
            update_session(session_id, "audio_features", voice_features)
        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass

    result = PreprocessResponse(
        session_id=session_id,
        language=language,
        clean_text=clean_text,
        transcript=transcript,
        voice_features=voice_features,
    )
    update_session(session_id, "last_preprocess", result.model_dump())
    return result


# ---------------- Route ----------------
@router.post("/preprocess", response_model=PreprocessResponse)
async def preprocess_input(
    request: Request,
    session_id: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
):
    # ---- JSON fallback ----
    if session_id is None and text is None and audio is None:
        try:
            body = await request.json()
            session_id = body.get("session_id")
            text = body.get("text")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request body")

    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    if text:
        return run_preprocess(session_id, text=text)
    if audio:
        wav_path = convert_to_wav(audio)
        try:
            return run_preprocess(session_id, audio_path=wav_path)
        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass
    raise HTTPException(status_code=400, detail="Provide text or audio")
