AGENT_ID = "lab-payload-echo"
AGENT_NAME = "Lab Payload Echo"
AGENT_SECRET = "lab-payload-echo-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        return {
            "container": ctx.container_name,
            "payload": payload,
            "resources": await ctx.resources(),
        }

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
