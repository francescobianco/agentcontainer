from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from agentcontainer.auth import attach_signature
from agentcontainer.client import send_message
from agentcontainer.cli import parse_args
from agentcontainer.config import Config
from agentcontainer.server import handle_client
from agentcontainer.runtime import AgentRuntime


AGENT_SOURCE = """
AGENT_ID = "test-agent"
AGENT_SECRET = "test-agent-secret"

class Agent:
    def __init__(self):
        self.events = []

    async def on_activate(self, ctx, payload):
        self.events.append(("activate", ctx.container_name, payload))
        return {"event": "activate", "container": ctx.container_name, "payload": payload}

    async def on_message(self, ctx, payload):
        self.events.append(("message", ctx.container_name, payload))
        if payload.get("command") == "clone":
            return await ctx.clone("child", {"command": "record", "from": ctx.container_name})
        if payload.get("command") == "move":
            return await ctx.move("child", {"command": "record", "from": ctx.container_name})
        return {"event": "message", "container": ctx.container_name, "payload": payload}
"""


def signed(secret: str, message_type: str, payload: dict) -> dict:
    return attach_signature(
        {
            "type": message_type,
            "sender": "admin",
            "timestamp": int(time.time()),
            "nonce": f"{message_type}-{time.time()}",
            "payload": payload,
        },
        secret,
    )


async def start_runtime(config: Config):
    runtime = AgentRuntime(config)
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(runtime, reader, writer),
        host=config.listen_host,
        port=config.listen_port,
    )
    return runtime, server


def test_deploy_and_invoke():
    async def scenario():
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp) / "root"
            (root_dir / "docs").mkdir(parents=True)
            config = Config(
                container_name="root",
                listen_host="127.0.0.1",
                listen_port=7100,
                admin_secret="root-secret",
                data_root=str(root_dir),
                federation={"name": "root", "host": "127.0.0.1", "port": 7100, "children": []},
            )
            runtime, server = await start_runtime(config)
            async with server:
                deploy = await send_message(
                    "127.0.0.1",
                    7100,
                    signed("root-secret", "deploy_agent", {"source_code": AGENT_SOURCE, "activate_payload": {"hello": "world"}}),
                )
                assert deploy["status"] == "ok"
                invoke = await send_message(
                    "127.0.0.1",
                    7100,
                    signed("root-secret", "invoke_agent", {"agent_id": "test-agent", "message": {"x": 1}}),
                )
                assert invoke["status"] == "ok"
                assert invoke["result"]["result"]["payload"] == {"x": 1}
                assert "test-agent" in runtime.agents

    asyncio.run(scenario())


def test_clone_and_move_between_nodes():
    async def scenario():
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp) / "root"
            child_dir = Path(tmp) / "child"
            (root_dir / "docs").mkdir(parents=True)
            (child_dir / "docs").mkdir(parents=True)

            root_config = Config(
                container_name="root",
                listen_host="127.0.0.1",
                listen_port=7101,
                admin_secret="root-secret",
                data_root=str(root_dir),
                federation={
                    "name": "root",
                    "host": "127.0.0.1",
                    "port": 7101,
                    "children": [{"name": "child", "host": "127.0.0.1", "port": 7102, "children": []}],
                },
            )
            child_config = Config(
                container_name="child",
                listen_host="127.0.0.1",
                listen_port=7102,
                admin_secret="child-secret",
                data_root=str(child_dir),
                federation={"name": "child", "host": "127.0.0.1", "port": 7102, "children": []},
            )

            root_runtime, root_server = await start_runtime(root_config)
            child_runtime, child_server = await start_runtime(child_config)

            async with root_server, child_server:
                deploy = await send_message(
                    "127.0.0.1",
                    7101,
                    signed("root-secret", "deploy_agent", {"source_code": AGENT_SOURCE, "activate_payload": {}}),
                )
                assert deploy["status"] == "ok"

                clone_response = await send_message(
                    "127.0.0.1",
                    7101,
                    signed("root-secret", "invoke_agent", {"agent_id": "test-agent", "message": {"command": "clone"}}),
                )
                assert clone_response["status"] == "ok"
                assert "test-agent" in root_runtime.agents
                assert "test-agent" in child_runtime.agents

                move_response = await send_message(
                    "127.0.0.1",
                    7101,
                    signed("root-secret", "invoke_agent", {"agent_id": "test-agent", "message": {"command": "move"}}),
                )
                assert move_response["status"] == "ok"
                assert "test-agent" not in root_runtime.agents
                assert "test-agent" in child_runtime.agents

    asyncio.run(scenario())


def test_cli_run_parsing():
    args = parse_args(
        [
            "run",
            "agents/demo/visitcontainer-and-go-back.py",
        ]
    )
    assert args.command == "run"
    assert args.agent_file == "agents/demo/visitcontainer-and-go-back.py"
    assert args.target_name == "sandbox"


def test_cli_server_short_syntax():
    args = parse_args(["server", "0.0.0.0:7007"])
    assert args.command == "server"
    assert args.address == "0.0.0.0:7007"
