import os
import re
import shutil
import subprocess
import sys
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


def generate_standalone(
    tmp_path: Path, platform_type: PlatformType, aip_core: bool
) -> Path:
    command = [
        sys.executable,
        "-m",
        "uvm_gen.cli",
        "-a",
        "axi",
        "-t",
        platform_type.value,
        "-o",
        str(tmp_path),
    ]
    if aip_core:
        command.append("--aip-core")
    completed = subprocess.run(
        command,
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return tmp_path / "axi_agent"


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


def task_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^[ \t]*(?:virtual[ \t]+)?task\b[^;]*\b{name}\b"
        rf"[^;]*;(?P<body>.*?)^[ \t]*endtask\b",
        source,
    )
    assert match, f"missing task {name}"
    return match.group("body")


def active_filelist_lines(source: str) -> list[str]:
    return [
        line.rstrip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "//"))
    ]


def split_config_lines(
    source: str, comment_prefix: str
) -> tuple[list[str], list[str]]:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    comments = [
        " ".join(line.removeprefix(comment_prefix).strip().split())
        for line in lines
        if line.startswith(comment_prefix)
    ]
    active = [line for line in lines if not line.startswith(comment_prefix)]
    return active, comments


def make_assignment_tokens(source: str, variable: str) -> list[str]:
    lines = source.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(rf"^{re.escape(variable)}\s*:=", line)
    ]
    assert len(starts) == 1, f"expected one {variable} assignment"

    index = starts[0]
    fragment = lines[index].split(":=", 1)[1].strip()
    fragments = []
    while True:
        continued = fragment.endswith("\\")
        fragments.append(fragment.removesuffix("\\").strip())
        if not continued:
            break
        index += 1
        assert index < len(lines), f"unterminated {variable} assignment"
        fragment = lines[index].strip()
    return " ".join(fragments).split()


def nested_filelist_targets(filelist: Path) -> list[Path]:
    targets = []
    for line in active_filelist_lines(filelist.read_text(encoding="utf-8")):
        match = re.match(r"^-F\s+(.+)$", line)
        if match:
            targets.append((filelist.parent / match.group(1)).resolve())
    return targets


def run_make(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "make",
            "--no-print-directory",
            "-f",
            str(REPOSITORY / "Makefile.uvm_template"),
            *arguments,
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )


