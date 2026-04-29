import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.agent import AgentGenerator


@pytest.fixture
def sc_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[AgentConfig(name="axi")],
    )


@pytest.fixture
def std_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[AgentConfig(name="axi")],
    )


def test_sc_agent_generates_all_files(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        agent_dir = os.path.join(tmpdir, "axi_agent")
        expected = [
            "axi_agent.f",
            "src/axi_agent_pkg.sv",
            "src/axi_agent.sv",
            "src/axi_trans.sv",
            "src/axi_agt_cfg.sv",
            "src/axi_drv.sv",
            "src/axi_mon.sv",
            "src/axi_sqr.sv",
            "src/axi_base_seq.sv",
            "src/axi_if.sv",
        ]
        for f in expected:
            assert os.path.exists(os.path.join(agent_dir, f)), f"Missing: {f}"


def test_sc_agent_has_internal_fifo(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agent.sv")) as f:
            content = f.read()
        assert "m_mon_fifo" in content
        assert "m_req_fifo" in content


def test_sc_base_seq_has_send_trans(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "task send_trans" in content
        assert "task send_trans_with_rsp" in content
        assert "task wait_trans" in content
        assert "task wait_request" in content
        assert "task send_response" in content


def test_sc_drv_has_master_slave_branch(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_drv.sv")) as f:
            content = f.read()
        assert "master_drive" in content
        assert "slave_drive" in content


def test_sc_cfg_has_agent_mode_enum(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agt_cfg.sv")) as f:
            content = f.read()
        assert "agent_mode_e" in content
        assert "AGENT_MASTER" in content
        assert "AGENT_ONLY_MONITOR" in content


def test_std_agent_no_internal_fifo(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(std_cfg)
        gen.generate_agent(std_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agent.sv")) as f:
            content = f.read()
        assert "m_mon_fifo" not in content
        assert "m_mon_ap" in content


def test_std_base_seq_no_task_wrappers(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(std_cfg)
        gen.generate_agent(std_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "task send_trans" not in content


def test_agent_filelist(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "axi_agent.f")) as f:
            content = f.read()
        assert "axi_agent_pkg.sv" in content
        assert "+incdir" in content
