AGENT_ID = "visitcontainer-and-go-back"
AGENT_NAME = "Visit Container And Go Back"
AGENT_SECRET = "visitcontainer-and-go-back-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        report = payload.get("report")
        stage = await ctx.stage()
        if report is not None and stage and ctx.container_name == stage["name"]:
            return {
                "status": "returned-to-stage",
                "stage": stage["name"],
                "report": report,
            }

        report = {
            "container": ctx.container_name,
            "stage": stage,
            "capabilities": await ctx.capabilities(),
            "resources": await ctx.resources(),
            "network": await ctx.networks(),
        }
        return await ctx.return_to_stage({"report": report})

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
