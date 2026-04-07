import time
import tempfile
from pathlib import Path

import pytest

from agentcontainer.auth import attach_signature, verify_message
from agentcontainer.identity import ensure_identity_config


def test_signature_roundtrip():
    message = {
        "type": "list_agents",
        "sender": "admin",
        "timestamp": int(time.time()),
        "nonce": "n1",
        "payload": {},
    }
    signed = attach_signature(message, "secret")
    verify_message(signed, "secret")


def test_signature_rejects_tampering():
    message = {
        "type": "list_agents",
        "sender": "admin",
        "timestamp": int(time.time()),
        "nonce": "n1",
        "payload": {},
    }
    signed = attach_signature(message, "secret")
    signed["payload"] = {"changed": True}
    with pytest.raises(ValueError):
        verify_message(signed, "secret")


def test_identity_signature_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        identity = ensure_identity_config(Path(tmp))
        message = {
            "type": "list_agents",
            "sender": "admin",
            "timestamp": int(time.time()),
            "nonce": "n1",
            "payload": {},
        }
        signed = attach_signature(message, identity)
        verify_message(signed, identity)
