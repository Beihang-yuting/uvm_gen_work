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


def assert_core_contract(core_raw: str) -> None:
    core = strip_sv_comments(core_raw)

    declarations = {
        "include guard": (
            r"(?m)^[ \t]*`ifndef[ \t]+COMMON_UVM_SCB__SV\b.*$\n"
            r"[ \t]*`define[ \t]+COMMON_UVM_SCB__SV\b"
        ),
        "parameterized scoreboard": (
            r"(?ms)^[ \t]*class\s+common_uvm_scb\s*#\s*\(\s*"
            r"type\s+TRANS_TYPE\s*=\s*uvm_sequence_item\s*,\s*"
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

    counters = (
        "expected_inputs",
        "actual_inputs",
        "matches",
        "mismatches",
        "allowed_drops",
        "unexpected_actuals",
        "overflows",
        "peak_pending",
        "detail_emitted",
        "suppressed_details",
    )
    for counter in counters:
        assert re.search(
            rf"(?m)^[ \t]*protected\s+longint\s+unsigned\s+m_{counter}\s*;",
            core,
        ), f"missing protected global counter m_{counter}"

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
                "optional config override",
                r"uvm_config_db\s*#\s*\(\s*common_uvm_scb_cfg\s*\)::get\s*\("
                r"\s*this\s*,\s*\"\"\s*,\s*\"cfg\"\s*,\s*configured\s*\)",
            ),
            (
                "report plusarg only",
                r"\$value\$plusargs\s*\(\s*\"SCB_REPORT_LIMIT=%d\"\s*,\s*value\s*\)",
            ),
            ("accepted report bound", r"if\s*\(\s*value\s*>=\s*-1\s*\)"),
            ("invalid plusarg warning", r"invalid SCB_REPORT_LIMIT=%0d; using 10"),
            ("report normalization", r"m_cfg\.m_report_limit\s*<\s*-1"),
            ("error-limit normalization", r"m_cfg\.m_err_limit\s*<\s*0"),
            ("pending-limit normalization", r"m_cfg\.m_pending_limit\s*<\s*0"),
        ],
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
    approved_warnings = [
        ("invalid report plusarg", invalid_report_warning),
        ("error-limit normalization", error_limit_warning),
        ("pending-limit normalization", pending_limit_warning),
    ]
    warning_positions = []
    for description, pattern in approved_warnings:
        matches = list(re.finditer(pattern, build))
        assert len(matches) == 1, (
            f"build_phase must contain exactly one approved {description} warning"
        )
        warning_positions.append(matches[0].start())
    all_warning_positions = [
        match.start() for match in re.finditer(r"`uvm_warning\s*\(", build)
    ]
    assert all_warning_positions == warning_positions, (
        "build_phase must contain only the three approved warnings in order"
    )
    assert not re.search(r"m_report_limit\s+must\b", build), (
        "config-db report-limit normalization must be silent"
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
            ("expected state lookup", r"state\s*=\s*state_for\s*\(\s*stream_id\s*\)\s*;"),
            ("global expected input", r"m_expected_inputs\s*\+\+\s*;"),
            ("stream expected input", r"state\.expected_inputs\s*\+\+\s*;"),
            ("expected retained copy", r"retained_copy\s*\(\s*tr\s*,\s*stream_id\s*,\s*\"expected\""),
            ("expected admission", r"can_enqueue\s*\(\s*state\s*,\s*stream_id\s*,\s*\"expected\""),
            ("expected enqueue", r"state\.expected_q\.push_back\s*\(\s*new\s*\(\s*retained\s*,\s*kind\s*\)\s*\)\s*;"),
            ("expected peak update", r"update_peak\s*\(\s*state\s*\)\s*;"),
            ("expected dispatch", r"case\s*\(\s*m_cfg\.m_cmp_mode\s*\)"),
            ("expected unordered dispatch", r"SCB_UNORDERED\s*:\s*reconcile_unordered_expected\s*\(\s*state\s*\)\s*;"),
        ],
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
            ("actual enqueue", r"state\.actual_q\.push_back\s*\(\s*new\s*\(\s*retained\s*,\s*kind\s*\)\s*\)\s*;"),
            ("actual peak update", r"update_peak\s*\(\s*state\s*\)\s*;"),
            ("actual dispatch", r"case\s*\(\s*m_cfg\.m_cmp_mode\s*\)"),
            ("actual unordered dispatch", r"SCB_UNORDERED\s*:\s*reconcile_unordered_actual\s*\(\s*state\s*\)\s*;"),
        ],
    )

    compare = core_method_body(
        core,
        r"function\s+bit\s+common_uvm_scb::compare_items\s*\([^;]+\)",
        "compare_items",
    )
    assert re.search(
        r"return\s+expected\.self_define_do_compare\s*\(\s*actual\s*,\s*diff\s*,\s*kind\s*\)\s*;",
        compare,
    ), "compare_items must delegate to self_define_do_compare"

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
            ("newest expected", r"expected\s*=\s*state\.expected_q\s*\[\s*state\.expected_q\.size\s*\(\s*\)\s*-\s*1\s*\]\s*;"),
            ("unordered expected scans actuals", r"foreach\s*\(\s*state\.actual_q\s*\[\s*i\s*\]\s*\)"),
            ("unordered expected removes newest", r"state\.expected_q\.pop_back\s*\(\s*\)"),
            ("unordered expected match", r"record_match\s*\(\s*state\s*,\s*expected\s*,\s*state\.actual_q\s*\[\s*match_index\s*\]"),
            ("unordered expected removes matched actual", r"state\.actual_q\.delete\s*\(\s*match_index\s*\)\s*;"),
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
            ("newest actual", r"actual\s*=\s*state\.actual_q\s*\[\s*state\.actual_q\.size\s*\(\s*\)\s*-\s*1\s*\]\s*;"),
            ("unordered actual scans expecteds", r"foreach\s*\(\s*state\.expected_q\s*\[\s*i\s*\]\s*\)"),
            ("unordered actual removes newest", r"state\.actual_q\.pop_back\s*\(\s*\)"),
            ("unordered actual match", r"record_match\s*\(\s*state\s*,\s*state\.expected_q\s*\[\s*match_index\s*\]\s*,\s*actual"),
            ("unordered actual removes matched expected", r"state\.expected_q\.delete\s*\(\s*match_index\s*\)\s*;"),
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
        "record_match": ("state.matches", "m_matches", "publish_result"),
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

    for task_six_method in (
        "get_status",
        "is_clean",
        "get_summary",
        "print_report",
        "reset_state",
        "check_phase",
        "report_phase",
        "finalize_pending",
    ):
        assert not re.search(
            rf"(?m)^[ \t]*function\b[^;\n]*common_uvm_scb::{task_six_method}\b",
            core,
        ), f"Task 5 must not define Task 6 method {task_six_method}"

    assert not re.search(r"\baip_|AIP_", core_raw), (
        "raw core template must remain AIP-independent"
    )
    assert "{{" not in core_raw and "{%" not in core_raw, (
        "core render must not retain Jinja markers"
    )


def test_standalone_core_template_implements_task5_comparison_contract():
    template_path = (
        Path(__file__).parents[1]
        / "uvm_gen/templates/common/base_scb.sv.j2"
    )
    assert template_path.is_file(), (
        "missing Task 5 core template: "
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

    assert_core_contract(core_raw)

    mutations = {
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
            r"(?s)else\s+(?P<warning>`uvm_warning\s*\(\s*\"SCB_CFG\"\s*,\s*"
            r"\$sformatf\s*\(\s*\"invalid SCB_REPORT_LIMIT=%0d; using 10\"\s*,\s*"
            r"value\s*\)\s*\))\s*end\s*"
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

