import re
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


def task_body(systemverilog: str, task_name: str) -> str:
    match = re.search(
        rf"^[ \t]*(?:virtual[ \t]+)?task[ \t]+"
        rf"(?:[A-Za-z_][A-Za-z0-9_$]*::)?{re.escape(task_name)}\b"
        rf"[^;]*;(.*?)^[ \t]*endtask\b",
        systemverilog,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing task definition for {task_name}"
    return match.group(1)


def strip_sv_comments(systemverilog: str) -> str:
    return re.sub(
        r"/\*.*?\*/|//[^\n]*",
        "",
        systemverilog,
        flags=re.DOTALL,
    )


def test_empty_protocol_hooks_block_until_reset(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    driver = read(project_dir, "env/agents/axi_agent/src/axi_drv.sv")
    monitor = read(project_dir, "env/agents/axi_agent/src/axi_mon.sv")

    for name in ("master_drive", "slave_drive"):
        body = task_body(driver, name)
        assert "AXI_DRV_PLACEHOLDER" in body
        assert "@(negedge m_vif.rst_n);" in strip_sv_comments(body)

    monitor_body = task_body(monitor, "mon_transaction")
    assert "AXI_MON_PLACEHOLDER" in monitor_body
    assert "@(negedge m_vif.rst_n);" in strip_sv_comments(monitor_body)


def test_reset_finishes_deasserted(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    base_test = read(project_dir, "tc/tc_base.sv")

    reset_body = strip_sv_comments(task_body(base_test, "reset_phase"))
    assert_in_order(
        reset_body,
        "harness.rst_n = 1'b0;",
        "i = $urandom_range(10, 20);",
        "repeat(i) @(posedge harness.clk);",
        "@(negedge harness.clk);",
        "harness.rst_n = 1'b1;",
        "repeat(2) @(posedge harness.clk);",
        "phase.drop_objection(this);",
    )
    assignments = list(
        re.finditer(r"\bharness\.rst_n\s*=\s*([^;]+);", reset_body)
    )
    assert assignments
    last_assignment = assignments[-1]
    assert last_assignment.group(1).strip() == "1'b1"
    assert_in_order(
        reset_body[last_assignment.start() :],
        "harness.rst_n = 1'b1;",
        "repeat(2) @(posedge harness.clk);",
        "phase.drop_objection(this);",
    )


def test_aip_activity_is_command_owned(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    base_sequence = read(
        project_dir, "env/agents/axi_agent/src/axi_base_seq.sv"
    )
    monitor = read(project_dir, "env/agents/axi_agent/src/axi_mon.sv")
    environment = read(project_dir, "env/top_env.sv")

    tick = "aip_activity::tick();"
    send_trans = strip_sv_comments(task_body(base_sequence, "send_trans"))
    send_trans_with_rsp = strip_sv_comments(
        task_body(base_sequence, "send_trans_with_rsp")
    )

    assert send_trans.count(tick) == 1
    assert_in_order(send_trans, "finish_item(tr);", tick)
    assert send_trans_with_rsp.count(tick) == 1
    assert_in_order(send_trans_with_rsp, "get_response(rsp);", tick)

    executable_monitor = strip_sv_comments(monitor)
    executable_environment = strip_sv_comments(environment)
    assert tick not in executable_monitor
    assert tick not in executable_environment
    assert "aip_activity_subscriber" not in executable_environment
    assert "m_axi_act_sub" not in executable_environment


def test_aip_agent_package_imports_core_package(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    agent_package = read(
        project_dir, "env/agents/axi_agent/src/axi_agent_pkg.sv"
    )

    assert_in_order(
        agent_package,
        "package axi_agent_pkg;",
        "import uvm_pkg::*;",
        "import aip_core_pkg::*;",
        "import common_lib_pkg::*;",
        '`include "axi_base_seq.sv"',
        "endpackage",
    )


def test_activity_subscriber_is_explicit_opt_in(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    subscriber = read(project_dir, "common/aip_activity_subscriber.sv")

    assert "EXPLICIT OPT-IN" in subscriber
    assert "mask a stuck AIP command" in subscriber
    assert "aip_activity::tick();" in strip_sv_comments(subscriber)


def test_tcl_demo_uses_ucli_input_script(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    tcl_demo = read(project_dir, "tc/tcl/tc_tcl_demo.tcl")

    assert (
        "./simv -ucli -i ../tc/tcl/tc_tcl_demo.tcl "
        "+UVM_TESTNAME=tc_tcl"
    ) in tcl_demo
    assert "-do" not in tcl_demo
    assert "end_test idle=1us timeout=10us" in tcl_demo


def test_non_aip_output_excludes_aip_integration(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=False)
    generated_text = "\n".join(
        f"{path.relative_to(project_dir)}\n"
        f"{read(project_dir, str(path.relative_to(project_dir)))}"
        for path in sorted(project_dir.rglob("*"))
        if path.is_file()
    )

    assert "aip_" not in generated_text.lower()
    assert not (project_dir / "tc" / "tc_tcl.sv").exists()


def test_aip_tb_file_keeps_core_package_entries(tmp_path, platform_type):
    project_dir = generate(tmp_path, platform_type, aip_core=True)
    tb_file = read(project_dir, "cfg/tb.f")

    aip_home_lines = [
        line.strip()
        for line in tb_file.splitlines()
        if line.strip() and "$AIP_CORE_HOME" in line
    ]
    assert aip_home_lines == [
        "+incdir+$AIP_CORE_HOME",
        "$AIP_CORE_HOME/aip_core_pkg.sv",
    ]
    assert tb_file.count("aip_core_pkg.sv") == 1
    assert not list(project_dir.rglob("aip_core_pkg.sv"))
