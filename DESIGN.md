# agentcontainer Design

## 1. Vision

`agentcontainer` is an execution node for mobile agents. An agent is not a database record or a serialized function: it is transferable Python source code, signed at the message level, loaded into memory by a container, and able to request local primitives from the container to act on the system or move across other federated containers.

The key separation is:

- the container provides the operational substrate;
- the agent contains identity, secret, logic, and external service configuration;
- access to LLMs or external APIs is decided by the agent, not by the container.

## 2. Requirements Mapped to Architecture

### 2.1 Authenticated Messages

Each message received on the TCP socket contains:

- `type`
- `sender`
- `timestamp`
- `nonce`
- `payload`
- `signature`

The signature is `HMAC-SHA256(secret, canonical_json(message_without_signature))`.

The server validates:

- timestamp freshness;
- nonce presence;
- signature validity;
- sender authorization for the requested message type.

### 2.2 Agents as Python Files

The agent is distributed as Python source text.

Minimum required manifest:

- `AGENT_ID`
- `AGENT_SECRET`
- `class Agent`

Supported hooks:

- `on_activate(ctx, payload)`
- `on_message(ctx, payload)`

### 2.3 Secret Carried by the Agent

The container is not the source of truth for the agent application secret. During deploy or `receive_agent`, the agent source carries the secret that the node uses to:

- verify messages signed by that agent once it is already registered;
- re-sign `clone` and `move` transfers;
- preserve identity consistency across nodes.

### 2.4 Host Primitives

The current base exposes these primitives:

- `networks()`: return the configured federated tree.
- `read_file(path)`: controlled read access within `data_root`.
- `search_files(query)`: full-text search on text files.
- `run(command)`: run a local process with a timeout.
- `http_request(...)`: outbound HTTP for LLMs or external APIs.
- `clone(destination, payload)`: copy the agent to another node and activate it there.
- `move(destination, payload)`: same as `clone`, then remove the local instance.
- `log(message)`: structured logging.

### 2.5 Tree Federation

The federation model is intentionally hierarchical:

- every node knows its children;
- the tree is declared in configuration;
- agents see the tree through `networks`;
- mobility always happens through the target node endpoint and port.

The current base does not implement dynamic discovery, consensus, opportunistic routing, or mesh topologies.

## 3. Protocol

### 3.1 Transport

- TCP
- framing: JSON Lines
- one request, one response

### 3.2 Message Types

#### `deploy_agent`

Expected sender: `admin`

Payload:

- `source_code`
- optional `activate_payload`

Effect:

- parse the manifest
- load the module
- instantiate the agent
- optionally invoke `on_activate`

#### `receive_agent`

Expected sender: an agent or an admin

Payload:

- `source_code`
- `activate_payload`
- `mode`: `clone` or `move`
- `trace`: already visited hops

Effect:

- register or update the agent
- invoke `on_activate`

#### `invoke_agent`

Expected sender: `admin`

Payload:

- `agent_id`
- `message`

Effect:

- invoke `on_message`

#### `network_tree`

Return the static tree defined in the local config.

#### `describe_container`

Return node name, port, and configured children.

## 4. Internal Runtime

### 4.1 Agent Registry

For each active agent, the node keeps:

- `agent_id`
- `agent_secret`
- `source_code`
- `instance`
- `module`
- `last_result`
- `metadata`

### 4.2 Dynamic Loader

The loader:

1. executes the source in a dedicated `ModuleType`;
2. extracts the manifest and the `Agent` class;
3. instantiates the class;
4. stores the instance in the registry.

### 4.3 Context

The `ctx` object passed to the agent wraps the runtime reference and the current agent identity. Primitives are therefore contextual rather than global.

## 5. Agent Mobility

### 5.1 Clone

`clone(destination, payload)`:

1. resolve the target node from the federated tree;
2. prepare a `receive_agent` message;
3. sign it using `AGENT_SECRET`;
4. send the source code;
5. let the target node load and optionally activate the clone;
6. keep the local instance alive.

### 5.2 Move

`move(destination, payload)`:

1. execute the `clone` flow;
2. if the target returns `ok`, deregister the local agent.

### 5.3 Tracing

To avoid trivial loops, the base supports a `trace` field that the agent can use to mark visited nodes. The runtime does not impose a global policy, but it provides the mechanism.

## 6. LLM Model

`agentcontainer` does not embed an LLM engine. Responsibility stays with the agent:

- the agent may carry its own URL, model id, and API key;
- the agent may use `http_request` or Python libraries imported inside its own source;
- the container remains provider-neutral.

This avoids architectural lock-in and keeps the agent portable.

## 7. Security

### 7.1 Properties Provided by the Current Base

- message integrity;
- sender identification through a shared secret;
- separation between admin secret and agent secret;
- a small and readable protocol surface.

### 7.2 Open Risks

- arbitrary code execution;
- weak bootstrap for a first-time arriving agent;
- lack of OS-level sandboxing;
- lack of fine-grained primitive restrictions;
- no secret rotation, revocation, attestation, or robust audit trail.

### 7.3 Hardening Roadmap

- asymmetric signatures with distributed public keys;
- per-agent sandboxing through subprocesses or microVMs;
- capability tokens for primitives;
- CPU, RAM, and I/O quotas;
- append-only event sourcing and auditing;
- federation discovery with trust anchors.

## 8. Project Layout

### 8.1 Package

- `auth.py`: HMAC, signing, verification.
- `cli.py`: unified CLI with `server`, `send`, `run`, and `invoke`.
- `protocol.py`: JSON Lines framing.
- `config.py`: config loading.
- `runtime.py`: registry, loader, context, and primitives.
- `server.py`: TCP server and dispatch.
- `client.py`: secondary control CLI.

### 8.2 Demo Material

- `agents/demo/travelling_scout.py`: mobile search agent.
- `examples/*.json`: node configs.
- `fixtures/*`: demo dataset.
- `docker-compose.yml`: federated lab.

## 9. Lab Usage Scenario

Each workstation in a lab runs an `agentcontainer`. An agent is deployed on the root node with the request:

- explore the tree;
- search for files that mention chess;
- leave copies in departments;
- return partial results on each node.

This repository implements a demonstrative version of exactly that scenario.

## 10. Local Testing Mode

The CLI includes `agentcontainer run <agent.py>`.

This mode:

- starts an isolated temporary local server;
- exposes a dedicated or configurable local `data_root`;
- automatically sends the agent to the server that was just started;
- can optionally invoke the agent immediately after deployment;
- stops the server when the test ends.

The goal is to support rapid agent development and debugging without depending on an already running departmental node. Even when a machine already has an `agentcontainer server`, `run` remains useful for isolated tests on a dedicated port.

## 11. Design Decisions

- pure Python and `asyncio` to reduce startup friction;
- custom TCP instead of HTTP to keep the protocol minimal;
- JSON Lines instead of a proprietary binary framing;
- static federation before discovery;
- an "unsafe by design" runtime to prioritize the conceptual model, with hardening deferred.
