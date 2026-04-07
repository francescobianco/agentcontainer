AGENT_ID = "basic-ping-agent"
AGENT_NAME = "Basic Ping Agent"
AGENT_SECRET = "basic-ping-agent-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        return {
            "status": "ok",
            "container": ctx.container_name,
            "payload": payload,
        }

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
