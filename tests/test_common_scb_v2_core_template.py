import re
from pathlib import Path

import pytest

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator


def strip_sv_comments(systemverilog: str) -> str:
    def replace_comment(match: re.Match) -> str:
        token = match.group(0)
        if token.startswith('"'):
            return token
        return "".join(char if char in "\r\n" else " " for char in token)

    return re.sub(
        r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*.*?\*/',
        replace_comment,
        systemverilog,
        flags=re.DOTALL,
    )


def sv_macro_calls(source: str, macro: str) -> list[str]:
    calls = []
    token = f"`{macro}"
    search_from = 0
    while True:
        start = source.find(token, search_from)
        if start < 0:
            return calls
        opening = source.find("(", start + len(token))
        assert opening >= 0, f"missing opening parenthesis for `{macro}"
        depth = 0
        in_string = False
        escaped = False
        for index in range(opening, len(source)):
            char = source[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    calls.append(source[start : index + 1])
                    search_from = index + 1
                    break
        else:
            raise AssertionError(f"unterminated `{macro} call")


def core_method_body(
    core: str, declaration: str, description: str, terminator: str = "function"
) -> str:
    match = re.search(
        rf"(?ms)^[ \t]*{declaration}[ \t]*;(?P<body>.*?)"
        rf"^[ \t]*end{terminator}\b",
        core,
    )
    assert match, f"missing core {description} body"
    return match.group("body")


def core_match_position(body: str, pattern: str, description: str) -> int:
    match = re.search(pattern, body, flags=re.MULTILINE | re.DOTALL)
    assert match, f"missing core {description}"
    return match.start()


def assert_positions_in_order(body: str, checks) -> None:
    positions = [
        core_match_position(body, pattern, description)
        for description, pattern in checks
    ]
    assert positions == sorted(positions), (
        "core operations are not in the required execution order: "
        + ", ".join(description for description, _ in checks)
    )


def assert_task6_lifecycle_report_contract(core: str) -> None:
    declarations = {
        "control proxy member": (
            r"(?m)^[ \t]*protected\s+common_scb_control_proxy\s+m_proxy\s*;"
        ),
        "row ordering helper": (
            r"(?m)^[ \t]*extern\s+protected\s+function\s+bit\s+row_before\s*\("
            r"\s*common_scb_problem_row\s+left\s*,\s*"
            r"common_scb_problem_row\s+right\s*\)\s*;"
        ),
        "row builder helper": (
            r"(?m)^[ \t]*extern\s+protected\s+function\s+common_scb_problem_row\s+"
            r"make_row\s*\(\s*state_t\s+state\s*\)\s*;"
        ),
    }
    for description, pattern in declarations.items():
        assert re.search(pattern, core), f"missing Task 6 {description}"

    row_before = core_method_body(
        core,
        r"function\s+bit\s+common_uvm_scb::row_before\s*\([^;]+\)",
        "row_before",
    )
    assert_positions_in_order(
        row_before,
        [
            (
                "severity ordering",
                r"if\s*\(\s*left\.status\s*!=\s*right\.status\s*\)\s*"
                r"return\s+left\.status\s*>\s*right\.status\s*;",
            ),
            (
                "issue-count ordering",
                r"if\s*\(\s*left\.issue_count\s*!=\s*right\.issue_count\s*\)\s*"
                r"return\s+left\.issue_count\s*>\s*right\.issue_count\s*;",
            ),
            (
                "stream-ID tie break",
                r"return\s+left\.stream_id\s*<\s*right\.stream_id\s*;",
            ),
        ],
    )

    make_row = core_method_body(
        core,
        r"function\s+common_scb_problem_row\s+common_uvm_scb::make_row\s*\([^;]+\)",
        "make_row",
    )
    assert_positions_in_order(
        make_row,
        [
            ("row allocation", r"row\s*=\s*new\s*\(\s*\)\s*;"),
            (
                "pending expected calculation",
                r"pending_expected\s*=\s*state\.expected_q\.size\s*\(\s*\)\s*;",
            ),
            (
                "pending actual calculation",
                r"pending_actual\s*=\s*state\.actual_q\.size\s*\(\s*\)\s*;",
            ),
            (
                "failure classification",
                r"state\.mismatches\s*\+\s*state\.unexpected_actuals\s*\+\s*"
                r"state\.overflows.*?row\.status\s*=\s*SCB_FAIL\s*;",
            ),
            (
                "warning classification",
                r"state\.allowed_drops\s*\+\s*state\.diagnostic_warnings\s*\+\s*"
                r"pending_expected\s*\+\s*pending_actual.*?row\.status\s*=\s*SCB_WARN\s*;",
            ),
            ("pass classification", r"else\s*row\.status\s*=\s*SCB_PASS\s*;"),
            ("issue count", r"row\.issue_count\s*=\s*state\.issue_count\s*\(\s*\)\s*;"),
            (
                "ten report cells",
                r"row\.cells\s*=\s*'\{\s*row\.status\.name\s*\(\s*\)\s*,\s*"
                r"\$sformatf\s*\(\s*\"0x%0h\"\s*,\s*state\.stream_id\s*\)\s*,"
                r".*?state\.match_count.*?state\.mismatches.*?state\.allowed_drops.*?"
                r"state\.unexpected_actuals.*?pending_expected.*?pending_actual.*?"
                r"state\.overflows.*?state\.peak_pending.*?\}\s*;",
            ),
        ],
    )

    status = core_method_body(
        core,
        r"function\s+scb_status_e\s+common_uvm_scb::get_status\s*\(\s*\)",
        "get_status",
    )
    assert_positions_in_order(
        status,
        [
            ("diagnostic accumulator", r"longint\s+unsigned\s+diagnostics\s*=\s*0\s*;"),
            (
                "diagnostic sum",
                r"foreach\s*\(\s*m_streams\s*\[\s*id\s*\]\s*\)\s*"
                r"diagnostics\s*\+=\s*m_streams\s*\[\s*id\s*\]\.diagnostic_warnings\s*;",
            ),
            (
                "global failure",
                r"m_mismatches\s*\+\s*m_unexpected_actuals\s*\+\s*m_overflows.*?"
                r"return\s+SCB_FAIL\s*;",
            ),
            (
                "global warning",
                r"m_allowed_drops\s*\+\s*diagnostics.*?return\s+SCB_WARN\s*;",
            ),
            ("global pass", r"return\s+SCB_PASS\s*;"),
        ],
    )

    clean = core_method_body(
        core,
        r"function\s+bit\s+common_uvm_scb::is_clean\s*\(\s*\)",
        "is_clean",
    )
    assert_positions_in_order(
        clean,
        [
            (
                "pending queue rejection",
                r"foreach\s*\(\s*m_streams\s*\[\s*id\s*\]\s*\).*?"
                r"expected_q\.size\s*\(\s*\).*?actual_q\.size\s*\(\s*\).*?return\s+0\s*;",
            ),
            ("status check", r"return\s+get_status\s*\(\s*\)\s*==\s*SCB_PASS\s*;"),
        ],
    )

    summary = core_method_body(
        core,
        r"function\s+string\s+common_uvm_scb::get_summary\s*\(\s*\)",
        "get_summary",
    )
    assert re.search(
        r"pending_expected\s*\+=\s*m_streams\s*\[\s*id\s*\]\.expected_q\.size\s*\(\s*\)\s*;",
        summary,
    )
    assert re.search(
        r"pending_actual\s*\+=\s*m_streams\s*\[\s*id\s*\]\.actual_q\.size\s*\(\s*\)\s*;",
        summary,
    )
    summary_format = re.search(
        r"return\s+\$sformatf\s*\(\s*\{\s*"
        r'"status=%s expected=%0d actual=%0d match=%0d mismatch=%0d "\s*,\s*'
        r'"drop=%0d unexpected=%0d pending_expected=%0d pending_actual=%0d "\s*,\s*'
        r'"overflow=%0d peak_pending=%0d suppressed=%0d"\s*\}\s*,',
        summary,
    )
    assert summary_format, (
        "get_summary must pass the exact Task 6 field order as one explicit "
        "concatenation expression"
    )
    assert not re.search(
        r"\$sformatf\s*\(\s*\"[^\"]*\"\s*\"",
        summary,
    ), "get_summary must not rely on adjacent string literals"

    report = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::print_report\s*\(\s*int\s+limit\s*=\s*-2\s*\)",
        "print_report",
    )
    assert re.search(
        r"string\s+headers\s*\[\$\]\s*=\s*'\{\s*\"Status\"\s*,\s*\"Stream\"\s*,\s*"
        r"\"Match\"\s*,\s*\"Mismatch\"\s*,\s*\"Drop\"\s*,\s*\"Unexpected\"\s*,\s*"
        r"\"PendExp\"\s*,\s*\"PendAct\"\s*,\s*\"Overflow\"\s*,\s*\"Peak\"\s*\}\s*;",
        report,
    ), "print_report must define the exact ten headers"
    assert re.search(
        r"bit\s+numeric\s*\[\$\]\s*=\s*'\{\s*0\s*,\s*0\s*,\s*1\s*,\s*1\s*,\s*1\s*,\s*1\s*,\s*1\s*,\s*1\s*,\s*1\s*,\s*1\s*\}\s*;",
        report,
    ), "print_report must define exact numeric-column metadata"
    assert_positions_in_order(
        report,
        [
            (
                "configured limit selection",
                r"effective_limit\s*=\s*\(\s*limit\s*==\s*-2\s*\)\s*\?\s*"
                r"m_cfg\.m_report_limit\s*:\s*limit\s*;",
            ),
            (
                "invalid limit fallback",
                r"if\s*\(\s*effective_limit\s*<\s*-1\s*\).*?"
                r"invalid report limit=%0d; using configured limit=%0d.*?"
                r"effective_limit\s*=\s*m_cfg\.m_report_limit\s*;",
            ),
            (
                "problem-row filter",
                r"row\s*=\s*make_row\s*\(\s*m_streams\s*\[\s*id\s*\]\s*\)\s*;\s*"
                r"if\s*\(\s*row\.issue_count\s*!=\s*0\s*\)",
            ),
            (
                "stable insertion point",
                r"int\s+insert_at\s*=\s*rows\.size\s*\(\s*\)\s*;.*?"
                r"if\s*\(\s*row_before\s*\(\s*row\s*,\s*rows\s*\[\s*i\s*\]\s*\)\s*\).*?"
                r"insert_at\s*=\s*i\s*;.*?break\s*;.*?rows\.insert\s*\(\s*insert_at\s*,\s*row\s*\)\s*;",
            ),
            (
                "all-or-top-N shown count",
                r"shown\s*=\s*\(\s*effective_limit\s*==\s*-1\s*\)\s*\?\s*rows\.size\s*\(\s*\)\s*"
                r":\s*\(\s*\(\s*effective_limit\s*<\s*rows\.size\s*\(\s*\)\s*\)\s*\?\s*"
                r"effective_limit\s*:\s*rows\.size\s*\(\s*\)\s*\)\s*;",
            ),
            ("omitted count", r"omitted\s*=\s*rows\.size\s*\(\s*\)\s*-\s*shown\s*;"),
            ("summary info", r"`uvm_info\s*\(\s*\"SCB_REPORT\"\s*,\s*get_summary\s*\(\s*\)"),
            (
                "problem-count info",
                r"Problem streams: total=%0d shown=%0d omitted=%0d",
            ),
            (
                "conditional table",
                r"if\s*\(\s*shown\s*!=\s*0\s*\)\s*begin\s*"
                r"reporter\.set_columns\s*\(\s*headers\s*,\s*numeric\s*\)\s*;.*?"
                r"for\s*\(\s*int\s+i\s*=\s*0\s*;\s*i\s*<\s*shown\s*;\s*i\+\+\s*\)\s*"
                r"reporter\.add_row\s*\(\s*rows\s*\[\s*i\s*\]\.cells\s*\)\s*;.*?"
                r"reporter\.render\s*\(\s*\)",
            ),
        ],
    )
    assert "normal streams" not in report.lower()

    finalize = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::finalize_pending\s*\(\s*\)",
        "finalize_pending",
    )
    assert_positions_in_order(
        finalize,
        [
            ("idempotence guard", r"if\s*\(\s*m_finalized\s*\)\s*return\s*;"),
            ("stream loop", r"foreach\s*\(\s*m_streams\s*\[\s*id\s*\]\s*\)"),
            (
                "lossy residual drops",
                r"if\s*\(\s*m_cfg\.m_cmp_mode\s*==\s*SCB_ORDERED_LOSSY\s*\).*?"
                r"while\s*\(\s*state\.expected_q\.size\s*\(\s*\)\s*!=\s*0\s*\)\s*"
                r"record_drop\s*\(\s*state\s*,\s*state\.expected_q\.pop_front\s*\(\s*\)\s*\)\s*;",
            ),
            (
                "non-lossy residual mismatches",
                r"else\s*begin\s*while\s*\(\s*state\.expected_q\.size\s*\(\s*\)\s*!=\s*0\s*\)\s*"
                r"record_mismatch\s*\(\s*state\s*,\s*state\.expected_q\.pop_front\s*\(\s*\)\s*,\s*null\s*,\s*"
                r"\"expected transaction has no actual match at check phase\"\s*\)\s*;\s*end",
            ),
            (
                "actual residual unexpected classification",
                r"while\s*\(\s*state\.actual_q\.size\s*\(\s*\)\s*!=\s*0\s*\)\s*"
                r"record_unexpected\s*\(\s*state\s*,\s*state\.actual_q\.pop_front\s*\(\s*\)\s*,\s*"
                r"\"actual transaction has no expected match at check phase\"\s*\)\s*;",
            ),
            ("finalized marker", r"m_finalized\s*=\s*1\s*;"),
        ],
    )

    check = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::check_phase\s*\(\s*uvm_phase\s+phase\s*\)",
        "check_phase",
    )
    assert_positions_in_order(
        check,
        [
            ("parent check", r"super\.check_phase\s*\(\s*phase\s*\)\s*;"),
            ("pending finalization", r"finalize_pending\s*\(\s*\)\s*;"),
            ("final status case", r"case\s*\(\s*get_status\s*\(\s*\)\s*\)"),
            ("failure message", r"SCB_FAIL\s*:\s*`uvm_error\s*\(\s*\"SCB_FINAL\"\s*,\s*get_summary\s*\(\s*\)\s*\)"),
            ("warning message", r"SCB_WARN\s*:\s*`uvm_warning\s*\(\s*\"SCB_FINAL\"\s*,\s*get_summary\s*\(\s*\)\s*\)"),
            ("pass message", r"default\s*:\s*`uvm_info\s*\(\s*\"SCB_FINAL\"\s*,\s*get_summary\s*\(\s*\)\s*,\s*UVM_LOW\s*\)"),
        ],
    )

    report_phase = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::report_phase\s*\(\s*uvm_phase\s+phase\s*\)",
        "report_phase",
    )
    assert_positions_in_order(
        report_phase,
        [
            ("parent report", r"super\.report_phase\s*\(\s*phase\s*\)\s*;"),
            ("enabled report", r"if\s*\(\s*m_cfg\.m_report_en\s*\)\s*print_report\s*\(\s*\)\s*;"),
            (
                "suppression warning",
                r"if\s*\(\s*m_suppressed_details\s*!=\s*0\s*\).*?"
                r"%0d runtime detail messages suppressed \(limit=%0d\).*?"
                r"m_suppressed_details\s*,\s*m_cfg\.m_err_limit",
            ),
        ],
    )
    assert "record_mismatch" not in report_phase
    assert "record_unexpected" not in report_phase

    reset = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::reset_state\s*\(\s*bit\s+clear_counters\s*=\s*1\s*\)",
        "reset_state",
    )
    assert_positions_in_order(
        reset,
        [
            ("stream deletion", r"m_streams\.delete\s*\(\s*\)\s*;"),
            ("finalized reset", r"m_finalized\s*=\s*0\s*;"),
            ("strict warning reset", r"m_strict_arrival_warned\s*=\s*0\s*;"),
            ("unconditional current gauge reset", r"m_current_pending\s*=\s*0\s*;"),
            ("cumulative counter guard", r"if\s*\(\s*clear_counters\s*\)\s*begin"),
            ("expected reset", r"m_expected_inputs\s*=\s*0\s*;"),
            ("actual reset", r"m_actual_inputs\s*=\s*0\s*;"),
            ("matches reset", r"m_matches\s*=\s*0\s*;"),
            ("mismatches reset", r"m_mismatches\s*=\s*0\s*;"),
            ("drops reset", r"m_allowed_drops\s*=\s*0\s*;"),
            ("unexpected reset", r"m_unexpected_actuals\s*=\s*0\s*;"),
            ("overflows reset", r"m_overflows\s*=\s*0\s*;"),
            ("peak reset", r"m_peak_pending\s*=\s*0\s*;"),
            ("detail reset", r"m_detail_emitted\s*=\s*0\s*;"),
            ("suppressed reset", r"m_suppressed_details\s*=\s*0\s*;"),
        ],
    )
    current_reset = re.search(r"m_current_pending\s*=\s*0\s*;", reset)
    clear_guard = re.search(r"if\s*\(\s*clear_counters\s*\)\s*begin", reset)
    assert current_reset and clear_guard and current_reset.start() < clear_guard.start(), (
        "reset_state must clear the current gauge even when cumulative counters are retained"
    )


