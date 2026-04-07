from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any

from .client import build_message, send_message
from .config import Config
from .identity import ensure_identity_config
from .server import handle_client, serve
from .runtime import AgentRuntime


DEFAULT_SECRET = "agentcontainer-dev-secret"


def _parse_target(target: str) -> tuple[str, int]:
    host, separator, port = target.rpartition(":")
    if not separator or not host or not port:
        raise ValueError("target must be in HOST:PORT format")
    return host, int(port)


def _allocate_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _normalize_connect_host(host: str) -> str:
    if host in {"0.0.0.0", "localhost"}:
        return "127.0.0.1"
    return host


def _guess_stage_host(remote_host: str) -> str:
    if remote_host in {"127.0.0.1", "0.0.0.0", "localhost"}:
        return "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect((remote_host, 9))
            return sock.getsockname()[0] or "127.0.0.1"
        except OSError:
            return "127.0.0.1"


def _make_server_config(address: str, secret: str, data_root: str | None, name: str | None) -> Config:
    host, port = _parse_target(address)
    container_name = name or f"container-{port}"
    root = str(Path(data_root or ".").resolve())
    federation = {"name": container_name, "host": host, "port": port, "children": []}
    return Config(
        container_name=container_name,
        listen_host=host,
        listen_port=port,
        admin_secret=secret,
        data_root=root,
        federation=federation,
        allow_subprocess=True,
    )


def _build_stage_network(stage_name: str, stage_host: str, stage_port: int, target_name: str, target_host: str, target_port: int) -> dict[str, Any]:
    return {
        "name": stage_name,
        "host": stage_host,
        "port": stage_port,
        "children": [
            {
                "name": target_name,
                "host": target_host,
                "port": target_port,
                "children": [],
            }
        ],
    }


async def _start_runtime_server(config: Config) -> tuple[AgentRuntime, asyncio.base_events.Server]:
    runtime = AgentRuntime(config)
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(runtime, reader, writer),
        host=config.listen_host,
        port=config.listen_port,
    )
    return runtime, server


async def _wait_for_return(runtime: AgentRuntime, agent_id: str, timeout: float | None) -> None:
    print("Stage attivo. Premi Ctrl+C per distruggerlo oppure attendi il ritorno dell'agente.", flush=True)
    start = asyncio.get_running_loop().time()
    while True:
        if agent_id in runtime.agents:
            print(f"L'agente {agent_id} e' rientrato nello stage. Arresto automatico.", flush=True)
            return
        if timeout is not None and (asyncio.get_running_loop().time() - start) >= timeout:
            print("Timeout stage raggiunto. Arresto dello stage.", flush=True)
            return
        await asyncio.sleep(0.25)


