import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator


REPOSITORY = Path(__file__).resolve().parents[1]
GENERATED_SCB_MATRIX_RUNNER = REPOSITORY / "tests/vcs/run_generated_scb_matrix.sh"
AIP_RUNTIME_RUNNER = REPOSITORY / "tests/vcs/run_aip_runtime_smoke.sh"
SCB_ADAPTER_SMOKE_TCL = REPOSITORY / "tests/vcs/scb_adapter_smoke.tcl"
SCOREBOARD_PATH = "uvm_test_top.m_env.m_scb.m_axi_scb"


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


def write_executable(path: Path, contents: str) -> None:
    path.write_text(textwrap.dedent(contents), encoding="utf-8")
    path.chmod(0o755)


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
    executable_lines = [
        line.strip()
        for line in tcl_demo.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert executable_lines.count("run") == 1
    assert executable_lines[-2:] == [
        "end_test idle=1us timeout=10us",
        "run",
    ]


def test_generated_scb_matrix_assets_cover_runtime_contract():
    assert GENERATED_SCB_MATRIX_RUNNER.is_file(), (
        "missing generated-project scoreboard VCS matrix runner"
    )
    assert SCB_ADAPTER_SMOKE_TCL.is_file(), "missing scoreboard AIP Tcl smoke"
    assert GENERATED_SCB_MATRIX_RUNNER.stat().st_mode & 0o111, (
        "generated-project scoreboard VCS matrix runner is not executable"
    )

    runner = GENERATED_SCB_MATRIX_RUNNER.read_text(encoding="utf-8")
    smoke = SCB_ADAPTER_SMOKE_TCL.read_text(encoding="utf-8")
    for contract in (
        "--validate-log",
        "realpath --",
        "timeout --kill-after",
        "-full64",
        "-sverilog",
        "-ntb_opts uvm-1.2",
        "-timescale=1ns/1ps",
        "-f tb.f",
        "-top harness",
        "+UVM_TESTNAME=tc_base",
        "+UVM_TESTNAME=tc_tcl",
        "-ucli",
        "TC PASSED",
        "TC FAILED.",
        "UVM_ERROR",
        "UVM_FATAL",
        "[ERROR]",
        "SCB_ADAPTER_SMOKE",
        SCOREBOARD_PATH,
        "validate_aip_off_tree",
        "unset AIP_CORE_HOME",
        "trap cleanup_normalized_log EXIT",
    ):
        assert contract in runner

    for invocation in (
        "scb_list",
        f"scb_status name={SCOREBOARD_PATH}",
        f"scb_report name={SCOREBOARD_PATH} limit=0",
        f"scb_set_limit name={SCOREBOARD_PATH} limit=-1",
        "end_test idle=1us timeout=10us",
    ):
        assert invocation in smoke
    assert smoke.count('puts "SCB_ADAPTER_SMOKE command=') == 5
    assert "scb_clear" not in smoke
    assert "reset_state" not in smoke


def test_generated_scb_matrix_validator_rejects_runtime_mutations(tmp_path):
    clean_status_marker = (
        "SCB_ADAPTER_SMOKE command=scb_status status=0 "
        "result=status=SCB_PASS expected=0 actual=0 match=0 mismatch=0 "
        "drop=0 unexpected=0 pending_expected=0 pending_actual=0 "
        "overflow=0 peak_pending=0 suppressed=0"
    )
    clean_report_marker = clean_status_marker.replace(
        "command=scb_status", "command=scb_report"
    )
    native_list_trace = "[tcl_cmd] smoke.tcl @ 1.000 ns: scb_list"
    native_report_trace = (
        f"[tcl_cmd] smoke.tcl @ 3.000 ns: scb_report "
        f"name={SCOREBOARD_PATH} limit=0"
    )
    clean_log = "\n".join(
        (
            "UVM_INFO @ 0 [PH/TRC/STRT] : Phase 'uvm.uvm_sched.reset' "
            "Starting phase",
            "UVM_INFO @ 10 [PH/TRC/DONE] : Phase 'uvm.uvm_sched.reset' "
            "Completed phase",
            "SCB_ADAPTER_REGISTRATION "
            "commands=scb_list,scb_status,scb_report,scb_set_limit",
            native_list_trace,
            f"SCB_ADAPTER_SMOKE command=scb_list status=0 result={SCOREBOARD_PATH}",
            f"[tcl_cmd] smoke.tcl @ 2.000 ns: scb_status name={SCOREBOARD_PATH}",
            clean_status_marker,
            native_report_trace,
            clean_report_marker,
            f"[tcl_cmd] smoke.tcl @ 4.000 ns: scb_set_limit "
            f"name={SCOREBOARD_PATH} limit=-1",
            "SCB_ADAPTER_SMOKE command=scb_set_limit status=0 "
            f"result={SCOREBOARD_PATH} report_limit=-1",
            f"UVM_INFO @ 4 {SCOREBOARD_PATH} [SCB_REPORT] "
            "Problem streams: total=0 shown=0 omitted=0",
            "[tcl_cmd] smoke.tcl @ 5.000 ns: "
            "end_test idle=1us timeout=10us",
            "SCB_ADAPTER_SMOKE command=end_test status=0 result=OK",
            "TC PASSED.(warning:1,error:0,fatal:0)",
            "UVM_ERROR : 0",
            "UVM_FATAL : 0",
            "",
        )
    )
    validator_tmp = tmp_path / "validator tmp"
    validator_tmp.mkdir()

    def validate(name: str, contents: str) -> subprocess.CompletedProcess[str]:
        log = tmp_path / name
        log.write_text(contents, encoding="utf-8")
        environment = os.environ.copy()
        environment["TMPDIR"] = str(validator_tmp)
        return subprocess.run(
            [
                str(GENERATED_SCB_MATRIX_RUNNER),
                "--validate-log",
                "tcl",
                "synthetic",
                str(log),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    clean = validate("clean.log", clean_log)
    assert clean.returncode == 0, clean.stderr

    missing_path = validate(
        "missing-path.log",
        clean_log.replace(SCOREBOARD_PATH, "uvm_test_top.m_env.m_scb.wrong"),
    )
    assert missing_path.returncode != 0

    unknown_command = validate(
        "unknown-command.log",
        clean_log + 'invalid command name "scb_status"\n',
    )
    assert unknown_command.returncode != 0

    mixed_failure = validate(
        "mixed-failure.log",
        clean_log.replace("UVM_ERROR : 0", "UVM_ERROR : 2")
        + "[ERROR] injected AIP failure\n",
    )
    assert mixed_failure.returncode != 0

    duplicate_pass = validate(
        "duplicate-pass.log",
        clean_log + "TC PASSED.(warning:0,error:0,fatal:0)\n",
    )
    assert duplicate_pass.returncode != 0

    missing_report = validate(
        "missing-report.log",
        clean_log.replace(clean_report_marker, clean_status_marker),
    )
    assert missing_report.returncode != 0

    failed_command = validate(
        "failed-command.log",
        clean_log
        + "SCB_ADAPTER_SMOKE command=scb_status status=1 "
        "result=command failed\n",
    )
    assert failed_command.returncode != 0

    contradictory_list = validate(
        "contradictory-list.log",
        clean_log
        + "SCB_ADAPTER_SMOKE command=scb_list status=0 "
        "result=uvm_test_top.m_env.m_scb.wrong\n",
    )
    assert contradictory_list.returncode != 0

    plain_aip_error = validate(
        "plain-aip-error.log",
        clean_log + "ERROR: injected AIP failure\n",
    )
    assert plain_aip_error.returncode != 0

    no_ack_bridge_warning = validate(
        "no-ack-bridge-warning.log",
        clean_log
        + "[AIP_TCL_BRIDGE] WARN: cmd 7 no ack after 50000ns. "
        "result 可能陈旧.\n",
    )
    assert no_ack_bridge_warning.returncode != 0

    wrong_path_native_trace = validate(
        "wrong-path-native-trace.log",
        clean_log
        + "[tcl_cmd] smoke.tcl @ 4.500 ns: scb_status "
        f"name={SCOREBOARD_PATH.rsplit('.', 1)[0]}.wrong\n",
    )
    assert wrong_path_native_trace.returncode != 0

    duplicate_native_trace = validate(
        "duplicate-native-trace.log",
        clean_log + native_list_trace + "\n",
    )
    assert duplicate_native_trace.returncode != 0

    unknown_native_trace = validate(
        "unknown-native-trace.log",
        clean_log
        + "[tcl_cmd] smoke.tcl @ 4.500 ns: scb_debug "
        f"name={SCOREBOARD_PATH}\n",
    )
    assert unknown_native_trace.returncode != 0

    missing_native_report = validate(
        "missing-native-report.log",
        clean_log.replace(native_report_trace, ""),
    )
    assert missing_native_report.returncode != 0
    assert not list(validator_tmp.glob("generated-scb-log.*"))


def test_generated_scb_matrix_rejects_nested_aip_leak_in_off_project(tmp_path):
    matrix_root = tmp_path / "matrix with spaces"
    projects = {}
    for label, platform, aip_core in (
        ("advance_off", PlatformType.ADVANCE, False),
        ("advance_on", PlatformType.ADVANCE, True),
        ("port_off", PlatformType.PORT, False),
        ("port_on", PlatformType.PORT, True),
    ):
        output = matrix_root / label
        output.mkdir(parents=True)
        projects[label] = generate(output, platform, aip_core)

    nested_agent = (
        projects["advance_off"]
        / "env/agents/axi_agent/src/axi_drv.sv"
    )
    nested_agent.write_text(
        nested_agent.read_text(encoding="utf-8")
        + "\nimport aip_core_pkg::*; // injected nested AIP leak\n",
        encoding="utf-8",
    )

    aip_core_dir = tmp_path / "aip core"
    aip_core_dir.mkdir()
    (aip_core_dir / "aip_core_pkg.sv").write_text("package aip_core_pkg; endpackage\n")
    (aip_core_dir / "aip_cmd.tcl").write_text("# test stub\n")
    tcl_script = tmp_path / "smoke script.tcl"
    tcl_script.write_text("# test stub\n")

    stub_bin = tmp_path / "stub bin"
    stub_bin.mkdir()
    write_executable(
        stub_bin / "timeout",
        """\
        #!/usr/bin/env bash
        echo "unexpected compile reached" >&2
        exit 93
        """,
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{stub_bin}:{environment['PATH']}"

    completed = subprocess.run(
        [
            str(GENERATED_SCB_MATRIX_RUNNER),
            *(str(projects[label]) for label in (
                "advance_off", "advance_on", "port_off", "port_on"
            )),
            str(aip_core_dir),
            str(tcl_script),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode != 0
    assert "advance_off: AIP-off generated text contains AIP integration" in (
        completed.stderr
    )
    assert "unexpected compile reached" not in completed.stderr


@pytest.mark.parametrize(
    ("relative_path", "duplicate_entry"),
    (
        ("cfg/tb.f", "$AIP_CORE_HOME/aip_core_pkg.sv"),
        ("cfg/env.f", "-F  ../common/common_lib_pkg.f"),
        ("common/common_lib_pkg.f", "./common_scb_aip_adapter.sv"),
    ),
    ids=("aip-package", "common-include", "adapter"),
)
def test_generated_scb_matrix_rejects_duplicate_aip_order_entries(
    tmp_path, relative_path, duplicate_entry
):
    matrix_root = tmp_path / "duplicate matrix with spaces"
    projects = {}
    for label, platform, aip_core in (
        ("advance_off", PlatformType.ADVANCE, False),
        ("advance_on", PlatformType.ADVANCE, True),
        ("port_off", PlatformType.PORT, False),
        ("port_on", PlatformType.PORT, True),
    ):
        output = matrix_root / label
        output.mkdir(parents=True)
        projects[label] = generate(output, platform, aip_core)

    mutated_file = projects["advance_on"] / relative_path
    mutated_file.write_text(
        mutated_file.read_text(encoding="utf-8") + f"{duplicate_entry}\n",
        encoding="utf-8",
    )

    aip_core_dir = tmp_path / "aip core"
    aip_core_dir.mkdir()
    (aip_core_dir / "aip_core_pkg.sv").write_text("package aip_core_pkg; endpackage\n")
    (aip_core_dir / "aip_cmd.tcl").write_text("# test stub\n")
    tcl_script = tmp_path / "smoke script.tcl"
    tcl_script.write_text("# test stub\n")

    stub_bin = tmp_path / "stub bin"
    stub_bin.mkdir()
    write_executable(
        stub_bin / "timeout",
        """\
        #!/usr/bin/env bash
        echo "unexpected compile reached" >&2
        exit 93
        """,
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{stub_bin}:{environment['PATH']}"
    completed = subprocess.run(
        [
            str(GENERATED_SCB_MATRIX_RUNNER),
            *(str(projects[label]) for label in (
                "advance_off", "advance_on", "port_off", "port_on"
            )),
            str(aip_core_dir),
            str(tcl_script),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode != 0
    assert "advance_on: AIP-on filelist entries must appear exactly once" in (
        completed.stderr
    )
    assert "syntax error in expression" not in completed.stderr
    assert "unexpected compile reached" not in completed.stderr


def test_aip_runtime_validator_rejects_adversarial_logs(tmp_path):
    clean_log = (
        "UVM_INFO @ 1.000ns: reset complete\r\n"
        "\x1b[32mTC PASSED.(warning:2,error:0,fatal:0)\x1b[0m\r\n"
        "UVM_ERROR : 0\r\n"
        "UVM_FATAL : 0\r\n"
    )
    validator_tmp = tmp_path / "validator tmp"
    validator_tmp.mkdir()

    def validate(name: str, contents: str, stage: str = "base"):
        log = tmp_path / name
        log.write_text(contents, encoding="utf-8")
        original = log.read_bytes()
        environment = os.environ.copy()
        environment["TMPDIR"] = str(validator_tmp)
        completed = subprocess.run(
            [
                str(AIP_RUNTIME_RUNNER),
                "--validate-log",
                stage,
                "synthetic",
                str(log),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert log.read_bytes() == original
        return completed

    clean = validate("clean.log", clean_log)
    assert clean.returncode == 0, clean.stderr

    mutations = {
        "duplicate-pass": clean_log
        + "TC PASSED.(warning:0,error:0,fatal:0)\n",
        "unclean-duplicate-pass": clean_log
        + "TC PASSED.(warning:0,error:1,fatal:0)\n",
        "failed-after-pass": clean_log + "TC FAILED.\n",
        "failed-after-pass-no-period": clean_log + "TC FAILED\n",
        "nonzero-summary": clean_log.replace("UVM_ERROR : 0", "UVM_ERROR : 2"),
        "duplicate-zero-summary": clean_log + "UVM_FATAL : 0\n",
        "uvm-error-diagnostic": clean_log
        + "UVM_ERROR file.sv(7) @ 1ns: top [INJECTED] error\n",
        "uvm-fatal-diagnostic": clean_log
        + "UVM_FATAL @ 1ns: top [INJECTED] fatal\n",
        "plain-error": clean_log + "ERROR: bridge command failed\n",
        "plain-fatal": clean_log + "FATAL: simulator stopped late\n",
        "vcs-runtime-error": clean_log + "Error-[RTERR] runtime failure\n",
        "bracket-error": clean_log + "[ERROR] bridge command failed\n",
        "bracket-fatal": clean_log + "[FATAL] bridge command failed\n",
        "aip-error": clean_log + "AIP command error while dispatching\n",
        "aip-failure": clean_log + "AIP command failure after completion\n",
        "no-ack": clean_log
        + "[AIP_TCL_BRIDGE] WARN: cmd 7 no ack after 50000ns\n",
        "stale-ack": clean_log
        + "[AIP_TCL_BRIDGE] WARN: stale acknowledgement reused\n",
        "missing-error-summary": clean_log.replace("UVM_ERROR : 0\r\n", ""),
        "missing-fatal-summary": clean_log.replace("UVM_FATAL : 0\r\n", ""),
        "zero-timestamp": clean_log.replace("@ 1.000ns", "@ 0ns"),
        "jinja-residue": clean_log + "generated={{ unresolved_name }}\n",
    }
    for name, contents in mutations.items():
        rejected = validate(f"{name}.log", contents)
        assert rejected.returncode != 0, f"accepted {name} mutation"

    invalid_stage = validate("invalid-stage.log", clean_log, stage="late")
    assert invalid_stage.returncode == 2
    assert "stage must be base or tcl" in invalid_stage.stderr
    wrong_arity = subprocess.run(
        [
            str(AIP_RUNTIME_RUNNER),
            "--validate-log",
            "base",
            "synthetic",
            str(tmp_path / "clean.log"),
            "extra",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert wrong_arity.returncode == 2
    assert "Usage:" in wrong_arity.stderr
    assert not list(validator_tmp.glob("aip-runtime-log.*"))


def test_aip_compile_validator_rejects_synthetic_diagnostics(tmp_path):
    clean_compile = "\x1b[36mChronologic VCS simulator compiler output\x1b[0m\r\n"
    clean_console = "\x1b[32mCompiler version and elapsed time\x1b[0m\r\n"
    validator_tmp = tmp_path / "validator tmp"
    validator_tmp.mkdir()

    def validate(name: str, compile_contents: str, console_contents: str):
        compile_log = tmp_path / f"{name}.compile.log"
        console_log = tmp_path / f"{name}.console.log"
        compile_log.write_text(compile_contents, encoding="utf-8")
        console_log.write_text(console_contents, encoding="utf-8")
        originals = (compile_log.read_bytes(), console_log.read_bytes())
        environment = os.environ.copy()
        environment["TMPDIR"] = str(validator_tmp)
        completed = subprocess.run(
            [
                str(AIP_RUNTIME_RUNNER),
                "--validate-compile",
                "synthetic",
                str(compile_log),
                str(console_log),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert (compile_log.read_bytes(), console_log.read_bytes()) == originals
        return completed

    clean = validate("clean", clean_compile, clean_console)
    assert clean.returncode == 0, clean.stderr
    benign = validate(
        "benign-prose",
        clean_compile + "summary: no error or fatal diagnostics were emitted\n",
        clean_console,
    )
    assert benign.returncode == 0, benign.stderr

    mutations = {
        "empty-compile": ("", clean_console),
        "empty-console": (clean_compile, ""),
        "jinja-compile": (clean_compile + "{{ unresolved }}\n", clean_console),
        "jinja-console": (clean_compile, clean_console + "{% broken %}\n"),
        "aip-error": (clean_compile + "[ERROR] AIP package rejected\n", clean_console),
        "aip-fatal": (clean_compile, clean_console + "[FATAL] AIP compile stopped\n"),
        "plain-error": (clean_compile + "Error: compile failed\n", clean_console),
        "plain-fatal": (clean_compile, clean_console + "Fatal: compile stopped\n"),
        "ansi-plain-error": (
            clean_compile + "\x1b[31mError: hidden compile failure\x1b[0m\r\n",
            clean_console,
        ),
        "uvm-error": (
            clean_compile + "UVM_ERROR file.sv(4): compile-time diagnostic\n",
            clean_console,
        ),
        "uvm-fatal": (
            clean_compile,
            clean_console + "UVM_FATAL @ 0: compile-time diagnostic\n",
        ),
        "vcs-syntax": (
            clean_compile + "Error-[SE] Syntax error in source file\n",
            clean_console,
        ),
        "vcs-type": (
            clean_compile,
            clean_console + "Error-[SV-IRT] Illegal reference to type\n",
        ),
        "vcs-unresolved": (
            clean_compile
            + "Error-[XMRE] Cross-module reference resolution error\n",
            clean_console,
        ),
        "plain-syntax": (clean_compile + "syntax error near token\n", clean_console),
        "undefined-type": (clean_compile, clean_console + "undefined type foo_t\n"),
        "unresolved-reference": (
            clean_compile + "unresolved reference to foo_pkg\n",
            clean_console,
        ),
    }
    for name, (compile_contents, console_contents) in mutations.items():
        rejected = validate(name, compile_contents, console_contents)
        assert rejected.returncode != 0, f"accepted {name} compile diagnostic"
    assert not list(validator_tmp.glob("aip-compile-log.*"))


def test_vcs_runtime_gate_rejects_zero_exit_compile_diagnostic(tmp_path):
    labels = ("advance_off", "advance_on", "port_off", "port_on")
    projects = {label: tmp_path / label for label in labels}
    for project_dir in projects.values():
        (project_dir / "cfg").mkdir(parents=True)

    aip_core_dir = tmp_path / "aip_core"
    aip_core_dir.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    write_executable(
        stub_bin / "timeout",
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        while (($#)); do
            case $1 in
                --kill-after=*|-*) shift ;;
                --) shift; break ;;
                *) shift; break ;;
            esac
        done
        exec "$@"
        """,
    )
    write_executable(
        stub_bin / "vcs",
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        simv=simv
        compile_log=
        while (($#)); do
            case $1 in
                -o) simv=$2; shift 2 ;;
                -l) compile_log=$2; shift 2 ;;
                *) shift ;;
            esac
        done
        [[ -n ${compile_log} ]]
        printf 'Error: generic compile failure injected despite exit zero\\n' > "${compile_log}"
        printf 'compiler console output\\n'
        cat > "${simv}" <<'SIMV'
        #!/usr/bin/env bash
        set -euo pipefail

        log_file=
        while (($#)); do
            case $1 in
                -l) log_file=$2; shift 2 ;;
                *) shift ;;
            esac
        done
        [[ -n ${log_file} ]]
        printf '@ 1ns\\nTC PASSED.(warning:0,error:0,fatal:0)\\nUVM_ERROR : 0\\nUVM_FATAL : 0\\n' > "${log_file}"
        SIMV
        chmod +x "${simv}"
        """,
    )

    environment = os.environ.copy()
    environment["PATH"] = f"{stub_bin}:{environment['PATH']}"
    completed = subprocess.run(
        [
            "bash",
            str(AIP_RUNTIME_RUNNER),
            *(str(projects[label]) for label in labels),
            str(aip_core_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode != 0
    assert "generic error/fatal or UVM diagnostic present" in completed.stderr


def test_vcs_runtime_gate_rejects_unknown_option_without_workflow_side_effect():
    completed = subprocess.run(
        [
            "bash",
            str(AIP_RUNTIME_RUNNER),
            "--bogus",
            "a",
            "b",
            "c",
            "d",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert completed.stderr.startswith("Usage:")
    assert "cd:" not in completed.stderr
    assert "AIP runtime" not in completed.stderr


def test_vcs_runtime_gate_requires_fresh_executable(tmp_path):
    labels = ("advance_off", "advance_on", "port_off", "port_on")
    projects = {label: tmp_path / label for label in labels}
    for project_dir in projects.values():
        (project_dir / "cfg").mkdir(parents=True)

    aip_core_dir = tmp_path / "aip_core"
    aip_core_dir.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()
    write_executable(
        stub_bin / "timeout",
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        while (($#)); do
            case $1 in
                --kill-after=*|-*) shift ;;
                --) shift; break ;;
                *) shift; break ;;
            esac
        done
        exec "$@"
        """,
    )
    write_executable(
        stub_bin / "vcs",
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        compile_log=
        while (($#)); do
            case $1 in
                -l) compile_log=$2; shift 2 ;;
                *) shift ;;
            esac
        done
        [[ -n ${compile_log} ]]
        printf 'VCS compile completed cleanly\\n' > "${compile_log}"
        printf 'VCS compiler console completed cleanly\\n'
        """,
    )

    environment = os.environ.copy()
    environment["PATH"] = f"{stub_bin}:{environment['PATH']}"
    completed = subprocess.run(
        [
            "bash",
            str(AIP_RUNTIME_RUNNER),
            *(str(projects[label]) for label in labels),
            str(aip_core_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode != 0
    assert "fresh executable missing or not executable" in completed.stderr


def test_vcs_runtime_gate_enables_compile_flags_for_aip_only(tmp_path):
    runtime_gate = (
        Path(__file__).parent.parent / "tests/vcs/run_aip_runtime_smoke.sh"
    )
    labels = ("advance_off", "advance_on", "port_off", "port_on")
    projects = {label: tmp_path / label for label in labels}
    for project_dir in projects.values():
        (project_dir / "cfg").mkdir(parents=True)

    aip_core_dir = tmp_path / "aip_core"
    aip_core_dir.mkdir()
    calls_dir = tmp_path / "vcs_calls"
    calls_dir.mkdir()
    stub_bin = tmp_path / "stub_bin"
    stub_bin.mkdir()

    write_executable(
        stub_bin / "timeout",
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        while (($#)); do
            case $1 in
                --kill-after=*|-*) shift ;;
                --) shift; break ;;
                *) shift; break ;;
            esac
        done
        exec "$@"
        """,
    )
    write_executable(
        stub_bin / "vcs",
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        label=$(basename "$(dirname "${PWD}")")
        printf '%s\\n' "${label}" >> "${VCS_CALLS_DIR}/calls"
        printf '%s\\n' "$@" > "${VCS_CALLS_DIR}/${label}.argv"

        simv=simv
        compile_log=
        while (($#)); do
            case $1 in
                -o) simv=$2; shift 2 ;;
                -l) compile_log=$2; shift 2 ;;
                *) shift ;;
            esac
        done
        [[ -n ${compile_log} ]]
        printf 'VCS compile completed cleanly\\n' > "${compile_log}"
        printf 'VCS compiler console completed cleanly\\n'

        cat > "${simv}" <<'SIMV'
        #!/usr/bin/env bash
        set -euo pipefail

        log_file=
        while (($#)); do
            case $1 in
                -l)
                    log_file=$2
                    shift 2
                    ;;
                *) shift ;;
            esac
        done
        [[ -n ${log_file} ]]
        printf '@ 1ns\\nTC PASSED.(warning:0,error:0,fatal:0)\\nUVM_ERROR : 0\\nUVM_FATAL : 0\\n' > "${log_file}"
        SIMV
        chmod +x "${simv}"
        """,
    )

    env = os.environ.copy()
    env["PATH"] = f"{stub_bin}:{env['PATH']}"
    env["VCS_CALLS_DIR"] = str(calls_dir)
    completed = subprocess.run(
        [
            "bash",
            str(runtime_gate),
            *(str(projects[label]) for label in labels),
            str(aip_core_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    assert (calls_dir / "calls").read_text(encoding="utf-8").splitlines() == [
        "advance_off",
        "advance_on",
        "port_off",
        "port_on",
    ]
    compile_argv = {
        label: (calls_dir / f"{label}.argv")
        .read_text(encoding="utf-8")
        .splitlines()
        for label in labels
    }
    for label in ("advance_on", "port_on"):
        assert "-debug_access+all" in compile_argv[label]
        assert "-lca" in compile_argv[label]
    for label in ("advance_off", "port_off"):
        assert "-debug_access+all" not in compile_argv[label]
        assert "-lca" not in compile_argv[label]


def test_vcs_runtime_gate_rejects_invalid_aip_compile_flag(tmp_path):
    runtime_gate = read(
        Path(__file__).parent.parent, "tests/vcs/run_aip_runtime_smoke.sh"
    )
    runtime_gate = runtime_gate.replace(
        'compile_and_run_base "${advance_off}" advance_off false',
        'compile_and_run_base "${advance_off}" advance_off invalid',
        1,
    )
    test_runtime_gate = tmp_path / "run_aip_runtime_smoke.sh"
    write_executable(test_runtime_gate, runtime_gate)

    completed = subprocess.run(
        [
            "bash",
            str(test_runtime_gate),
            str(tmp_path / "advance_off"),
            str(tmp_path / "advance_on"),
            str(tmp_path / "port_off"),
            str(tmp_path / "port_on"),
            str(tmp_path / "aip_core"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert completed.stderr == (
        "AIP runtime advance_off: AIP_ENABLED must be true or false "
        "(got invalid)\n"
    )


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
