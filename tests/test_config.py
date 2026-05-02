import pytest
from uvm_gen.config import PlatformType, AgentConfig, ProjectConfig


def test_platform_type_values():
    assert PlatformType.ADVANCE.value == "advance"
    assert PlatformType.PORT.value == "port"


def test_agent_config_defaults():
    cfg = AgentConfig(name="axi")
    assert cfg.name == "axi"


def test_project_config_defaults():
    cfg = ProjectConfig(block_name="top")
    assert cfg.platform_type == PlatformType.ADVANCE
    assert cfg.agents == []
    assert cfg.output_dir is None
    assert cfg.author != ""


def test_project_config_with_agents():
    cfg = ProjectConfig(
        block_name="top",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="axi"), AgentConfig(name="apb")],
    )
    assert len(cfg.agents) == 2
    assert cfg.agents[0].name == "axi"
    assert cfg.platform_type == PlatformType.PORT


def test_project_config_from_yaml():
    yaml_str = """
block: top
type: advance
agents:
  - name: axi
  - name: apb
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.block_name == "top"
    assert cfg.platform_type == PlatformType.ADVANCE
    assert len(cfg.agents) == 2


def test_project_config_from_yaml_port():
    yaml_str = """
block: sub
type: port
agents:
  - name: pcie
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.platform_type == PlatformType.PORT
    assert cfg.agents[0].name == "pcie"


def test_project_config_from_yaml_missing_block():
    with pytest.raises(ValueError, match="missing required field 'block'"):
        ProjectConfig.from_yaml("agents:\n  - name: axi\n")
