AGENT_ID = "basic-inspect-primitives"
AGENT_NAME = "Basic Inspect Primitives"
AGENT_SECRET = "basic-inspect-primitives-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        return {
            "container": ctx.container_name,
            "capabilities": await ctx.capabilities(),
            "resources": await ctx.resources(),
        }

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
