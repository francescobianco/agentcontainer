# agentcontainer

`agentcontainer` is a TCP runtime for mobile agents written in Python. Each agent is sent as a pure Python file authenticated at the message level, loaded live into the destination container, and can use host primitives for filesystem access, local processes, HTTP networking, and mobility across federated tree-structured containers.

## Goals

- Transport and activate Python agents as pure Python files.
- Provide explicit per-message authentication through HMAC.
- Keep the agent secret embedded inside the agent itself.
- Avoid coupling the container to a specific LLM provider.
- Provide base primitives for clone, move, networks, filesystem, and HTTP.
- Support `agentcontainer` federation in tree topologies.
- Provide a Docker environment to test deployment, cloning, travel, and distributed search.

## Project Status

This repository currently implements a working base:

- `asyncio` TCP server with a JSON Lines protocol.
- Unified CLI with `server`, `send`, `run`, `invoke`, and `tree`.
- Python agent loader with `on_activate` and `on_message` lifecycle hooks.
- Host primitives: `read_file`, `search_files`, `run`, `http_request`, `clone`, `move`, `networks`, `capabilities`, `resources`, `return_to_stage`.
- Static tree federation configured through JSON files.
- Example `travelling_scout` agent that visits nodes and searches files for a query.
- Automated tests for authentication, deploy/invoke, and clone/move.
- `docker compose` environment with three federated containers.

## Quick Architecture

Each message is a single JSON line with this structure:

```json
{
  "type": "deploy_agent",
  "sender": "admin",
  "timestamp": 1770000000,
  "nonce": "uuid",
  "payload": {},
  "signature": "hex-hmac"
}
```

The signature is computed on the canonical message without `signature`.

Main message types:

- `deploy_agent`: administrative deployment of an agent source file.
- `invoke_agent`: invoke an already active agent.
- `receive_agent`: reception of an agent that was cloned or moved.
- `list_agents`: list loaded agents.
- `describe_container`: node metadata.
- `network_tree`: configured federation topology.

## Agent Contract

An agent is a Python file that defines at least:

```python
AGENT_ID = "travelling-scout"
AGENT_SECRET = "change-me"

class Agent:
    async def on_activate(self, ctx, payload):
        ...

    async def on_message(self, ctx, payload):
        ...
```

`ctx` exposes host and mobility primitives. The agent carries its own secret and uses it implicitly when the container performs `clone` or `move`.

## CLI

`agentcontainer` is also the user CLI you can install on your workstation to send agents to remote nodes. The agent exchange always remains a pure Python source file; stage, routing, and authentication travel as metadata separate from the file.

Examples:

```bash
agentcontainer server 0.0.0.0:7007
agentcontainer send agents/demo/visitcontainer-and-go-back.py 0.0.0.0:7007
agentcontainer run agents/demo/visitcontainer-and-go-back.py
agentcontainer list-agents 127.0.0.1:7007
```

`agentcontainer server HOST:PORT` starts a node with a ready-to-use development configuration. `agentcontainer send AGENT.py HOST:PORT` automatically opens a local stage, ships the pure Python file to the remote node, and waits until the agent returns to the stage or until you press `Ctrl+C`. `agentcontainer run AGENT.py` does the same thing but also creates a local sandbox destination node for quick testing.

To start a node as a service:

```bash
agentcontainer server 0.0.0.0:7007
```

## Local Startup

```bash
make install
pytest -q
agentcontainer server 0.0.0.0:7007
```

`make install` uses `pipx` when available, which is the correct choice on systems that enforce PEP 668. If `pipx` is not available, it creates `.venv/` and a local `./bin/agentcontainer` wrapper.

In another terminal:

```bash
agentcontainer send agents/demo/visitcontainer-and-go-back.py 0.0.0.0:7007
```

If the remote node must call back into your stage through a different IP than the one detected automatically, use `--stage-host`.

## Federated Docker Environment

Start it with:

```bash
docker compose up --build
```

Deploy the agent to the root node:

```bash
agentcontainer send agents/demo/visitcontainer-and-go-back.py 127.0.0.1:7000 --secret root-admin-secret
```

List agents:

```bash
agentcontainer list-agents 127.0.0.1:7000 --secret root-admin-secret
```

Topology:

```bash
agentcontainer tree 127.0.0.1:7000 --secret root-admin-secret
```

## Planned Demo

The Docker containers mount different datasets:

- `root`: general documents.
- `department-a`: documents that mention chess.
- `department-b`: technical documents and another chess-related reference.

The `travelling_scout` agent:

- searches the query locally;
- reads the federated tree;
- clones itself into children that have not yet been visited;
- can move to a specific node;
- accumulates local results and returns them through `invoke`.

The agent [visitcontainer-and-go-back.py](/home/francesco/Develop/_/agentcontainer/agents/demo/visitcontainer-and-go-back.py):

- arrives in the target container;
- reads the primitives and resources exposed to agents;
- prepares a report;
- returns to the stage it came from;
- automatically ends the `send` or `run` CLI flow when it comes back.

## Security and Current Limits

- The trust model is intentionally minimal: message integrity is guaranteed by HMAC, but the first `receive_agent` on a new node relies on the secret transported by the agent.
- The runtime executes dynamic Python code: it should only be used in trusted or strongly isolated environments.
- Local primitives are powerful. Production usage requires process sandboxing, quotas, ACLs, auditing, and network/filesystem policy controls.
- Federation in the current base is static and configuration-driven; dynamic discovery and PKI are not included.

## Main Files

- [README.md](/home/francesco/Develop/_/agentcontainer/README.md)
- [DESIGN.md](/home/francesco/Develop/_/agentcontainer/DESIGN.md)
- [pyproject.toml](/home/francesco/Develop/_/agentcontainer/pyproject.toml)
- [src/agentcontainer/server.py](/home/francesco/Develop/_/agentcontainer/src/agentcontainer/server.py)
- [src/agentcontainer/runtime.py](/home/francesco/Develop/_/agentcontainer/src/agentcontainer/runtime.py)
- [src/agentcontainer/client.py](/home/francesco/Develop/_/agentcontainer/src/agentcontainer/client.py)
- [agents/demo/travelling_scout.py](/home/francesco/Develop/_/agentcontainer/agents/demo/travelling_scout.py)
- [docker-compose.yml](/home/francesco/Develop/_/agentcontainer/docker-compose.yml)
- [scripts/generate_whitepaper_pdf.py](/home/francesco/Develop/_/agentcontainer/scripts/generate_whitepaper_pdf.py)
- [WHITEPAPER.pdf](/home/francesco/Develop/_/agentcontainer/WHITEPAPER.pdf)

## Whitepaper

The whitepaper source is in [WHITEPAPER.md](/home/francesco/Develop/_/agentcontainer/WHITEPAPER.md), and the PDF is generated with:

```bash
python3 scripts/generate_whitepaper_pdf.py
```
