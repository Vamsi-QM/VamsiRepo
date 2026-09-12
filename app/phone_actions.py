"""Deterministic phone action parsing for Phase 4 phone features."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PhoneAction:
    reply: str
    action: dict


_APP_ALIASES = {
    "whatsapp": {
        "label": "WhatsApp",
        "packages": ["com.whatsapp", "com.whatsapp.w4b"],
    },
    "whatsapp business": {
        "label": "WhatsApp Business",
        "packages": ["com.whatsapp.w4b", "com.whatsapp"],
    },
    "youtube": {
        "label": "YouTube",
        "packages": ["com.google.android.youtube"],
    },
    "chrome": {
        "label": "Chrome",
        "packages": ["com.android.chrome"],
    },
    "google": {
        "label": "Google",
        "packages": ["com.google.android.googlequicksearchbox", "com.android.chrome"],
    },
    "phone": {
        "label": "Phone",
        "packages": ["com.google.android.dialer", "com.android.dialer", "com.coloros.dialer"],
        "intent": "dialer",
    },
    "dialer": {
        "label": "Phone",
        "packages": ["com.google.android.dialer", "com.android.dialer", "com.coloros.dialer"],
        "intent": "dialer",
    },
    "settings": {
        "label": "Settings",
        "packages": ["com.android.settings"],
        "intent": "settings",
    },
    "play store": {
        "label": "Play Store",
        "packages": ["com.android.vending"],
        "intent": "play_store",
    },
    "store": {
        "label": "Play Store",
        "packages": ["com.android.vending"],
        "intent": "play_store",
    },
}

_OPEN_PREFIX = re.compile(
    r"^\s*(?:hey\s+bro\s+|bro\s+|please\s+|pls\s+)?(?:open|launch|start)\s+(?:my\s+)?(.+?)\s*$",
    re.I,
)

_NOTIFICATION_PATTERNS = [
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:any|read|show|check|tell\s+me)(?:\s+my)?\s+notifications?\s*(?:bro)?\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:who\s+messaged\s+me|any\s+messages?)\s*(?:bro)?\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:read|show|check|tell\s+me)(?:\s+my)?\s+(?:latest|last|recent)?\s*whatsapp\s+(?:message|notification)s?\s*(?:bro)?\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:any|read|show|check)(?:\s+my)?\s+whatsapp\s+(?:message|notification)s?\s*(?:bro)?\s*$", re.I),
]


def _normalize_command(text: str) -> str:
    normalized = (text or "").strip().lower()
    normalized = re.sub(r"[?!.,]+$", "", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _parse_notification_action(text: str) -> Optional[PhoneAction]:
    normalized = _normalize_command(text)
    if not normalized:
        return None
    if not any(pattern.match(normalized) for pattern in _NOTIFICATION_PATTERNS):
        return None
    app = "whatsapp" if "whatsapp" in normalized or "message" in normalized or "messaged" in normalized else ""
    label = "WhatsApp notifications" if app == "whatsapp" else "notifications"
    return PhoneAction(
        reply=f"Checking your {label} bro.",
        action={
            "type": "read_notifications",
            "app": app,
            "label": label,
            "limit": 5,
        },
    )


def parse_phone_action(text: str) -> Optional[PhoneAction]:
    normalized = _normalize_command(text)
    notification_action = _parse_notification_action(normalized)
    if notification_action is not None:
        return notification_action
    match = _OPEN_PREFIX.match(normalized)
    if not match:
        return None
    requested = re.sub(r"\b(app|application)\b", "", match.group(1).strip(), flags=re.I).strip().lower()
    requested = re.sub(r"\s+", " ", requested)
    if requested.startswith("the "):
        requested = requested[4:]
    app = _APP_ALIASES.get(requested)
    if not app:
        known = ", ".join(sorted({v["label"] for v in _APP_ALIASES.values()}))
        return PhoneAction(
            reply=f"I can open only these apps right now: {known}.",
            action={"type": "unsupported_open_app", "requested": requested},
        )
    label = app["label"]
    return PhoneAction(
        reply=f"Opening {label} bro.",
        action={
            "type": "open_app",
            "app": requested,
            "label": label,
            "packages": app["packages"],
            "intent": app.get("intent", "launch"),
        },
    )
