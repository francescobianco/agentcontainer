from __future__ import annotations

import argparse
import asyncio
import json

from .client import build_message, send_message
from .server import serve


def _parse_target(target: str) -> tuple[str, int]:
    host, separator, port = target.rpartition(":")
    if not separator or not host or not port:
        raise ValueError("target must be in HOST:PORT format")
    return host, int(port)


async def _run_send(args: argparse.Namespace) -> None:
    host, port = _parse_target(args.target)
    if args.command == "send":
        payload = {
            "source_code": open(args.agent_file, "r", encoding="utf-8").read(),
            "activate_payload": json.loads(args.activate or "{}"),
        }
        message = build_message("deploy_agent", args.secret, payload)
    elif args.command == "invoke":
        payload = {"agent_id": args.agent_id, "message": json.loads(args.message or "{}")}
        message = build_message("invoke_agent", args.secret, payload)
    elif args.command == "list-agents":
        message = build_message("list_agents", args.secret, {})
    elif args.command == "tree":
        message = build_message("network_tree", args.secret, {})
    elif args.command == "describe":
        message = build_message("describe_container", args.secret, {})
    else:
        raise ValueError(f"unsupported command {args.command}")
    response = await send_message(host, port, message)
    print(json.dumps(response, indent=2, ensure_ascii=True))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="agentcontainer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_cmd = subparsers.add_parser("server", help="Run an agentcontainer service")
    server_cmd.add_argument("--config", required=True, help="Path to the container JSON config")

    send_cmd = subparsers.add_parser("send", help="Send an agent source file to a remote container")
    send_cmd.add_argument("agent_file")
    send_cmd.add_argument("target", help="HOST:PORT")
    send_cmd.add_argument("--secret", required=True, help="Remote admin secret")
    send_cmd.add_argument("--activate", help="JSON payload for activation")

    invoke_cmd = subparsers.add_parser("invoke", help="Invoke an existing remote agent")
    invoke_cmd.add_argument("agent_id")
    invoke_cmd.add_argument("target", help="HOST:PORT")
    invoke_cmd.add_argument("--secret", required=True, help="Remote admin secret")
    invoke_cmd.add_argument("--message", help="JSON payload delivered to the agent")

    list_cmd = subparsers.add_parser("list-agents", help="List agents on a remote container")
    list_cmd.add_argument("target", help="HOST:PORT")
    list_cmd.add_argument("--secret", required=True, help="Remote admin secret")

    tree_cmd = subparsers.add_parser("tree", help="Read the federation tree from a remote container")
    tree_cmd.add_argument("target", help="HOST:PORT")
    tree_cmd.add_argument("--secret", required=True, help="Remote admin secret")

    describe_cmd = subparsers.add_parser("describe", help="Describe a remote container")
    describe_cmd.add_argument("target", help="HOST:PORT")
    describe_cmd.add_argument("--secret", required=True, help="Remote admin secret")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.command == "server":
        asyncio.run(serve(args.config))
        return
    asyncio.run(_run_send(args))


if __name__ == "__main__":
    main()
