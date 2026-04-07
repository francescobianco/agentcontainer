AGENT_ID = "maintain-echo-env-probe"
AGENT_NAME = "Maintain Echo Env Probe"
AGENT_SECRET = "maintain-echo-env-probe-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        result = await ctx.run(["env"], timeout=int(payload.get("timeout", 5)))
        return {"container": ctx.container_name, "result": result}

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
