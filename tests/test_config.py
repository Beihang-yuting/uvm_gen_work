import pytest
from uvm_gen.config import PlatformType, AgentConfig, ProjectConfig


def test_platform_type_values():
    assert PlatformType.SELF_CONTAINED.value == "self-contained"
    assert PlatformType.STANDARD.value == "standard"


def test_agent_config_defaults():
    cfg = AgentConfig(name="axi")
    assert cfg.name == "axi"


def test_project_config_defaults():
    cfg = ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
    )
    assert cfg.platform_type == PlatformType.SELF_CONTAINED
    assert cfg.agents == []
    assert cfg.output_dir is None


def test_project_config_with_agents():
    cfg = ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[
            AgentConfig(name="axi"),
            AgentConfig(name="apb"),
        ],
    )
    assert len(cfg.agents) == 2
    assert cfg.agents[0].name == "axi"
    assert cfg.agents[1].name == "apb"
    assert cfg.platform_type == PlatformType.STANDARD


def test_project_config_from_yaml():
    yaml_str = """
project: bootis
author: ryan.yu
block: top
type: self-contained
agents:
  - name: axi
  - name: apb
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.project_name == "bootis"
    assert cfg.author == "ryan.yu"
    assert cfg.block_name == "top"
    assert cfg.platform_type == PlatformType.SELF_CONTAINED
    assert len(cfg.agents) == 2
    assert cfg.agents[0].name == "axi"


def test_project_config_from_yaml_standard():
    yaml_str = """
project: chip_a
author: test
block: sub
type: standard
agents:
  - name: pcie
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.platform_type == PlatformType.STANDARD
    assert cfg.agents[0].name == "pcie"
