AGENT_ID = "basic-read-docs-preview"
AGENT_NAME = "Basic Read Docs Preview"
AGENT_SECRET = "basic-read-docs-preview-secret"


class Agent:
    async def on_activate(self, ctx, payload):
        path = payload.get("path", "docs")
        resources = await ctx.resources()
        previews = []
        for relative in resources.get("files", []):
            if not relative.startswith(path):
                continue
            try:
                content = await ctx.read_file(relative, limit=120)
            except Exception as exc:  # noqa: BLE001
                previews.append({"path": relative, "error": str(exc)})
                continue
            previews.append({"path": relative, "preview": content})
            if len(previews) >= 5:
                break
        return {"container": ctx.container_name, "previews": previews}

    async def on_message(self, ctx, payload):
        return await self.on_activate(ctx, payload)
