from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml


class PlatformType(Enum):
    SELF_CONTAINED = "self-contained"
    STANDARD = "standard"


@dataclass
class AgentConfig:
    name: str


@dataclass
class ProjectConfig:
    project_name: str
    author: str
    block_name: str
    platform_type: PlatformType = PlatformType.SELF_CONTAINED
    agents: list[AgentConfig] = field(default_factory=list)
    output_dir: Optional[str] = None

    @classmethod
    def from_yaml(cls, yaml_str: str) -> ProjectConfig:
        data = yaml.safe_load(yaml_str)
        agents = []
        for a in data.get("agents", []):
            name = a if isinstance(a, str) else a["name"]
            agents.append(AgentConfig(name=name))
        return cls(
            project_name=data["project"],
            author=data["author"],
            block_name=data["block"],
            platform_type=PlatformType(data.get("type", "self-contained")),
            agents=agents,
            output_dir=data.get("output_dir"),
        )
