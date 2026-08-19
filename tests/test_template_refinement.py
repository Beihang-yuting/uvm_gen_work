import re
import shutil
import subprocess
from pathlib import Path

import pytest

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator


REPOSITORY = Path(__file__).resolve().parents[1]


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
        agents=[AgentConfig("axi"), AgentConfig("apb")],
        platform_type=platform_type,
        aip_core=aip_core,
        output_dir=str(tmp_path),
    )
    return Path(PlatformGenerator(config).generate())


def read(project: Path, relative_path: str) -> str:
    return (project / relative_path).read_text(encoding="utf-8")


def strip_sv_comments(source: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^[ \t]*(?:virtual[ \t]+)?function\b[^;]*\b{name}\b"
        rf"[^;]*;(?P<body>.*?)^[ \t]*endfunction\b",
        source,
    )
    assert match, f"missing function {name}"
    return match.group("body")


def active_filelist_lines(source: str) -> list[str]:
    return [
        line.rstrip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "//"))
    ]


def require_iverilog() -> str:
    executable = shutil.which("iverilog")
    if executable is None:
        pytest.skip("iverilog is unavailable; skipping compile-only regression")
    return executable


OBSOLETE_COMMON = {
    "common_uvm_scb_legacy.sv",
    "common_draw_table.sv",
    "common_self_debug_scb.sv",
    "aip_activity_subscriber.sv",
    "common_report_server.sv",
}


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_common_layout_is_minimal(tmp_path, platform_type, aip_core):
    project = generate(tmp_path, platform_type, aip_core=aip_core)
    common_names = {path.name for path in (project / "common").iterdir()}
    assert common_names.isdisjoint(OBSOLETE_COMMON)
    package = read(project, "common/common_lib_pkg.sv")
    filelist = read(project, "common/common_lib_pkg.f")
    for obsolete in OBSOLETE_COMMON:
        assert obsolete not in package
        assert obsolete not in filelist
    assert ("common_scb_registry.sv" in common_names) is aip_core
    assert ("common_scb_aip_adapter.sv" in common_names) is aip_core


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_scoreboard_proxy_is_aip_conditional(tmp_path, platform_type, aip_core):
    project = generate(tmp_path, platform_type, aip_core=aip_core)
    core = read(project, "common/common_uvm_scb.sv")
    proxy_tokens = (
        "common_scb_control_proxy",
        "common_scb_typed_proxy",
        "m_proxy",
        "common_scb_registry::register_proxy",
    )
    for token in proxy_tokens:
        assert (token in core) is aip_core


def test_tc_base_uses_standard_uvm_report_server(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=False)
    base_test = read(project, "tc/tc_base.sv")
    assert "common_report_server" not in base_test
    assert "uvm_report_server::set_server" not in base_test
    assert '$timeformat(-9,2,"ns",12);' in base_test
    assert "get_severity_count(UVM_ERROR)" in base_test


def test_common_macros_have_fixed_public_signatures(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=False)
    declarations = read(project, "common/common_dec.sv")

    expected_signatures = (
        "`define UVG_IF_CONNECT(ROLE, FLOW, RTL_SIG, VIF_SIG)",
        "`define UVG_VIF_SET(IF_TYPE, PATH, VIF)",
        "`define UVG_VIF_GET(IF_TYPE, VIF)",
        "`define UVG_CLK(CLK, PERIOD, OFFSET)",
        "`define UVG_RSTN(RST_N, CLK, CYCLES)",
        "`define UVG_STATIC_ASSERT(NAME, EXPR, MESSAGE)",
    )
    for signature in expected_signatures:
        assert signature in declarations

    assert "RTL_SIG, VIF_SIG" in declarations
    assert "CLK_GEN" not in declarations
    assert "RST_GEN" not in declarations


def test_bind_examples_are_generated_but_disabled(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=False)
    bind_example = read(project, "th/bind/bind_example.sv")
    common_sva = read(project, "th/bind/common_sva.svh")

    assert "UVG_SVA_NO_X" in common_sva
    assert "UVG_SVA_HOLD" in common_sva
    for phrase in (
        "module type",
        "hierarchical instance",
        "parameterized checker",
        "interface instance",
        "generate hierarchy",
        "multiple checkers",
    ):
        assert phrase in bind_example

    active_env_lines = active_filelist_lines(read(project, "cfg/env.f"))
    assert not any(
        "../th/bind/bind_example.sv" in line for line in active_env_lines
    )