def install_fake_vcs(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_vcs = fake_bin / "vcs"
    fake_vcs.write_text(
        """#!/usr/bin/env python3
import os
import stat
import sys
from pathlib import Path

event_log = Path(os.environ["EVENT_LOG"])
stale_path = Path(os.environ["STALE_PATH"])
if stale_path.exists():
    event_log.write_text("compile-before-clean\\n", encoding="utf-8")
    raise SystemExit(90)

arguments = sys.argv[1:]
with event_log.open("a", encoding="utf-8") as log:
    log.write("compile " + " ".join(arguments) + "\\n")
output = Path(arguments[arguments.index("-o") + 1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    "#!/usr/bin/env python3\\n"
    "import os, sys\\n"
    "from pathlib import Path\\n"
    "with Path(os.environ['EVENT_LOG']).open('a', encoding='utf-8') as log:\\n"
    "    log.write('run ' + ' '.join(sys.argv[1:]) + '\\\\n')\\n",
    encoding="utf-8",
)
output.chmod(output.stat().st_mode | stat.S_IXUSR)
""",
        encoding="utf-8",
    )
    fake_vcs.chmod(0o755)
    return fake_bin


def assert_task6_filelist_contract(
    env_source: str,
    tb_source: str,
    expected_tb_lines: list[str],
    block_name: str = "top",
    agent_names: tuple[str, ...] = ("axi", "apb"),
) -> None:
    env_lines = active_filelist_lines(env_source)
    tb_lines = active_filelist_lines(tb_source)
    harness = "../th/harness.sv"
    block_env = f"../env/{block_name}_env.sv"

    expected_env_lines = [
        "-F  ../common/common_lib_pkg.f",
        *[
            f"-F  ../env/agents/{name}_agent/{name}_agent.f"
            for name in agent_names
        ],
        "+incdir+../env",
        f"../env/{block_name}_sys_if.sv",
        f"../env/{block_name}_vsqr.sv",
        f"../env/{block_name}_rm.sv",
        f"../env/{block_name}_checker.sv",
        f"../env/{block_name}_env_cfg.sv",
        block_env,
        "+incdir+../th/bind",
        harness,
    ]
    assert env_lines == expected_env_lines
    assert env_lines[-3:] == [block_env, "+incdir+../th/bind", harness]
    assert env_lines.count(block_env) == 1
    assert env_lines.count(harness) == 1
    assert len(env_lines) == len(set(env_lines))
    assert tb_lines == expected_tb_lines
    assert len(tb_lines) == len(set(tb_lines))
    assert not any(harness in line for line in tb_lines)

    physical_lines = env_source.splitlines()
    harness_index = physical_lines.index(harness)
    assert physical_lines[harness_index + 1 : harness_index + 3] == [
        "# Optional bind checks compile after the harness:",
        "# ../th/bind/bind_example.sv",
    ]


def assert_task6_cfg_contract(
    xprop: str, initreg: str, coverage: str, wave: str
) -> None:
    xprop_active, xprop_comments = split_config_lines(xprop, "//")
    assert xprop_active == [
        "merge = tmerge;",
        "tree {harness} {xpropOn};",
    ]
    assert "instance {harness.u_dut.u0} {xpropOff};" in xprop_comments
    assert "module {sram_model} {xpropOff};" in xprop_comments
    assert "xpropMode" not in xprop

    initreg_active, initreg_comments = split_config_lines(initreg, "//")
    assert initreg_active == ["+vcs+initreg+random"]
    assert "+vcs+initreg+0" in initreg_comments
    assert "+vcs+initreg+1" in initreg_comments
    assert not re.search(r"(?<!\+vcs)\+initreg\+", initreg)

    coverage_active, coverage_comments = split_config_lines(coverage, "//")
    assert coverage_active == []
    assert any(
        re.search(
            r"\bvcs\b.*-cm\s+line\+cond\+fsm\+tgl\+branch.*"
            r"-cm_hier\s+coverage\.cfg",
            comment,
        )
        for comment in coverage_comments
    )
    assert "+tree harness.u_dut" in coverage_comments
    assert "-module sram_model" in coverage_comments
    assert not re.search(r"-cm_cond\s+obsv\b", coverage)

    wave_active, wave_comments = split_config_lines(wave, "#")
    assert wave_active == [
        'fsdbDumpfile "wave.fsdb"',
        'fsdbDumpvars 0 "harness"',
        "run",
        "quit",
    ]
    assert any(
        re.search(
            r"\bsimv\b.*-ucli\s+-i\s+wave\.tcl(?:\s|$)",
            comment,
        )
        for comment in wave_comments
    )
    assert 'fsdbDumpvars 0 "tb"' not in wave
    assert "\ufffd" not in wave


def assert_task6_makefile_contract(makefile: str) -> None:
    vcs_tokens = make_assignment_tokens(makefile, "VCS_OPTS")
    assert vcs_tokens == [
        "-full64",
        "-sverilog",
        "-ntb_opts",
        "uvm-1.2",
        "-timescale=$(TIMESCALE)",
        "-debug_access+all",
        "-kdb",
        "-lca",
        "+define+UVM_NO_DEPRECATED",
        "-F",
        "$(TB_F)",
        "-Mdir=$(BUILD_DIR)/csrc",
        "-o",
        "$(SIMV)",
        "-l",
        "$(CMP_LOG)",
    ]
    assert vcs_tokens.count("-F") == 1
    assert "-f" not in vcs_tokens
    assert "$(DUT_F)" not in vcs_tokens
    assert "$(ENV_F)" not in vcs_tokens
    assert makefile.count(
        "SIMV_OPTS += -ucli -i $(WAVE_TCL)"
    ) == 1
    assert "WAVE      ?= none" in makefile
    assert "-ucli -do" not in makefile


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


def test_readme_describes_final_platform_contract():
    readme = (REPOSITORY / "README.md").read_text(encoding="utf-8")

    def section(heading: str) -> str:
        match = re.search(
            rf"(?ms)^{re.escape(heading)}[ \t]*\n"
            rf"(?P<body>.*?)(?=^#{{1,6}}[ \t]+|\Z)",
            readme,
        )
        assert match, f"missing README section: {heading}"
        return match.group("body")

    platform = section("## Platform Types")
    for mode in ("AGENT_MASTER", "AGENT_SLAVE", "AGENT_ONLY_MONITOR"):
        assert mode in platform

    advance = section("### Advance task-only routing")
    advance_flow = """axi_trans observed;
axi_trans expected_q[$];

m_env.m_axi_agt.get_mon_item(observed);
m_env.m_rm.predict_axi(observed, expected_q);
m_env.m_scb.send_axi_actual(observed);
foreach (expected_q[i])
    m_env.m_scb.send_axi_expected(expected_q[i]);"""
    assert advance_flow in advance
    advance_text = " ".join(advance.split())
    assert "inside a task of a `tc_base`-derived test" in advance_text
    assert (
        "or another UVM component that owns or otherwise has access to the "
        "`m_env` handle"
    ) in advance_text
    assert "one external consumer" in advance_text

    port_text = " ".join(section("### PORT TLM/FIFO routing").split())
    assert "environment-owned TLM/FIFO" in port_text

    transaction_text = " ".join(
        section("## Transactions and comparison").split()
    )
    assert "fail-safe" in transaction_text
    assert "returns a mismatch with `comparison not implemented`" in transaction_text

    scoreboard_text = " ".join(section("## Common Scoreboard v2").split())
    assert "by default, up to the top 10 problem streams" in scoreboard_text
    assert "number of omitted problem streams" in scoreboard_text
    assert "`+SCB_REPORT_LIMIT=0` prints the summary only" in scoreboard_text
    assert "`+SCB_REPORT_LIMIT=-1` prints every problem stream" in scoreboard_text
    assert "full unmatched list is off by default" in scoreboard_text

    helper = section("## Interface and harness helpers")
    assert re.search(
        r"(?m)^`UVG_IF_CONNECT\(ROLE, FLOW, RTL_SIG, VIF_SIG\)$",
        helper,
    )
    helper_text = " ".join(helper.split())
    assert "RTL before VIF" in helper_text
    assert (
        "`th/harness.sv` is the final active source in `cfg/env.f`"
        in helper_text
    )
    assert "`th/bind/bind_example.sv` line follows the harness" in helper_text
    assert "commented out" in helper_text
    assert "disabled by default" in helper_text

    aip_text = " ".join(section("## aip_core Integration").split())
    assert "sole supported layout is `$AIP_HOME/aip_core`" in aip_text
    assert "+incdir+$AIP_HOME/aip_core" in aip_text
    assert "$AIP_HOME/aip_core/aip_core_pkg.sv" in aip_text
    assert "source $env(AIP_HOME)/aip_core/aip_cmd.tcl" in aip_text
    assert "enable the commented monitor tick" in aip_text
    assert "once per completed transaction or accepted beat" in aip_text
    assert "never once per clock" in aip_text
    assert "`end_test timeout`" in aip_text
    assert "all AIP activity shares one counter" in aip_text
    assert "unrelated monitor traffic" in aip_text
    assert "keep the `end_test` idle wait" in aip_text
    assert "a stalled AIP command watchdog alive" in aip_text

    for removed in (
        "common_uvm_scb_legacy",
        "aip_activity_subscriber",
        "common_report_server",
        "AIP_CORE_HOME",
        "AGENT_ONLY_MASTER",
        "AGENT_ONLY_SLAVE",
    ):
        assert removed not in readme


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
    active_base_test = strip_sv_comments(base_test)
    assert "common_report_server" not in base_test
    assert "uvm_report_server::set_server" not in base_test
    assert "uvm_report_server::get_server()" in active_base_test
    assert not re.search(r"(?<!::)\bget_report_server\s*\(", active_base_test)
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

    assert '`include "common_sva.svh"' in bind_example
    assert "../th/bind/common_sva.svh" not in bind_example
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


def test_optional_bind_compiles_from_root_and_cfg_flows(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type, aip_core=False)
    common_sva = read(project, "th/bind/common_sva.svh")
    assert 'else $error("%s contains X/Z", `"SIGNAL`");' in common_sva
    assert 'else $error("%s changed while stalled", `"PAYLOAD`");' in common_sva

    env_path = project / "cfg/env.f"
    enabled_env = env_path.read_text(encoding="utf-8").replace(
        "# ../th/bind/bind_example.sv",
        "../th/bind/bind_example.sv",
        1,
    )
    env_path.write_text(enabled_env, encoding="utf-8")
    enabled_lines = active_filelist_lines(enabled_env)
    assert enabled_lines[-3:] == [
        "+incdir+../th/bind",
        "../th/harness.sv",
        "../th/bind/bind_example.sv",
    ]

    flows = (
        (project, "th/bind", "th/bind/bind_example.sv", "root"),
        (project / "cfg", "../th/bind", "../th/bind/bind_example.sv", "cfg"),
    )
    for cwd, include_dir, source, label in flows:
        completed = subprocess.run(
            [
                require_iverilog(),
                "-g2012",
                "-gno-assertions",
                "-I",
                include_dir,
                "-s",
                "uvg_bind_checker",
                "-o",
                str(project / f"bind_example_{label}.vvp"),
                source,
            ],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_standalone_cli_generates_complete_compilation_tree(
    tmp_path, platform_type, aip_core
):
    project = generate_standalone(tmp_path, platform_type, aip_core)
    tb_lines = active_filelist_lines(read(project, "test_env/cfg/tb.f"))
    env_lines = active_filelist_lines(read(project, "test_env/cfg/env.f"))
    expected_tb = [
        "-F ./env.f",
        "+incdir+../",
        "../axi_test_env_cfg.sv",
        "../axi_test_env.sv",
        "../axi_base_test.sv",
        "../axi_test_harness.sv",
    ]
    if aip_core:
        expected_tb[:0] = [
            "+incdir+$AIP_HOME/aip_core",
            "$AIP_HOME/aip_core/aip_core_pkg.sv",
        ]
    assert tb_lines == expected_tb
    assert env_lines == [
        "-F ../../common/common_lib_pkg.f",
        "-F ../../axi_agent.f",
    ]

    common_filelist = read(project, "common/common_lib_pkg.f")
    assert ("./common_scb_aip_adapter.sv" in common_filelist) is aip_core
    assert (project / "common/common_scb_registry.sv").exists() is aip_core
    assert (project / "common/common_scb_aip_adapter.sv").exists() is aip_core
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(project.rglob("*"))
        if path.is_file()
    )
    assert "AIP_CORE_HOME" not in combined
    assert ("$AIP_HOME/aip_core" in combined) is aip_core
    assert "aip_activity_subscriber" not in combined


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_embedded_agent_test_env_reuses_platform_common_tree(
    tmp_path, platform_type, aip_core
):
    project = generate(tmp_path, platform_type, aip_core)
    test_env = project / "env/agents/axi_agent/test_env"
    tb_lines = active_filelist_lines(
        (test_env / "cfg/tb.f").read_text(encoding="utf-8")
    )
    env_lines = active_filelist_lines(
        (test_env / "cfg/env.f").read_text(encoding="utf-8")
    )
    assert tb_lines[(-6):] == [
        "-F ./env.f",
        "+incdir+../",
        "../axi_test_env_cfg.sv",
        "../axi_test_env.sv",
        "../axi_base_test.sv",
        "../axi_test_harness.sv",
    ]
    assert env_lines == [
        "-F ../../../../../common/common_lib_pkg.f",
        "-F ../../axi_agent.f",
    ]
    common_target = (test_env / "cfg/../../../../../common").resolve()
    assert common_target == (project / "common").resolve()
    assert ("$AIP_HOME/aip_core/aip_core_pkg.sv" in tb_lines) is aip_core
    assert not list(project.glob("env/agents/*_agent/common"))


def test_standalone_harness_uses_public_vif_contract(
    tmp_path, platform_type
):
    project = generate_standalone(tmp_path, platform_type, aip_core=False)
    harness = read(project, "test_env/axi_test_harness.sv")
    generated_sv = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(project.rglob("*.sv"))
    )

    assert "`UVG_VIF_SET(axi_if," in harness
    assert '"uvm_test_top.m_env.m_axi_agt*"' in harness
    assert '"m_axi_if"' not in harness
    assert "uvm_config_db#(virtual axi_if)::set" not in harness
    assert generated_sv.count("`UVG_VIF_GET(axi_if, m_vif)") == 1


