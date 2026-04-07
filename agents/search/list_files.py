AGENT_ID = "search-list-files"
AGENT_NAME = "Search List Files"
AGENT_SECRET = "search-list-files-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        prefix = payload.get("prefix", "")
        resources = await ctx.resources()
        files = [item for item in resources.get("files", []) if item.startswith(prefix)]
        return {"container": ctx.container_name, "files": files}

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
