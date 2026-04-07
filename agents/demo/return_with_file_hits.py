AGENT_ID = "demo-return-with-file-hits"
AGENT_NAME = "Demo Return With File Hits"
AGENT_SECRET = "demo-return-with-file-hits-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        report = payload.get("report")
        stage = await ctx.stage()
        if report is not None and stage and ctx.container_name == stage["name"]:
            return {"status": "returned-to-stage", "report": report}

        query = payload.get("query", "scacchi")
        hits = await ctx.search_files(query, path=payload.get("path", "."), limit=25)
        report = {
            "container": ctx.container_name,
            "query": query,
            "hits": hits,
            "resources": await ctx.resources(),
        }
        return await ctx.return_to_stage({"report": report})

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