def assert_task6_proxy_contract(core: str) -> None:
    core_class_end = core.index("endclass", core.index("class common_uvm_scb"))
    first_core_body = core.index("function common_uvm_scb::new")
    proxy_match = re.search(
        r"(?ms)class\s+common_scb_typed_proxy\s*#\s*\(\s*type\s+TRANS_TYPE\s*,\s*"
        r"int\s+STREAM_ID_WIDTH\s*=\s*64\s*\)\s*extends\s+common_scb_control_proxy\s*;"
        r"(?P<body>.*?)^[ \t]*endclass",
        core,
    )
    assert proxy_match, "missing explicit-type Task 6 typed proxy"
    assert core_class_end < proxy_match.start() < first_core_body, (
        "typed proxy must follow the core declaration and precede method bodies"
    )
    proxy = proxy_match.group("body")
    assert re.search(
        r"typedef\s+common_uvm_scb\s*#\s*\(\s*TRANS_TYPE\s*,\s*STREAM_ID_WIDTH\s*\)\s+scoreboard_t\s*;",
        proxy,
    )
    assert re.search(r"protected\s+scoreboard_t\s+m_scoreboard\s*;", proxy)
    expected_proxy_bodies = {
        "constructor": r"function\s+new\s*\(\s*string\s+name\s*,\s*scoreboard_t\s+scoreboard\s*\).*?super\.new\s*\(\s*name\s*\).*?m_scoreboard\s*=\s*scoreboard",
        "scoreboard name": r"function\s+string\s+scoreboard_name\s*\(\s*\).*?return\s+m_scoreboard\.get_full_name\s*\(\s*\)",
        "status": r"function\s+scb_status_e\s+status\s*\(\s*\).*?return\s+m_scoreboard\.get_status\s*\(\s*\)",
        "summary": r"function\s+string\s+summary\s*\(\s*\).*?return\s+m_scoreboard\.get_summary\s*\(\s*\)",
        "report": r"function\s+void\s+report\s*\(\s*int\s+limit\s*=\s*-2\s*\).*?m_scoreboard\.print_report\s*\(\s*limit\s*\)",
        "limit validation": r"function\s+bit\s+set_report_limit\s*\(\s*int\s+limit\s*,\s*output\s+string\s+error\s*\).*?if\s*\(\s*limit\s*<\s*-1\s*\).*?report limit must be -1 or non-negative, got %0d.*?return\s+0\s*;.*?m_scoreboard\.m_cfg\.m_report_limit\s*=\s*limit\s*;.*?error\s*=\s*\"\"\s*;.*?return\s+1\s*;",
    }
    for description, pattern in expected_proxy_bodies.items():
        assert re.search(pattern, proxy, flags=re.DOTALL), (
            f"typed proxy has incorrect {description} body"
        )
    assert not re.search(r"type\s+TRANS_TYPE\s*=", proxy_match.group(0))

    build = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::build_phase\s*\(\s*uvm_phase\s+phase\s*\)",
        "build_phase",
    )
    registration = re.search(
        r"(?ms)begin\s*common_scb_typed_proxy\s*#\s*\(\s*TRANS_TYPE\s*,\s*STREAM_ID_WIDTH\s*\)\s+typed_proxy\s*;\s*"
        r"string\s+registry_error\s*;\s*"
        r"typed_proxy\s*=\s*new\s*\(\s*\{\s*get_name\s*\(\s*\)\s*,\s*\"_proxy\"\s*\}\s*,\s*this\s*\)\s*;\s*"
        r"m_proxy\s*=\s*typed_proxy\s*;\s*"
        r"if\s*\(\s*!\s*common_scb_registry::register_proxy\s*\(\s*m_proxy\s*,\s*registry_error\s*\)\s*\)\s*"
        r"`uvm_error\s*\(\s*\"SCB_REGISTRY\"\s*,\s*registry_error\s*\)\s*end\s*$",
        build,
    )
    assert registration, "build_phase must register the typed proxy at its end"
    assert not re.search(r"\baip_|AIP_", proxy_match.group(0))


