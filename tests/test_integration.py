import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.platform import PlatformGenerator

@pytest.fixture
def adv_three_agents():
    return ProjectConfig(block_name="top", author="engineer",
        platform_type=PlatformType.ADVANCE,
        agents=[AgentConfig(name="axi"),
                AgentConfig(name="apb"),
                AgentConfig(name="pcie")])

@pytest.fixture
def port_two_agents():
    return ProjectConfig(block_name="sub", author="engineer",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="spi"),
                AgentConfig(name="uart")])

def test_adv_full_generation(adv_three_agents):
    """Advance platform with 3 agents generates complete structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        adv_three_agents.output_dir = tmpdir
        gen = PlatformGenerator(adv_three_agents)
        project_dir = gen.generate()

        for name in ["axi", "apb", "pcie"]:
            agent_sv = os.path.join(project_dir, "env", "agents", f"{name}_agent", "src", f"{name}_agent.sv")
            assert os.path.exists(agent_sv)

        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_agent.sv")) as f:
            assert "m_mon_fifo" in f.read()
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            assert "uvm_tlm_analysis_fifo" not in f.read()

        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
            assert "send_trans" in content
            assert "wait_trans" in content

        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            content = f.read()
            assert "m_axi_agt" in content
            assert "m_apb_agt" in content
            assert "m_pcie_agt" in content

def test_port_full_generation(port_two_agents):
    """Port platform with 2 agents generates FIFO-based env."""
    with tempfile.TemporaryDirectory() as tmpdir:
        port_two_agents.output_dir = tmpdir
        gen = PlatformGenerator(port_two_agents)
        project_dir = gen.generate()

        with open(os.path.join(project_dir, "env", "agents", "spi_agent", "src", "spi_agent.sv")) as f:
            assert "m_mon_fifo" not in f.read()
        with open(os.path.join(project_dir, "env", "sub_env.sv")) as f:
            assert "uvm_tlm_analysis_fifo" in f.read()
        with open(os.path.join(project_dir, "env", "agents", "spi_agent", "src", "spi_base_seq.sv")) as f:
            assert "send_trans" not in f.read()

def test_duplicate_project_raises(adv_three_agents):
    """Generating into existing directory raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        adv_three_agents.output_dir = tmpdir
        PlatformGenerator(adv_three_agents).generate()
        with pytest.raises(FileExistsError):
            PlatformGenerator(adv_three_agents).generate()

def test_cfg_filelist_references_agents(adv_three_agents):
    """env.f filelist references all agent .f files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        adv_three_agents.output_dir = tmpdir
        project_dir = PlatformGenerator(adv_three_agents).generate()
        with open(os.path.join(project_dir, "cfg", "env.f")) as f:
            content = f.read()
        assert "axi_agent" in content
        assert "apb_agent" in content
        assert "pcie_agent" in content
