AGENT_ID = "maintain-disk-report"
AGENT_NAME = "Maintain Disk Report"
AGENT_SECRET = "maintain-disk-report-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        resources = await ctx.resources()
        return {
            "container": ctx.container_name,
            "data_root": resources.get("data_root"),
            "file_count": len(resources.get("files", [])),
            "allow_subprocess": resources.get("allow_subprocess"),
        }

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
