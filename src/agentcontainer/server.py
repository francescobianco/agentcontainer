from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from .auth import verify_message
from .config import load_config
from .identity import ensure_identity_config
from .protocol import read_message, write_message
from .runtime import AgentRuntime


async def handle_client(runtime: AgentRuntime, reader, writer) -> None:
    peer = writer.get_extra_info("peername")
    try:
        message = await read_message(reader)
        verify_message(message, runtime.identity, max_skew_seconds=86400 * 365)
        response = await runtime.handle_message(message)
    except Exception as exc:  # noqa: BLE001
        runtime.log(f"request from {peer} failed: {exc}")
        response = {"status": "error", "error": str(exc)}

    await write_message(writer, response)
    writer.close()
    await writer.wait_closed()


async def serve(config_path: str) -> None:
    config = load_config(config_path)
    runtime = AgentRuntime(config, ensure_identity_config(Path.cwd()))
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(runtime, reader, writer),
        host=config.listen_host,
        port=config.listen_port,
    )
    runtime.log(f"listening on {config.listen_host}:{config.listen_port}")
    async with server:
        await server.serve_forever()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an agentcontainer TCP server")
    parser.add_argument("--config", required=True, help="Path to the container JSON config")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(serve(args.config))


if __name__ == "__main__":
    main()
