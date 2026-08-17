from pathlib import Path

import pytest

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator


@pytest.fixture(
    params=[PlatformType.ADVANCE, PlatformType.PORT],
    ids=lambda platform_type: platform_type.value,
)
def platform_type(request):
    return request.param


def generate(tmp_path: Path, platform_type: PlatformType, aip_core: bool) -> Path:
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=platform_type,
        aip_core=aip_core,
        output_dir=str(tmp_path),
    )
    return Path(PlatformGenerator(config).generate())


def read(project_dir: Path, relative_path: str) -> str:
    return (project_dir / relative_path).read_text(encoding="utf-8")


def assert_in_order(text: str, *snippets: str) -> None:
    position = 0
    for snippet in snippets:
        next_position = text.find(snippet, position)
        assert next_position >= 0, f"expected {snippet!r} after offset {position}"
        position = next_position + len(snippet)


def test_empty_protocol_hooks_block_until_reset(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    driver = read(project_dir, "env/agents/axi_agent/src/axi_drv.sv")
    monitor = read(project_dir, "env/agents/axi_agent/src/axi_mon.sv")

    assert driver.count("@(negedge m_vif.rst_n);") >= 3
    assert "AXI_DRV_PLACEHOLDER" in driver
    assert "AXI_MON_PLACEHOLDER" in monitor
    assert "@(negedge m_vif.rst_n);" in monitor


def test_reset_finishes_deasserted(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    base_test = read(project_dir, "tc/tc_base.sv")

    assert_in_order(
        base_test,
        "harness.rst_n = 1'b0;",
        "i = $urandom_range",
        "repeat(i) @(posedge harness.clk);",
        "harness.rst_n = 1'b1;",
        "repeat(2) @(posedge harness.clk);",
        "phase.drop_objection(this);",
    )


def test_aip_activity_is_command_owned(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    base_sequence = read(
        project_dir, "env/agents/axi_agent/src/axi_base_seq.sv"
    )
    environment = read(project_dir, "env/top_env.sv")

    assert "send_trans" in base_sequence
    assert "send_trans_with_rsp" in base_sequence
    assert base_sequence.count("aip_activity::tick();") == 2
    assert "aip_activity_subscriber" not in environment
    assert "m_axi_act_sub" not in environment


def test_activity_subscriber_is_explicit_opt_in(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    subscriber = read(project_dir, "common/aip_activity_subscriber.sv")

    assert "EXPLICIT OPT-IN" in subscriber
    assert "mask a stuck AIP command" in subscriber
    assert "aip_activity::tick();" in subscriber


def test_tcl_demo_uses_ucli_input_script(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    tcl_demo = read(project_dir, "tc/tcl/tc_tcl_demo.tcl")

    assert "./simv -ucli -i ../tc/tcl/tc_tcl_demo.tcl" in tcl_demo
    assert "end_test" in tcl_demo


def test_non_aip_output_excludes_aip_integration(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=False)
    generated_text = "\n".join(
        f"{path.relative_to(project_dir)}\n"
        f"{read(project_dir, str(path.relative_to(project_dir)))}"
        for path in sorted(project_dir.rglob("*"))
        if path.is_file()
    )

    for forbidden in ("aip_activity", "aip_tcl_bridge", "aip_core_pkg.sv"):
        assert forbidden not in generated_text
    assert not (project_dir / "tc" / "tc_tcl.sv").exists()


def test_aip_tb_file_keeps_core_package_entries(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    tb_file = read(project_dir, "cfg/tb.f")

    assert "+incdir+$AIP_CORE_HOME" in tb_file
    assert "$AIP_CORE_HOME/aip_core_pkg.sv" in tb_file