def _extract_return_report(response: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return response["result"]["activate_result"]["report"]
    except (KeyError, TypeError):
        return None


def _print_stage_summary(label: str, response: dict[str, Any]) -> None:
    def find_return_report(payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            if isinstance(payload.get("report"), dict):
                return payload["report"]
            for value in payload.values():
                found = find_return_report(value)
                if found is not None:
                    return found
        if isinstance(payload, list):
            for value in payload:
                found = find_return_report(value)
                if found is not None:
                    return found
        return None

    status = response.get("status", "unknown")
    if status != "ok":
        print(f"{label}: errore: {response.get('error', 'unknown error')}", flush=True)
        return
    result = response.get("result", {})
    agent_id = result.get("agent_id", "?")
    print(f"{label}: ok agent={agent_id}", flush=True)
    report = find_return_report(result)
    if isinstance(report, dict):
        container_name = report.get("container", "?")
        capabilities = report.get("capabilities", [])
        files = report.get("resources", {}).get("files", [])
        print(
            f"ritorno: container={container_name} primitive={len(capabilities)} files={len(files)}",
            flush=True,
        )


async def _stage_and_send(
    *,
    source_code: str,
    target_host: str,
    target_port: int,
    target_name: str,
    target_secret: str,
    activate_payload: dict[str, Any],
    stage_name: str,
    stage_host: str,
    stage_port: int,
    timeout: float | None,
) -> None:
    with tempfile.TemporaryDirectory(prefix="agentcontainer-stage-") as tmp:
        identity = ensure_identity_config(Path.cwd())
        stage_secret = secrets.token_hex(16)
        stage_network = _build_stage_network(stage_name, stage_host, stage_port, target_name, target_host, target_port)
        stage_config = Config(
            container_name=stage_name,
            listen_host="127.0.0.1",
            listen_port=stage_port,
            admin_secret=stage_secret,
            data_root=tmp,
            federation=stage_network,
            allow_subprocess=True,
        )
        stage_runtime, stage_server = await _start_runtime_server(stage_config)
        async with stage_server:
            deploy_response = await send_message(
                "127.0.0.1",
                stage_port,
                build_message(
                    "deploy_agent",
                    identity,
                    {
                        "source_code": source_code,
                        "activate_payload": None,
                        "agent_metadata": {
                            "stage": {"name": stage_name, "host": stage_host, "port": stage_port},
                            "network": stage_network,
                        },
                    },
                ),
            )
            if deploy_response.get("status") != "ok":
                print(f"stage deploy fallito: {deploy_response.get('error', 'unknown error')}", flush=True)
                raise SystemExit(1)
            agent_id = deploy_response["result"]["agent_id"]
            print(f"stage pronto: agent={agent_id} stage={stage_host}:{stage_port}", flush=True)

            dispatch_response = await send_message(
                "127.0.0.1",
                stage_port,
                build_message(
                    "dispatch_agent",
                    identity,
                    {
                        "agent_id": agent_id,
                        "destination": target_name,
                        "mode": "move",
                        "activate_payload": activate_payload,
                        "metadata_patch": {
                            "stage": {"name": stage_name, "host": stage_host, "port": stage_port},
                            "network": stage_network,
                        },
                    },
                ),
            )
            if dispatch_response.get("status") != "ok":
                print(f"invio fallito: {dispatch_response.get('error', 'unknown error')}", flush=True)
                raise SystemExit(1)
            _print_stage_summary("invio", dispatch_response)
            await _wait_for_return(stage_runtime, agent_id, timeout)


async def _run_server(args: argparse.Namespace) -> None:
    if args.config:
        await serve(args.config)
        return
    config = _make_server_config(args.address, args.secret, args.data_root, args.name)
    runtime, server = await _start_runtime_server(config)
    runtime.log(f"listening on {config.listen_host}:{config.listen_port}")
    async with server:
        await server.serve_forever()


async def _run_send(args: argparse.Namespace) -> None:
    host, port = _parse_target(args.target)
    connect_host = _normalize_connect_host(host)
    stage_port = args.stage_port or _allocate_tcp_port()
    stage_host = args.stage_host or _guess_stage_host(connect_host)
    await _stage_and_send(
        source_code=Path(args.agent_file).read_text(encoding="utf-8"),
        target_host=connect_host,
        target_port=port,
        target_name=args.target_name,
        target_secret=args.secret,
        activate_payload=json.loads(args.activate or "{}"),
        stage_name=args.stage_name,
        stage_host=stage_host,
        stage_port=stage_port,
        timeout=args.timeout,
    )


async def _run_local(args: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="agentcontainer-run-") as tmp:
        target_port = args.target_port or _allocate_tcp_port()
        target_root = Path(args.data_root or tmp).resolve()
        target_root.mkdir(parents=True, exist_ok=True)
        target_config = Config(
            container_name=args.target_name,
            listen_host="127.0.0.1",
            listen_port=target_port,
            admin_secret=DEFAULT_SECRET,
            data_root=str(target_root),
            federation={"name": args.target_name, "host": "127.0.0.1", "port": target_port, "children": []},
            allow_subprocess=not args.disable_subprocess,
        )
        _, target_server = await _start_runtime_server(target_config)
        async with target_server:
            await _stage_and_send(
                source_code=Path(args.agent_file).read_text(encoding="utf-8"),
                target_host="127.0.0.1",
                target_port=target_port,
                target_name=args.target_name,
                target_secret=DEFAULT_SECRET,
                activate_payload=json.loads(args.activate or "{}"),
                stage_name=args.stage_name,
                stage_host="127.0.0.1",
                stage_port=args.stage_port or _allocate_tcp_port(),
                timeout=args.timeout,
            )


async def _run_control(args: argparse.Namespace) -> None:
    host, port = _parse_target(args.target)
    host = _normalize_connect_host(host)
    identity = ensure_identity_config(Path.cwd())
    if args.command == "invoke":
        message = build_message("invoke_agent", identity, {"agent_id": args.agent_id, "message": json.loads(args.message or "{}")})
    elif args.command == "list-agents":
        message = build_message("list_agents", identity, {})
    elif args.command == "tree":
        message = build_message("network_tree", identity, {})
    elif args.command == "describe":
        message = build_message("describe_container", identity, {})
    else:
        raise ValueError(f"unsupported command {args.command}")
    response = await send_message(host, port, message)
    print(json.dumps(response, indent=2, ensure_ascii=True))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="agentcontainer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_cmd = subparsers.add_parser("server", help="Run an agentcontainer service")
    server_cmd.add_argument("address", nargs="?", help="HOST:PORT")
    server_cmd.add_argument("--config", help="Path to the container JSON config")
    server_cmd.add_argument("--secret", default=DEFAULT_SECRET, help="Admin secret for the server")
    server_cmd.add_argument("--data-root", help="Directory exposed by the container")
    server_cmd.add_argument("--name", help="Container name")

    send_cmd = subparsers.add_parser("send", help="Stage a Python agent locally and send it to a target container")
    send_cmd.add_argument("agent_file")
    send_cmd.add_argument("target", help="HOST:PORT")
    send_cmd.add_argument("--secret", default=DEFAULT_SECRET, help="Remote admin secret")
    send_cmd.add_argument("--activate", help="JSON payload for the remote activation")
    send_cmd.add_argument("--stage-name", default="stage", help="Name of the local stage container")
    send_cmd.add_argument("--target-name", default="target", help="Target node name exposed to the agent")
    send_cmd.add_argument("--stage-host", help="Host or IP that the remote node can use to return to the local stage")
    send_cmd.add_argument("--stage-port", type=int, default=0, help="Local stage port, 0 means auto")
    send_cmd.add_argument("--timeout", type=float, help="Auto-stop timeout for the stage in seconds")

    run_cmd = subparsers.add_parser("run", help="Start a local sandbox container and send the agent from a local stage")
    run_cmd.add_argument("agent_file")
    run_cmd.add_argument("--activate", help="JSON payload for activation")
    run_cmd.add_argument("--data-root", help="Directory exposed to the local sandbox")
    run_cmd.add_argument("--stage-name", default="stage", help="Name of the local stage container")
    run_cmd.add_argument("--target-name", default="sandbox", help="Name of the local sandbox container")
    run_cmd.add_argument("--stage-port", type=int, default=0, help="Local stage port, 0 means auto")
    run_cmd.add_argument("--target-port", type=int, default=0, help="Local sandbox port, 0 means auto")
    run_cmd.add_argument("--timeout", type=float, help="Auto-stop timeout for the stage in seconds")
    run_cmd.add_argument("--disable-subprocess", action="store_true", help="Disable subprocess primitive in the local sandbox")

    invoke_cmd = subparsers.add_parser("invoke", help="Invoke an existing remote agent")
    invoke_cmd.add_argument("agent_id")
    invoke_cmd.add_argument("target", help="HOST:PORT")
    invoke_cmd.add_argument("--secret", default=DEFAULT_SECRET)
    invoke_cmd.add_argument("--message")

    list_cmd = subparsers.add_parser("list-agents", help="List agents on a remote container")
    list_cmd.add_argument("target", help="HOST:PORT")
    list_cmd.add_argument("--secret", default=DEFAULT_SECRET)

    tree_cmd = subparsers.add_parser("tree", help="Read the federation tree from a remote container")
    tree_cmd.add_argument("target", help="HOST:PORT")
    tree_cmd.add_argument("--secret", default=DEFAULT_SECRET)

    describe_cmd = subparsers.add_parser("describe", help="Describe a remote container")
    describe_cmd.add_argument("target", help="HOST:PORT")
    describe_cmd.add_argument("--secret", default=DEFAULT_SECRET)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        ensure_identity_config(Path.cwd())
        if args.command == "server":
            asyncio.run(_run_server(args))
            return
        if args.command == "send":
            asyncio.run(_run_send(args))
            return
        if args.command == "run":
            asyncio.run(_run_local(args))
            return
        asyncio.run(_run_control(args))
    except KeyboardInterrupt:
        print("Stage distrutto manualmente.", flush=True)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"errore: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
