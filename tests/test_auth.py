import time

import pytest

from agentcontainer.auth import attach_signature, verify_message


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
