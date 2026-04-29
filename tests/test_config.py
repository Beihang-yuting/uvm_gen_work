import pytest
from uvm_gen.config import PlatformType, AgentMode, AgentConfig, ProjectConfig


def test_platform_type_values():
    assert PlatformType.SELF_CONTAINED.value == "self-contained"
    assert PlatformType.STANDARD.value == "standard"


def test_agent_mode_values():
    assert AgentMode.MASTER.value == "master"
    assert AgentMode.SLAVE.value == "slave"
    assert AgentMode.ONLY_MASTER.value == "only-master"
    assert AgentMode.ONLY_SLAVE.value == "only-slave"
    assert AgentMode.ONLY_MONITOR.value == "only-monitor"


def test_agent_config_defaults():
    cfg = AgentConfig(name="axi")
    assert cfg.name == "axi"
    assert cfg.mode == AgentMode.MASTER


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
            AgentConfig(name="axi", mode=AgentMode.MASTER),
            AgentConfig(name="apb", mode=AgentMode.SLAVE),
        ],
    )
    assert len(cfg.agents) == 2
    assert cfg.agents[0].name == "axi"
    assert cfg.agents[1].mode == AgentMode.SLAVE
    assert cfg.platform_type == PlatformType.STANDARD


def test_project_config_from_yaml():
    yaml_str = """
project: bootis
author: ryan.yu
block: top
type: self-contained
agents:
  - name: axi
    mode: master
  - name: apb
    mode: slave
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.project_name == "bootis"
    assert cfg.author == "ryan.yu"
    assert cfg.block_name == "top"
    assert cfg.platform_type == PlatformType.SELF_CONTAINED
    assert len(cfg.agents) == 2
    assert cfg.agents[0].mode == AgentMode.MASTER


def test_project_config_from_yaml_standard():
    yaml_str = """
project: chip_a
author: test
block: sub
type: standard
agents:
  - name: pcie
    mode: only-monitor
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.platform_type == PlatformType.STANDARD
    assert cfg.agents[0].mode == AgentMode.ONLY_MONITOR
