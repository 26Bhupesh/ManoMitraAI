from fastapi import APIRouter, UploadFile, Form, File, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import numpy as np
import cv2
import tempfile
import base64
import logging
from app.session_state import update_session

router = APIRouter()
logger = logging.getLogger("video_service")

class VideoFrameResponse(BaseModel):
    session_id: str
    face_emotion: Optional[str]
    confidence: float
    detected_at: str

try:
    from deepface import DeepFace
    logger.info("✅ DeepFace imported successfully.")
except Exception as e:
    DeepFace = None
    logger.warning("⚠️ DeepFace not available. Install via `pip install deepface`.")

def decode_base64_image(base64_str: str):
    try:
        img_data = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return None

def analyze_emotion(image_path: str):
    if DeepFace is None:
        raise RuntimeError("DeepFace not available.")
    try:
        analysis = DeepFace.analyze(
            img_path=image_path,
            actions=["emotion"],
            enforce_detection=False
        )
        if isinstance(analysis, list):
            analysis = analysis[0]
        dominant = analysis.get("dominant_emotion")
        confidence = analysis.get("emotion", {}).get(dominant, 0.0)
        confidence = round(confidence / 100, 2)  # Normalize 0–1
        return dominant, confidence
    except Exception:
        return None, 0.0

@router.post("/video_frame", response_model=VideoFrameResponse)
async def process_video_frame(
    request: Request,
    session_id: Optional[str] = Form(None),
    frame: Optional[UploadFile] = File(None),
    frame_base64: Optional[str] = Form(None),
):
    if session_id is None and frame is None and frame_base64 is None:
        try:
            body = await request.json()
            session_id = body.get("session_id")
            frame_base64 = body.get("frame")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request body")

    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    face_emotion, confidence = None, 0.0

    try:
        if frame:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(await frame.read())
                tmp.flush()
                face_emotion, confidence = analyze_emotion(tmp.name)

        elif frame_base64:
            image = decode_base64_image(frame_base64)
            if image is not None:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    cv2.imwrite(tmp.name, image)
                    face_emotion, confidence = analyze_emotion(tmp.name)
            else:
                face_emotion, confidence = None, 0.0
        else:
            raise HTTPException(status_code=400, detail="No frame provided")

        result = VideoFrameResponse(
            session_id=session_id,
            face_emotion=face_emotion,
            confidence=confidence,
            detected_at=datetime.utcnow().isoformat(),
        )

        # Update session only with key emotion
        update_session(
            session_id,
            "last_video_emotion",
            {
                "value": face_emotion,
                "confidence": confidence,
            }
        )
        return result

    except Exception as e:
        logger.exception("Error processing video frame")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def health_check():
    return {"status": "ok", "deepface_loaded": DeepFace is not None}
