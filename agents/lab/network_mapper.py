AGENT_ID = "lab-network-mapper"
AGENT_NAME = "Lab Network Mapper"
AGENT_SECRET = "lab-network-mapper-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        return {
            "container": ctx.container_name,
            "network": await ctx.networks(),
            "stage": await ctx.stage(),
        }

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
