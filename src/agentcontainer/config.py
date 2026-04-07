from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Config:
    container_name: str
    listen_host: str
    listen_port: int
    admin_secret: str
    data_root: str
    advertise_host: str | None = None
    parent_target: str | None = None
    federation: dict[str, Any] = field(default_factory=dict)
    allow_subprocess: bool = True


def load_config(path: str | Path) -> Config:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Config(
        container_name=raw["container_name"],
        listen_host=raw.get("listen_host", "0.0.0.0"),
        listen_port=int(raw["listen_port"]),
        admin_secret=raw["admin_secret"],
        data_root=raw["data_root"],
        advertise_host=raw.get("advertise_host"),
        parent_target=raw.get("parent_target"),
        federation=raw.get("federation", {}),
        allow_subprocess=bool(raw.get("allow_subprocess", True)),
    )
