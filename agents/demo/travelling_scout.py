AGENT_ID = "demo-travelling-scout"
AGENT_NAME = "Demo Travelling Scout"
AGENT_SECRET = "demo-travelling-scout-secret"


class Agent:
    def __init__(self) -> None:
        self.visited = []
        self.findings = []

    async def on_activate(self, ctx, payload):
        return await self._handle(ctx, payload)

    async def on_message(self, ctx, payload):
        return await self._handle(ctx, payload)

    async def _handle(self, ctx, payload):
        query = payload.get("query", "scacchi")
        incoming_visited = payload.get("visited", [])
        if incoming_visited:
            self.visited = list(dict.fromkeys(incoming_visited + self.visited))
        if ctx.container_name not in self.visited:
            self.visited.append(ctx.container_name)

        hits = await ctx.search_files(query, path=payload.get("path", "."), limit=20)
        result = {
            "container": ctx.container_name,
            "query": query,
            "visited": list(self.visited),
            "hits": hits,
        }
        self.findings.append(result)

        if payload.get("tour", True):
            tree = await ctx.networks()
            children = tree.get("children", [])
            clones = []
            for child in children:
                if child["name"] in self.visited:
                    continue
                clones.append(
                    {
                        "destination": child["name"],
                        "response": await ctx.clone(
                            child["name"],
                            {"query": query, "tour": True, "visited": list(self.visited), "path": payload.get("path", ".")},
                        ),
                    }
                )
            result["clones"] = clones
        return result
