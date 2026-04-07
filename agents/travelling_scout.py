AGENT_ID = "travelling-scout"
AGENT_NAME = "Travelling Scout"
AGENT_SECRET = "travelling-scout-secret"


class Agent:
    def __init__(self) -> None:
        self.visited = []
        self.findings = []

    async def on_activate(self, ctx, payload):
        if payload:
            return await self._handle(ctx, payload)
        return {"status": "activated", "container": ctx.container_name}

    async def on_message(self, ctx, payload):
        return await self._handle(ctx, payload)

    async def _handle(self, ctx, payload):
        action = payload.get("action", "tour")
        if action == "status":
            return {
                "container": ctx.container_name,
                "visited": list(self.visited),
                "findings": list(self.findings),
            }

        query = payload.get("query", "scacchi")
        incoming_visited = payload.get("visited", [])
        if incoming_visited:
            self.visited = list(dict.fromkeys(incoming_visited + self.visited))
        if ctx.container_name not in self.visited:
            self.visited.append(ctx.container_name)

        local_hits = await ctx.search_files(query, path="docs")
        result = {
            "container": ctx.container_name,
            "query": query,
            "hits": local_hits,
            "visited": list(self.visited),
        }
        self.findings.append(result)

        if action == "move" and payload.get("destination"):
            move_payload = {
                "action": "tour",
                "query": query,
                "visited": list(self.visited),
            }
            await ctx.log(f"moving to {payload['destination']}")
            remote = await ctx.move(payload["destination"], move_payload)
            return {"mode": "move", "remote": remote, "local": result}

        if payload.get("tour", True):
            network = await ctx.networks()
            clones = []
            for child in network.get("children", []):
                if child["name"] in self.visited:
                    continue
                clone_payload = {
                    "action": "tour",
                    "query": query,
                    "visited": list(self.visited),
                    "tour": True,
                }
                remote = await ctx.clone(child["name"], clone_payload)
                clones.append({"destination": child["name"], "response": remote})
            result["clones"] = clones

        return result
