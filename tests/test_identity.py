from __future__ import annotations

import tempfile
from pathlib import Path

from agentcontainer.identity import IDENTITY_FILE, ensure_identity_config


def test_ensure_identity_config_creates_agentcontainer_file():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        config = ensure_identity_config(directory)
        path = directory / IDENTITY_FILE

        assert path.exists()
        raw = path.read_text(encoding="utf-8")
        assert "[private_key]" in raw
        assert "[public_access]" in raw
        assert "BEGIN OPENSSH PRIVATE KEY" in raw
        assert config.public_access[0]["public_key"] in raw


def test_ensure_identity_config_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        first = ensure_identity_config(directory)
        second = ensure_identity_config(directory)

        assert first.private_key["key"] == second.private_key["key"]
        assert first.public_access == second.public_access
