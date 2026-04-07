from __future__ import annotations

import json
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


IDENTITY_FILE = ".agentcontainer"


@dataclass(slots=True)
class IdentityConfig:
    path: Path
    private_key: dict[str, str]
    public_access: list[dict[str, str]]


def default_identity_name() -> str:
    return f"agentcontainer@{socket.gethostname()}"


def _generate_keypair(identity: str) -> tuple[dict[str, str], dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix="agentcontainer-keygen-") as tmp:
        tmp_path = Path(tmp)
        key_path = tmp_path / "id_ed25519"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", identity, "-f", str(key_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        private_key = {
            "identity": identity,
            "key": key_path.read_text(encoding="utf-8"),
        }
        public_key = {
            "identity": identity,
            "public_key": key_path.with_suffix(".pub").read_text(encoding="utf-8").strip(),
        }
        return private_key, public_key


def load_identity_config(directory: Path) -> IdentityConfig:
    path = directory / IDENTITY_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    return IdentityConfig(
        path=path,
        private_key=raw["private_key"],
        public_access=raw["public_access"],
    )


def ensure_identity_config(directory: Path) -> IdentityConfig:
    path = directory / IDENTITY_FILE
    if path.exists():
        return load_identity_config(directory)

    identity = default_identity_name()
    private_key, public_key = _generate_keypair(identity)
    config = IdentityConfig(
        path=path,
        private_key=private_key,
        public_access=[public_key],
    )
    payload = {
        "private_key": config.private_key,
        "public_access": config.public_access,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return config
