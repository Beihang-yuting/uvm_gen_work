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


def generate(
    tmp_path: Path, platform_type: PlatformType, aip_core: bool = False
) -> Path:
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


def registry_function_body(
    registry: str, declaration: str, description: str
) -> str:
    match = re.search(
        rf"(?ms){declaration}(?P<body>.*?)^[ \t]*endfunction",
        registry,
    )
    assert match, f"missing registry {description} function body"
    return match.group("body")


def registry_match_position(body: str, pattern: str, description: str) -> int:
    match = re.search(pattern, body, flags=re.MULTILINE | re.DOTALL)
    assert match, f"missing registry {description}"
    return match.start()


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
    }
    for description, (pattern, replacement) in mutations.items():
        broken, replacements = re.subn(pattern, replacement, core_raw)
        assert replacements == 1, f"failed to construct {description} mutation"
        with pytest.raises(AssertionError):
            assert_core_contract(broken)


def assert_registry_contract(registry_raw: str) -> None:
    registry = strip_sv_comments(registry_raw)

    declarations = {
        "include guard": (
            r"(?m)^[ \t]*`ifndef[ \t]+COMMON_SCB_REGISTRY__SV\b.*$\n"
            r"[ \t]*`define[ \t]+COMMON_SCB_REGISTRY__SV\b"
        ),
        "control proxy": (
            r"(?m)^[ \t]*virtual[ \t]+class[ \t]+"
            r"common_scb_control_proxy[ \t]+extends[ \t]+uvm_object[ \t]*;"
        ),
        "proxy constructor": (
            r"(?m)^[ \t]*function[ \t]+new[ \t]*\([ \t]*string[ \t]+"
            r"name[ \t]*=[ \t]*\"common_scb_control_proxy\"[ \t]*\)[ \t]*;"
        ),
        "proxy scoreboard name": (
            r"(?m)^[ \t]*pure[ \t]+virtual[ \t]+function[ \t]+string[ \t]+"
            r"scoreboard_name[ \t]*\([ \t]*\)[ \t]*;"
        ),
        "proxy status": (
            r"(?m)^[ \t]*pure[ \t]+virtual[ \t]+function[ \t]+scb_status_e[ \t]+"
            r"status[ \t]*\([ \t]*\)[ \t]*;"
        ),
        "proxy summary": (
            r"(?m)^[ \t]*pure[ \t]+virtual[ \t]+function[ \t]+string[ \t]+"
            r"summary[ \t]*\([ \t]*\)[ \t]*;"
        ),
        "proxy report": (
            r"(?m)^[ \t]*pure[ \t]+virtual[ \t]+function[ \t]+void[ \t]+"
            r"report[ \t]*\([ \t]*int[ \t]+limit[ \t]*=[ \t]*-2[ \t]*\)[ \t]*;"
        ),
        "proxy report limit": (
            r"(?m)^[ \t]*pure[ \t]+virtual[ \t]+function[ \t]+bit[ \t]+"
            r"set_report_limit[ \t]*\([ \t]*int[ \t]+limit[ \t]*,[ \t]*"
            r"output[ \t]+string[ \t]+error[ \t]*\)[ \t]*;"
        ),
        "registry": r"(?m)^[ \t]*class[ \t]+common_scb_registry[ \t]*;",
        "registry storage": (
            r"(?m)^[ \t]*local[ \t]+static[ \t]+common_scb_control_proxy[ \t]+"
            r"m_proxies[ \t]*\[[ \t]*string[ \t]*\][ \t]*;"
        ),
        "register proxy": (
            r"(?m)^[ \t]*static[ \t]+function[ \t]+bit[ \t]+register_proxy\s*\("
            r"\s*common_scb_control_proxy[ \t]+proxy[ \t]*,\s*"
            r"output[ \t]+string[ \t]+error[ \t]*\)[ \t]*;"
        ),
        "find": (
            r"(?m)^[ \t]*static[ \t]+function[ \t]+common_scb_control_proxy[ \t]+"
            r"find[ \t]*\([ \t]*string[ \t]+name[ \t]*\)[ \t]*;"
        ),
        "get names": (
            r"(?m)^[ \t]*static[ \t]+function[ \t]+void[ \t]+get_names[ \t]*\("
            r"[ \t]*ref[ \t]+string[ \t]+names[ \t]*\[[ \t]*\$[ \t]*\][ \t]*\)[ \t]*;"
        ),
        "size": (
            r"(?m)^[ \t]*static[ \t]+function[ \t]+int[ \t]+size[ \t]*\([ \t]*\)"
            r"[ \t]*;"
        ),
    }
    for description, pattern in declarations.items():
        assert re.search(pattern, registry), f"missing registry {description}"

    register_proxy = registry_function_body(
        registry,
        (
            r"^[ \t]*static[ \t]+function[ \t]+bit[ \t]+register_proxy\s*\("
            r"\s*common_scb_control_proxy[ \t]+proxy[ \t]*,\s*"
            r"output[ \t]+string[ \t]+error[ \t]*\)[ \t]*;"
        ),
        "register_proxy",
    )
    register_positions = [
        registry_match_position(
            register_proxy,
            r"^[ \t]*string[ \t]+name[ \t]*;",
            "register_proxy local name declaration",
        ),
        registry_match_position(
            register_proxy,
            r"if\s*\(\s*proxy\s*==\s*null\s*\)\s*begin\s*"
            r"error\s*=\s*\"cannot register a null scoreboard proxy\"\s*;\s*"
            r"return\s+0\s*;\s*end",
            "register_proxy null rejection",
        ),
        registry_match_position(
            register_proxy,
            r"name\s*=\s*proxy\.scoreboard_name\s*\(\s*\)\s*;",
            "register_proxy scoreboard name lookup",
        ),
        registry_match_position(
            register_proxy,
            r"if\s*\(\s*name\s*==\s*\"\"\s*\)\s*begin\s*"
            r"error\s*=\s*\"cannot register a scoreboard with an empty name\"\s*;\s*"
            r"return\s+0\s*;\s*end",
            "register_proxy empty-name rejection",
        ),
        registry_match_position(
            register_proxy,
            r"if\s*\(\s*m_proxies\.exists\s*\(\s*name\s*\)\s*\)\s*begin\s*"
            r"error\s*=\s*\$sformatf\s*\(\s*\"scoreboard '%s' is already registered\"\s*,\s*"
            r"name\s*\)\s*;\s*return\s+0\s*;\s*end",
            "register_proxy duplicate rejection",
        ),
        registry_match_position(
            register_proxy,
            r"m_proxies\s*\[\s*name\s*\]\s*=\s*proxy\s*;",
            "register_proxy storage assignment",
        ),
        registry_match_position(
            register_proxy,
            r"error\s*=\s*\"\"\s*;",
            "register_proxy success error reset",
        ),
        registry_match_position(
            register_proxy,
            r"return\s+1\s*;",
            "register_proxy success return",
        ),
    ]
    assert register_positions == sorted(register_positions), (
        "register_proxy must declare, guard, then register in execution order"
    )

    find = registry_function_body(
        registry,
        (
            r"^[ \t]*static[ \t]+function[ \t]+common_scb_control_proxy[ \t]+"
            r"find[ \t]*\([ \t]*string[ \t]+name[ \t]*\)[ \t]*;"
        ),
        "find",
    )
    find_positions = [
        registry_match_position(
            find,
            r"if\s*\(\s*!\s*m_proxies\.exists\s*\(\s*name\s*\)\s*\)\s*"
            r"return\s+null\s*;",
            "find absent-name rejection",
        ),
        registry_match_position(
            find,
            r"return\s+m_proxies\s*\[\s*name\s*\]\s*;",
            "find stored proxy return",
        ),
    ]
    assert find_positions == sorted(find_positions), (
        "find must reject absent names before returning the stored proxy"
    )

    get_names = registry_function_body(
        registry,
        (
            r"^[ \t]*static[ \t]+function[ \t]+void[ \t]+get_names[ \t]*\("
            r"[ \t]*ref[ \t]+string[ \t]+names[ \t]*\[[ \t]*\$[ \t]*\][ \t]*\)[ \t]*;"
        ),
        "get_names",
    )
    get_names_positions = [
        registry_match_position(
            get_names,
            r"names\.delete\s*\(\s*\)\s*;",
            "get_names output reset",
        ),
        registry_match_position(
            get_names,
            r"foreach\s*\(\s*m_proxies\s*\[\s*name\s*\]\s*\)\s*"
            r"names\.push_back\s*\(\s*name\s*\)\s*;",
            "get_names proxy enumeration",
        ),
        registry_match_position(
            get_names,
            r"names\.sort\s*\(\s*\)\s*;",
            "get_names deterministic sort",
        ),
    ]
    assert get_names_positions == sorted(get_names_positions), (
        "get_names must reset, enumerate, then sort names"
    )

    size = registry_function_body(
        registry,
        r"^[ \t]*static[ \t]+function[ \t]+int[ \t]+size[ \t]*\([ \t]*\)[ \t]*;",
        "size",
    )
    assert re.search(r"return\s+m_proxies\.num\s*\(\s*\)\s*;", size), (
        "size must return the proxy count"
    )

    assert not re.search(r"\baip_|AIP_", registry_raw), (
        "registry must not depend on AIP identifiers or tokens"
    )
    assert "{{" not in registry_raw and "{%" not in registry_raw, (
        "registry render must not retain Jinja markers"
    )


