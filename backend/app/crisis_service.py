# app/crisis_service.py
"""
Crisis Handling Module
Purpose:
- Activated ONLY after routing sends user to "crisis"
- Classifies crisis level: MODERATE or HIGH
- Provides appropriate actions:
    - Moderate:  Helpline suggestion + in-app connect button
    - High:      Helpline + emergency contact notification (email-to-SMS)
                 Emergency contact is read directly from users.json
                 (populated at registration — no extra onboarding step needed)
"""

import json
import logging
import smtplib
import os
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.session_state import get_session, update_session

router = APIRouter()
logger = logging.getLogger("crisis_service")
logger.setLevel(logging.INFO)

# users.json lives one level above the app/ package
# crisis_service.py  →  backend/app/crisis_service.py
# users.json         →  backend/users.json
USERS_JSON_PATH = Path(__file__).resolve().parent.parent / "users.json"


# ─────────────────────────── Schemas ───────────────────────────

class CrisisResponse(BaseModel):
    session_id: str
    crisis_level: str            # "moderate" | "high"
    action: str                  # "helpline" | "helpline_and_family"
    reason: str
    notification_sent: bool      # True if emergency contact was actually notified
    notification_channel: str    # "email" | "none"
    timestamp: str


# ─────────────────────── Gmail SMTP config ───────────────────────
# Set these two environment variables (never hard-code credentials):
#
#   ALERT_EMAIL_ADDRESS   – Gmail address that sends the alert
#   ALERT_EMAIL_PASSWORD  – Gmail App Password  <- NOT your login password
#                           Generate at:
#                           Google Account -> Security -> 2-Step Verification
#                           -> App Passwords -> create one for "Mail"
#
SENDER_EMAIL    = os.getenv("ALERT_EMAIL_ADDRESS", "")
SENDER_PASSWORD = os.getenv("ALERT_EMAIL_PASSWORD", "")


# ─────────────────── users.json helpers ──────────────────────────

def _load_users() -> list[dict]:
    """Load all users from users.json. Returns empty list on any error."""
    try:
        with open(USERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("users", [])
    except FileNotFoundError:
        logger.error(f"users.json not found at {USERS_JSON_PATH}")
    except json.JSONDecodeError as exc:
        logger.error(f"users.json is malformed: {exc}")
    return []


def get_emergency_contact(user_id: str) -> Optional[dict]:
    """
    Returns a dict with keys: name, email, relation
    or None if the user / contact is not found.
    """
    for user in _load_users():
        if user.get("id") == user_id:
            name     = user.get("emergency_contact_name", "").strip()
            email    = user.get("emergency_contact_email", "").strip()
            relation = user.get("emergency_contact_relation", "").strip()

            if not name or not email:
                logger.warning(
                    f"User {user_id} has incomplete emergency contact "
                    f"(name={name!r}, email={email!r})"
                )
                return None

            return {"name": name, "email": email, "relation": relation}

    logger.warning(f"User {user_id} not found in users.json")
    return None


# ─────────────────── Notification logic ──────────────────────────

def _build_email_body(contact_name: str, relation: str, crisis_level: str) -> str:
    """
    Build the email body for emergency notification.
    """
    return f"""EMERGENCY ALERT: Crisis Detected

Your {relation} {contact_name} is experiencing a mental health crisis (level: {crisis_level}).

Please check on them immediately and provide support.

Helpline Information:
- iCall: 9152987821
- Vandrevala Foundation: 1860-2662-345
- NIMHANS: 080-46110007

This is an automated notification from ManoMitraAI.
"""


def send_email_notification(
    contact: dict,
    crisis_level: str,
    reason: str,
) -> tuple[bool, str]:
    """
    Sends an email to the emergency contact's email address.
    Returns (success: bool, channel: str).
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.warning(
            "ALERT_EMAIL_ADDRESS / ALERT_EMAIL_PASSWORD not configured — "
            "skipping emergency contact notification"
        )
        return False, "none"

    email   = contact["email"]
    name    = contact["name"]
    relation = contact.get("relation", "contact")
    body    = _build_email_body(name, relation, crisis_level)

    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"EMERGENCY: Crisis Alert for {name}"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [email], msg.as_string())

        logger.info(
            f"Emergency email sent to {email}"
        )
        return True, "email"

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail authentication failed — check ALERT_EMAIL_PASSWORD "
            "(must be an App Password, not your login password)"
        )
        return False, "none"

    except Exception as exc:
        logger.error(
            f"Failed to send emergency email to {email}: {exc}"
        )
        return False, "none"


# ───────────────────────── Crisis logic ──────────────────────────

def classify_crisis(phq9: int, gad7: int, emotion: str) -> tuple[str, str, str]:
    """Returns (crisis_level, action, reason)."""

    if emotion in ("sad", "fear") and phq9 >= 20:
        return "high", "helpline_and_family", "severe_emotional_distress" # "Severe emotional distress with high PHQ-9"

    if phq9 >= 20 or gad7 >= 15:
        return "high", "helpline_and_family", "severe_screening_scores" # "Severe screening scores"

    return "moderate", "helpline", "moderate" # "Moderate psychological distress detected"


# ───────────────────────────── Endpoint ──────────────────────────

@router.post("/handle", response_model=CrisisResponse)
def handle_crisis(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    routing = session.get("routing_decision", {}).get("value")
    if not routing or routing.get("route") != "crisis":
        raise HTTPException(status_code=400, detail="Session is not routed to crisis")

    screening = session.get("screening_result", {}).get("value")
    if not screening:
        raise HTTPException(status_code=400, detail="Screening results missing")

    phq9         = screening.get("phq9_score", 0)
    gad7         = screening.get("gad7_score", 0)
    fusion_state = session.get("fusion_state", {}).get("value", {})
    emotion      = fusion_state.get("fusion_emotion", "neutral")

    # Session must carry the authenticated user's UUID
    # (store this under "user_id" when the user logs in / session is created)
    user_id = session.get("user_id", {}).get("value")

    crisis_level, action, reason = classify_crisis(phq9, gad7, emotion)

    # ── Notification ──────────────────────────────────────────────
    notification_sent    = False
    notification_channel = "none"

    if action == "helpline_and_family":
        if not user_id:
            logger.warning(
                f"action=helpline_and_family but session {session_id} "
                "has no user_id — cannot look up emergency contact"
            )
        else:
            contact = get_emergency_contact(user_id)
            if contact:
                notification_sent, notification_channel = send_email_notification(
                    contact, crisis_level, reason
                )
            else:
                logger.warning(
                    f"No valid emergency contact found for user {user_id}"
                )

    # ── Persist & respond ─────────────────────────────────────────
    result = {
        "crisis_level":         crisis_level,
        "action":               action,
        "reason":               reason,
        "notification_sent":    notification_sent,
        "notification_channel": notification_channel,
        "timestamp":            datetime.now(timezone.utc).isoformat(),
    }
    update_session(session_id, "crisis_state", result)

    logger.info(
        f"Crisis handled | session={session_id} user={user_id} "
        f"level={crisis_level} action={action} "
        f"notified={notification_sent} channel={notification_channel}"
    )

    return CrisisResponse(
        session_id=session_id,
        crisis_level=crisis_level,
        action=action,
        reason=reason,
        notification_sent=notification_sent,
        notification_channel=notification_channel,
        timestamp=result["timestamp"],
    )