def test_standalone_vcs_matrix_runner_covers_public_cli_and_root_filelist():
    runner = REPOSITORY / "tests/vcs/run_standalone_agent_matrix.sh"
    assert runner.exists()
    assert os.access(runner, os.X_OK)
    source = runner.read_text(encoding="utf-8")
    assert "set -euo pipefail" in source
    assert "python3 -m uvm_gen.cli" in source
    assert "-a axi" in source
    assert "-t \"${platform_type}\"" in source
    assert "--aip-core" in source
    assert "-F test_env/cfg/tb.f" in source
    assert "+UVM_TESTNAME=axi_base_test" in source
    assert "STANDALONE_AGENT_TEST_PASS" in source
    assert "normalize_log" in source
    assert "require_nonempty_log" in source
    assert "require_clean_runtime" in source
    assert "Error-\\[[^]]+\\]" in source
    assert "segmentation fault" in source
    for label in ("advance_off", "advance_on", "port_off", "port_on"):
        assert label in source
    assert "STANDALONE_AGENT_MATRIX_PASS" in source
    assert "STANDALONE_AGENT_MATRIX_PASS total=4" in source


def test_standalone_base_test_emits_stable_pass_marker(
    tmp_path, platform_type
):
    project = generate_standalone(tmp_path, platform_type, aip_core=False)
    base_test = read(project, "test_env/axi_base_test.sv")
    run_phase = task_body(base_test, "run_phase")

    assert run_phase.count('$display("STANDALONE_AGENT_TEST_PASS");') == 1
    delay = run_phase.index("#100ns;")
    marker = run_phase.index('$display("STANDALONE_AGENT_TEST_PASS");')
    drop = run_phase.index("phase.drop_objection(this);")
    assert delay < marker < drop


