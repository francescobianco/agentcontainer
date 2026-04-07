from __future__ import annotations

import asyncio
import json
import time
import types
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .auth import attach_signature
from .config import Config
from .protocol import read_message, write_message


@dataclass(slots=True)
class AgentRecord:
    agent_id: str
    secret: str
    source_code: str
    instance: Any
    module: types.ModuleType
    metadata: dict[str, Any] = field(default_factory=dict)
    last_result: Any = None


class AgentContext:
    def __init__(self, runtime: "AgentRuntime", agent_id: str) -> None:
        self._runtime = runtime
        self.agent_id = agent_id

    @property
    def container_name(self) -> str:
        return self._runtime.config.container_name

    async def log(self, message: str) -> None:
        self._runtime.log(f"[agent:{self.agent_id}] {message}")

    async def networks(self) -> dict[str, Any]:
        record = self._runtime.agents[self.agent_id]
        return record.metadata.get("network", self._runtime.config.federation)

    async def capabilities(self) -> list[str]:
        return [
            "log",
            "networks",
            "capabilities",
            "resources",
            "stage",
            "return_to_stage",
            "read_file",
            "search_files",
            "run",
            "http_request",
            "clone",
            "move",
        ]

    async def resources(self) -> dict[str, Any]:
        return self._runtime.describe_resources()

    async def stage(self) -> dict[str, Any] | None:
        record = self._runtime.agents[self.agent_id]
        return record.metadata.get("stage")

    async def read_file(self, path: str, limit: int = 65536) -> str:
        resolved = self._runtime.resolve_path(path)
        return resolved.read_text(encoding="utf-8")[:limit]

    async def search_files(self, query: str, path: str = ".", limit: int = 100) -> list[dict[str, Any]]:
        root = self._runtime.resolve_path(path)
        matches: list[dict[str, Any]] = []
        for candidate in root.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                content = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if query.lower() in content.lower():
                matches.append(
                    {
                        "path": str(candidate.relative_to(self._runtime.data_root)),
                        "preview": content[:160],
                    }
                )
                if len(matches) >= limit:
                    break
        return matches

    async def run(self, command: list[str], timeout: int = 10) -> dict[str, Any]:
        if not self._runtime.config.allow_subprocess:
            raise RuntimeError("subprocess primitive disabled")
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._runtime.data_root),
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("process timeout")
        return {
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }

    async def http_request(
        self,
        method: str,
        url: str,
        body: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 20,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._blocking_http_request,
            method,
            url,
            body,
            headers or {},
            timeout,
        )

    def _blocking_http_request(
        self, method: str, url: str, body: str | None, headers: dict[str, str], timeout: int
    ) -> dict[str, Any]:
        data = body.encode("utf-8") if body is not None else None
        request = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8", errors="replace")
                return {"status": response.status, "body": payload, "headers": dict(response.headers)}
        except urllib.error.HTTPError as exc:
            return {"status": exc.code, "body": exc.read().decode("utf-8", errors="replace"), "headers": dict(exc.headers)}

    async def clone(self, destination: str, activate_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._runtime.transfer_agent(
            agent_id=self.agent_id,
            destination=destination,
            mode="clone",
            activate_payload=activate_payload or {},
        )

    async def move(self, destination: str, activate_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._runtime.transfer_agent(
            agent_id=self.agent_id,
            destination=destination,
            mode="move",
            activate_payload=activate_payload or {},
        )

    async def return_to_stage(self, activate_payload: dict[str, Any] | None = None, mode: str = "move") -> dict[str, Any]:
        stage = await self.stage()
        if not stage:
            raise RuntimeError("agent was not started from a stage")
        return await self._runtime.transfer_agent(
            agent_id=self.agent_id,
            destination=stage["name"],
            mode=mode,
            activate_payload=activate_payload or {},
        )


class AgentRuntime:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.data_root = Path(config.data_root).resolve()
        self.agents: dict[str, AgentRecord] = {}

    def log(self, message: str) -> None:
        print(f"[{self.config.container_name}] {message}", flush=True)

    def resolve_path(self, path: str) -> Path:
        candidate = (self.data_root / path).resolve()
        if self.data_root not in candidate.parents and candidate != self.data_root:
            raise ValueError("path escapes data_root")
        return candidate

    def _load_module(self, source_code: str, module_name: str) -> types.ModuleType:
        module = types.ModuleType(module_name)
        exec(compile(source_code, module_name, "exec"), module.__dict__)
        return module

    def parse_agent_manifest(self, source_code: str) -> dict[str, Any]:
        module = self._load_module(source_code, "__agent_manifest__")
        if not hasattr(module, "AGENT_ID") or not hasattr(module, "AGENT_SECRET") or not hasattr(module, "Agent"):
            raise ValueError("agent source must define AGENT_ID, AGENT_SECRET and Agent")
        return {
            "agent_id": getattr(module, "AGENT_ID"),
            "agent_secret": getattr(module, "AGENT_SECRET"),
            "agent_name": getattr(module, "AGENT_NAME", getattr(module, "AGENT_ID")),
        }

    async def deploy_agent(
        self,
        source_code: str,
        activate_payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        manifest = self.parse_agent_manifest(source_code)
        module = self._load_module(source_code, f"agent_{manifest['agent_id']}")
        instance = module.Agent()
        record = AgentRecord(
            agent_id=manifest["agent_id"],
            secret=manifest["agent_secret"],
            source_code=source_code,
            instance=instance,
            module=module,
            metadata={"agent_name": manifest["agent_name"], **(metadata or {})},
        )
        self.agents[record.agent_id] = record
        if hasattr(instance, "on_activate"):
            ctx = AgentContext(self, record.agent_id)
            record.last_result = await instance.on_activate(ctx, activate_payload or {})
        return {"agent_id": record.agent_id, "status": "active", "activate_result": record.last_result}

    async def invoke_agent(self, agent_id: str, message: dict[str, Any]) -> dict[str, Any]:
        record = self.agents[agent_id]
        if not hasattr(record.instance, "on_message"):
            raise ValueError("agent does not implement on_message")
        ctx = AgentContext(self, agent_id)
        record.last_result = await record.instance.on_message(ctx, message)
        return {"agent_id": agent_id, "result": record.last_result}

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": record.agent_id,
                "agent_name": record.metadata.get("agent_name", record.agent_id),
                "last_result": record.last_result,
            }
            for record in self.agents.values()
        ]

    def describe_container(self) -> dict[str, Any]:
        return {
            "container_name": self.config.container_name,
            "listen_host": self.config.listen_host,
            "listen_port": self.config.listen_port,
            "children": self.config.federation.get("children", []),
        }

    def describe_resources(self) -> dict[str, Any]:
        files: list[str] = []
        if self.data_root.exists():
            for candidate in sorted(self.data_root.rglob("*")):
                if candidate.is_file():
                    files.append(str(candidate.relative_to(self.data_root)))
                if len(files) >= 50:
                    break
        return {
            "container": self.describe_container(),
            "data_root": str(self.data_root),
            "files": files,
            "allow_subprocess": self.config.allow_subprocess,
        }

    async def dispatch_agent(
        self,
        *,
        agent_id: str,
        destination: str,
        mode: str,
        activate_payload: dict[str, Any],
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = self.agents[agent_id]
        if metadata_patch:
            record.metadata.update(metadata_patch)
        return await self.transfer_agent(
            agent_id=agent_id,
            destination=destination,
            mode=mode,
            activate_payload=activate_payload,
        )

    async def transfer_agent(
        self,
        *,
        agent_id: str,
        destination: str,
        mode: str,
        activate_payload: dict[str, Any],
    ) -> dict[str, Any]:
        record = self.agents[agent_id]
        node = self._find_destination(destination, record.metadata.get("network"))
        message = {
            "type": "receive_agent",
            "sender": agent_id,
            "timestamp": int(time.time()),
            "nonce": f"{agent_id}-{mode}-{node['name']}",
            "payload": {
                "source_code": record.source_code,
                "activate_payload": activate_payload,
                "mode": mode,
                "agent_secret": record.secret,
                "agent_metadata": record.metadata,
            },
        }
        signed = attach_signature(message, record.secret)
        response = await self._send_remote(node["host"], int(node["port"]), signed)
        if mode == "move" and response.get("status") == "ok":
            self.agents.pop(agent_id, None)
        return response

    def _find_destination(self, destination: str, network: dict[str, Any] | None = None) -> dict[str, Any]:
        stack = [network or self.config.federation]
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            if node.get("name") == destination:
                return node
            stack.extend(reversed(node.get("children", [])))
        raise KeyError(f"unknown destination {destination}")

    async def _send_remote(self, host: str, port: int, message: dict[str, Any]) -> dict[str, Any]:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            await write_message(writer, message)
            return await read_message(reader)
        finally:
            writer.close()
            await writer.wait_closed()

    def resolve_secret_for_message(self, message: dict[str, Any]) -> str:
        sender = message.get("sender")
        if sender == "admin":
            return self.config.admin_secret
        if sender in self.agents:
            return self.agents[sender].secret
        if message.get("type") == "receive_agent":
            secret = message.get("payload", {}).get("agent_secret")
            if not isinstance(secret, str) or not secret:
                raise ValueError("receive_agent requires payload.agent_secret")
            return secret
        raise ValueError(f"unknown sender {sender}")

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        message_type = message["type"]
        payload = message.get("payload", {})
        if message_type == "deploy_agent":
            result = await self.deploy_agent(
                payload["source_code"],
                payload.get("activate_payload", {}),
                payload.get("agent_metadata"),
            )
            return {"status": "ok", "result": result}
        if message_type == "receive_agent":
            result = await self.deploy_agent(
                payload["source_code"],
                payload.get("activate_payload", {}),
                payload.get("agent_metadata"),
            )
            return {"status": "ok", "result": result}
        if message_type == "dispatch_agent":
            result = await self.dispatch_agent(
                agent_id=payload["agent_id"],
                destination=payload["destination"],
                mode=payload.get("mode", "move"),
                activate_payload=payload.get("activate_payload", {}),
                metadata_patch=payload.get("metadata_patch"),
            )
            return {"status": "ok", "result": result}
        if message_type == "invoke_agent":
            result = await self.invoke_agent(payload["agent_id"], payload.get("message", {}))
            return {"status": "ok", "result": result}
        if message_type == "list_agents":
            return {"status": "ok", "result": self.list_agents()}
        if message_type == "describe_container":
            return {"status": "ok", "result": self.describe_container()}
        if message_type == "network_tree":
            return {"status": "ok", "result": self.config.federation}
        raise ValueError(f"unsupported message type {message_type}")
