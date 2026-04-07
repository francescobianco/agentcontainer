AGENT_ID = "network-tree-walker"
AGENT_NAME = "Network Tree Walker"
AGENT_SECRET = "network-tree-walker-secret"


class Agent:
    # The constructor stores per-instance memory that survives while the same
    # agent instance remains alive inside a container.
    def __init__(self) -> None:
        # `visited_map` tracks every visited node keyed by node name.
        self.visited_map = {}
        # `travel_log` keeps a chronological list of hops and actions.
        self.travel_log = []

    # `on_activate` is called when the agent is first activated in a container.
    async def on_activate(self, ctx, payload):
        # Delegate all behavior to the shared handler.
        return await self._walk(ctx, payload)

    # `on_message` is also supported so the same agent can be reinvoked.
    async def on_message(self, ctx, payload):
        # Reuse the same walking logic for consistency.
        return await self._walk(ctx, payload)

    # This helper traverses the visible dynamic tree using the local map.
    async def _walk(self, ctx, payload):
        # If the agent is back on its stage container, stop immediately and
        # expose the final state instead of restarting the traversal.
        stage = await ctx.stage()
        if stage and ctx.container_name == stage.get("name"):
            return {
                "status": "returned-to-stage",
                "container": ctx.container_name,
                "visited_map": dict(self.visited_map),
                "travel_log": list(self.travel_log),
                "payload": payload,
            }

        # Restore the visited map carried by the agent payload, if any.
        incoming_map = payload.get("visited_map", {})
        if incoming_map:
            self.visited_map = dict(incoming_map)

        # Restore the chronological travel log carried across hops.
        incoming_log = payload.get("travel_log", [])
        if incoming_log:
            self.travel_log = list(incoming_log)

        # Read the container-local network view.
        network = await ctx.networks()
        # Read the current container resources to enrich the map.
        resources = await ctx.resources()
        # Read the current list of capabilities exposed to agents.
        capabilities = await ctx.capabilities()

        # Register the current node in the internal visited map.
        self.visited_map[ctx.container_name] = {
            "container": ctx.container_name,
            "children": [child["name"] for child in network.get("children", [])],
            "files": resources.get("files", []),
            "capabilities": capabilities,
        }

        # Add a trace entry for this visit.
        self.travel_log.append(
            {
                "container": ctx.container_name,
                "children_seen": [child["name"] for child in network.get("children", [])],
            }
        )

        # Build the list of unvisited children by consulting the internal map.
        unvisited_children = [
            child for child in network.get("children", []) if child["name"] not in self.visited_map
        ]

        # The current result always includes the accumulated map and log.
        result = {
            "container": ctx.container_name,
            "visited_map": dict(self.visited_map),
            "travel_log": list(self.travel_log),
            "spawned": [],
        }

        # Spawn one clone for each unvisited child in the current subtree.
        for child in unvisited_children:
            # Build the payload passed to the next hop.
            child_payload = {
                "visited_map": dict(self.visited_map),
                "travel_log": list(self.travel_log),
            }
            # Clone into that child so the subtree is explored recursively.
            response = await ctx.clone(child["name"], child_payload)
            # Keep the response for observability.
            result["spawned"].append(
                {
                    "destination": child["name"],
                    "response": response,
                }
            )

        # If this agent was launched from a stage and no more children remain,
        # return the collected map to the stage.
        stage = await ctx.stage()
        if stage and not unvisited_children:
            return await ctx.return_to_stage(
                {
                    "report": {
                        "container": ctx.container_name,
                        "visited_map": dict(self.visited_map),
                        "travel_log": list(self.travel_log),
                    }
                }
            )

        # Otherwise return the local state.
        return result