def run_synthetic_standalone_agent_matrix(
    tmp_path: Path, mode: str
) -> tuple[subprocess.CompletedProcess, Path]:
    runner = REPOSITORY / "tests/vcs/run_standalone_agent_matrix.sh"
    aip_home = tmp_path / "aip"
    aip_core = aip_home / "aip_core"
    aip_core.mkdir(parents=True)
    (aip_core / "aip_core_pkg.sv").write_text(
        "package aip_core_pkg; endpackage\n", encoding="utf-8"
    )

    event_log = tmp_path / "events.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_vcs = fake_bin / "vcs"
    fake_vcs.write_text(
        r'''#!/usr/bin/env bash
set -euo pipefail

label=$(basename "$(dirname "$PWD")")
compile_log=
output=
arguments=("$@")
while (($#)); do
    case $1 in
        -l) compile_log=$2; shift 2 ;;
        -o) output=$2; shift 2 ;;
        *) shift ;;
    esac
done
[[ -n ${compile_log} && -n ${output} ]]
printf 'compile %s %s\n' "${label}" "${arguments[*]}" \
    >> "${STANDALONE_FAKE_EVENTS}"

case ${STANDALONE_FAKE_MODE} in
    compile_timeout)
        printf 'synthetic compile timeout\n'
        exit 124
        ;;
    compile_crash)
        printf 'Segmentation fault (synthetic compile crash)\n'
        exit 139
        ;;
    compile_missing_primary) ;;
    compile_empty_primary) : > "${compile_log}" ;;
    compile_diagnostic)
        printf 'Error-[SYNTHETIC] injected compile diagnostic\n' \
            > "${compile_log}"
        ;;
    *) printf 'synthetic compile completed\n' > "${compile_log}" ;;
esac

cat > "${output}" <<'SIMV'
#!/usr/bin/env bash
set -euo pipefail

label=$(basename "$(dirname "$PWD")")
run_log=
arguments=("$@")
while (($#)); do
    case $1 in
        -l) run_log=$2; shift 2 ;;
        *) shift ;;
    esac
done
[[ -n ${run_log} ]]
printf 'run %s %s\n' "${label}" "${arguments[*]}" \
    >> "${STANDALONE_FAKE_EVENTS}"

case ${STANDALONE_FAKE_MODE} in
    runtime_timeout)
        printf 'synthetic runtime timeout\n'
        exit 124
        ;;
    runtime_crash)
        printf 'Segmentation fault (synthetic runtime crash)\n'
        exit 139
        ;;
    runtime_missing_primary)
        printf 'synthetic runtime console\n'
        exit 0
        ;;
    runtime_empty_primary) : > "${run_log}" ;;
    runtime_diagnostic)
        printf '%s\n' \
            'STANDALONE_AGENT_TEST_PASS' \
            'Error-[SYNTHETIC] injected runtime diagnostic' \
            'UVM_ERROR : 0' \
            'UVM_FATAL : 0' > "${run_log}"
        ;;
    runtime_vif_fatal)
        printf '%s\n' \
            'UVM_FATAL axi_agent.sv(1) @ 0: uvm_test_top.m_env.m_axi_agt [UVG_VIF_GET] missing virtual interface type=axi_if component=uvm_test_top.m_env.m_axi_agt field=m_axi_if' \
            'UVM_ERROR : 0' \
            'UVM_FATAL : 1' > "${run_log}"
        ;;
    *)
        printf '%s\n' \
            'STANDALONE_AGENT_TEST_PASS' \
            'UVM_ERROR : 0' \
            'UVM_FATAL : 0' > "${run_log}"
        ;;
esac

if [[ ${STANDALONE_FAKE_MODE} != runtime_empty_console ]]; then
    cat "${run_log}"
fi
SIMV
chmod +x "${output}"

if [[ ${STANDALONE_FAKE_MODE} != compile_empty_console ]]; then
    printf 'synthetic compile console\n'
fi
''',
        encoding="utf-8",
    )
    fake_vcs.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "STANDALONE_FAKE_EVENTS": str(event_log),
            "STANDALONE_FAKE_MODE": mode,
            "TMPDIR": str(tmp_path),
        }
    )
    completed = subprocess.run(
        [str(runner), str(aip_home)],
        cwd=REPOSITORY,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, event_log


@pytest.mark.parametrize(
    ("mode", "diagnostic"),
    [
        ("compile_missing_primary", "compile primary log missing or empty"),
        ("compile_empty_primary", "compile primary log missing or empty"),
        ("compile_empty_console", "compile console log missing or empty"),
        ("compile_diagnostic", "unexpected compile diagnostic"),
        ("compile_timeout", "compile timeout/infrastructure failure (exit 124)"),
        ("compile_crash", "compile failed/infrastructure failure (exit 139)"),
        ("runtime_missing_primary", "runtime primary log missing or empty"),
        ("runtime_empty_primary", "runtime primary log missing or empty"),
        ("runtime_empty_console", "runtime console log missing or empty"),
        ("runtime_diagnostic", "unexpected runtime diagnostic"),
        ("runtime_timeout", "runtime timeout/infrastructure failure (exit 124)"),
        ("runtime_crash", "runtime failed/infrastructure failure (exit 139)"),
        ("runtime_vif_fatal", "unexpected runtime UVM diagnostic"),
    ],
)
def test_standalone_matrix_rejects_invalid_compile_and_runtime_evidence(
    tmp_path, mode, diagnostic
):
    completed, _ = run_synthetic_standalone_agent_matrix(tmp_path, mode)
    output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert diagnostic in output
    assert "STANDALONE_AGENT_MATRIX_PASS" not in output


def test_standalone_matrix_requires_four_clean_compile_and_runtime_legs(
    tmp_path,
):
    completed, event_log = run_synthetic_standalone_agent_matrix(
        tmp_path, "healthy"
    )
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0, output
    labels = re.findall(
        r"(?m)^STANDALONE_AGENT_MATRIX_PASS "
        r"(advance_off|advance_on|port_off|port_on)$",
        output,
    )
    assert labels == ["advance_off", "advance_on", "port_off", "port_on"]
    assert output.count("STANDALONE_AGENT_MATRIX_PASS total=4") == 1
    events = event_log.read_text(encoding="utf-8").splitlines()
    assert [event.split()[0] for event in events] == [
        "compile",
        "run",
        "compile",
        "run",
        "compile",
        "run",
        "compile",
        "run",
    ]
    run_events = [event for event in events if event.startswith("run ")]
    assert len(run_events) == 4
    assert all("+UVM_TESTNAME=axi_base_test" in event for event in run_events)


def test_interactive_cli_describes_current_aip_integration():
    cli_source = (REPOSITORY / "uvm_gen/cli.py").read_text(encoding="utf-8")
    assert "activity subscriber" not in cli_source
    assert "Adds AIP package, control adapter, and activity integration" in cli_source


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


def assert_advance_agent_monitor_fifo_contract(agent_raw: str) -> None:
    agent = strip_sv_comments(agent_raw)
    assert "task axi_agent::get_mon_item" in agent
    assert "function bit axi_agent::try_get_mon_item" in agent
    assert (
        len(
            re.findall(
                r"uvm_tlm_analysis_fifo\s*#\s*\(\s*axi_trans\s*\)", agent
            )
        )
        == 1
    )
    assert re.search(
        r'(?m)^[ \t]*m_mon_fifo\s*=\s*new\s*\(\s*"m_mon_fifo"\s*,\s*'
        r"this\s*\)\s*;",
        agent,
    ), "Advance agent must construct its monitor FIFO"
    assert re.search(
        r"(?m)^[ \t]*m_mon\s*\.\s*m_ap\s*\.\s*connect\s*\(\s*"
        r"m_mon_fifo\s*\.\s*analysis_export\s*\)\s*;",
        agent,
    ), "Advance monitor must feed the agent-local FIFO"
    assert re.search(
        r"\bm_mon_fifo\s*\.\s*get\s*\(\s*tr\s*\)\s*;",
        task_body(agent, "get_mon_item"),
    ), "get_mon_item must block on the agent-local FIFO"
    assert re.search(
        r"\breturn\s+m_mon_fifo\s*\.\s*try_get\s*\(\s*tr\s*\)\s*;",
        function_body(agent, "try_get_mon_item"),
    ), "try_get_mon_item must return the FIFO nonblocking result"


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_advance_uses_only_explicit_transaction_tasks(tmp_path, aip_core):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=aip_core)
    agent = read(project, "env/agents/axi_agent/src/axi_agent.sv")
    sequencer = read(project, "env/agents/axi_agent/src/axi_sqr.sv")
    base_sequence = read(project, "env/agents/axi_agent/src/axi_base_seq.sv")
    rm = read(project, "env/top_rm.sv")
    checker = read(project, "env/top_checker.sv")
    env = read(project, "env/top_env.sv")
    active_env = strip_sv_comments(env)

    assert_advance_agent_monitor_fifo_contract(agent)
    assert "only one external consumer" in agent
    for obsolete_fifo in ("m_req_fifo", "m_rsp_fifo"):
        assert obsolete_fifo not in agent + sequencer
    assert "m_mon_fifo" not in sequencer
    assert "wait_trans" not in base_sequence
    assert "wait_request" not in base_sequence

    assert "task top_rm::predict_axi" in rm
    assert "task top_checker::send_axi_actual" in checker
    assert "task top_checker::send_axi_expected" in checker
    assert "m_ap.connect(m_rm" not in active_env
    assert "m_ap.connect(m_scb" not in active_env
    assert "m_expected_ap.connect" not in active_env
    assert (
        "Flow: get_mon_item -> predict_axi -> "
        "send_axi_actual/send_axi_expected"
    ) in env


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            'm_mon_fifo = new("m_mon_fifo", this);',
            'm_mon_fifo = null;',
        ),
        (
            "m_mon.m_ap.connect(m_mon_fifo.analysis_export);",
            "m_mon.m_ap.connect(m_other_fifo.analysis_export);",
        ),
        ("m_mon_fifo.get(tr);", "m_mon_fifo.peek(tr);"),
        ("return m_mon_fifo.try_get(tr);", "return 1'b0;"),
    ],
    ids=["construction", "connection", "blocking_get", "nonblocking_get"],
)
def test_advance_monitor_fifo_contract_rejects_broken_behavior(
    tmp_path, needle, replacement
):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
    agent = read(project, "env/agents/axi_agent/src/axi_agent.sv")
    mutated = agent.replace(needle, replacement, 1)
    assert mutated != agent, "failed to construct monitor FIFO mutation"

    with pytest.raises(AssertionError):
        assert_advance_agent_monitor_fifo_contract(mutated)


def test_port_retains_env_owned_fifo_lifecycle(tmp_path):
    project = generate(tmp_path, PlatformType.PORT, aip_core=False)
    env = read(project, "env/top_env.sv")

    for fifo in (
        "m_axi_agt_mon_to_rm_fifo",
        "m_rm_axi_trans_to_scb_fifo",
        "m_agt_axi_trans_to_scb_fifo",
    ):
        assert fifo in env
    assert "m_rm.stop_workers();" in env
    assert "m_scb.wait_for_workers_stopped();" in env
    assert "m_rm.request_workers_restart();" in env


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


@pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
def test_filelist_places_harness_last_in_env_only(
    tmp_path, platform_type, aip_core
):
    project = generate(tmp_path, platform_type, aip_core=aip_core)
    expected_tb_lines = [
        "-F   ./dut.f",
        "-F   ./env.f",
        "-F   ../tc/tc.f",
    ]
    if aip_core:
        expected_tb_lines[:0] = [
            "+incdir+$AIP_HOME/aip_core",
            "$AIP_HOME/aip_core/aip_core_pkg.sv",
        ]

    assert_task6_filelist_contract(
        read(project, "cfg/env.f"),
        read(project, "cfg/tb.f"),
        expected_tb_lines,
    )


def test_cfg_examples_use_reviewed_vcs_syntax(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=False)
    xprop = read(project, "cfg/xprop.cfg")
    initreg = read(project, "cfg/initreg.cfg")
    coverage = read(project, "cfg/coverage.cfg")
    wave = read(project, "cfg/wave.tcl")

    assert_task6_cfg_contract(xprop, initreg, coverage, wave)


