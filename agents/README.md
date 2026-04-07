# Agent Catalog

Initial collection of agents organized by category.

- `basic/`: minimal agents for smoke tests and basic introspection.
- `demo/`: demonstration agents for stage, travel, and tours.
- `search/`: agents focused on finding information in local files.
- `maintain/`: agents for operational snapshots and maintenance tasks.
- `lab/`: experimental agents for test and lab environments.
- `network/`: agents that traverse the federated tree and reason about node topology.

Each file is a pure Python agent that can be sent directly with:

```bash
agentcontainer send agents/basic/ping_agent.py 0.0.0.0:7007
```
