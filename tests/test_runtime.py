from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from agentcontainer.auth import attach_signature
from agentcontainer.client import send_message
from agentcontainer.cli import parse_args
from agentcontainer.config import Config
from agentcontainer.identity import ensure_identity_config
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

OTHER_AGENT_SOURCE = """
AGENT_ID = "other-agent"
AGENT_SECRET = "other-agent-secret"

class Agent:
    async def on_activate(self, ctx, payload):
        return {"event": "activate", "container": ctx.container_name, "payload": payload}
"""


def signed(identity, message_type: str, payload: dict) -> dict:
    return attach_signature(
        {
            "type": message_type,
            "sender": "admin",
            "timestamp": int(time.time()),
            "nonce": f"{message_type}-{time.time()}",
            "payload": payload,
        },
        identity,
    )


async def start_runtime(config: Config, identity):
    runtime = AgentRuntime(config, identity)
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
            identity = ensure_identity_config(Path(tmp))
            config = Config(
                container_name="root",
                listen_host="127.0.0.1",
                listen_port=7100,
                admin_secret="root-secret",
                data_root=str(root_dir),
                federation={"name": "root", "host": "127.0.0.1", "port": 7100, "children": []},
            )
            runtime, server = await start_runtime(config, identity)
            async with server:
                deploy = await send_message(
                    "127.0.0.1",
                    7100,
                    signed(identity, "deploy_agent", {"source_code": AGENT_SOURCE, "activate_payload": {"hello": "world"}}),
                )
                assert deploy["status"] == "ok"
                instance_id = deploy["result"]["instance_id"]
                invoke = await send_message(
                    "127.0.0.1",
                    7100,
                    signed(identity, "invoke_agent", {"agent_id": instance_id, "message": {"x": 1}}),
                )
                assert invoke["status"] == "ok"
                assert invoke["result"]["result"]["payload"] == {"x": 1}
                assert instance_id in runtime.agents

    asyncio.run(scenario())


def test_clone_and_move_between_nodes():
    async def scenario():
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp) / "root"
            child_dir = Path(tmp) / "child"
            (root_dir / "docs").mkdir(parents=True)
            (child_dir / "docs").mkdir(parents=True)
            identity = ensure_identity_config(Path(tmp))

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

            root_runtime, root_server = await start_runtime(root_config, identity)
            child_runtime, child_server = await start_runtime(child_config, identity)

            async with root_server, child_server:
                deploy = await send_message(
                    "127.0.0.1",
                    7101,
                    signed(identity, "deploy_agent", {"source_code": AGENT_SOURCE, "activate_payload": {}}),
                )
                assert deploy["status"] == "ok"
                instance_id = deploy["result"]["instance_id"]

                clone_response = await send_message(
                    "127.0.0.1",
                    7101,
                    signed(identity, "invoke_agent", {"agent_id": instance_id, "message": {"command": "clone"}}),
                )
                assert clone_response["status"] == "ok"
                assert instance_id in root_runtime.agents
                assert any(record.agent_id == "test-agent" for record in child_runtime.agents.values())

                move_response = await send_message(
                    "127.0.0.1",
                    7101,
                    signed(identity, "invoke_agent", {"agent_id": instance_id, "message": {"command": "move"}}),
                )
                assert move_response["status"] == "ok"
                assert instance_id not in root_runtime.agents
                assert any(record.agent_id == "test-agent" for record in child_runtime.agents.values())

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


