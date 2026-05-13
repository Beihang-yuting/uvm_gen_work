import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.platform import PlatformGenerator


@pytest.fixture
def aip_port_cfg():
    return ProjectConfig(
        block_name="top", author="test",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="axi"), AgentConfig(name="apb")],
        aip_core=True,
    )

@pytest.fixture
def aip_adv_cfg():
    return ProjectConfig(
        block_name="top", author="test",
        platform_type=PlatformType.ADVANCE,
        agents=[AgentConfig(name="axi"), AgentConfig(name="apb")],
        aip_core=True,
    )

@pytest.fixture
def no_aip_cfg():
    return ProjectConfig(
        block_name="top", author="test",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="axi")],
        aip_core=False,
    )


# --- Task 4: vsqr static members ---

def test_vsqr_static_member_port(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_vsqr.sv")) as f:
            content = f.read()
        assert "static axi_sqr" in content
        assert "static apb_sqr" in content
        assert "s_axi_sqr" in content
        assert "s_apb_sqr" in content


def test_vsqr_static_member_advance(aip_adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_adv_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_adv_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_vsqr.sv")) as f:
            content = f.read()
        assert "static axi_sqr" in content
        assert "static apb_sqr" in content
        assert "s_axi_sqr" in content
        assert "s_apb_sqr" in content


def test_vsqr_no_static_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_vsqr.sv")) as f:
            content = f.read()
        assert "static" not in content


# --- Task 5: trans set_path ---

def test_trans_set_path(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_trans.sv")) as f:
            content = f.read()
        assert "set_path" in content
        assert "aip_int" in content


def test_trans_set_path_advance(aip_adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_adv_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_adv_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_trans.sv")) as f:
            content = f.read()
        assert "set_path" in content
        assert "aip_int" in content


def test_trans_no_set_path_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_trans.sv")) as f:
            content = f.read()
        assert "set_path" not in content


# --- Task 6: base_seq aip_cmd_seq example ---

def test_base_seq_cmd_seq_example(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "aip_cmd_seq" in content
        assert "top_vsqr::s_axi_sqr" in content


def test_base_seq_cmd_seq_advance(aip_adv_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_adv_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_adv_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "aip_cmd_seq" in content
        assert "top_vsqr::s_axi_sqr" in content


def test_base_seq_no_cmd_seq_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "aip_cmd_seq" not in content
