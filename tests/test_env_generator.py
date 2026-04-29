import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.env import EnvGenerator


@pytest.fixture
def sc_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[
            AgentConfig(name="axi"),
            AgentConfig(name="apb"),
        ],
    )


@pytest.fixture
def std_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[
            AgentConfig(name="axi"),
            AgentConfig(name="apb"),
        ],
    )


def test_sc_env_generates_all_files(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        for f in ["top_env.sv", "top_env_cfg.sv", "top_rm.sv", "top_checker.sv", "top_vsqr.sv"]:
            assert os.path.exists(os.path.join(tmpdir, f)), f"Missing: {f}"


def test_sc_env_no_fifo(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "uvm_tlm_analysis_fifo" not in content
        assert "m_axi_agt" in content
        assert "m_apb_agt" in content


def test_std_env_has_fifo(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(std_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "uvm_tlm_analysis_fifo" in content


def test_env_cfg_has_agent_cfgs(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env_cfg.sv")) as f:
            content = f.read()
        assert "axi_agt_cfg" in content
        assert "apb_agt_cfg" in content


def test_vsqr_has_agent_sqrs(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_vsqr.sv")) as f:
            content = f.read()
        assert "axi_sqr" in content


def test_std_env_generates_all_files(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(std_cfg)
        gen.generate(tmpdir)
        for f in ["top_env.sv", "top_env_cfg.sv", "top_rm.sv", "top_checker.sv", "top_vsqr.sv"]:
            assert os.path.exists(os.path.join(tmpdir, f)), f"Missing: {f}"


def test_std_rm_has_blocking_get_port(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(std_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_rm.sv")) as f:
            content = f.read()
        assert "uvm_blocking_get_port" in content


def test_std_checker_has_blocking_get_port(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(std_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_checker.sv")) as f:
            content = f.read()
        assert "uvm_blocking_get_port" in content


def test_sc_rm_has_analysis_imp(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_rm.sv")) as f:
            content = f.read()
        assert "uvm_analysis_imp" in content


def test_sc_checker_has_analysis_imp(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_checker.sv")) as f:
            content = f.read()
        assert "uvm_analysis_imp" in content


def test_std_vsqr_has_agent_sqrs(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(std_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_vsqr.sv")) as f:
            content = f.read()
        assert "axi_sqr" in content
        assert "apb_sqr" in content


def test_env_header_present(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "bootis" in content
        assert "ryan.yu" in content
        assert "top_env.sv" in content


def test_env_guard_macro(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "`ifndef  TOP_ENV__SV" in content
        assert "`define  TOP_ENV__SV" in content
        assert "`endif" in content