def assert_vcs_portable_match_counter(types_raw: str, core_raw: str) -> None:
    types = strip_sv_comments(types_raw)
    core = strip_sv_comments(core_raw)
    stream_state = re.search(
        r"(?ms)^[ \t]*class\s+common_scb_stream_state\b(?P<body>.*?)"
        r"^[ \t]*endclass",
        types,
    )
    assert stream_state, "missing common_scb_stream_state declaration"
    state_body = stream_state.group("body")
    assert re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+match_count\s*;",
        state_body,
    ), "stream state must use the VCS-portable match_count field"
    assert not re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+matches\s*;",
        state_body,
    ), "matches is a reserved SystemVerilog identifier"
    assert not re.search(r"\.matches\b", types + core), (
        "generated scoreboard sources must not retain stale .matches references"
    )


def render_task6_sources() -> tuple[str, str]:
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=PlatformType.ADVANCE,
        aip_core=False,
    )
    generator = PlatformGenerator(config)
    core = generator.render_template(
        "common/base_scb.sv.j2",
        file_name="common_uvm_scb.sv",
    )
    types = generator.render_template(
        "common/common_scb_types.sv.j2",
        file_name="common_scb_types.sv",
    )
    return core, types


def test_vcs_portability_summary_uses_explicit_string_concatenation():
    core_raw, _ = render_task6_sources()
    summary = core_method_body(
        strip_sv_comments(core_raw),
        r"function\s+string\s+common_uvm_scb::get_summary\s*\(\s*\)",
        "get_summary",
    )
    assert re.search(r"return\s+\$sformatf\s*\(\s*\{", summary)


def test_vcs_portability_uses_extern_before_protected():
    core_raw, _ = render_task6_sources()
    core = strip_sv_comments(core_raw)
    declaration = core[: core.index("endclass", core.index("class common_uvm_scb"))]
    assert len(re.findall(r"(?m)^[ \t]*extern\s+protected\s+function\b", declaration)) == 18
    assert not re.search(r"(?m)^[ \t]*protected\s+extern\s+function\b", declaration)


def test_vcs_portability_allocates_queue_items_before_push():
    core_raw, _ = render_task6_sources()
    core = strip_sv_comments(core_raw)
    expected = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::push_expected\s*\([^;]+\)",
        "push_expected",
    )
    actual = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::push_actual\s*\([^;]+\)",
        "push_actual",
    )
    assert re.search(r"^[ \t]*pending_t\s+pending\s*;", expected, flags=re.MULTILINE)
    assert re.search(r"^[ \t]*pending_t\s+pending\s*;", actual, flags=re.MULTILINE)
    assert not re.search(r"push_back\s*\(\s*new\s*\(", expected + actual)


def test_vcs_portability_avoids_reserved_matches_identifier():
    core_raw, types_raw = render_task6_sources()
    assert_vcs_portable_match_counter(types_raw, core_raw)


