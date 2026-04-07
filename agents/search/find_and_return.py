AGENT_ID = "search-find-and-return"
AGENT_NAME = "Search Find And Return"
AGENT_SECRET = "search-find-and-return-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        report = payload.get("report")
        stage = await ctx.stage()
        if report is not None and stage and ctx.container_name == stage["name"]:
            return {"status": "returned-to-stage", "report": report}

        query = payload.get("query", "scacchi")
        report = {
            "container": ctx.container_name,
            "query": query,
            "hits": await ctx.search_files(query, path=payload.get("path", "."), limit=int(payload.get("limit", 25))),
        }
        if stage:
            return await ctx.return_to_stage({"report": report})
        return report

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