def test_makefile_uses_tb_filelist_and_ucli_input_script():
    makefile = (REPOSITORY / "Makefile.uvm_template").read_text(
        encoding="utf-8"
    )
    assert_task6_makefile_contract(makefile)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "../th/harness.sv",
            "../th/harness.sv\n../th/harness.sv",
        ),
        (
            "# Optional bind checks compile after the harness:",
            "# bind documentation removed",
        ),
        (
            "-F  ../common/common_lib_pkg.f\n"
            "-F  ../env/agents/axi_agent/axi_agent.f",
            "-F  ../env/agents/axi_agent/axi_agent.f\n"
            "-F  ../common/common_lib_pkg.f",
        ),
    ],
    ids=["duplicate-harness", "missing-bind-comment", "env-order"],
)
def test_filelist_contract_rejects_env_mutations(
    tmp_path, needle, replacement
):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=True)
    env_source = read(project, "cfg/env.f")
    mutated_env = env_source.replace(needle, replacement, 1)
    assert mutated_env != env_source

    with pytest.raises(AssertionError):
        assert_task6_filelist_contract(
            mutated_env,
            read(project, "cfg/tb.f"),
            [
                "+incdir+$AIP_HOME/aip_core",
                "$AIP_HOME/aip_core/aip_core_pkg.sv",
                "-F   ./dut.f",
                "-F   ./env.f",
                "-F   ../tc/tc.f",
            ],
        )


@pytest.mark.parametrize(
    ("relative_path", "needle", "replacement"),
    [
        (
            "cfg/xprop.cfg",
            "tree {harness} {xpropOn};",
            "tree {harness} {xpropOn};\nmerge = xmerge;",
        ),
        (
            "cfg/xprop.cfg",
            "// instance {harness.u_dut.u0} {xpropOff};",
            "// disabled instance example removed",
        ),
        (
            "cfg/initreg.cfg",
            "// +vcs+initreg+0",
            "+vcs+initreg+0",
        ),
        (
            "cfg/coverage.cfg",
            "// +tree harness.u_dut",
            "+module unexpected_dut",
        ),
        (
            "cfg/coverage.cfg",
            "// -module sram_model",
            "// exclusion example removed",
        ),
        (
            "cfg/coverage.cfg",
            "// -module sram_model",
            "// -module sram_model\n// -cm_cond obsv",
        ),
        (
            "cfg/wave.tcl",
            "run\nquit",
            "quit\nrun",
        ),
        (
            "cfg/wave.tcl",
            "-ucli -i",
            "-ucli -do",
        ),
    ],
    ids=[
        "extra-xprop-directive",
        "missing-xprop-example",
        "active-initreg-alternative",
        "active-coverage-hierarchy",
        "missing-coverage-exclusion",
        "forbidden-coverage-obsv",
        "wave-command-order",
        "wave-guidance-option",
    ],
)
def test_cfg_contract_rejects_mutations(
    tmp_path, relative_path, needle, replacement
):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
    sources = {
        path: read(project, path)
        for path in (
            "cfg/xprop.cfg",
            "cfg/initreg.cfg",
            "cfg/coverage.cfg",
            "cfg/wave.tcl",
        )
    }
    mutated = sources[relative_path].replace(needle, replacement, 1)
    assert mutated != sources[relative_path]
    sources[relative_path] = mutated

    with pytest.raises(AssertionError):
        assert_task6_cfg_contract(
            sources["cfg/xprop.cfg"],
            sources["cfg/initreg.cfg"],
            sources["cfg/coverage.cfg"],
            sources["cfg/wave.tcl"],
        )


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        ("-F $(TB_F)", "-F $(EXTRA_F) -F $(TB_F)"),
        ("            -kdb \\", "            "),
        ("-F $(TB_F)", "-F cfg/rogue.f -F $(TB_F)"),
    ],
    ids=["extra-f", "missing-required-flag", "extra-root-file"],
)
def test_makefile_contract_rejects_compile_mutations(needle, replacement):
    makefile = (REPOSITORY / "Makefile.uvm_template").read_text(
        encoding="utf-8"
    )
    mutated = makefile.replace(needle, replacement, 1)
    assert mutated != makefile

    with pytest.raises(AssertionError):
        assert_task6_makefile_contract(mutated)


def test_filelist_contract_allows_trailing_comments(tmp_path):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
    env_source = read(project, "cfg/env.f") + "\n# Local project note\n\n"

    assert_task6_filelist_contract(
        env_source,
        read(project, "cfg/tb.f"),
        ["-F   ./dut.f", "-F   ./env.f", "-F   ../tc/tc.f"],
    )


def test_cfg_contract_allows_harmless_comments_and_wording(tmp_path):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
    xprop = read(project, "cfg/xprop.cfg").replace(
        "// tmerge evaluates the 0 and 1 branches and merges their results.",
        "// tmerge explores both values before merging the result.",
    )
    initreg = read(project, "cfg/initreg.cfg").replace(
        "// Pass this response file during compile: vcs ... -f initreg.cfg",
        "// Compile using: vcs ... -f initreg.cfg",
    )
    coverage = (
        read(project, "cfg/coverage.cfg")
        + "// Optional experiment: -cm_cond basic\n"
    )
    wave = read(project, "cfg/wave.tcl").replace(
        "# Run with:", "# Example:"
    )

    assert_task6_cfg_contract(
        xprop + "// Local xprop note\n",
        initreg + "// Local initreg note\n",
        coverage,
        wave + "# Local waveform note\n",
    )


def test_cfg_contract_allows_optional_prose_and_wave_plusarg_omission(
    tmp_path,
):
    project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
    optional_xprop_comments = {
        "// Compile with: vcs ... -xprop=xprop.cfg -f tb.f",
        "// tmerge evaluates the 0 and 1 branches and merges their results.",
        "// xmerge is more pessimistic and directly propagates X.",
    }
    xprop = "\n".join(
        line
        for line in read(project, "cfg/xprop.cfg").splitlines()
        if line not in optional_xprop_comments
    )
    initreg = read(project, "cfg/initreg.cfg").replace(
        "// Pass this response file during compile: vcs ... -f initreg.cfg\n",
        "",
    )
    wave = read(project, "cfg/wave.tcl").replace(
        " +UVM_TESTNAME=tc_base", ""
    )

    assert_task6_cfg_contract(
        xprop,
        initreg,
        read(project, "cfg/coverage.cfg"),
        wave,
    )


def test_filelist_nested_paths_resolve_from_each_list_location(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type, aip_core=False)
    tb_targets = nested_filelist_targets(project / "cfg/tb.f")

    assert tb_targets == [
        (project / "cfg/dut.f").resolve(),
        (project / "cfg/env.f").resolve(),
        (project / "tc/tc.f").resolve(),
    ]
    assert all(target.is_file() for target in tb_targets)

    env_targets = nested_filelist_targets(project / "cfg/env.f")
    assert env_targets == [
        (project / "common/common_lib_pkg.f").resolve(),
        (project / "env/agents/axi_agent/axi_agent.f").resolve(),
        (project / "env/agents/apb_agent/apb_agent.f").resolve(),
    ]
    assert all(target.is_file() for target in env_targets)


