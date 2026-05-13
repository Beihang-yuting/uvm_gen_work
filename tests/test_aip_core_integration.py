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


# --- Task 7: env activity_subscriber + static sqr ---

def test_env_activity_subscriber(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            content = f.read()
        assert "aip_activity_subscriber" in content
        assert "m_axi_act_sub" in content
        assert "m_apb_act_sub" in content
        assert "s_axi_sqr" in content


def test_env_no_subscriber_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            content = f.read()
        assert "aip_activity_subscriber" not in content


# --- Task 8: common — aip_activity_subscriber template ---

def test_common_activity_subscriber(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        sub_path = os.path.join(project_dir, "common", "aip_activity_subscriber.sv")
        assert os.path.exists(sub_path)
        with open(sub_path) as f:
            content = f.read()
        assert "aip_activity::tick()" in content
        assert "uvm_subscriber" in content


def test_no_activity_subscriber_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        assert not os.path.exists(os.path.join(project_dir, "common", "aip_activity_subscriber.sv"))


# --- Task 9: harness — aip_clk 100MHz demo ---

def test_harness_aip_clk(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "th", "harness.sv")) as f:
            content = f.read()
        assert "aip_clk_create" in content
        assert "100e6" in content


def test_harness_no_aip_clk_without(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "th", "harness.sv")) as f:
            content = f.read()
        assert "aip_clk_create" not in content
        assert "CLK_GEN" in content


# --- Task 10: tc_tcl + tc_base + TCL demo ---

def test_tc_tcl_generated(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        tc_tcl = os.path.join(project_dir, "tc", "tc_tcl.sv")
        assert os.path.exists(tc_tcl)
        with open(tc_tcl) as f:
            content = f.read()
        assert "aip_tcl_bridge::run_loop()" in content
        assert "tc_tcl" in content

        tc_base = os.path.join(project_dir, "tc", "tc_base.sv")
        assert os.path.exists(tc_base)

        tc_f = os.path.join(project_dir, "tc", "tc.f")
        with open(tc_f) as f:
            content = f.read()
        assert "tc_tcl.sv" in content
        assert "tc_base.sv" in content


def test_tcl_demo_generated(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        demo = os.path.join(project_dir, "tc", "tcl", "tc_tcl_demo.tcl")
        assert os.path.exists(demo)
        with open(demo) as f:
            content = f.read()
        assert "AIP_CORE_HOME" in content
        assert "end_test" in content


def test_no_tc_tcl_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        assert not os.path.exists(os.path.join(project_dir, "tc", "tc_tcl.sv"))
        assert not os.path.exists(os.path.join(project_dir, "tc", "tcl"))


# --- Task 11: tb.f — AIP_CORE_HOME ---

def test_tb_f_aip_core_home(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "cfg", "tb.f")) as f:
            content = f.read()
        assert "AIP_CORE_HOME" in content
        assert "aip_core_pkg.sv" in content