def assert_core_contract(core_raw: str) -> None:
    core = strip_sv_comments(core_raw)

    declarations = {
        "include guard": (
            r"(?m)^[ \t]*`ifndef[ \t]+COMMON_UVM_SCB__SV\b.*$\n"
            r"[ \t]*`define[ \t]+COMMON_UVM_SCB__SV\b"
        ),
        "parameterized scoreboard": (
            r"(?ms)^[ \t]*class\s+common_uvm_scb\s*#\s*\(\s*"
            r"type\s+TRANS_TYPE\s*,\s*"
            r"int\s+STREAM_ID_WIDTH\s*=\s*64\s*\)\s*"
            r"extends\s+uvm_scoreboard\s*;"
        ),
        "stream ID typedef": (
            r"(?m)^[ \t]*typedef\s+bit\s*\[\s*STREAM_ID_WIDTH\s*-\s*1\s*:\s*0\s*\]"
            r"\s+stream_id_t\s*;"
        ),
        "component registration": (
            r"`uvm_component_param_utils\s*\(\s*common_uvm_scb\s*#\s*\(\s*"
            r"TRANS_TYPE\s*,\s*STREAM_ID_WIDTH\s*\)\s*\)"
        ),
        "configuration member": r"(?m)^[ \t]*common_uvm_scb_cfg\s+m_cfg\s*;",
        "result analysis port": (
            r"(?m)^[ \t]*uvm_analysis_port\s*#\s*\(\s*result_t\s*\)"
            r"\s+m_result_ap\s*;"
        ),
        "expected function API": (
            r"(?m)^[ \t]*extern\s+function\s+void\s+push_expected\s*\("
        ),
        "actual function API": (
            r"(?m)^[ \t]*extern\s+function\s+void\s+push_actual\s*\("
        ),
        "virtual compare API": (
            r"(?m)^[ \t]*extern\s+virtual\s+function\s+bit\s+compare_items\s*\("
        ),
        "status declaration": (
            r"(?m)^[ \t]*extern\s+function\s+scb_status_e\s+get_status\s*\(\s*\)\s*;"
        ),
        "clean declaration": (
            r"(?m)^[ \t]*extern\s+function\s+bit\s+is_clean\s*\(\s*\)\s*;"
        ),
        "summary declaration": (
            r"(?m)^[ \t]*extern\s+function\s+string\s+get_summary\s*\(\s*\)\s*;"
        ),
        "report declaration": (
            r"(?m)^[ \t]*extern\s+function\s+void\s+print_report\s*\(\s*"
            r"int\s+limit\s*=\s*-2\s*\)\s*;"
        ),
        "reset declaration": (
            r"(?m)^[ \t]*extern\s+function\s+void\s+reset_state\s*\(\s*"
            r"bit\s+clear_counters\s*=\s*1\s*\)\s*;"
        ),
        "expected legacy task": (
            r"(?m)^[ \t]*extern\s+virtual\s+task\s+send_rm_trans_to_cmp\s*\("
        ),
        "actual legacy task": (
            r"(?m)^[ \t]*extern\s+virtual\s+task\s+send_dut_trans_to_cmp\s*\("
        ),
    }
    for description, pattern in declarations.items():
        assert re.search(pattern, core), f"missing core {description}"

    core_declaration = core[: core.index("endclass", core.index("class common_uvm_scb"))]
    protected_methods = (
        "state_for",
        "retained_copy",
        "can_enqueue",
        "reconcile_ordered_exact",
        "reconcile_ordered_lossy",
        "reconcile_unordered_expected",
        "reconcile_unordered_actual",
        "record_match",
        "record_mismatch",
        "record_drop",
        "record_unexpected",
        "record_overflow",
        "emit_detail",
        "publish_result",
        "update_peak",
        "row_before",
        "make_row",
        "finalize_pending",
    )
    for method in protected_methods:
        assert re.search(
            rf"(?m)^[ \t]*extern\s+protected\s+function\s+\w+\s+"
            rf"{method}\s*\([^;]*;",
            core_declaration,
        ), f"protected method {method} must use VCS-portable extern protected order"
    assert len(re.findall(r"(?m)^[ \t]*extern\s+protected\s+function\b", core_declaration)) == len(
        protected_methods
    ), "every protected method declaration must use extern protected order"
    assert not re.search(
        r"(?m)^[ \t]*protected\s+extern\s+function\b",
        core_declaration,
    ), "VCS rejects protected extern qualifier order"

    counters = (
        "expected_inputs",
        "actual_inputs",
        "matches",
        "mismatches",
        "allowed_drops",
        "unexpected_actuals",
        "overflows",
        "current_pending",
        "peak_pending",
        "detail_emitted",
        "suppressed_details",
    )
    for counter in counters:
        assert re.search(
            rf"(?m)^[ \t]*protected\s+longint\s+unsigned\s+m_{counter}\s*;",
            core,
        ), f"missing protected global counter m_{counter}"

    current_pending_declaration = re.search(
        r"(?m)^[ \t]*protected\s+longint\s+unsigned\s+m_current_pending\s*;",
        core,
    )
    peak_pending_declaration = re.search(
        r"(?m)^[ \t]*protected\s+longint\s+unsigned\s+m_peak_pending\s*;",
        core,
    )
    assert current_pending_declaration.start() < peak_pending_declaration.start(), (
        "current pending gauge must be declared beside and before peak pending"
    )

    build = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::build_phase\s*\(\s*uvm_phase\s+phase\s*\)",
        "build_phase",
    )
    assert_positions_in_order(
        build,
        [
            ("configured declaration", r"^[ \t]*common_uvm_scb_cfg\s+configured\s*;"),
            ("plusarg value declaration", r"^[ \t]*int\s+value\s*;"),
            ("parent build", r"super\.build_phase\s*\(\s*phase\s*\)\s*;"),
            (
                "stream-width range guard",
                r"STREAM_ID_WIDTH\s*<\s*1.*?STREAM_ID_WIDTH\s*>\s*64",
            ),
            ("stream-width fatal", r"`uvm_fatal\s*\(\s*\"SCB_CFG\""),
            (
                "optional config override",
                r"uvm_config_db\s*#\s*\(\s*common_uvm_scb_cfg\s*\)::get\s*\("
                r"\s*this\s*,\s*\"\"\s*,\s*\"cfg\"\s*,\s*configured\s*\)",
            ),
            ("non-null config guard", r"if\s*\(\s*configured\s*!=\s*null\s*\)"),
            ("config override assignment", r"m_cfg\s*=\s*configured\s*;"),
            ("null config warning", r"null cfg override ignored; using default"),
            (
                "report plusarg only",
                r"\$value\$plusargs\s*\(\s*\"SCB_REPORT_LIMIT=%d\"\s*,\s*value\s*\)",
            ),
            ("accepted report bound", r"if\s*\(\s*value\s*>=\s*-1\s*\)"),
            ("invalid plusarg warning", r"invalid SCB_REPORT_LIMIT=%0d; using 10"),
            ("report normalization", r"m_cfg\.m_report_limit\s*<\s*-1"),
            ("error-limit normalization", r"m_cfg\.m_err_limit\s*<\s*0"),
            ("pending-limit normalization", r"m_cfg\.m_pending_limit\s*<\s*0"),
            ("comparison-mode validation", r"case\s*\(\s*m_cfg\.m_cmp_mode\s*\)"),
            ("comparison-mode default", r"default\s*:"),
            ("comparison-mode warning", r"invalid m_cmp_mode=%0d; using SCB_UNORDERED"),
            ("comparison-mode fallback", r"m_cfg\.m_cmp_mode\s*=\s*SCB_UNORDERED\s*;"),
        ],
    )
    width_guard = re.search(
        r"if\s*\(\s*\(\s*STREAM_ID_WIDTH\s*<\s*1\s*\)\s*\|\|\s*"
        r"\(\s*STREAM_ID_WIDTH\s*>\s*64\s*\)\s*\)\s*"
        r"`uvm_fatal\s*\(\s*\"SCB_CFG\"\s*,\s*\$sformatf\s*\(\s*"
        r"\"STREAM_ID_WIDTH must be in range 1\.\.64; got %0d\"\s*,\s*"
        r"STREAM_ID_WIDTH\s*\)\s*\)",
        build,
    )
    assert width_guard, "build_phase must fatally reject stream widths outside 1..64"

    config_override = re.search(
        r"if\s*\(\s*uvm_config_db\s*#\s*\(\s*common_uvm_scb_cfg\s*\)::get\s*\("
        r"\s*this\s*,\s*\"\"\s*,\s*\"cfg\"\s*,\s*configured\s*\)\s*\)\s*begin\s*"
        r"if\s*\(\s*configured\s*!=\s*null\s*\)\s*"
        r"m_cfg\s*=\s*configured\s*;\s*else\s*"
        r"`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*"
        r"\"null cfg override ignored; using default\"\s*\)\s*end",
        build,
    )
    assert config_override, (
        "config override must accept non-null handles and warn while retaining defaults on null"
    )

    invalid_plusarg_branch = re.search(
        r"if\s*\(\s*\$value\$plusargs\s*\(\s*\"SCB_REPORT_LIMIT=%d\"\s*,\s*"
        r"value\s*\)\s*\)\s*begin\s*if\s*\(\s*value\s*>=\s*-1\s*\)\s*"
        r"m_cfg\.m_report_limit\s*=\s*value\s*;\s*else\s*begin\s*"
        r"`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*\$sformatf\s*\(\s*"
        r"\"invalid SCB_REPORT_LIMIT=%0d; using 10\"\s*,\s*value\s*\)\s*\)\s*"
        r"m_cfg\.m_report_limit\s*=\s*value\s*;\s*end\s*end",
        build,
    )
    assert invalid_plusarg_branch, (
        "invalid report plusargs must store the invalid value for common fallback normalization"
    )
    invalid_report_warning = (
        r"`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*\$sformatf\s*\(\s*"
        r"\"invalid SCB_REPORT_LIMIT=%0d; using 10\"\s*,\s*value\s*\)\s*\)"
    )
    error_limit_warning = (
        r"`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*"
        r"\"m_err_limit must be non-negative; using 10\"\s*\)"
    )
    pending_limit_warning = (
        r"`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*"
        r"\"m_pending_limit must be non-negative; using 0\"\s*\)"
    )
    null_config_warning = (
        r"`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*"
        r"\"null cfg override ignored; using default\"\s*\)"
    )
    invalid_mode_warning = (
        r"`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*\$sformatf\s*\(\s*"
        r"\"invalid m_cmp_mode=%0d; using SCB_UNORDERED\"\s*,\s*"
        r"m_cfg\.m_cmp_mode\s*\)\s*\)"
    )
    required_warnings = [
        ("null config override", null_config_warning),
        ("invalid report plusarg", invalid_report_warning),
        ("error-limit normalization", error_limit_warning),
        ("pending-limit normalization", pending_limit_warning),
        ("invalid comparison mode", invalid_mode_warning),
    ]
    warning_positions = []
    for description, pattern in required_warnings:
        matches = list(re.finditer(pattern, build))
        assert len(matches) == 1, (
            f"build_phase must contain exactly one required {description} warning"
        )
        warning_positions.append(matches[0].start())
    assert warning_positions == sorted(warning_positions), (
        "configuration warnings must follow config, plusarg, bounds, then mode order"
    )
    report_warning_calls = [
        call
        for call in sv_macro_calls(build, "uvm_warning")
        if re.search(r"report[_ ]limit", call, flags=re.IGNORECASE)
    ]
    assert len(report_warning_calls) == 1 and re.fullmatch(
        invalid_report_warning, report_warning_calls[0]
    ), (
        "the invalid plusarg path must be the only report-limit warning"
    )
    report_default_assignment = (
        r"m_cfg\.m_report_limit\s*=\s*10\s*;"
    )
    assignments = list(re.finditer(report_default_assignment, build))
    assert len(assignments) == 1, (
        "build_phase must normalize m_report_limit to 10 exactly once"
    )
    report_normalization = re.search(
        r"if\s*\(\s*m_cfg\.m_report_limit\s*<\s*-1\s*\)\s*"
        r"m_cfg\.m_report_limit\s*=\s*10\s*;",
        build,
    )
    assert report_normalization, (
        "the sole report-limit default assignment must belong to the silent "
        "post-plusarg normalization"
    )
    assert assignments[0].start() > report_normalization.start(), (
        "report-limit default assignment must occur after its normalization guard"
    )

    mode_validation = re.search(
        r"case\s*\(\s*m_cfg\.m_cmp_mode\s*\)\s*"
        r"SCB_ORDERED_EXACT\s*,\s*SCB_ORDERED_LOSSY\s*,\s*SCB_UNORDERED\s*:\s*;\s*"
        r"default\s*:\s*begin\s*"
        + invalid_mode_warning
        + r"\s*m_cfg\.m_cmp_mode\s*=\s*SCB_UNORDERED\s*;\s*end\s*endcase",
        build,
    )
    assert mode_validation, "build_phase must normalize invalid comparison modes"

    retained = core_method_body(
        core,
        r"function\s+bit\s+common_uvm_scb::retained_copy\s*\([^;]+\)",
        "retained_copy",
    )
    assert_positions_in_order(
        retained,
        [
            ("clone declaration", r"^[ \t]*uvm_object\s+cloned\s*;"),
            ("state declaration", r"^[ \t]*state_t\s+state\s*;"),
            ("state lookup", r"state\s*=\s*state_for\s*\(\s*stream_id\s*\)\s*;"),
            ("retained reset", r"retained\s*=\s*null\s*;"),
            ("null guard", r"if\s*\(\s*source\s*==\s*null\s*\)"),
            ("null accounting", r"record_overflow\s*\([^;]+\)\s*;"),
            ("null detail", r"SCB_NULL_INPUT"),
            ("clone-disable path", r"if\s*\(\s*!\s*m_cfg\.m_clone_en\s*\)"),
            ("source retention", r"retained\s*=\s*source\s*;"),
            ("clone call", r"cloned\s*=\s*source\.clone\s*\(\s*\)\s*;"),
            ("typed clone cast", r"\$cast\s*\(\s*retained\s*,\s*cloned\s*\)"),
            ("clone failure detail", r"SCB_CLONE_FAILED"),
        ],
    )

    admission = core_method_body(
        core,
        r"function\s+bit\s+common_uvm_scb::can_enqueue\s*\([^;]+\)",
        "can_enqueue",
    )
    assert_positions_in_order(
        admission,
        [
            (
                "nonzero pending bound",
                r"if\s*\(\s*\(\s*m_cfg\.m_pending_limit\s*!=\s*0\s*\)\s*&&\s*"
                r"\(\s*depth\s*>=\s*m_cfg\.m_pending_limit\s*\)\s*\)",
            ),
            ("overflow accounting", r"record_overflow\s*\([^;]+\)\s*;"),
            ("overflow detail", r"SCB_PENDING_OVERFLOW"),
            ("overflow rejection", r"return\s+0\s*;"),
            ("admission", r"return\s+1\s*;"),
        ],
    )

    expected_push = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::push_expected\s*\([^;]+\)",
        "push_expected",
    )
    assert_positions_in_order(
        expected_push,
        [
            ("expected retained declaration", r"^[ \t]*TRANS_TYPE\s+retained\s*;"),
            ("expected state declaration", r"^[ \t]*state_t\s+state\s*;"),
            ("expected pending declaration", r"^[ \t]*pending_t\s+pending\s*;"),
            ("expected state lookup", r"state\s*=\s*state_for\s*\(\s*stream_id\s*\)\s*;"),
            ("global expected input", r"m_expected_inputs\s*\+\+\s*;"),
            ("stream expected input", r"state\.expected_inputs\s*\+\+\s*;"),
            ("expected retained copy", r"retained_copy\s*\(\s*tr\s*,\s*stream_id\s*,\s*\"expected\""),
            ("expected admission", r"can_enqueue\s*\(\s*state\s*,\s*stream_id\s*,\s*\"expected\""),
            ("expected pending allocation", r"pending\s*=\s*new\s*\(\s*retained\s*,\s*kind\s*\)\s*;"),
            ("expected enqueue", r"state\.expected_q\.push_back\s*\(\s*pending\s*\)\s*;"),
            ("expected pending gauge increment", r"m_current_pending\s*\+\+\s*;"),
            ("expected peak update", r"update_peak\s*\(\s*state\s*\)\s*;"),
            ("expected dispatch", r"case\s*\(\s*m_cfg\.m_cmp_mode\s*\)"),
            ("expected unordered dispatch", r"SCB_UNORDERED\s*:\s*reconcile_unordered_expected\s*\(\s*state\s*\)\s*;"),
            ("expected defensive default", r"default\s*:\s*reconcile_unordered_expected\s*\(\s*state\s*\)\s*;"),
        ],
    )
    assert len(re.findall(r"m_current_pending\s*\+\+\s*;", expected_push)) == 1, (
        "each successful expected enqueue must increment the gauge exactly once"
    )

    actual_push = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::push_actual\s*\([^;]+\)",
        "push_actual",
    )
    assert_positions_in_order(
        actual_push,
        [
            ("actual retained declaration", r"^[ \t]*TRANS_TYPE\s+retained\s*;"),
            ("actual state declaration", r"^[ \t]*state_t\s+state\s*;"),
            ("actual pending declaration", r"^[ \t]*pending_t\s+pending\s*;"),
            ("actual state lookup", r"state\s*=\s*state_for\s*\(\s*stream_id\s*\)\s*;"),
            ("global actual input", r"m_actual_inputs\s*\+\+\s*;"),
            ("stream actual input", r"state\.actual_inputs\s*\+\+\s*;"),
            (
                "strict-arrival condition",
                r"if\s*\(\s*m_cfg\.m_strict_arrival\s*&&\s*\(\s*state\.expected_q\.size\s*\(\s*\)\s*==\s*0\s*\)\s*\)",
            ),
            ("per-occurrence diagnostic", r"state\.diagnostic_warnings\s*\+\+\s*;"),
            ("global warning guard", r"if\s*\(\s*!\s*m_strict_arrival_warned\s*\)"),
            ("strict warning", r"SCB_ACTUAL_FIRST"),
            ("actual retained copy", r"retained_copy\s*\(\s*tr\s*,\s*stream_id\s*,\s*\"actual\""),
            ("actual admission", r"can_enqueue\s*\(\s*state\s*,\s*stream_id\s*,\s*\"actual\""),
            ("actual pending allocation", r"pending\s*=\s*new\s*\(\s*retained\s*,\s*kind\s*\)\s*;"),
            ("actual enqueue", r"state\.actual_q\.push_back\s*\(\s*pending\s*\)\s*;"),
            ("actual pending gauge increment", r"m_current_pending\s*\+\+\s*;"),
            ("actual peak update", r"update_peak\s*\(\s*state\s*\)\s*;"),
            ("actual dispatch", r"case\s*\(\s*m_cfg\.m_cmp_mode\s*\)"),
            ("actual unordered dispatch", r"SCB_UNORDERED\s*:\s*reconcile_unordered_actual\s*\(\s*state\s*\)\s*;"),
            ("actual defensive default", r"default\s*:\s*reconcile_unordered_actual\s*\(\s*state\s*\)\s*;"),
        ],
    )
    assert len(re.findall(r"m_current_pending\s*\+\+\s*;", actual_push)) == 1, (
        "each successful actual enqueue must increment the gauge exactly once"
    )
    assert not re.search(r"push_back\s*\(\s*new\s*\(", expected_push + actual_push), (
        "VCS-portable queue insertion requires a separately allocated pending handle"
    )

    peak_update = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::update_peak\s*\([^;]+\)",
        "update_peak",
    )
    assert_positions_in_order(
        peak_update,
        [
            ("stream depth declaration", r"^[ \t]*longint\s+unsigned\s+depth\s*;"),
            ("stream depth calculation", r"depth\s*=\s*state\.expected_q\.size\s*\(\s*\)\s*\+\s*state\.actual_q\.size\s*\(\s*\)\s*;"),
            ("stream peak update", r"if\s*\(\s*depth\s*>\s*state\.peak_pending\s*\)\s*state\.peak_pending\s*=\s*depth\s*;"),
            ("global peak comparison", r"if\s*\(\s*m_current_pending\s*>\s*m_peak_pending\s*\)"),
            ("global peak update", r"m_peak_pending\s*=\s*m_current_pending\s*;"),
        ],
    )
    assert not re.search(r"foreach\s*\(\s*m_streams\b", peak_update), (
        "global pending peak must not scan the stream map"
    )
    assert "total_depth" not in peak_update, (
        "global pending peak must use the O(1) current-pending gauge"
    )

    compare = core_method_body(
        core,
        r"function\s+bit\s+common_uvm_scb::compare_items\s*\([^;]+\)",
        "compare_items",
    )
    assert re.search(
        r"diff\s*=\s*\"\"\s*;\s*"
        r"return\s+expected\.self_define_do_compare\s*\(\s*actual\s*,\s*diff\s*,\s*kind\s*\)\s*;",
        compare,
    ), "compare_items must clear diff immediately before delegating"

    exact = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::reconcile_ordered_exact\s*\([^;]+\)",
        "reconcile_ordered_exact",
    )
    assert_positions_in_order(
        exact,
        [
            ("exact dual-queue loop", r"while\s*\(\s*\(\s*state\.expected_q\.size\s*\(\s*\)\s*!=\s*0\s*\)\s*&&\s*\(\s*state\.actual_q\.size\s*\(\s*\)\s*!=\s*0\s*\)\s*\)"),
            ("exact expected pop", r"expected\s*=\s*state\.expected_q\.pop_front\s*\(\s*\)\s*;"),
            ("exact actual pop", r"actual\s*=\s*state\.actual_q\.pop_front\s*\(\s*\)\s*;"),
            ("exact compare", r"compare_items\s*\(\s*expected\.tr\s*,\s*actual\.tr"),
            ("exact match accounting", r"record_match\s*\(\s*state\s*,\s*expected\s*,\s*actual"),
            ("exact mismatch accounting", r"record_mismatch\s*\(\s*state\s*,\s*expected\s*,\s*actual"),
        ],
    )

    lossy = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::reconcile_ordered_lossy\s*\([^;]+\)",
        "reconcile_ordered_lossy",
    )
    assert_positions_in_order(
        lossy,
        [
            ("lossy oldest-actual loop", r"while\s*\(\s*\(\s*state\.actual_q\.size\s*\(\s*\)\s*!=\s*0\s*\)\s*&&\s*\(\s*state\.expected_q\.size\s*\(\s*\)\s*!=\s*0\s*\)\s*\)"),
            ("lossy scan", r"foreach\s*\(\s*state\.expected_q\s*\[\s*i\s*\]\s*\)"),
            ("lossy compares oldest actual", r"state\.actual_q\s*\[\s*0\s*\]\.tr"),
            ("lossy retains unmatched actual", r"if\s*\(\s*match_index\s*<\s*0\s*\)\s*return\s*;"),
            ("lossy records preceding drops", r"repeat\s*\(\s*match_index\s*\)\s*record_drop\s*\(\s*state\s*,\s*state\.expected_q\.pop_front\s*\(\s*\)\s*\)\s*;"),
            ("lossy pops matched pair", r"record_match\s*\(\s*state\s*,\s*state\.expected_q\.pop_front\s*\(\s*\)\s*,\s*state\.actual_q\.pop_front\s*\(\s*\)"),
        ],
    )
    assert "record_unexpected" not in lossy, (
        "lossy reconciliation must retain, not classify, an unmatched actual"
    )

    unordered_expected = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::reconcile_unordered_expected\s*\([^;]+\)",
        "reconcile_unordered_expected",
    )
    assert_positions_in_order(
        unordered_expected,
        [
            ("unordered expected declaration", r"^[ \t]*pending_t\s+expected\s*;"),
            ("unordered actual declaration", r"^[ \t]*pending_t\s+actual\s*;"),
            ("newest expected", r"expected\s*=\s*state\.expected_q\s*\[\s*state\.expected_q\.size\s*\(\s*\)\s*-\s*1\s*\]\s*;"),
            ("unordered expected scans actuals", r"foreach\s*\(\s*state\.actual_q\s*\[\s*i\s*\]\s*\)"),
            ("unordered expected captures actual", r"actual\s*=\s*state\.actual_q\s*\[\s*match_index\s*\]\s*;"),
            ("unordered expected removes newest", r"state\.expected_q\.pop_back\s*\(\s*\)"),
            ("unordered expected removes matched actual", r"state\.actual_q\.delete\s*\(\s*match_index\s*\)\s*;"),
            ("unordered expected match", r"record_match\s*\(\s*state\s*,\s*expected\s*,\s*actual\s*,\s*diff\s*\)\s*;"),
        ],
    )

    unordered_actual = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::reconcile_unordered_actual\s*\([^;]+\)",
        "reconcile_unordered_actual",
    )
    assert_positions_in_order(
        unordered_actual,
        [
            ("unordered actual declaration", r"^[ \t]*pending_t\s+actual\s*;"),
            ("unordered expected declaration", r"^[ \t]*pending_t\s+expected\s*;"),
            ("newest actual", r"actual\s*=\s*state\.actual_q\s*\[\s*state\.actual_q\.size\s*\(\s*\)\s*-\s*1\s*\]\s*;"),
            ("unordered actual scans expecteds", r"foreach\s*\(\s*state\.expected_q\s*\[\s*i\s*\]\s*\)"),
            ("unordered actual captures expected", r"expected\s*=\s*state\.expected_q\s*\[\s*match_index\s*\]\s*;"),
            ("unordered actual removes newest", r"state\.actual_q\.pop_back\s*\(\s*\)"),
            ("unordered actual removes matched expected", r"state\.expected_q\.delete\s*\(\s*match_index\s*\)\s*;"),
            ("unordered actual match", r"record_match\s*\(\s*state\s*,\s*expected\s*,\s*actual\s*,\s*diff\s*\)\s*;"),
        ],
    )

    publication = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::publish_result\s*\([^;]+\)",
        "publish_result",
    )
    assert_positions_in_order(
        publication,
        [
            ("result declaration", r"^[ \t]*result_t\s+result\s*;"),
            ("result allocation", r"result\s*=\s*new\s*\(\s*\"result\"\s*\)\s*;"),
            ("result stream", r"result\.stream_id\s*=\s*state\.stream_id\s*;"),
            ("nullable expected", r"result\.expected\s*=\s*\(\s*expected\s*==\s*null\s*\)\s*\?\s*null\s*:\s*expected\.tr\s*;"),
            ("nullable actual", r"result\.actual\s*=\s*\(\s*actual\s*==\s*null\s*\)\s*\?\s*null\s*:\s*actual\.tr\s*;"),
            ("result kind selection", r"result\.kind\s*=\s*\(\s*expected\s*!=\s*null\s*\)\s*\?\s*expected\.kind\s*:\s*\(\s*\(\s*actual\s*!=\s*null\s*\)\s*\?\s*actual\.kind\s*:\s*-1\s*\)\s*;"),
            ("result matched", r"result\.matched\s*=\s*matched\s*;"),
            ("result diff", r"result\.diff\s*=\s*diff\s*;"),
            ("result publication", r"m_result_ap\.write\s*\(\s*result\s*\)\s*;"),
        ],
    )

    accounting = {
        "record_match": ("state.match_count", "m_matches", "publish_result"),
        "record_mismatch": ("state.mismatches", "m_mismatches", "publish_result", "SCB_MISMATCH"),
        "record_drop": ("state.allowed_drops", "m_allowed_drops"),
        "record_unexpected": ("state.unexpected_actuals", "m_unexpected_actuals", "publish_result", "SCB_UNEXPECTED_ACTUAL"),
        "record_overflow": ("state.overflows", "m_overflows"),
    }
    for method, tokens in accounting.items():
        body = core_method_body(
            core,
            rf"function\s+void\s+common_uvm_scb::{method}\s*\([^;]+\)",
            method,
        )
        previous = -1
        for token in tokens:
            position = body.find(token)
            assert position >= 0, f"missing core {method} accounting token {token}"
            assert position > previous, f"core {method} accounting is out of order"
            previous = position

    match_accounting = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::record_match\s*\([^;]+\)",
        "record_match",
    )
    mismatch_accounting = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::record_mismatch\s*\([^;]+\)",
        "record_mismatch",
    )
    drop_accounting = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::record_drop\s*\([^;]+\)",
        "record_drop",
    )
    unexpected_accounting = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::record_unexpected\s*\([^;]+\)",
        "record_unexpected",
    )
    overflow_accounting = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::record_overflow\s*\([^;]+\)",
        "record_overflow",
    )
    expected_decrement = (
        r"if\s*\(\s*expected\s*!=\s*null\s*\)\s*m_current_pending\s*--\s*;"
    )
    actual_decrement = (
        r"if\s*\(\s*actual\s*!=\s*null\s*\)\s*m_current_pending\s*--\s*;"
    )
    for description, body in (
        ("match", match_accounting),
        ("mismatch", mismatch_accounting),
    ):
        expected_match = re.search(expected_decrement, body)
        actual_match = re.search(actual_decrement, body)
        first_counter = re.search(r"state\.(?:match_count|mismatches)\s*\+\+\s*;", body)
        assert expected_match and actual_match and first_counter, (
            f"{description} must decrement every non-null consumed side"
        )
        assert len(re.findall(expected_decrement, body)) == 1
        assert len(re.findall(actual_decrement, body)) == 1
        assert expected_match.start() < actual_match.start() < first_counter.start(), (
            f"{description} pending decrements must precede result accounting"
        )
    assert re.search(expected_decrement, drop_accounting), (
        "drop must decrement its consumed non-null expected item"
    )
    assert len(re.findall(expected_decrement, drop_accounting)) == 1
    assert re.search(actual_decrement, unexpected_accounting), (
        "unexpected must decrement its consumed non-null actual item"
    )
    assert len(re.findall(actual_decrement, unexpected_accounting)) == 1
    assert "m_current_pending" not in overflow_accounting, (
        "overflow must not change the admitted-pending gauge"
    )
    for description, body in (
        ("match", match_accounting),
        ("mismatch", mismatch_accounting),
        ("drop", drop_accounting),
        ("unexpected", unexpected_accounting),
    ):
        assert not re.search(
            r"if\s*\([^)]*\bm_current_pending\b[^)]*\)", body
        ), f"{description} must not hide pending accounting bugs with a gauge guard"

    assert not re.search(r"\.matches\b", core), (
        "generated core must not reference the reserved SystemVerilog identifier matches"
    )

    details = core_method_body(
        core,
        r"function\s+void\s+common_uvm_scb::emit_detail\s*\([^;]+\)",
        "emit_detail",
    )
    assert_positions_in_order(
        details,
        [
            ("detail state declaration", r"^[ \t]*state_t\s+state\s*;"),
            ("detail state lookup", r"state\s*=\s*state_for\s*\(\s*stream_id\s*\)\s*;"),
            ("global detail limit", r"if\s*\(\s*m_detail_emitted\s*<\s*m_cfg\.m_err_limit\s*\)"),
            ("emitted accounting", r"m_detail_emitted\s*\+\+\s*;"),
            ("stream-tagged error", r"`uvm_error\s*\(\s*id\s*,\s*\$sformatf\s*\(\s*\"stream=0x%0h %s\""),
            ("global suppression accounting", r"m_suppressed_details\s*\+\+\s*;"),
            ("stream suppression accounting", r"state\.suppressed_details\s*\+\+\s*;"),
        ],
    )

    expected_wrapper = core_method_body(
        core,
        r"task\s+common_uvm_scb::send_rm_trans_to_cmp\s*\([^;]+\)",
        "send_rm_trans_to_cmp",
        terminator="task",
    )
    actual_wrapper = core_method_body(
        core,
        r"task\s+common_uvm_scb::send_dut_trans_to_cmp\s*\([^;]+\)",
        "send_dut_trans_to_cmp",
        terminator="task",
    )
    assert re.search(
        r"push_expected\s*\(\s*rm_tr\s*,\s*stream_id\s*,\s*kind\s*\)\s*;",
        expected_wrapper,
    ), "legacy RM wrapper must call push_expected"
    assert re.search(
        r"push_actual\s*\(\s*dut_tr\s*,\s*stream_id\s*,\s*kind\s*\)\s*;",
        actual_wrapper,
    ), "legacy DUT wrapper must call push_actual"

    assert_task6_lifecycle_report_contract(core)
    assert_task6_proxy_contract(core)

    assert not re.search(r"\baip_|AIP_", core_raw), (
        "raw core template must remain AIP-independent"
    )
    assert "{{" not in core_raw and "{%" not in core_raw, (
        "core render must not retain Jinja markers"
    )


