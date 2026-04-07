from __future__ import annotations

import json
from typing import Any


async def read_message(reader) -> dict[str, Any]:
    raw = await reader.readline()
    if not raw:
        raise ConnectionError("connection closed")
    return json.loads(raw.decode("utf-8"))


async def write_message(writer, message: dict[str, Any]) -> None:
    writer.write(json.dumps(message, ensure_ascii=True).encode("utf-8") + b"\n")
    await writer.drain()