@pytest.mark.parametrize(
    "sim_dir", ["sim", "artifacts/sim"], ids=["default", "nested"]
)
def test_makefile_dry_run_uses_absolute_simv_runtime_paths(tmp_path, sim_dir):
    completed = run_make(
        tmp_path,
        "-n",
        "run",
        f"SIM_DIR={sim_dir}",
        "TEST=tc_smoke",
        "SEED=17",
        "COV=1",
        "WAVE=fsdb",
        "VERDI_HOME=/synthetic/verdi",
    )
    output = completed.stdout + completed.stderr
    sim_root = (tmp_path / sim_dir).resolve()

    assert completed.returncode == 0, output
    assert "-F cfg/tb.f" in output
    assert f"-l {sim_root}/logs/run_tc_smoke_17.log" in output
    assert f"-cm_dir {sim_root}/cov/simv.vdb" in output
    assert f"-ucli -i {(tmp_path / 'cfg/wave.tcl').resolve()}" in output
    assert "-P /synthetic/verdi/share/PLI/VCS/LINUX64/novas.tab" in output
    assert "/synthetic/verdi/share/PLI/VCS/LINUX64/pli.a" in output
    assert "../../../" not in output


def test_makefile_default_wave_is_usable_without_fsdb(tmp_path):
    completed = run_make(tmp_path, "-n", "run")
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0, output
    assert "-ucli" not in output
    assert "novas.tab" not in output


@pytest.mark.parametrize(
    ("verdi_home", "diagnostic"),
    [("", "VERDI_HOME"), ("/missing/verdi", "FSDB PLI")],
    ids=["unset", "missing-files"],
)
def test_makefile_fsdb_preflight_fails_clearly(
    tmp_path, verdi_home, diagnostic
):
    completed = run_make(
        tmp_path,
        "run",
        "WAVE=fsdb",
        f"VERDI_HOME={verdi_home}",
    )
    output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert diagnostic in output
    assert "vcs " not in output
    assert "simv" not in output


@pytest.mark.parametrize(
    ("jobs", "wave"),
    [
        (None, "none"),
        ("4", "none"),
        (None, "fsdb"),
        ("4", "fsdb"),
    ],
    ids=["serial-none", "parallel-none", "serial-fsdb", "parallel-fsdb"],
)
def test_makefile_rerun_cleans_compiles_once_then_runs(
    tmp_path, jobs, wave
):
    makefile = tmp_path / "Makefile.uvm_template"
    shutil.copy2(REPOSITORY / "Makefile.uvm_template", makefile)
    makefile_source = makefile.read_text(encoding="utf-8")
    makefile.write_text(
        makefile_source.replace(
            "fsdb-preflight:\n",
            "fsdb-preflight:\n"
            "\t@printf 'preflight\\n' >> $(PREFLIGHT_LOG)\n",
            1,
        ),
        encoding="utf-8",
    )
    fake_bin = install_fake_vcs(tmp_path)
    sim_dir = tmp_path / "artifacts/sim"
    stale_path = sim_dir / "runs/stale.marker"
    stale_path.parent.mkdir(parents=True)
    stale_path.write_text("must be removed before compile", encoding="utf-8")
    stale_simv = sim_dir / "build/simv"
    stale_simv.parent.mkdir(parents=True)
    stale_simv.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "from pathlib import Path\n"
        "with Path(os.environ['EVENT_LOG']).open('a') as log:\n"
        "    log.write('stale-run\\n')\n",
        encoding="utf-8",
    )
    stale_simv.chmod(0o755)
    event_log = tmp_path / "events.log"
    preflight_log = tmp_path / "preflight.log"
    verdi_home = tmp_path / "verdi"
    fsdb_pli_dir = verdi_home / "share/PLI/VCS/LINUX64"
    fsdb_pli_dir.mkdir(parents=True)
    (fsdb_pli_dir / "novas.tab").touch()
    (fsdb_pli_dir / "pli.a").touch()
    command = [
        "make",
        "--no-print-directory",
        "-f",
        str(makefile),
    ]
    if jobs is not None:
        command.append(f"-j{jobs}")
    command.extend(
        [
            "rerun",
            "SIM_DIR=artifacts/sim",
            f"WAVE={wave}",
            f"VERDI_HOME={verdi_home}",
            "COV=1",
            "XPROP=1",
            "TEST=tc_rerun",
            "SEED=41",
            f"PREFLIGHT_LOG={preflight_log}",
        ]
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "EVENT_LOG": str(event_log),
            "STALE_PATH": str(stale_path),
        }
    )

    completed = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    events = event_log.read_text(encoding="utf-8").splitlines()
    preflight_events = (
        preflight_log.read_text(encoding="utf-8").splitlines()
        if preflight_log.exists()
        else []
    )

    assert completed.returncode == 0, output
    assert [event.split()[0] for event in events] == ["compile", "run"]
    assert preflight_events == (["preflight"] if wave == "fsdb" else [])
    assert events[0].count("-o artifacts/sim/build/simv") == 1
    assert "-cm line+cond+fsm+branch+tgl" in events[0]
    assert "-xprop=cfg/xprop.cfg" in events[0]
    assert "+UVM_TESTNAME=tc_rerun" in events[1]
    assert "+ntb_random_seed=41" in events[1]


def test_template_refinement_vcs_assets_cover_semantics():
    runner = REPOSITORY / "tests/vcs/run_template_refinement.sh"
    source = REPOSITORY / "tests/vcs/template_refinement_tb.sv"

    assert runner.is_file() and runner.stat().st_mode & 0o111
    assert source.is_file()
    script = runner.read_text(encoding="utf-8")
    for token in (
        "+define+UVG_WIDTH_MISMATCH",
        "+UVG_SKIP_VIF_SET",
        "-xprop=xprop.cfg",
        "-f initreg.cfg",
        "-cm_hier coverage.cfg",
        "-ucli -i wave.tcl",
        "TEMPLATE_REFINEMENT_VCS_PASS",
    ):
        assert token in script

    root_bind_leg = script[
        script.index("root_bind_env_file=") :
        script.index('cd "${run_dir}/cfg"')
    ]
    assert 'sed -i' in root_bind_leg
    assert '# ../th/bind/bind_example.sv' in root_bind_leg
    assert 'cd "${run_dir}"' in root_bind_leg
    assert "run_vcs_compile root_bind" in root_bind_leg
    assert "-F cfg/tb.f" in root_bind_leg
    assert "-top harness" in root_bind_leg

    width_leg = script[
        script.index("set +e\n") :
        script.index("bad_width_status=$?")
    ]
    assert "+define+UVG_WIDTH_MISMATCH" in width_leg
    assert "-timescale=1ns/1ps" in width_leg
    for fsdb_contract in (
        "novas.tab",
        "pli.a",
        "fsdb_compile_options",
        "TEMPLATE_REFINEMENT_FSDB_UNAVAILABLE backend=portable",
        "rename fsdbDumpfile {}",
        "rename fsdbDumpvars {}",
    ):
        assert fsdb_contract in script
    xprop_compile = script[
        script.index("run_vcs_compile xprop") :
        script.index("run_vcs_compile initreg")
    ]
    assert "-timescale=1ns/1ps" in xprop_compile
    assert '"${fsdb_compile_options[@]}"' in xprop_compile
    wave_run = script[script.index("-ucli -i wave.tcl") - 160 :]
    assert "./simv_xprop +UVM_TESTNAME=tc_base" in wave_run

    missing_vif_plusarg = script.index("+UVG_SKIP_VIF_SET")
    missing_vif_start = script.rindex("set +e\n", 0, missing_vif_plusarg)
    missing_vif_leg = script[
        missing_vif_start :
        script.index("missing VIF leg reached the positive PASS marker")
    ]
    assert "timeout --kill-after=10s 90s" in missing_vif_leg
    assert "missing_vif_status" in missing_vif_leg
    for timeout_status in ("124", "125", "126", "127", "137"):
        assert timeout_status in missing_vif_leg

    width_status_check = script[
        script.index("bad_width_status=$?") :
        script.index("fsdb_native=false")
    ]
    assert "bad_width_status" in width_status_check
    for timeout_status in ("124", "125", "126", "127", "137"):
        assert timeout_status in width_status_check
    assert "CFCILFBI" in script

    cleanup = script[script.index("cleanup() {") : script.index("trap cleanup EXIT")]
    assert "mktemp -d" in cleanup
    assert "template-refinement-failure.XXXXXX" in cleanup
    assert "template-refinement-failure.$$.logs" not in cleanup
    assert '${log_file#"${run_dir}/"}' in cleanup

    stale_wave_removal = script.index("rm -f -- wave.fsdb")
    wave_runtime = script.index("./simv_xprop +UVM_TESTNAME=tc_base")
    assert stale_wave_removal < wave_runtime


