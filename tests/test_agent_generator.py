import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.agent import AgentGenerator


@pytest.fixture
def adv_cfg():
    return ProjectConfig(
        block_name="top",
        author="ryan.yu",
        platform_type=PlatformType.ADVANCE,
        agents=[AgentConfig(name="axi")],
    )


@pytest.fixture
def port_cfg():
    return ProjectConfig(
        block_name="top",
        author="ryan.yu",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="axi")],
    )


def test_adv_agent_generates_all_files(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(adv_cfg)
        gen.generate_agent(adv_cfg.agents[0], tmpdir)
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


def test_adv_agent_has_internal_fifo(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(adv_cfg)
        gen.generate_agent(adv_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agent.sv")) as f:
            content = f.read()
        assert "m_mon_fifo" in content
        assert "m_req_fifo" in content


def test_adv_base_seq_has_send_trans(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(adv_cfg)
        gen.generate_agent(adv_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "task send_trans" in content
        assert "task send_trans_with_rsp" in content
        assert "task wait_trans" in content
        assert "task wait_request" in content
        assert "task send_response" in content


def test_adv_drv_has_master_slave_branch(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(adv_cfg)
        gen.generate_agent(adv_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_drv.sv")) as f:
            content = f.read()
        assert "master_drive" in content
        assert "slave_drive" in content


def test_adv_cfg_has_agent_mode_enum(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(adv_cfg)
        gen.generate_agent(adv_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agt_cfg.sv")) as f:
            content = f.read()
        assert "agent_mode_e" in content
        assert "AGENT_MASTER" in content
        assert "AGENT_ONLY_MONITOR" in content


def test_port_agent_no_internal_fifo(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(port_cfg)
        gen.generate_agent(port_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agent.sv")) as f:
            content = f.read()
        assert "m_mon_fifo" not in content
        assert "m_mon_ap" in content


def test_port_base_seq_no_task_wrappers(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(port_cfg)
        gen.generate_agent(port_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "task send_trans" not in content


def test_agent_filelist(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(adv_cfg)
        gen.generate_agent(adv_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "axi_agent.f")) as f:
            content = f.read()
        assert "axi_agent_pkg.sv" in content
        assert "+incdir" in content


def test_agent_generates_test_env(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(adv_cfg)
        gen.generate_agent(adv_cfg.agents[0], tmpdir)
        test_env_dir = os.path.join(tmpdir, "axi_agent", "test_env")
        assert os.path.isdir(test_env_dir)
        assert os.path.exists(os.path.join(test_env_dir, "axi_test_env.sv"))
        assert os.path.exists(os.path.join(test_env_dir, "axi_test_env_cfg.sv"))
        assert os.path.exists(os.path.join(test_env_dir, "axi_test_harness.sv"))
        assert os.path.exists(os.path.join(test_env_dir, "axi_base_test.sv"))
        assert os.path.exists(os.path.join(test_env_dir, "cfg", "tb.f"))
        assert os.path.exists(os.path.join(test_env_dir, "cfg", "env.f"))
