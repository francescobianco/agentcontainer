from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from .auth import attach_signature
from .identity import IdentityConfig, ensure_identity_config
from .protocol import read_message, write_message


async def send_message(host: str, port: int, message: dict[str, Any]) -> dict[str, Any]:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        await write_message(writer, message)
        return await read_message(reader)
    finally:
        writer.close()
        await writer.wait_closed()


def build_message(message_type: str, signer: str | IdentityConfig, payload: dict[str, Any], sender: str = "admin") -> dict[str, Any]:
    message = {
        "type": message_type,
        "sender": sender,
        "timestamp": int(time.time()),
        "nonce": str(uuid.uuid4()),
        "payload": payload,
    }
    return attach_signature(message, signer)


async def run_client(args: argparse.Namespace) -> dict[str, Any]:
    identity = ensure_identity_config(Path.cwd())
    if args.command == "deploy":
        payload = {
            "source_code": Path(args.agent_file).read_text(encoding="utf-8"),
            "activate_payload": json.loads(args.activate or "{}"),
        }
        message = build_message("deploy_agent", identity, payload)
    elif args.command == "invoke":
        payload = {"agent_id": args.agent_id, "message": json.loads(args.message or "{}")}
        message = build_message("invoke_agent", identity, payload)
    elif args.command == "list-agents":
        message = build_message("list_agents", identity, {})
    elif args.command == "tree":
        message = build_message("network_tree", identity, {})
    elif args.command == "describe":
        message = build_message("describe_container", identity, {})
    else:
        raise ValueError(f"unsupported command {args.command}")
    return await send_message(args.host, args.port, message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="agentcontainer CLI client")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)

    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("agent_file")
    deploy.add_argument("--activate")

    invoke = subparsers.add_parser("invoke")
    invoke.add_argument("agent_id")
    invoke.add_argument("--message")

    subparsers.add_parser("list-agents")
    subparsers.add_parser("tree")
    subparsers.add_parser("describe")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    ensure_identity_config(Path.cwd())
    response = asyncio.run(run_client(args))
    print(json.dumps(response, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
