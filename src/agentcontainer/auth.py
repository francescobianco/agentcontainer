from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any


def canonical_payload(message: dict[str, Any]) -> bytes:
    data = {key: value for key, value in message.items() if key != "signature"}
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_message(message: dict[str, Any], secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), canonical_payload(message), hashlib.sha256).hexdigest()


def attach_signature(message: dict[str, Any], secret: str) -> dict[str, Any]:
    signed = dict(message)
    signed["signature"] = sign_message(signed, secret)
    return signed


def verify_message(message: dict[str, Any], secret: str, *, max_skew_seconds: int = 300) -> None:
    signature = message.get("signature")
    if not isinstance(signature, str) or not signature:
        raise ValueError("missing signature")

    timestamp = message.get("timestamp")
    if not isinstance(timestamp, int):
        raise ValueError("timestamp must be an integer unix epoch")

    if abs(int(time.time()) - timestamp) > max_skew_seconds:
        raise ValueError("timestamp outside allowed skew")

    expected = sign_message(message, secret)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid signature")