def test_standalone_registry_template_exposes_aip_independent_control_api():
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=PlatformType.ADVANCE,
        aip_core=False,
    )
    registry_raw = PlatformGenerator(config).render_template(
        "common/common_scb_registry.sv.j2",
        file_name="common_scb_registry.sv",
    )

    assert_registry_contract(registry_raw)


def test_registry_contract_rejects_broken_control_bodies():
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=PlatformType.ADVANCE,
        aip_core=False,
    )
    registry_raw = PlatformGenerator(config).render_template(
        "common/common_scb_registry.sv.j2",
        file_name="common_scb_registry.sv",
    )
    mutations = {
        "always-success registration": (
            r"(?ms)(^[ \t]*static[ \t]+function[ \t]+bit[ \t]+register_proxy.*?;).*?"
            r"^[ \t]*endfunction",
            r'\1\n        error = "";\n        return 1;\n    endfunction',
        ),
        "always-null find": (
            r"(?ms)(^[ \t]*static[ \t]+function[ \t]+common_scb_control_proxy[ \t]+find.*?;).*?"
            r"^[ \t]*endfunction",
            r"\1\n        return null;\n    endfunction",
        ),
        "input-only get_names": (
            r"(?ms)(^[ \t]*static[ \t]+function[ \t]+void[ \t]+get_names.*?;).*?"
            r"^[ \t]*endfunction",
            r"\1\n        names.sort();\n    endfunction",
        ),
        "constant size": (
            r"(?ms)(^[ \t]*static[ \t]+function[ \t]+int[ \t]+size.*?;).*?"
            r"^[ \t]*endfunction",
            r"\1\n        return 0;\n    endfunction",
        ),
    }
    for description, (pattern, replacement) in mutations.items():
        broken, replacements = re.subn(pattern, replacement, registry_raw)
        assert replacements == 1, f"failed to construct {description} mutation"
        with pytest.raises(AssertionError):
            assert_registry_contract(broken)


