from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .identity import IdentityConfig


SIGNING_NAMESPACE = "agentcontainer"


def canonical_payload(message: dict[str, Any]) -> bytes:
    data = {key: value for key, value in message.items() if key != "signature"}
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sign_with_identity(message: dict[str, Any], identity: IdentityConfig) -> str:
    with tempfile.TemporaryDirectory(prefix="agentcontainer-sign-") as tmp:
        tmp_path = Path(tmp)
        message_path = tmp_path / "message.json"
        key_path = tmp_path / "id_ed25519"
        message_path.write_bytes(canonical_payload(message))
        key_path.write_text(identity.private_key["key"], encoding="utf-8")
        key_path.chmod(0o600)
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-n", SIGNING_NAMESPACE, "-f", str(key_path), str(message_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return (tmp_path / "message.json.sig").read_text(encoding="utf-8")


def sign_message(message: dict[str, Any], signer: str | IdentityConfig) -> str:
    if isinstance(signer, IdentityConfig):
        return _sign_with_identity(message, signer)
    return hmac.new(signer.encode("utf-8"), canonical_payload(message), hashlib.sha256).hexdigest()


def attach_signature(message: dict[str, Any], signer: str | IdentityConfig) -> dict[str, Any]:
    signed = dict(message)
    if isinstance(signer, IdentityConfig):
        signed["sender"] = signer.private_key["identity"]
    signed["signature"] = sign_message(signed, signer)
    return signed


def _verify_with_identity(message: dict[str, Any], identity: IdentityConfig) -> None:
    sender = message.get("sender")
    if not isinstance(sender, str) or not sender:
        raise ValueError("missing sender")

    trusted = [entry for entry in identity.public_access if entry["identity"] == sender]
    if not trusted:
        raise ValueError(f"sender {sender} is not trusted")

    signature = message.get("signature")
    with tempfile.TemporaryDirectory(prefix="agentcontainer-verify-") as tmp:
        tmp_path = Path(tmp)
        signature_path = tmp_path / "message.sig"
        allowed_signers = tmp_path / "allowed_signers"
        signature_path.write_text(signature, encoding="utf-8")
        allowed_signers.write_text(
            "".join(f'{entry["identity"]} namespaces="{SIGNING_NAMESPACE}" {entry["public_key"]}\n' for entry in trusted),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(allowed_signers),
                "-I",
                sender,
                "-n",
                SIGNING_NAMESPACE,
                "-s",
                str(signature_path),
            ],
            input=canonical_payload(message),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise ValueError("invalid signature")


def verify_message(message: dict[str, Any], verifier: str | IdentityConfig, *, max_skew_seconds: int = 300) -> None:
    signature = message.get("signature")
    if not isinstance(signature, str) or not signature:
        raise ValueError("missing signature")

    timestamp = message.get("timestamp")
    if not isinstance(timestamp, int):
        raise ValueError("timestamp must be an integer unix epoch")

    if abs(int(time.time()) - timestamp) > max_skew_seconds:
        raise ValueError("timestamp outside allowed skew")

    if isinstance(verifier, IdentityConfig):
        _verify_with_identity(message, verifier)
        return

    expected = sign_message(message, verifier)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid signature")


def compute_agent_hmac(
    source_code: str,
    activate_payload: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    mode: str,
    secret: str,
) -> str:
    payload = {
        "source_code": source_code,
        "activate_payload": activate_payload,
        "agent_metadata": metadata or {},
        "mode": mode,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def verify_agent_hmac(
    *,
    source_code: str,
    activate_payload: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    mode: str,
    secret: str,
    provided_hmac: str | None,
) -> None:
    if not isinstance(provided_hmac, str) or not provided_hmac:
        raise ValueError("missing agent_hmac")
    expected = compute_agent_hmac(source_code, activate_payload, metadata, mode, secret)
    if not hmac.compare_digest(provided_hmac, expected):
        raise ValueError("invalid agent_hmac")