def run_synthetic_template_refinement_gate(
    tmp_path: Path,
    *,
    width_status: int = 255,
    missing_status: int = 0,
    width_primary_extra: str = "",
    width_console_extra: str = "",
    missing_primary_extra: str = "",
    missing_console_extra: str = "",
    duplicate_failure_logs: bool = False,
) -> tuple[subprocess.CompletedProcess, Path]:
    runner = REPOSITORY / "tests/vcs/run_template_refinement.sh"
    project = tmp_path / "project"
    cfg = project / "cfg"
    cfg.mkdir(parents=True)
    (cfg / "tb.f").write_text("# synthetic filelist\n", encoding="utf-8")
    (cfg / "env.f").write_text(
        "+incdir+../th/bind\n"
        "../th/harness.sv\n"
        "# Optional bind checks compile after the harness:\n"
        "# ../th/bind/bind_example.sv\n",
        encoding="utf-8",
    )
    (cfg / "wave.tcl").write_text(
        'fsdbDumpfile "wave.fsdb"\n'
        'fsdbDumpvars 0 "harness"\n'
        "run\nquit\n",
        encoding="utf-8",
    )
    if duplicate_failure_logs:
        for relative, content in (
            ("nested/a/shared.log", "first preserved log\n"),
            ("nested/b/shared.log", "second preserved log\n"),
        ):
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    aip_home = tmp_path / "aip"
    aip_core = aip_home / "aip_core"
    aip_core.mkdir(parents=True)
    (aip_core / "aip_core_pkg.sv").write_text(
        "package aip_core_pkg; endpackage\n", encoding="utf-8"
    )
    (aip_core / "aip_cmd.tcl").write_text(
        "# synthetic Tcl\n", encoding="utf-8"
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_vcs = fake_bin / "vcs"
    fake_vcs.write_text(
        r'''#!/usr/bin/env bash
set -euo pipefail

compile_log=
output=
width_mismatch=false
while (($#)); do
    case $1 in
        -l) compile_log=$2; shift 2 ;;
        -o) output=$2; shift 2 ;;
        +define+UVG_WIDTH_MISMATCH) width_mismatch=true; shift ;;
        *) shift ;;
    esac
done
[[ -n ${compile_log} && -n ${output} ]]
if [[ ${width_mismatch} == true ]]; then
    cat > "${compile_log}" <<'WIDTH'
Error-[CFCILFBI] Cannot find cell in liblist
  Cell 'UVG_STATIC_ASSERTION_FAILED' cannot be found in liblist for binding
  instance 'template_refinement_tb.genblk8.u_uvg_if_width_mismatch'.
WIDTH
    if [[ -n ${WIDTH_PRIMARY_EXTRA:-} ]]; then
        printf '%s\n' "${WIDTH_PRIMARY_EXTRA}" >> "${compile_log}"
    fi
    cat "${compile_log}"
    if [[ -n ${WIDTH_CONSOLE_EXTRA:-} ]]; then
        printf '%s\n' "${WIDTH_CONSOLE_EXTRA}"
    fi
    exit "${WIDTH_STATUS:-255}"
fi

printf 'synthetic compile completed\n' > "${compile_log}"
printf 'synthetic compile console\n'
cat > "${output}" <<'SIMV'
#!/usr/bin/env bash
set -euo pipefail

log_file=
skip_vif=false
while (($#)); do
    case $1 in
        -l) log_file=$2; shift 2 ;;
        +UVG_SKIP_VIF_SET) skip_vif=true; shift ;;
        *) shift ;;
    esac
done
[[ -n ${log_file} ]]
if [[ $(basename "$0") == simv_template ]]; then
    if [[ ${skip_vif} == true ]]; then
        expected_fatal='UVM_FATAL template_refinement_tb.sv(21) @ 0: uvm_test_top.m_consumer [UVG_VIF_GET] missing virtual interface type=uvg_probe_if component=uvm_test_top.m_consumer field=m_vif'
        printf '%s\n' "${expected_fatal}" \
            'UVM_ERROR :    0' \
            'UVM_FATAL :    1' > "${log_file}"
        if [[ -n ${MISSING_PRIMARY_EXTRA:-} ]]; then
            printf '%s\n' "${MISSING_PRIMARY_EXTRA}" >> "${log_file}"
        fi
        printf '%s\n' "${expected_fatal}" \
            'UVM_ERROR :    0' \
            'UVM_FATAL :    1'
        if [[ -n ${MISSING_CONSOLE_EXTRA:-} ]]; then
            printf '%s\n' "${MISSING_CONSOLE_EXTRA}"
        fi
        exit "${MISSING_STATUS:-0}"
    fi
    printf '%s\n' \
        'TEMPLATE_REFINEMENT_VCS_PASS' \
        'UVM_ERROR : 0' \
        'UVM_FATAL : 0' > "${log_file}"
else
    printf '%s\n' \
        'TC PASSED.(warning:0,error:0,fatal:0)' \
        'TEMPLATE_REFINEMENT_FSDB_UNAVAILABLE backend=portable' \
        'TEMPLATE_REFINEMENT_WAVE_CALL fsdbDumpfile wave.fsdb' \
        'TEMPLATE_REFINEMENT_WAVE_CALL fsdbDumpvars 0 harness' \
        'UVM_ERROR : 0' \
        'UVM_FATAL : 0' > "${log_file}"
fi
printf 'synthetic runtime console\n'
SIMV
chmod +x "${output}"
''',
        encoding="utf-8",
    )
    fake_vcs.chmod(0o755)
    failure_tmp = tmp_path / "failures"
    failure_tmp.mkdir()
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "TMPDIR": str(failure_tmp),
            "WIDTH_STATUS": str(width_status),
            "MISSING_STATUS": str(missing_status),
            "WIDTH_PRIMARY_EXTRA": width_primary_extra,
            "WIDTH_CONSOLE_EXTRA": width_console_extra,
            "MISSING_PRIMARY_EXTRA": missing_primary_extra,
            "MISSING_CONSOLE_EXTRA": missing_console_extra,
        }
    )
    environment.pop("VERDI_HOME", None)
    environment.pop("NOVAS_HOME", None)

    completed = subprocess.run(
        [str(runner), str(project), str(aip_home)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    return completed, failure_tmp


@pytest.mark.parametrize("status", [124, 125, 126, 127, 137])
def test_template_refinement_width_gate_rejects_timeout_status(
    tmp_path, status
):
    completed, _ = run_synthetic_template_refinement_gate(
        tmp_path, width_status=status
    )

    assert completed.returncode != 0
    assert (
        f"width mismatch compile timeout infrastructure failure (exit {status})"
        in completed.stderr
    )
    assert "TEMPLATE_REFINEMENT_VCS_GATE_PASS" not in completed.stdout


@pytest.mark.parametrize("status", [124, 125, 126, 127, 137])
def test_template_refinement_missing_vif_rejects_timeout_status(
    tmp_path, status
):
    completed, _ = run_synthetic_template_refinement_gate(
        tmp_path, missing_status=status
    )

    assert completed.returncode != 0
    assert (
        f"missing VIF leg timeout infrastructure failure (exit {status})"
        in completed.stderr
    )
    assert "TEMPLATE_REFINEMENT_VCS_GATE_PASS" not in completed.stdout


def test_template_refinement_width_gate_rejects_unrelated_vcs_error(tmp_path):
    completed, _ = run_synthetic_template_refinement_gate(
        tmp_path,
        width_primary_extra="Error-[SYNTHETIC] unrelated injected failure",
    )

    assert completed.returncode != 0
    assert "unexpected width mismatch diagnostic" in completed.stderr


def test_template_refinement_width_gate_accepts_only_expected_diagnostic(tmp_path):
    completed, _ = run_synthetic_template_refinement_gate(tmp_path)
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0, output
    assert "TEMPLATE_REFINEMENT_VCS_GATE_PASS" in completed.stdout


@pytest.mark.parametrize(
    ("primary_extra", "console_extra"),
    [
        (
            "UVM_FATAL injected.sv(1) @ 0: uvm_test_top [UNRELATED] extra fatal",
            "",
        ),
        ("", "Error-[SYNTHETIC] unrelated runtime diagnostic"),
    ],
    ids=["extra-uvm-fatal", "console-vcs-error"],
)
def test_template_refinement_missing_vif_rejects_unrelated_diagnostic(
    tmp_path, primary_extra, console_extra
):
    completed, _ = run_synthetic_template_refinement_gate(
        tmp_path,
        missing_primary_extra=primary_extra,
        missing_console_extra=console_extra,
    )

    assert completed.returncode != 0
    assert "unexpected missing VIF diagnostic" in completed.stderr


@pytest.mark.parametrize(
    ("leg", "diagnostic"),
    [
        ("width", "Segmentation fault (core dumped)"),
        ("width", "bus ERROR"),
        ("missing-vif", "Segmentation fault (core dumped)"),
        ("missing-vif", "bus ERROR"),
    ],
)
def test_template_refinement_negative_gate_rejects_process_crash(
    tmp_path, leg, diagnostic
):
    extras = (
        {"width_console_extra": diagnostic}
        if leg == "width"
        else {"missing_console_extra": diagnostic}
    )
    completed, _ = run_synthetic_template_refinement_gate(
        tmp_path, **extras
    )
    output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert "TEMPLATE_REFINEMENT_VCS_GATE_PASS" not in output


def test_template_refinement_failure_logs_preserve_relative_paths(tmp_path):
    completed, failure_tmp = run_synthetic_template_refinement_gate(
        tmp_path,
        width_status=0,
        duplicate_failure_logs=True,
    )

    assert completed.returncode != 0
    match = re.search(r"failure logs preserved at (.+)", completed.stderr)
    assert match
    failure_dir = Path(match.group(1))
    assert failure_dir.parent == failure_tmp
    assert failure_dir.name.startswith("template-refinement-failure.")
    assert (failure_dir / "nested/a/shared.log").read_text(
        encoding="utf-8"
    ) == "first preserved log\n"
    assert (failure_dir / "nested/b/shared.log").read_text(
        encoding="utf-8"
    ) == "second preserved log\n"


def test_template_refinement_vcs_gate_rejects_stale_native_fsdb(tmp_path):
    runner = REPOSITORY / "tests/vcs/run_template_refinement.sh"
    project = tmp_path / "project"
    cfg = project / "cfg"
    cfg.mkdir(parents=True)
    (cfg / "tb.f").write_text("# synthetic filelist\n", encoding="utf-8")
    (cfg / "env.f").write_text(
        "+incdir+../th/bind\n"
        "../th/harness.sv\n"
        "# Optional bind checks compile after the harness:\n"
        "# ../th/bind/bind_example.sv\n",
        encoding="utf-8",
    )
    (cfg / "wave.tcl").write_text(
        'fsdbDumpfile "wave.fsdb"\n'
        'fsdbDumpvars 0 "harness"\n'
        "run\nquit\n",
        encoding="utf-8",
    )
    stale_wave = cfg / "wave.fsdb"
    stale_wave.write_text("stale database\n", encoding="utf-8")

    aip_home = tmp_path / "aip"
    aip_core = aip_home / "aip_core"
    aip_core.mkdir(parents=True)
    (aip_core / "aip_core_pkg.sv").write_text(
        "package aip_core_pkg; endpackage\n", encoding="utf-8"
    )
    (aip_core / "aip_cmd.tcl").write_text(
        "# synthetic Tcl\n", encoding="utf-8"
    )

    verdi_home = tmp_path / "verdi"
    pli_dir = verdi_home / "share/PLI/VCS/LINUX64"
    pli_dir.mkdir(parents=True)
    (pli_dir / "novas.tab").write_text("synthetic\n", encoding="utf-8")
    (pli_dir / "pli.a").write_text("synthetic\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_vcs = fake_bin / "vcs"
    fake_vcs.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

compile_log=
output=
width_mismatch=false
while (($#)); do
    case $1 in
        -l) compile_log=$2; shift 2 ;;
        -o) output=$2; shift 2 ;;
        +define+UVG_WIDTH_MISMATCH) width_mismatch=true; shift ;;
        *) shift ;;
    esac
done
[[ -n ${compile_log} && -n ${output} ]]
if [[ ${width_mismatch} == true ]]; then
    printf '%s\n' \
        'Error-[CFCILFBI] Cannot find cell in liblist' \
        "  Cell 'UVG_STATIC_ASSERTION_FAILED' cannot be found in liblist for binding" \
        "  instance 'template_refinement_tb.genblk8.u_uvg_if_width_mismatch'." \
        > "${compile_log}"
    cat "${compile_log}"
    exit 1
fi
printf 'synthetic compile completed\n' > "${compile_log}"
printf 'synthetic compile console\n'
cat > "${output}" <<'SIMV'
#!/usr/bin/env bash
set -euo pipefail

log_file=
skip_vif=false
while (($#)); do
    case $1 in
        -l) log_file=$2; shift 2 ;;
        +UVG_SKIP_VIF_SET) skip_vif=true; shift ;;
        *) shift ;;
    esac
