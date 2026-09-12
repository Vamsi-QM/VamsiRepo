"""Deterministic phone action parsing for Phase 4A."""

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


def parse_phone_action(text: str) -> Optional[PhoneAction]:
    match = _OPEN_PREFIX.match(text or "")
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
