AGENT_ID = "search-find-text"
AGENT_NAME = "Search Find Text"
AGENT_SECRET = "search-find-text-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        query = payload.get("query", "chess")
        path = payload.get("path", ".")
        limit = int(payload.get("limit", 25))
        return {
            "container": ctx.container_name,
            "query": query,
            "hits": await ctx.search_files(query, path=path, limit=limit),
        }

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