def test_static_assert_macro_expands_to_valid_systemverilog(tmp_path):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
    probe = project / "static_assert_probe.sv"
    probe.write_text(
        """\
`include "common/common_dec.sv"
module static_assert_probe;
    `UVG_STATIC_ASSERT(valid_static_assert, 1, "valid expression")
endmodule
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            require_iverilog(),
            "-g2012",
            "-s",
            "static_assert_probe",
            "-o",
            str(project / "static_assert_probe.vvp"),
            probe.name,
        ],
        cwd=project,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_disabled_bind_example_compiles_with_sva_macros(tmp_path):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
    common_sva = read(project, "th/bind/common_sva.svh")
    assert 'else $error("%s contains X/Z", `"SIGNAL`");' in common_sva
    assert 'else $error("%s changed while stalled", `"PAYLOAD`");' in common_sva

    completed = subprocess.run(
        [
            require_iverilog(),
            "-g2012",
            "-gno-assertions",
            "-s",
            "uvg_bind_checker",
            "-o",
            str(project / "bind_example.vvp"),
            "../th/bind/bind_example.sv",
        ],
        cwd=project / "cfg",
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_agent_modes_and_vif_ownership_are_standardized(
    tmp_path, platform_type, aip_core
):
    project = generate(tmp_path, platform_type, aip_core=aip_core)
    sources = {
        kind: read(project, f"env/agents/axi_agent/src/axi_{kind}.sv")
        for kind in ("agt_cfg", "agent", "drv", "mon", "sqr", "base_seq")
    }
    combined = "\n".join(sources.values())
    cfg = sources["agt_cfg"]
    enum_match = re.search(
        r"typedef\s+enum\s*\{(?P<modes>.*?)\}\s*agent_mode_e\s*;",
        cfg,
        flags=re.DOTALL,
    )
    assert enum_match is not None
    assert re.findall(r"\bAGENT_[A-Z_]+\b", enum_match.group("modes")) == [
        "AGENT_MASTER",
        "AGENT_SLAVE",
        "AGENT_ONLY_MONITOR",
    ]
    for obsolete in (
        "AGENT_ONLY_MASTER",
        "AGENT_ONLY_SLAVE",
        "MASTER_NO_MONITOR",
        "SLAVE_NO_MONITOR",
        "m_self_debug_en",
        "m_debug_scb",
        "common_self_debug_scb",
    ):
        assert obsolete not in combined

    agent = sources["agent"]
    assert agent.count("`UVG_VIF_GET(axi_if, m_vif)") == 1
    assert "m_mon.m_cfg = m_cfg;" in agent
    assert "m_mon.m_vif = m_vif;" in agent
    assert "m_sqr.m_cfg = m_cfg;" in agent
    assert "m_drv.m_cfg = m_cfg;" in agent
    assert "m_drv.m_vif = m_vif;" in agent
    assert 'default: `uvm_fatal("AGENT_MODE", "unsupported agent mode")' in agent

    for kind in ("drv", "mon"):
        child = sources[kind]
        assert "uvm_config_db#" not in child
        assert "m_vif == null" in child
        assert "internal VIF propagation failed" in child

    driver_case = re.search(
        r"case\s*\(m_cfg\.m_mode\)(?P<body>.*?)endcase",
        sources["drv"],
        flags=re.DOTALL,
    )
    assert driver_case is not None
    assert re.findall(
        r"^\s*(AGENT_[A-Z_]+)\s*:",
        driver_case.group("body"),
        flags=re.MULTILINE,
    ) == [
        "AGENT_MASTER",
        "AGENT_SLAVE",
    ]
    assert "AGENT_MASTER: master_drive();" in driver_case.group("body")
    assert "AGENT_SLAVE:  slave_drive();" in driver_case.group("body")
    assert "monitor-only mode has no driver" in driver_case.group("body")


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_transaction_has_explicit_fail_safe_uvm_hooks(
    tmp_path, platform_type, aip_core
):
    project = generate(tmp_path, platform_type, aip_core=aip_core)
    transaction = read(project, "env/agents/axi_agent/src/axi_trans.sv")

    assert "`uvm_object_utils(axi_trans)" in transaction
    assert "`uvm_object_utils_begin" not in transaction
    for function_name in (
        "do_copy",
        "do_compare",
        "convert2string",
        "do_print",
        "self_define_do_compare",
    ):
        function_body(transaction, function_name)
    assert "super.do_copy(rhs);" in function_body(transaction, "do_copy")
    assert "super.do_compare(rhs, comparer)" in function_body(
        transaction, "do_compare"
    )
    assert "super.do_print(printer);" in function_body(transaction, "do_print")
    comparison_hook = function_body(transaction, "self_define_do_compare")
    assert "comparison not implemented" in comparison_hook
    assert not re.search(r"\breturn\s+1\s*;", comparison_hook)
    assert "return '1;" in function_body(transaction, "get_scb_stream_id")
    assert "return -1;" in function_body(transaction, "get_scb_kind")


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_interface_separates_master_slave_and_monitor_clocking(
    tmp_path, platform_type, aip_core
):
    project = generate(tmp_path, platform_type, aip_core=aip_core)
    interface = read(project, "env/agents/axi_agent/src/axi_if.sv")
    driver = read(project, "env/agents/axi_agent/src/axi_drv.sv")

    assert "clocking mst_drv_cb @(posedge clk);" in interface
    assert "clocking slv_drv_cb @(posedge clk);" in interface
    assert "clocking mon_cb @(posedge clk);" in interface
    assert not re.search(r"\bclocking\s+drv_cb\b", interface)
    assert "modport mst_drv_mp (clocking mst_drv_cb);" in interface
    assert "modport slv_drv_mp (clocking slv_drv_cb);" in interface
    assert "modport mon_mp     (clocking mon_cb);" in interface
    assert "M2S protocol fields are outputs; S2M fields are inputs." in interface
    assert "M2S protocol fields are inputs; S2M fields are outputs." in interface
    assert "Every observed protocol field is an input." in interface
    assert "m_vif.drv_cb" not in driver
    assert "m_vif.mst_drv_cb" in driver
    assert "m_vif.slv_drv_cb" in driver
