import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.platform import PlatformGenerator

@pytest.fixture
def sc_cfg():
    return ProjectConfig(project_name="bootis", author="ryan.yu", block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[AgentConfig(name="axi", mode=AgentMode.MASTER),
                AgentConfig(name="apb", mode=AgentMode.SLAVE)])

@pytest.fixture
def std_cfg():
    return ProjectConfig(project_name="bootis", author="ryan.yu", block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[AgentConfig(name="axi", mode=AgentMode.MASTER)])

def test_sc_platform_full_structure(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        sc_cfg.output_dir = tmpdir
        gen = PlatformGenerator(sc_cfg)
        gen.generate()
        project_dir = os.path.join(tmpdir, "bootis_top")
        for d in ["agents", "env", "common", "harness", "tc", "cfg", "sim", "ral", "doc"]:
            assert os.path.isdir(os.path.join(project_dir, d)), f"Missing dir: {d}"
        assert os.path.isdir(os.path.join(project_dir, "agents", "axi_agent", "src"))
        assert os.path.isdir(os.path.join(project_dir, "agents", "apb_agent", "src"))
        assert os.path.exists(os.path.join(project_dir, "env", "top_env.sv"))
        assert os.path.exists(os.path.join(project_dir, "common", "common_lib_pkg.sv"))
        assert os.path.exists(os.path.join(project_dir, "harness", "harness.sv"))
        assert os.path.exists(os.path.join(project_dir, "tc", "base_test.sv"))
        assert os.path.exists(os.path.join(project_dir, "cfg", "tb.f"))
        assert os.path.exists(os.path.join(project_dir, "sim", "Makefile"))

def test_std_platform_full_structure(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        std_cfg.output_dir = tmpdir
        gen = PlatformGenerator(std_cfg)
        gen.generate()
        project_dir = os.path.join(tmpdir, "bootis_top")
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            assert "uvm_tlm_analysis_fifo" in f.read()

def test_platform_sim_dirs(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        sc_cfg.output_dir = tmpdir
        gen = PlatformGenerator(sc_cfg)
        gen.generate()
        project_dir = os.path.join(tmpdir, "bootis_top")
        assert os.path.isdir(os.path.join(project_dir, "sim", "log"))
        assert os.path.isdir(os.path.join(project_dir, "sim", "wave"))
