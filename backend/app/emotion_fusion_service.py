import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from collections import defaultdict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.session_state import get_session, update_session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter()

# CONFIGURATION

BASE_WEIGHTS = {
    "text": 0.4,
    "voice": 0.3,
    "video": 0.3
}

FRESHNESS_WINDOW = 20  # seconds - emotions older than this are considered stale

# Mapping of session state keys to modality names
MODALITY_KEYS = {
    "text": "text_emotion",
    "voice": "voice_emotion",
    "video": "last_video_emotion"
}

# PYDANTIC MODELS

class ModalityWeight(BaseModel):
    """Weight information for a single modality"""
    base: float = Field(..., description="Base weight for this modality")
    effective: float = Field(..., description="Effective weight after recency adjustment")
    recency_factor: float = Field(..., description="Recency factor (0-1 based on age)")
    age_seconds: Optional[float] = Field(None, description="Age of the emotion data in seconds")


class FusionResponse(BaseModel):
    """Response model for emotion fusion"""
    session_id: str = Field(..., description="Session identifier")
    fusion_emotion: str = Field(..., description="Final fused emotion label")
    confidence: float = Field(..., description="Confidence score for fused emotion (0-1)")
    weights: Dict[str, ModalityWeight] = Field(..., description="Weight details for each modality")
    fusion_method: str = Field(..., description="Method used for fusion")
    timestamp: str = Field(..., description="Timestamp of fusion operation")
    component_emotions: Dict[str, Optional[Dict[str, Any]]] = Field(
        ..., 
        description="Individual emotion predictions from each modality"
    )


class HealthResponse(BaseModel):
    """Health check response for fusion service"""
    status: str = Field(..., description="Service status")
    base_weights: Dict[str, float] = Field(..., description="Base weights configuration")
    freshness_window_seconds: int = Field(..., description="Freshness window in seconds")
    modality_keys: Dict[str, str] = Field(..., description="Session state key mappings")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_recency_factor(age_seconds: float) -> float:
    if age_seconds < 0:
        return 1.0
    return max(0.0, 1.0 - (age_seconds / FRESHNESS_WINDOW))


def get_emotion_age(updated_at_str: str, current_time: datetime) -> float:
    try:
        # Parse the timestamp - session_state.py uses datetime.utcnow().isoformat()
        updated_at = datetime.fromisoformat(updated_at_str)
        
        # Ensure both datetimes are timezone-aware for comparison
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        age = (current_time - updated_at).total_seconds()
        return max(0.0, age)
    except Exception as e:
        logger.error(f"Error calculating emotion age from '{updated_at_str}': {e}")
        return float('inf')  # Treat as very old if parsing fails


def extract_modality_data(
    session_data: Dict[str, Any],
    modality: str,
    current_time: datetime
) -> Optional[Dict[str, Any]]:
    key = MODALITY_KEYS.get(modality)
    if not key or key not in session_data:
        logger.debug(f"Modality '{modality}' (key: {key}) not found in session")
        return None
    
    modality_entry = session_data[key]
    
    # Verify structure: must have 'value' and 'updated_at'
    if not isinstance(modality_entry, dict):
        logger.debug(f"Invalid structure for modality '{modality}': not a dict")
        return None
    
    if "value" not in modality_entry or "updated_at" not in modality_entry:
        logger.debug(f"Missing 'value' or 'updated_at' for modality '{modality}'")
        return None
    
    emotion_value = modality_entry["value"]
    
    # emotion_value should be a dict with 'value' (emotion label) and 'confidence'
    if not isinstance(emotion_value, dict):
        logger.debug(f"Invalid emotion value format for modality '{modality}': not a dict")
        return None
    
    emotion_label = emotion_value.get("value")
    confidence = emotion_value.get("confidence", 0.0)
    
    if not emotion_label:
        logger.debug(f"No emotion label found for modality '{modality}'")
        return None
    
    # Calculate age
    age = get_emotion_age(modality_entry["updated_at"], current_time)
    
    return {
        "emotion": emotion_label,
        "confidence": confidence,
        "age": age,
        "updated_at": modality_entry["updated_at"]
    }


