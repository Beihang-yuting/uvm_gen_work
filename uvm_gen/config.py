from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml


class PlatformType(Enum):
    SELF_CONTAINED = "self-contained"
    STANDARD = "standard"


class AgentMode(Enum):
    MASTER = "master"
    SLAVE = "slave"
    ONLY_MASTER = "only-master"
    ONLY_SLAVE = "only-slave"
    ONLY_MONITOR = "only-monitor"


@dataclass
class AgentConfig:
    name: str
    mode: AgentMode = AgentMode.MASTER


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
            agents.append(AgentConfig(
                name=a["name"],
                mode=AgentMode(a.get("mode", "master")),
            ))
        return cls(
            project_name=data["project"],
            author=data["author"],
            block_name=data["block"],
            platform_type=PlatformType(data.get("type", "self-contained")),
            agents=agents,
            output_dir=data.get("output_dir"),
        )
