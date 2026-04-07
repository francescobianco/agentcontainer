AGENT_ID = "maintain-process-snapshot"
AGENT_NAME = "Maintain Process Snapshot"
AGENT_SECRET = "maintain-process-snapshot-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        command = payload.get("command", ["ps", "aux"])
        result = await ctx.run(command, timeout=int(payload.get("timeout", 5)))
        return {"container": ctx.container_name, "command": command, "result": result}

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
