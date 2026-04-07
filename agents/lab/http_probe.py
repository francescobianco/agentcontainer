AGENT_ID = "lab-http-probe"
AGENT_NAME = "Lab HTTP Probe"
AGENT_SECRET = "lab-http-probe-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        url = payload.get("url", "https://example.com")
        result = await ctx.http_request("GET", url, timeout=int(payload.get("timeout", 10)))
        return {"container": ctx.container_name, "url": url, "result": result}

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
