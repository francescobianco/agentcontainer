from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agentcontainer.identity import IDENTITY_FILE, ensure_identity_config


def test_ensure_identity_config_creates_agentcontainer_file():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        config = ensure_identity_config(directory)
        path = directory / IDENTITY_FILE

        assert path.exists()
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["private_key"]["identity"] == config.private_key["identity"]
        assert "BEGIN OPENSSH PRIVATE KEY" in raw["private_key"]["key"]
        assert raw["public_access"][0]["identity"] == config.private_key["identity"]
        assert raw["public_access"][0]["public_key"].startswith("ssh-ed25519 ")


def test_ensure_identity_config_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        first = ensure_identity_config(directory)
        second = ensure_identity_config(directory)

        assert first.private_key["key"] == second.private_key["key"]
        assert first.public_access == second.public_access
