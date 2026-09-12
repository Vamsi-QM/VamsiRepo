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

_LIST_WHATSAPP_PATTERNS = [
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:which|list|show|check|what)\s+whatsapps?\s+(?:are\s+)?(?:installed|available)(?:\s+on\s+this\s+phone)?\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:list|show)\s+whatsapp\s+(?:apps|accounts)\s*$", re.I),
]

_NOTIFICATION_PATTERNS = [
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:any|read|show|check|tell\s+me)(?:\s+my)?\s+notifications?\s*(?:bro)?\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:who\s+messaged\s+me|any\s+messages?)\s*(?:bro)?\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:read|show|check|tell\s+me)(?:\s+my)?\s+(?:latest|last|recent)?\s*whatsapp\s+(?:message|notification)s?\s*(?:bro)?\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:any|read|show|check)(?:\s+my)?\s+whatsapp\s+(?:message|notification)s?\s*(?:bro)?\s*$", re.I),
]

_REPLY_PATTERNS = [
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?reply\s+to\s+(?P<target>[^:]+?)\s*:\s*(?P<text>.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?reply\s+to\s+(?P<target>[^:]+?)\s+with\s+(?P<text>.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?reply\s+tell\s+(?:him|her|them)\s+(.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?reply\s+(?:him|her|them)\s+(.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?reply\s+(?:to\s+(?:the\s+)?(?:latest|last|recent)\s+)?(?:whatsapp\s*)?(?:message\s*)?(?:with\s+)?[:\-]?\s*(.+?)\s*$", re.I),
]

_DIRECT_WHATSAPP_PATTERNS = [
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:send|message|whatsapp)\s+whatsapp\s*(?P<slot>[12])\s+to\s+(?P<target>[^:]+?)\s*:\s*(?P<text>.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:send|message)\s+(?P<target>[^:]+?)\s+on\s+whatsapp\s*(?P<slot>[12])\s*:\s*(?P<text>.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:send|message|whatsapp)\s+(?:a\s+)?(?:whatsapp\s+)?(?:message\s+)?to\s+(?P<target>[^:]+?)\s*:\s*(?P<text>.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:send|message)\s+(?P<target>[^:]+?)\s+on\s+whatsapp\s*:\s*(?P<text>.+?)\s*$", re.I),
    re.compile(r"^\s*(?:hey\s+bro\s+|bro\s+)?(?:send|message|whatsapp)\s+(?:a\s+)?whatsapp\s+(?:message\s+)?(?:with\s+)?(?P<text>.+?)\s*$", re.I),
]


def _normalize_command(text: str) -> str:
    normalized = (text or "").strip().lower()
    normalized = re.sub(r"[?!.,]+$", "", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _clean_command_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"[?!]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


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


def _parse_list_whatsapp_action(text: str) -> Optional[PhoneAction]:
    normalized = _normalize_command(text)
    if not normalized:
        return None
    if not any(pattern.match(normalized) for pattern in _LIST_WHATSAPP_PATTERNS):
        return None
    return PhoneAction(
        reply="Checking installed WhatsApp apps bro.",
        action={"type": "list_whatsapp_apps"},
    )


def _parse_reply_action(text: str) -> Optional[PhoneAction]:
    cleaned = _clean_command_text(text)
    if not cleaned:
        return None
    for pattern in _REPLY_PATTERNS:
        match = pattern.match(cleaned)
        if not match:
            continue
        groups = match.groupdict()
        raw_target = groups.get("target", "").strip()
        reply_text = (groups.get("text") or match.group(match.lastindex or 1)).strip()
        reply_text = re.sub(r"^(that|saying)\s+", "", reply_text).strip()
        if not reply_text:
            return PhoneAction(
                reply="Tell me the reply message also bro.",
                action={"type": "unsupported_reply_notification", "reason": "empty_reply"},
            )
        action = {
            "type": "reply_notification",
            "app": "whatsapp",
            "label": "WhatsApp",
            "text": reply_text,
        }
        target_label = "the latest WhatsApp notification"
        if raw_target:
            normalized_target = _normalize_command(raw_target)
            ignored_targets = {
                "latest",
                "last",
                "recent",
                "latest whatsapp",
                "last whatsapp",
                "recent whatsapp",
                "latest whatsapp message",
                "last whatsapp message",
                "recent whatsapp message",
                "whatsapp",
                "whatsapp message",
            }
            if normalized_target not in ignored_targets:
                if normalized_target.isdigit():
                    action["target_index"] = int(normalized_target)
                    target_label = f"WhatsApp notification {normalized_target}"
                else:
                    target_name = re.sub(r"\b(whatsapp|message|notification)\b", "", raw_target, flags=re.I).strip()
                    target_name = target_name.strip(" \"'“”‘’")
                    target_name = re.sub(r"\s+", " ", target_name)
                    if target_name:
                        action["target_name"] = target_name
                        target_label = f"WhatsApp notification from {target_name}"
        return PhoneAction(
            reply=f"Sending that reply through {target_label} bro.",
            action=action,
        )
    return None


def _phone_digits(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if len(digits) == 10:
        return "91" + digits
    if 8 <= len(digits) <= 15:
        return digits
    return ""


def _parse_direct_whatsapp_action(text: str) -> Optional[PhoneAction]:
    cleaned = _clean_command_text(text)
    if not cleaned:
        return None
    for pattern in _DIRECT_WHATSAPP_PATTERNS:
        match = pattern.match(cleaned)
        if not match:
            continue
        groups = match.groupdict()
        raw_target = (groups.get("target") or "").strip().strip(" \"'“”‘’")
        message = (groups.get("text") or "").strip()
        message = re.sub(r"^(that|saying)\s+", "", message).strip()
        if not message:
            return PhoneAction(
                reply="Tell me the WhatsApp message also bro.",
                action={"type": "unsupported_direct_whatsapp", "reason": "empty_message"},
            )
        action = {
            "type": "direct_whatsapp",
            "label": "WhatsApp",
            "text": message,
        }
        raw_slot = groups.get("slot")
        if raw_slot:
            action["whatsapp_slot"] = int(raw_slot)
            action["label"] = f"WhatsApp {raw_slot}"
        target_label = "WhatsApp"
        if raw_slot:
            target_label = f"WhatsApp {raw_slot}"
        if raw_target:
            phone = _phone_digits(raw_target)
            if phone:
                action["phone"] = phone
                target_label = f"{target_label} number {raw_target}"
            else:
                action["target_name"] = raw_target
                target_label = f"{target_label} contact {raw_target}"
        return PhoneAction(
            reply=f"Opening {target_label} with your message bro.",
            action=action,
        )
    return None


def parse_phone_action(text: str) -> Optional[PhoneAction]:
    normalized = _normalize_command(text)
    list_whatsapp_action = _parse_list_whatsapp_action(normalized)
    if list_whatsapp_action is not None:
        return list_whatsapp_action
    reply_action = _parse_reply_action(text)
    if reply_action is not None:
        return reply_action
    direct_whatsapp_action = _parse_direct_whatsapp_action(text)
    if direct_whatsapp_action is not None:
        return direct_whatsapp_action
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
    whatsapp_slot = re.fullmatch(r"whatsapp\s*([12])", requested)
    if whatsapp_slot:
        slot = int(whatsapp_slot.group(1))
        return PhoneAction(
            reply=f"Opening WhatsApp {slot} bro.",
            action={
                "type": "open_app",
                "app": f"whatsapp {slot}",
                "label": f"WhatsApp {slot}",
                "packages": [],
                "intent": "whatsapp_slot",
                "whatsapp_slot": slot,
            },
        )
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
