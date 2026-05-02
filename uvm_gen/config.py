from __future__ import annotations

import getpass
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml


class PlatformType(Enum):
    ADVANCE = "advance"
    PORT = "port"


@dataclass
class AgentConfig:
    name: str


@dataclass
class ProjectConfig:
    block_name: str
    author: str = ""
    platform_type: PlatformType = PlatformType.ADVANCE
    agents: list[AgentConfig] = field(default_factory=list)
    output_dir: Optional[str] = None

    def __post_init__(self):
        if not self.author:
            self.author = getpass.getuser()

    @classmethod
    def from_yaml(cls, yaml_str: str) -> ProjectConfig:
        data = yaml.safe_load(yaml_str)
        if "block" not in data:
            raise ValueError("missing required field 'block' in config file.")
        agents = []
        for a in data.get("agents", []):
            name = a if isinstance(a, str) else a["name"]
            agents.append(AgentConfig(name=name))
        return cls(
            block_name=data["block"],
            author=data.get("author", ""),
            platform_type=PlatformType(data.get("type", "advance")),
            agents=agents,
            output_dir=data.get("output_dir"),
        )
