from __future__ import annotations

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


def _extract_identity_from_public_key(public_key: str) -> str:
    parts = public_key.strip().split()
    if len(parts) >= 3:
        return parts[2]
    return default_identity_name()


def _public_key_from_private_key(private_key_text: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="agentcontainer-pubkey-") as tmp:
        tmp_path = Path(tmp)
        key_path = tmp_path / "id_ed25519"
        key_path.write_text(private_key_text, encoding="utf-8")
        key_path.chmod(0o600)
        result = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(key_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        public_key = result.stdout.strip()
        return {
            "identity": _extract_identity_from_public_key(public_key),
            "public_key": public_key,
        }


def _serialize_identity_config(config: IdentityConfig) -> str:
    public_access = "\n".join(entry["public_key"] for entry in config.public_access)
    return (
        "[private_key]\n"
        f"{config.private_key['key'].rstrip()}\n"
        "\n"
        "[public_access]\n"
        f"{public_access}\n"
    )


def _parse_identity_config(text: str, path: Path) -> IdentityConfig:
    current_section: str | None = None
    private_key_lines: list[str] = []
    public_access_lines: list[str] = []

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "[private_key]":
            current_section = "private_key"
            continue
        if stripped == "[public_access]":
            current_section = "public_access"
            continue
        if current_section == "private_key":
            private_key_lines.append(line)
        elif current_section == "public_access":
            public_access_lines.append(stripped)

    if not private_key_lines:
        raise ValueError("missing [private_key] section")
    if not public_access_lines:
        raise ValueError("missing [public_access] section")

    private_key_text = "\n".join(private_key_lines).strip() + "\n"
    private_public = _public_key_from_private_key(private_key_text)
    return IdentityConfig(
        path=path,
        private_key={
            "identity": private_public["identity"],
            "key": private_key_text,
        },
        public_access=[
            {
                "identity": _extract_identity_from_public_key(public_key),
                "public_key": public_key,
            }
            for public_key in public_access_lines
        ],
    )


def load_identity_config(directory: Path) -> IdentityConfig:
    path = directory / IDENTITY_FILE
    return _parse_identity_config(path.read_text(encoding="utf-8"), path)


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
    path.write_text(_serialize_identity_config(config), encoding="utf-8")
    return config