def test_common_output_contains_legacy_and_v2_scoreboard_files(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    common_dir = project / "common"
    required_files = [
        "common_uvm_scb_legacy.sv",
        "common_scb_types.sv",
        "common_scb_reporter.sv",
        "common_scb_registry.sv",
        "common_uvm_scb.sv",
    ]

    missing_files = [
        filename for filename in required_files if not (common_dir / filename).is_file()
    ]
    assert not missing_files, f"missing generated common files: {missing_files}"


def test_legacy_and_v2_scoreboards_have_distinct_names(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    legacy_path = project / "common/common_uvm_scb_legacy.sv"
    v2_path = project / "common/common_uvm_scb.sv"
    missing_files = [
        path.name for path in (legacy_path, v2_path) if not path.is_file()
    ]
    assert not missing_files, f"missing generated scoreboard files: {missing_files}"

    legacy = strip_sv_comments(read(project, "common/common_uvm_scb_legacy.sv"))
    v2 = strip_sv_comments(read(project, "common/common_uvm_scb.sv"))

    legacy_class = (
        r"(?m)^[ \t]*(?:virtual[ \t]+)?class[ \t]+"
        r"common_uvm_scb_legacy\b"
    )
    legacy_enum = (
        r"(?ms)^[ \t]*typedef[ \t]+enum\b.*?\}\s*"
        r"legacy_scb_cmp_mode_e\b\s*;"
    )
    legacy_cfg_class = (
        r"(?m)^[ \t]*(?:virtual[ \t]+)?class[ \t]+"
        r"common_uvm_scb_legacy_cfg\b"
    )
    legacy_manager_class = (
        r"(?m)^[ \t]*(?:virtual[ \t]+)?class[ \t]+"
        r"common_scb_legacy_stream_manager\b"
    )
    stale_enum = (
        r"(?ms)^[ \t]*typedef[ \t]+enum\b[^;]*?\}\s*"
        r"scb_cmp_mode\b\s*;"
    )
    stale_cfg_class = (
        r"(?m)^[ \t]*(?:virtual[ \t]+)?class[ \t]+common_uvm_scb_cfg\b"
    )
    stale_manager_class = (
        r"(?m)^[ \t]*(?:virtual[ \t]+)?class[ \t]+stream_trans_manager\b"
    )
    v2_class = (
        r"(?m)^[ \t]*(?:virtual[ \t]+)?class[ \t]+common_uvm_scb\b"
        r"[ \t\r\n]*#[ \t\r\n]*\("
    )

    assert re.search(
        legacy_class, legacy
    ), "missing legacy scoreboard class declaration"
    assert re.search(legacy_enum, legacy), "missing legacy comparison-mode enum"
    assert re.search(
        legacy_cfg_class, legacy
    ), "missing legacy scoreboard configuration class declaration"
    assert re.search(
        legacy_manager_class, legacy
    ), "missing legacy stream-manager class declaration"
    assert re.search(
        r"(?m)^[ \t]*`ifndef[ \t]+COMMON_UVM_SCB_LEGACY__SV\b", legacy
    ), "missing legacy scoreboard `ifndef guard"
    assert re.search(
        r"(?m)^[ \t]*`define[ \t]+COMMON_UVM_SCB_LEGACY__SV\b", legacy
    ), "missing legacy scoreboard `define guard"
    assert not re.search(
        stale_enum, legacy
    ), "legacy source still declares stale enum scb_cmp_mode"
    assert not re.search(
        stale_cfg_class, legacy
    ), "legacy source still declares stale class common_uvm_scb_cfg"
    assert not re.search(
        stale_manager_class, legacy
    ), "legacy source still declares stale class stream_trans_manager"
    assert not re.search(
        r"(?m)^[ \t]*`ifndef[ \t]+COMMON_UVM_SCB__SV\b", legacy
    ), "legacy source still contains stale `ifndef COMMON_UVM_SCB__SV guard"
    assert not re.search(
        r"(?m)^[ \t]*`define[ \t]+COMMON_UVM_SCB__SV\b", legacy
    ), "legacy source still contains stale `define COMMON_UVM_SCB__SV guard"
    assert not re.search(
        v2_class, legacy
    ), "legacy source still declares the parameterized common_uvm_scb class"
    assert re.search(v2_class, v2), "missing parameterized v2 scoreboard class"


def test_common_package_includes_scoreboard_dependencies_in_order(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    common_package = strip_sv_comments(read(project, "common/common_lib_pkg.sv"))
    required_includes = [
        "common_scb_types.sv",
        "common_scb_reporter.sv",
        "common_scb_registry.sv",
        "common_uvm_scb_legacy.sv",
        "common_uvm_scb.sv",
    ]
    active_includes = re.findall(
        r'(?m)^[ \t]*`include[ \t]+"([^"\r\n]+)"[ \t]*$',
        common_package,
    )
    scoreboard_includes = [
        filename for filename in active_includes if filename in required_includes
    ]

    assert scoreboard_includes == required_includes, (
        "scoreboard package include sequence mismatch: "
        f"expected {required_includes}, got {scoreboard_includes}"
    )


def test_v2_types_expose_approved_defaults(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    types_path = project / "common/common_scb_types.sv"
    assert types_path.is_file(), "missing generated v2 types contract file"

    types = strip_sv_comments(read(project, "common/common_scb_types.sv"))
    declarations = {
        "comparison-mode enum": (
            r"(?ms)^[ \t]*typedef\s+enum\s+int\s*\{\s*"
            r"SCB_ORDERED_EXACT\s*,\s*SCB_ORDERED_LOSSY\s*,\s*"
            r"SCB_UNORDERED\s*\}\s*common_scb_cmp_mode_e\s*;"
        ),
        "status enum": (
            r"(?ms)^[ \t]*typedef\s+enum\s+int\s*\{\s*"
            r"SCB_PASS\s*,\s*SCB_WARN\s*,\s*SCB_FAIL\s*\}\s*"
            r"scb_status_e\s*;"
        ),
        "comparison-mode default": (
            r"(?m)^[ \t]*common_scb_cmp_mode_e\s+m_cmp_mode\s*=\s*"
            r"SCB_UNORDERED\s*;"
        ),
        "report-limit default": r"(?m)^[ \t]*int\s+m_report_limit\s*=\s*10\s*;",
        "error-limit default": r"(?m)^[ \t]*int\s+m_err_limit\s*=\s*10\s*;",
        "pending-limit default": r"(?m)^[ \t]*int\s+m_pending_limit\s*=\s*0\s*;",
        "report-enable default": r"(?m)^[ \t]*bit\s+m_report_en\s*=\s*1\s*;",
        "clone-enable default": r"(?m)^[ \t]*bit\s+m_clone_en\s*=\s*1\s*;",
        "strict-arrival default": r"(?m)^[ \t]*bit\s+m_strict_arrival\s*=\s*0\s*;",
    }
    for description, pattern in declarations.items():
        assert re.search(pattern, types), f"missing v2 types {description}"

    diagnostic_counter = re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+diagnostic_warnings\s*;",
        types,
    )
    assert diagnostic_counter, "missing per-stream diagnostic_warnings counter"
    overflow_counter = re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+overflows\s*;",
        types,
    )
    assert overflow_counter and diagnostic_counter.start() > overflow_counter.start(), (
        "diagnostic_warnings must be declared beside and after overflows"
    )
    issue_count = re.search(
        r"(?ms)^[ \t]*function\s+longint\s+unsigned\s+issue_count\s*\(\s*\)\s*;"
        r"(?P<body>.*?)^[ \t]*endfunction",
        types,
    )
    assert issue_count, "missing stream-state issue_count function body"
    assert re.search(
        r"return\s+mismatches\s*\+\s*allowed_drops\s*\+\s*"
        r"unexpected_actuals\s*\+\s*overflows\s*\+\s*diagnostic_warnings\s*\+\s*"
        r"expected_q\.size\s*\(\s*\)\s*\+\s*actual_q\.size\s*\(\s*\)\s*;",
        issue_count.group("body"),
    ), "issue_count must include every Task 5 issue source"


def test_v2_core_has_function_api_and_result_port(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core_path = project / "common/common_uvm_scb.sv"
    assert core_path.is_file(), "missing generated v2 core: common/common_uvm_scb.sv"
    core = read(project, "common/common_uvm_scb.sv")
    required_api = [
        "function void push_expected",
        "function void push_actual",
        "virtual function bit compare_items",
        "function scb_status_e get_status",
        "function bit is_clean",
        "function string get_summary",
        "function void print_report",
        "function void reset_state",
        "uvm_analysis_port#(result_t) m_result_ap",
    ]
    missing_api = [item for item in required_api if item not in core]
    assert not missing_api, f"missing generated v2 core API: {missing_api}"


def test_v2_core_clones_and_bounds_pending_state(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core_path = project / "common/common_uvm_scb.sv"
    assert core_path.is_file(), "missing generated v2 core: common/common_uvm_scb.sv"
    core = read(project, "common/common_uvm_scb.sv")
    required_admission = [
        "source.clone()",
        "$cast(retained, cloned)",
        "m_pending_limit",
        "SCB_PENDING_OVERFLOW",
        "SCB_REPORT_LIMIT=%d",
    ]
    missing_admission = [item for item in required_admission if item not in core]
    assert not missing_admission, (
        f"missing generated v2 clone/admission behavior: {missing_admission}"
    )


def test_v2_core_keeps_legacy_task_wrappers(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core_path = project / "common/common_uvm_scb.sv"
    assert core_path.is_file(), "missing generated v2 core: common/common_uvm_scb.sv"
    core = read(project, "common/common_uvm_scb.sv")
    required_wrappers = [
        "task send_rm_trans_to_cmp",
        "task send_dut_trans_to_cmp",
        "push_expected(rm_tr",
        "push_actual(dut_tr",
    ]
    missing_wrappers = [item for item in required_wrappers if item not in core]
    assert not missing_wrappers, (
        f"missing generated v2 legacy wrappers: {missing_wrappers}"
    )


def test_reporter_uses_structured_cells_and_per_column_widths(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    reporter_path = project / "common/common_scb_reporter.sv"
    assert reporter_path.is_file(), "missing generated v2 reporter contract file"

    reporter = strip_sv_comments(read(project, "common/common_scb_reporter.sv"))
    declarations = {
        "reporter class": r"(?m)^[ \t]*class\s+common_scb_reporter\s*;",
        "header storage": r"(?m)^[ \t]*string\s+m_headers\s*\[\$\]\s*;",
        "numeric storage": r"(?m)^[ \t]*bit\s+m_numeric\s*\[\$\]\s*;",
        "per-column width storage": r"(?m)^[ \t]*int\s+m_widths\s*\[\$\]\s*;",
        "row storage": (
            r"(?m)^[ \t]*common_scb_report_row\s+m_rows\s*\[\$\]\s*;"
        ),
        "add-row function": (
            r"(?m)^[ \t]*function\s+void\s+add_row\s*\(\s*input\s+"
            r"string\s+cells\s*\[\$\]\s*\)\s*;"
        ),
        "render function": r"(?m)^[ \t]*function\s+string\s+render\s*\(\s*\)\s*;",
    }
    for description, pattern in declarations.items():
        assert re.search(pattern, reporter), (
            f"missing structured reporter {description}"
        )

    set_columns = re.search(
        r"(?ms)^[ \t]*function\s+void\s+set_columns\b.*?;(?P<body>.*?)"
        r"^[ \t]*endfunction",
        reporter,
    )
    assert set_columns, "missing structured reporter set_columns function"
    set_columns_body = set_columns.group("body")
    for state in ("m_headers", "m_numeric", "m_widths", "m_rows"):
        cleared_state = re.search(
            rf"(?m)^[ \t]*{state}\.delete\s*\(\s*\)\s*;", set_columns_body
        )
        assert cleared_state, (
            f"set_columns must clear {state} before reuse"
        )
        assert cleared_state.start() < set_columns_body.find("if"), (
            f"set_columns must clear {state} before metadata validation"
        )
    assert re.search(
        r"if\s*\(\s*headers\.size\s*\(\s*\)\s*==\s*0\s*\|\|\s*"
        r"headers\.size\s*\(\s*\)\s*!=\s*numeric\.size\s*\(\s*\)\s*\)\s*"
        r"return\s*;",
        set_columns_body,
    ), "set_columns must reject empty or mismatched column metadata"
    assert re.search(r"(?m)^[ \t]*m_headers\s*=\s*headers\s*;", set_columns_body), (
        "set_columns must copy valid headers"
    )
    assert re.search(r"(?m)^[ \t]*m_numeric\s*=\s*numeric\s*;", set_columns_body), (
        "set_columns must copy valid numeric metadata"
    )
    assert re.search(
        r"foreach\s*\(\s*m_headers\s*\[\s*i\s*\]\s*\)\s*"
        r"m_widths\.push_back\s*\(\s*m_headers\s*\[\s*i\s*\]\.len\s*\(\s*\)\s*\)\s*;",
        set_columns_body,
    ), "set_columns must rebuild widths from valid headers"

    add_row = re.search(
        r"(?ms)^[ \t]*function\s+void\s+add_row\b.*?;(?P<body>.*?)"
        r"^[ \t]*endfunction",
        reporter,
    )
    assert add_row, "missing structured reporter add_row function body"
    add_row_body = add_row.group("body")
    invalid_row = re.search(
        r"if\s*\(\s*m_headers\.size\s*\(\s*\)\s*==\s*0\s*\|\|\s*"
        r"cells\.size\s*\(\s*\)\s*!=\s*m_headers\.size\s*\(\s*\)\s*\)\s*"
        r"return\s*;",
        add_row_body,
    )
    assert invalid_row, "add_row must reject unconfigured or mismatched rows"
    row_declaration = re.search(
        r"(?m)^[ \t]*common_scb_report_row\s+row\s*;",
        add_row_body,
    )
    assert row_declaration, "add_row must declare the row before executable statements"
    row_allocation = re.search(
        r"(?m)^[ \t]*row\s*=\s*new\s*\(\s*\)\s*;",
        add_row_body,
    )
    assert row_allocation, "add_row must allocate the row after validation"
    assert row_declaration.start() < invalid_row.start() < row_allocation.start(), (
        "add_row must declare, validate, then allocate for VCS portability"
    )

    render = re.search(
        r"(?ms)^[ \t]*function\s+string\s+render\b.*?;(?P<body>.*?)"
        r"^[ \t]*endfunction",
        reporter,
    )
    assert render, "missing structured reporter render function body"
    render_body = render.group("body")
    assert re.search(
        r'if\s*\(\s*m_headers\.size\s*\(\s*\)\s*==\s*0\s*\)\s*return\s+""\s*;',
        render_body,
    ), "render must return an empty string without configured columns"
    assert re.search(
        r"if\s*\(\s*m_rows\.size\s*\(\s*\)\s*==\s*0\s*\)\s*return\s+text\s*;",
        render_body,
    ), "render must avoid a duplicate closing border when there are no rows"
    assert "insert_line_content" not in reporter, (
        "structured reporter must not use legacy insert_line_content"
    )


def test_v2_contract_regexes_reject_comments_suffixes_and_wrong_defaults():
    comparison_mode = (
        r"(?ms)^[ \t]*typedef\s+enum\s+int\s*\{\s*"
        r"SCB_ORDERED_EXACT\s*,\s*SCB_ORDERED_LOSSY\s*,\s*"
        r"SCB_UNORDERED\s*\}\s*common_scb_cmp_mode_e\s*;"
    )
    report_limit = r"(?m)^[ \t]*int\s+m_report_limit\s*=\s*10\s*;"
    reporter_class = r"(?m)^[ \t]*class\s+common_scb_reporter\s*;"
    add_row = (
        r"(?m)^[ \t]*function\s+void\s+add_row\s*\(\s*input\s+"
        r"string\s+cells\s*\[\$\]\s*\)\s*;"
    )
    row_declaration = r"(?m)^[ \t]*common_scb_report_row\s+row\s*;"
    row_allocation = r"(?m)^[ \t]*row\s*=\s*new\s*\(\s*\)\s*;"
    invalid_row_guard = (
        r"if\s*\(\s*m_headers\.size\s*\(\s*\)\s*==\s*0\s*\|\|\s*"
        r"cells\.size\s*\(\s*\)\s*!=\s*m_headers\.size\s*\(\s*\)\s*\)\s*"
        r"return\s*;"
    )
    portable_add_row = (
        "common_scb_report_row row;\n"
        "if (m_headers.size() == 0 || cells.size() != m_headers.size()) return;\n"
        "row = new();"
    )
    mixed_declaration = (
        "common_scb_report_row row = new();\n"
        "if (m_headers.size() == 0 || cells.size() != m_headers.size()) return;"
    )

    assert re.search(
        comparison_mode,
        "typedef enum int { SCB_ORDERED_EXACT, SCB_ORDERED_LOSSY, "
        "SCB_UNORDERED } common_scb_cmp_mode_e;",
    )
    assert re.search(report_limit, "int m_report_limit = 10;")
    assert re.search(reporter_class, "class common_scb_reporter;")
    assert re.search(add_row, "function void add_row(input string cells[$]);")
    declaration = re.search(row_declaration, portable_add_row)
    guard = re.search(invalid_row_guard, portable_add_row)
    allocation = re.search(row_allocation, portable_add_row)
    assert declaration and guard and allocation
    assert declaration.start() < guard.start() < allocation.start()
    assert not re.search(report_limit, "int m_report_limit = 11;")
    assert not re.search(reporter_class, "class common_scb_reporter_bad;")
    assert not re.search(add_row, "function void add_row_extra(input string cells[$]);")
    assert not re.search(row_declaration, mixed_declaration)
    assert not re.search(
        comparison_mode,
        "// typedef enum int { SCB_ORDERED_EXACT, SCB_ORDERED_LOSSY, "
        "SCB_UNORDERED } common_scb_cmp_mode_e;",
    )