done
[[ -n ${log_file} ]]
if [[ $(basename "$0") == simv_template ]]; then
    if [[ ${skip_vif} == true ]]; then
        expected_fatal='UVM_FATAL template_refinement_tb.sv(21) @ 0: uvm_test_top.m_consumer [UVG_VIF_GET] missing virtual interface type=uvg_probe_if component=uvm_test_top.m_consumer field=m_vif'
        printf '%s\n' \
            "${expected_fatal}" \
            'UVM_ERROR : 0' \
            'UVM_FATAL : 1' \
            > "${log_file}"
        cat "${log_file}"
        exit 1
    fi
    printf '%s\n' \
        'TEMPLATE_REFINEMENT_VCS_PASS' \
        'UVM_ERROR : 0' \
        'UVM_FATAL : 0' > "${log_file}"
else
    printf '%s\n' \
        'TC PASSED.(warning:0,error:0,fatal:0)' \
        'UVM_ERROR : 0' \
        'UVM_FATAL : 0' > "${log_file}"
fi
printf 'synthetic runtime console\n'
SIMV
chmod +x "${output}"
""",
        encoding="utf-8",
    )
    fake_vcs.chmod(0o755)
    failure_tmp = tmp_path / "failures"
    failure_tmp.mkdir()
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "TMPDIR": str(failure_tmp),
            "VERDI_HOME": str(verdi_home),
        }
    )

    completed = subprocess.run(
        [str(runner), str(project), str(aip_home)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode != 0
    assert "native FSDB PLI was loaded but no wave.fsdb was produced" in (
        completed.stderr
    )
    assert stale_wave.read_text(encoding="utf-8") == "stale database\n"