def perform_weighted_fusion(
    modalities_data: Dict[str, Dict[str, Any]],
    current_time: datetime
) -> Dict[str, Any]:
    # Calculate effective weights for each modality
    weights_info = {}
    effective_weights = {}
    
    for modality in ["text", "voice", "video"]:
        base_weight = BASE_WEIGHTS[modality]
        
        if modality not in modalities_data:
            # Missing modality
            weights_info[modality] = ModalityWeight(
                base=base_weight,
                effective=0.0,
                recency_factor=0.0,
                age_seconds=None
            )
            effective_weights[modality] = 0.0
            logger.debug(f"Modality '{modality}' missing - effective weight: 0.0")
        else:
            age = modalities_data[modality]["age"]
            recency_factor = calculate_recency_factor(age)
            effective = base_weight * recency_factor
            
            weights_info[modality] = ModalityWeight(
                base=base_weight,
                effective=effective,
                recency_factor=recency_factor,
                age_seconds=round(age, 2)
            )
            effective_weights[modality] = effective
            
            logger.info(
                f"Modality '{modality}': age={age:.2f}s, "
                f"recency_factor={recency_factor:.2f}, "
                f"effective_weight={effective:.3f}"
            )
    
    # Normalize weights
    total_weight = sum(effective_weights.values())
    
    if total_weight == 0:
        # All modalities are stale or missing
        logger.warning("All modalities are stale or missing")
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "weights": weights_info,
            "method": "no_valid_data",
            "component_emotions": {k: None for k in ["text", "voice", "video"]}
        }
    
    # Normalize weights
    normalized_weights = {k: v / total_weight for k, v in effective_weights.items()}
    
    # Update weights_info with normalized values
    for modality, norm_weight in normalized_weights.items():
        weights_info[modality].effective = round(norm_weight, 3)
    
    logger.info(f"Normalized weights: {normalized_weights}")
    
    # Aggregate emotions by label with weighted confidence
    emotion_scores = defaultdict(float)
    
    for modality, data in modalities_data.items():
        emotion_label = data["emotion"]
        confidence = data["confidence"]
        weight = normalized_weights[modality]
        
        weighted_confidence = confidence * weight
        emotion_scores[emotion_label] += weighted_confidence
        
        logger.debug(
            f"Adding {modality}: {emotion_label} "
            f"(conf={confidence:.2f}, weight={weight:.3f}, "
            f"weighted={weighted_confidence:.3f})"
        )
    
    # Determine fusion method
    num_valid_modalities = sum(1 for w in effective_weights.values() if w > 0)
    
    if num_valid_modalities == 1:
        # Only one modality is valid
        valid_modality = [k for k, v in effective_weights.items() if v > 0][0]
        fusion_method = f"{valid_modality}_only_fallback"
    elif num_valid_modalities == len(BASE_WEIGHTS):
        fusion_method = "weighted_fusion"
    else:
        fusion_method = "partial_fusion"
    
    # Get dominant emotion
    if emotion_scores:
        dominant_emotion = max(emotion_scores.items(), key=lambda x: x[1])
        final_emotion = dominant_emotion[0]
        final_confidence = round(dominant_emotion[1], 3)
    else:
        final_emotion = "neutral"
        final_confidence = 0.0
    
    logger.info(
        f"Fusion complete: emotion={final_emotion}, "
        f"confidence={final_confidence:.3f}, method={fusion_method}"
    )
    
    # Prepare component emotions for response
    component_emotions = {}
    for modality in ["text", "voice", "video"]:
        if modality in modalities_data:
            component_emotions[modality] = {
                "emotion": modalities_data[modality]["emotion"],
                "confidence": modalities_data[modality]["confidence"],
                "age_seconds": modalities_data[modality]["age"]
            }
        else:
            component_emotions[modality] = None
    
    return {
        "emotion": final_emotion,
        "confidence": final_confidence,
        "weights": weights_info,
        "method": fusion_method,
        "component_emotions": component_emotions
    }

# CORE FUSION (callable from orchestrator)
def run_fusion(session_id: str) -> Optional[FusionResponse]:
    """
    Run fusion logic and update fusion_state. Returns FusionResponse or None if session
    missing or no valid modality data (caller can set default fusion_state).
    """
    session_data = get_session(session_id)
    if not session_data:
        logger.debug(f"Session not found or empty: {session_id}")
        return None
    current_time = datetime.now(timezone.utc)
    modalities_data = {}
    for modality in ["text", "voice", "video"]:
        data = extract_modality_data(session_data, modality, current_time)
        if data:
            modalities_data[modality] = data
    if not modalities_data:
        logger.debug(f"No valid emotion data for session: {session_id}")
        return None
    fusion_result = perform_weighted_fusion(modalities_data, current_time)
    response = FusionResponse(
        session_id=session_id,
        fusion_emotion=fusion_result["emotion"],
        confidence=fusion_result["confidence"],
        weights=fusion_result["weights"],
        fusion_method=fusion_result["method"],
        timestamp=current_time.isoformat(),
        component_emotions=fusion_result["component_emotions"],
    )
    update_session(session_id, "fusion_state", response.model_dump())
    logger.info(f"Fusion for {session_id}: {response.fusion_emotion} ({response.fusion_method})")
    return response


# API ENDPOINTS
@router.post(
    "/{session_id}",
    response_model=FusionResponse,
    summary="Fuse emotion predictions",
    description="Fuses text, voice, and video emotion predictions using recency-based weighting"
)
async def fuse_emotions(session_id: str) -> FusionResponse:
    result = run_fusion(session_id)
    if result is None:
        session_data = get_session(session_id)
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found or has no data"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid emotion data available for fusion."
        )
    return result


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns configuration and health status of the fusion service"
)
async def health_check() -> HealthResponse:
    logger.debug("Health check requested")
    
    return HealthResponse(
        status="healthy",
        base_weights=BASE_WEIGHTS,
        freshness_window_seconds=FRESHNESS_WINDOW,
        modality_keys=MODALITY_KEYS
    )

# ADDITIONAL UTILITY ENDPOINTS

@router.get(
    "/{session_id}/status",
    summary="Get fusion status",
    description="Check which modalities are available and their freshness for a session"
)
async def get_fusion_status(session_id: str) -> Dict[str, Any]:
    logger.info(f"Checking fusion status for session: {session_id}")
    
    session_data = get_session(session_id)
    
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found"
        )
    
    current_time = datetime.now(timezone.utc)
    status_info = {}
    
    for modality in ["text", "voice", "video"]:
        data = extract_modality_data(session_data, modality, current_time)
        
        if data:
            is_fresh = data["age"] <= FRESHNESS_WINDOW
            status_info[modality] = {
                "available": True,
                "emotion": data["emotion"],
                "confidence": data["confidence"],
                "age_seconds": round(data["age"], 2),
                "is_fresh": is_fresh,
                "updated_at": data["updated_at"]
            }
        else:
            status_info[modality] = {
                "available": False,
                "emotion": None,
                "confidence": None,
                "age_seconds": None,
                "is_fresh": False,
                "updated_at": None
            }
    
    return {
        "session_id": session_id,
        "modalities": status_info,
        "freshness_window_seconds": FRESHNESS_WINDOW,
        "checked_at": current_time.isoformat()
    }