def test_same_agent_id_gets_unique_instance_sequence():
    async def scenario():
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = Path(tmp) / "root"
            (root_dir / "docs").mkdir(parents=True)
            identity = ensure_identity_config(Path(tmp))
            config = Config(
                container_name="root",
                listen_host="127.0.0.1",
                listen_port=7105,
                admin_secret="unused",
                data_root=str(root_dir),
                federation={"name": "root", "host": "127.0.0.1", "port": 7105, "children": []},
            )
            runtime, server = await start_runtime(config, identity)
            async with server:
                first = await send_message(
                    "127.0.0.1",
                    7105,
                    signed(identity, "deploy_agent", {"source_code": AGENT_SOURCE, "activate_payload": {}}),
                )
                second = await send_message(
                    "127.0.0.1",
                    7105,
                    signed(identity, "deploy_agent", {"source_code": AGENT_SOURCE, "activate_payload": {}}),
                )
                third = await send_message(
                    "127.0.0.1",
                    7105,
                    signed(identity, "deploy_agent", {"source_code": OTHER_AGENT_SOURCE, "activate_payload": {}}),
                )
                assert first["result"]["instance_id"] == "test-agent#1"
                assert second["result"]["instance_id"] == "test-agent#2"
                assert third["result"]["instance_id"] == "other-agent#1"
                assert len(runtime.agents) == 3

    asyncio.run(scenario())


def test_agent_can_return_to_stage():
    async def scenario():
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stage_dir = base / "stage"
            target_dir = base / "target"
            stage_dir.mkdir(parents=True)
            target_dir.mkdir(parents=True)

            identity = ensure_identity_config(base)
            source = (Path(__file__).resolve().parents[1] / "agents" / "demo" / "visitcontainer-and-go-back.py").read_text(encoding="utf-8")

            stage_config = Config(
                container_name="stage",
                listen_host="127.0.0.1",
                listen_port=7110,
                admin_secret="unused",
                data_root=str(stage_dir),
                federation={
                    "name": "stage",
                    "host": "127.0.0.1",
                    "port": 7110,
                    "children": [{"name": "target", "host": "127.0.0.1", "port": 7111, "children": []}],
                },
            )
            target_config = Config(
                container_name="target",
                listen_host="127.0.0.1",
                listen_port=7111,
                admin_secret="unused",
                data_root=str(target_dir),
                federation={"name": "target", "host": "127.0.0.1", "port": 7111, "children": []},
            )

            stage_runtime, stage_server = await start_runtime(stage_config, identity)
            target_runtime, target_server = await start_runtime(target_config, identity)

            async with stage_server, target_server:
                deploy = await send_message(
                    "127.0.0.1",
                    7110,
                    signed(
                        identity,
                        "deploy_agent",
                        {
                            "source_code": source,
                            "activate_payload": None,
                            "agent_metadata": {
                                "stage": {"name": "stage", "host": "127.0.0.1", "port": 7110},
                                "network": {
                                    "name": "stage",
                                    "host": "127.0.0.1",
                                    "port": 7110,
                                    "children": [{"name": "target", "host": "127.0.0.1", "port": 7111, "children": []}],
                                },
                            },
                        },
                    ),
                )
                assert deploy["status"] == "ok"
                stage_instance_id = deploy["result"]["instance_id"]

                dispatch = await send_message(
                    "127.0.0.1",
                    7110,
                    signed(
                        identity,
                        "dispatch_agent",
                        {
                            "agent_id": stage_instance_id,
                            "destination": "target",
                            "mode": "move",
                            "activate_payload": {},
                            "metadata_patch": {
                                "stage": {"name": "stage", "host": "127.0.0.1", "port": 7110},
                                "network": {
                                    "name": "stage",
                                    "host": "127.0.0.1",
                                    "port": 7110,
                                    "children": [{"name": "target", "host": "127.0.0.1", "port": 7111, "children": []}],
                                },
                            },
                        },
                    ),
                )
                assert dispatch["status"] == "ok"
                assert any(record.agent_id == "visitcontainer-and-go-back" for record in stage_runtime.agents.values())
                assert not any(record.agent_id == "visitcontainer-and-go-back" for record in target_runtime.agents.values())
                returned_record = next(record for record in stage_runtime.agents.values() if record.agent_id == "visitcontainer-and-go-back")
                returned = returned_record.last_result
                assert returned["status"] == "returned-to-stage"
                assert returned["report"]["container"] == "target"

    asyncio.run(scenario())
