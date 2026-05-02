import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.platform import PlatformGenerator

@pytest.fixture
def adv_cfg():
    return ProjectConfig(block_name="top", author="ryan.yu",
        platform_type=PlatformType.ADVANCE,
        agents=[AgentConfig(name="axi"),
                AgentConfig(name="apb")])

@pytest.fixture
def port_cfg():
    return ProjectConfig(block_name="top", author="ryan.yu",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="axi")])

def test_adv_platform_full_structure(adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        adv_cfg.output_dir = tmpdir
        gen = PlatformGenerator(adv_cfg)
        gen.generate()
        project_dir = os.path.join(tmpdir, "top")
        for d in ["env", "env/agents", "env/ral", "common", "th", "tc", "cfg", "doc"]:
            assert os.path.isdir(os.path.join(project_dir, d)), f"Missing dir: {d}"
        assert os.path.isdir(os.path.join(project_dir, "env", "agents", "axi_agent", "src"))
        assert os.path.isdir(os.path.join(project_dir, "env", "agents", "apb_agent", "src"))
        assert os.path.exists(os.path.join(project_dir, "env", "top_env.sv"))
        assert os.path.exists(os.path.join(project_dir, "env", "top_sys_if.sv"))
        assert os.path.exists(os.path.join(project_dir, "common", "common_lib_pkg.sv"))
        assert os.path.exists(os.path.join(project_dir, "th", "harness.sv"))
        assert os.path.exists(os.path.join(project_dir, "tc", "base_test.sv"))
        assert os.path.exists(os.path.join(project_dir, "cfg", "tb.f"))
        assert os.path.exists(os.path.join(project_dir, "cfg", "initreg.cfg"))
        assert os.path.exists(os.path.join(project_dir, "cfg", "xprop.cfg"))
        assert os.path.exists(os.path.join(project_dir, "cfg", "wave.tcl"))

def test_port_platform_full_structure(port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        port_cfg.output_dir = tmpdir
        gen = PlatformGenerator(port_cfg)
        gen.generate()
        project_dir = os.path.join(tmpdir, "top")
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            assert "uvm_tlm_analysis_fifo" in f.read()
