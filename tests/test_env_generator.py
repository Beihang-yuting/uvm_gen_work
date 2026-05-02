import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.env import EnvGenerator


@pytest.fixture
def adv_cfg():
    return ProjectConfig(
        block_name="top",
        author="ryan.yu",
        platform_type=PlatformType.ADVANCE,
        agents=[
            AgentConfig(name="axi"),
            AgentConfig(name="apb"),
        ],
    )


@pytest.fixture
def port_cfg():
    return ProjectConfig(
        block_name="top",
        author="ryan.yu",
        platform_type=PlatformType.PORT,
        agents=[
            AgentConfig(name="axi"),
            AgentConfig(name="apb"),
        ],
    )


def test_adv_env_generates_all_files(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        for f in ["top_env.sv", "top_env_cfg.sv", "top_rm.sv", "top_checker.sv", "top_vsqr.sv"]:
            assert os.path.exists(os.path.join(tmpdir, f)), f"Missing: {f}"


def test_adv_env_no_fifo(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "uvm_tlm_analysis_fifo" not in content
        assert "m_axi_agt" in content
        assert "m_apb_agt" in content


def test_port_env_has_fifo(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(port_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "uvm_tlm_analysis_fifo" in content


def test_env_cfg_has_agent_cfgs(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env_cfg.sv")) as f:
            content = f.read()
        assert "axi_agt_cfg" in content
        assert "apb_agt_cfg" in content


def test_vsqr_has_agent_sqrs(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_vsqr.sv")) as f:
            content = f.read()
        assert "axi_sqr" in content


def test_port_env_generates_all_files(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(port_cfg)
        gen.generate(tmpdir)
        for f in ["top_env.sv", "top_env_cfg.sv", "top_rm.sv", "top_checker.sv", "top_vsqr.sv"]:
            assert os.path.exists(os.path.join(tmpdir, f)), f"Missing: {f}"


def test_port_rm_has_blocking_get_port(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(port_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_rm.sv")) as f:
            content = f.read()
        assert "uvm_blocking_get_port" in content


def test_port_checker_has_blocking_get_port(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(port_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_checker.sv")) as f:
            content = f.read()
        assert "uvm_blocking_get_port" in content


def test_adv_rm_has_analysis_imp(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_rm.sv")) as f:
            content = f.read()
        assert "uvm_analysis_imp" in content


def test_adv_checker_has_analysis_imp(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_checker.sv")) as f:
            content = f.read()
        assert "uvm_analysis_imp" in content


def test_port_vsqr_has_agent_sqrs(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(port_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_vsqr.sv")) as f:
            content = f.read()
        assert "axi_sqr" in content
        assert "apb_sqr" in content


def test_env_header_present(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "top" in content
        assert "ryan.yu" in content
        assert "top_env.sv" in content


def test_env_guard_macro(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "`ifndef  TOP_ENV__SV" in content
        assert "`define  TOP_ENV__SV" in content
        assert "`endif" in content


def test_env_generates_sys_if(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(adv_cfg)
        gen.generate(tmpdir)
        assert os.path.exists(os.path.join(tmpdir, "top_sys_if.sv"))
        with open(os.path.join(tmpdir, "top_sys_if.sv")) as f:
            content = f.read()
        assert "axi_if" in content
        assert "apb_if" in content