def test_standalone_core_template_implements_task6_lifecycle_report_contract():
    template_path = (
        Path(__file__).parents[1]
        / "uvm_gen/templates/common/base_scb.sv.j2"
    )
    assert template_path.is_file(), (
        "missing Task 6 core template: "
        "uvm_gen/templates/common/base_scb.sv.j2"
    )
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=PlatformType.ADVANCE,
        aip_core=False,
    )
    core_raw = PlatformGenerator(config).render_template(
        "common/base_scb.sv.j2",
        file_name="common_uvm_scb.sv",
    )
    types_raw = PlatformGenerator(config).render_template(
        "common/common_scb_types.sv.j2",
        file_name="common_scb_types.sv",
    )

    assert_core_contract(core_raw)
    assert_vcs_portable_match_counter(types_raw, core_raw)

    mutations = {
        "default transaction type": (
            r"class common_uvm_scb #\(type TRANS_TYPE,",
            r"class common_uvm_scb #(type TRANS_TYPE=uvm_sequence_item,",
        ),
        "unconditional null config assignment": (
            r"(?s)if \(uvm_config_db#\(common_uvm_scb_cfg\)::get\(this, \"\", \"cfg\", configured\)\) begin\s*"
            r"if \(configured != null\)\s*m_cfg = configured;\s*else\s*"
            r"`uvm_warning\(\"SCB_CFG\", \"null cfg override ignored; using default\"\)\s*end",
            r"if (uvm_config_db#(common_uvm_scb_cfg)::get(this, \"\", \"cfg\", configured))\n"
            r"        m_cfg = configured;",
        ),
        "invalid plusarg does not force common fallback": (
            r"(?s)(else begin\s*`uvm_warning\(\"SCB_CFG\",\s*"
            r"\$sformatf\(\"invalid SCB_REPORT_LIMIT=%0d; using 10\", value\)\))\s*"
            r"m_cfg\.m_report_limit = value;",
            r"\1",
        ),
        "missing stream width guard": (
            r"(?s)if \(\(STREAM_ID_WIDTH < 1\) \|\| \(STREAM_ID_WIDTH > 64\)\)\s*"
            r"`uvm_fatal\(\"SCB_CFG\",\s*\$sformatf\("
            r"\"STREAM_ID_WIDTH must be in range 1\.\.64; got %0d\",\s*STREAM_ID_WIDTH\)\)",
            "",
        ),
        "missing comparison mode validation": (
            r"(?s)case \(m_cfg\.m_cmp_mode\)\s*"
            r"SCB_ORDERED_EXACT, SCB_ORDERED_LOSSY, SCB_UNORDERED: ;\s*"
            r"default: begin\s*`uvm_warning\(\"SCB_CFG\",\s*\$sformatf\("
            r"\"invalid m_cmp_mode=%0d; using SCB_UNORDERED\",\s*m_cfg\.m_cmp_mode\)\)\s*"
            r"m_cfg\.m_cmp_mode = SCB_UNORDERED;\s*end\s*endcase",
            "",
        ),
        "missing clone call": (
            r"(?m)^[ \t]*cloned\s*=\s*source\.clone\s*\(\s*\)\s*;[ \t]*$",
            "",
        ),
        "missing typed cast": (
            r"\(cloned == null\) \|\| !\$cast\(retained, cloned\)",
            "cloned == null",
        ),
        "blocking expected API": (
            r"extern function void push_expected",
            "extern task push_expected",
        ),
        "missing expected pending increment": (
            r"(?s)(function void common_uvm_scb::push_expected\b.*?"
            r"state\.expected_q\.push_back\(pending\);)\s*"
            r"m_current_pending\+\+;",
            r"\1",
        ),
        "missing actual pending increment": (
            r"(?s)(function void common_uvm_scb::push_actual\b.*?"
            r"state\.actual_q\.push_back\(pending\);)\s*"
            r"m_current_pending\+\+;",
            r"\1",
        ),
        "missing expected default dispatch": (
            r"default:\s*reconcile_unordered_expected\(state\);",
            "",
        ),
        "missing actual default dispatch": (
            r"default:\s*reconcile_unordered_actual\(state\);",
            "",
        ),
        "old global peak stream scan": (
            r"(?ms)^function void common_uvm_scb::update_peak\(state_t state\);.*?"
            r"^endfunction",
            "function void common_uvm_scb::update_peak(state_t state);\n"
            "    longint unsigned depth;\n"
            "    longint unsigned total_depth;\n"
            "    depth = state.expected_q.size() + state.actual_q.size();\n"
            "    total_depth = 0;\n"
            "    if (depth > state.peak_pending) state.peak_pending = depth;\n"
            "    foreach (m_streams[id])\n"
            "        total_depth += m_streams[id].expected_q.size()\n"
            "                     + m_streams[id].actual_q.size();\n"
            "    if (total_depth > m_peak_pending) m_peak_pending = total_depth;\n"
            "endfunction",
        ),
        "missing match actual decrement": (
            r"(?s)(function void common_uvm_scb::record_match\b.*?)"
            r"if \(actual != null\) m_current_pending--;",
            r"\1",
        ),
        "missing mismatch expected decrement": (
            r"(?s)(function void common_uvm_scb::record_mismatch\b.*?)"
            r"if \(expected != null\) m_current_pending--;",
            r"\1",
        ),
        "missing drop decrement": (
            r"(?s)(function void common_uvm_scb::record_drop\b.*?)"
            r"if \(expected != null\) m_current_pending--;",
            r"\1",
        ),
        "missing unexpected decrement": (
            r"(?s)(function void common_uvm_scb::record_unexpected\b.*?)"
            r"if \(actual != null\) m_current_pending--;",
            r"\1",
        ),
        "truthy pending underflow guard": (
            r"(?s)(function void common_uvm_scb::record_drop\b.*?)"
            r"(if \(expected != null\) m_current_pending--;)",
            r"\1if (m_current_pending) \2",
        ),
        "missing deterministic diff reset": (
            r"diff = \"\";\s*(return expected\.self_define_do_compare)",
            r"\1",
        ),
        "early lossy classification": (
            r"if \(match_index < 0\) return;",
            "if (match_index < 0) begin\n"
            "            record_unexpected(state, state.actual_q[0], \"early\");\n"
            "            return;\n"
            "        end",
        ),
        "bypassed global detail limit": (
            r"if \(m_detail_emitted < m_cfg.m_err_limit\) begin",
            "if (1) begin",
        ),
        "extra report warning and early assignment": (
            r"(?s)else begin\s*(?P<warning>`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*"
            r"\$sformatf\s*\(\s*\"invalid SCB_REPORT_LIMIT=%0d; using 10\"\s*,\s*"
            r"value\s*\)\s*\))\s*m_cfg\.m_report_limit\s*=\s*value\s*;\s*end\s*end\s*"
            r"if\s*\(\s*m_cfg\.m_report_limit\s*<\s*-1\s*\)\s*"
            r"m_cfg\.m_report_limit\s*=\s*10\s*;",
            r"else begin\n            \g<warning>\n"
            r"            m_cfg.m_report_limit = 10;\n"
            r"        end\n    end\n"
            r"    if (m_cfg.m_report_limit < -1) begin\n"
            r"        `uvm_warning(\"SCB_CFG\", "
            r"\"m_report_limit must be -1 or greater; using 10\")\n"
            r"        m_cfg.m_report_limit = 10;\n"
            r"    end",
        ),
        "differently worded report warning": (
            r"if \(m_cfg.m_report_limit < -1\)",
            r"`uvm_warning(\"SCB_CFG\", \"configured report limit invalid\")\n"
            r"    if (m_cfg.m_report_limit < -1)",
        ),
        "missing error-limit warning": (
            r"`uvm_warning\(\"SCB_CFG\", "
            r"\"m_err_limit must be non-negative; using 10\"\)",
            "",
        ),
        "missing pending-limit warning": (
            r"`uvm_warning\(\"SCB_CFG\", "
            r"\"m_pending_limit must be non-negative; using 0\"\)",
            "",
        ),
    }
    for description, (pattern, replacement) in mutations.items():
        broken, replacements = re.subn(pattern, replacement, core_raw)
        assert replacements == 1, f"failed to construct {description} mutation"
        with pytest.raises(AssertionError):
            assert_core_contract(broken)

    task_six_mutations = {
        "adjacent summary string literals": (
            r"(?s)\$sformatf\s*\(\s*\{\s*"
            r'"status=%s expected=%0d actual=%0d match=%0d mismatch=%0d "\s*,\s*'
            r'"drop=%0d unexpected=%0d pending_expected=%0d pending_actual=%0d "\s*,\s*'
            r'"overflow=%0d peak_pending=%0d suppressed=%0d"\s*\}\s*,',
            '$sformatf("status=%s expected=%0d actual=%0d match=%0d mismatch=%0d "\n'
            '        "drop=%0d unexpected=%0d pending_expected=%0d pending_actual=%0d "\n'
            '        "overflow=%0d peak_pending=%0d suppressed=%0d",',
        ),
        "invalid protected extern order": (
            r"extern protected function state_t state_for",
            "protected extern function state_t state_for",
        ),
        "inline expected queue allocation": (
            r"pending = new\(retained, kind\);\s*"
            r"state\.expected_q\.push_back\(pending\);",
            "state.expected_q.push_back(new(retained, kind));",
        ),
        "expected allocation before admission": (
            r"(?s)(function void common_uvm_scb::push_expected\([^;]+;\s*"
            r"TRANS_TYPE retained;\s*state_t state;\s*pending_t pending;)\s*"
            r"(?P<admission>.*?if \(!can_enqueue\(state, stream_id, \"expected\", "
            r"state\.expected_q\.size\(\)\)\) return;)\s*"
            r"pending = new\(retained, kind\);",
            r"\1\n    pending = new(retained, kind);\g<admission>",
        ),
        "reserved state matches reference": (
            r"state\.match_count\+\+;",
            "state.matches++;",
        ),
        "missing finalized guard": (
            r"(?m)^[ \t]*if \(m_finalized\) return;[ \t]*$",
            "",
        ),
        "lossy residual classified as mismatch": (
            r"(?s)(function void common_uvm_scb::finalize_pending\(\);.*?)"
            r"record_drop\(state, state\.expected_q\.pop_front\(\)\);",
            r'\1record_mismatch(state, state.expected_q.pop_front(), null, "wrong");',
        ),
        "report includes normal rows": (
            r"if \(row\.issue_count != 0\) begin",
            "if (row.issue_count >= 0) begin",
        ),
        "top-N ignored": (
            r"(?s)shown = \(effective_limit == -1\) \? rows\.size\(\)\s*"
            r": \(\(effective_limit < rows\.size\(\)\) \? effective_limit : rows\.size\(\)\);",
            "shown = rows.size();",
        ),
        "descending stream tie break": (
            r"return left\.stream_id < right\.stream_id;",
            "return left.stream_id > right.stream_id;",
        ),
        "current gauge reset only with counters": (
            r"(?s)m_current_pending = 0;\s*if \(clear_counters\) begin",
            "if (clear_counters) begin\n        m_current_pending = 0;",
        ),
        "proxy accepts reserved minus two": (
            r"if \(limit < -1\) begin",
            "if (limit < -2) begin",
        ),
        "proxy registration skipped": (
            r"if \(!common_scb_registry::register_proxy\(m_proxy, registry_error\)\)",
            "if (0)",
        ),
    }
    for description, (pattern, replacement) in task_six_mutations.items():
        broken, replacements = re.subn(pattern, replacement, core_raw)
        assert replacements == 1, f"failed to construct {description} mutation"
        with pytest.raises(AssertionError):
            assert_core_contract(broken)

    portable_counter_mutations = {
        "reserved match field declaration": (
            types_raw.replace(
                "longint unsigned match_count;",
                "longint unsigned matches;",
            ),
            core_raw,
        ),
        "stale core match field reference": (
            types_raw,
            core_raw.replace("state.match_count++;", "state.matches++;", 1),
        ),
    }
    for description, (broken_types, broken_core) in portable_counter_mutations.items():
        assert (broken_types, broken_core) != (types_raw, core_raw), (
            f"failed to construct {description} mutation"
        )
        with pytest.raises(AssertionError):
            assert_vcs_portable_match_counter(broken_types, broken_core)
