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


def test_standalone_registry_template_exposes_aip_independent_control_api():
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=PlatformType.ADVANCE,
        aip_core=False,
    )
    registry = strip_sv_comments(
        PlatformGenerator(config).render_template(
            "common/common_scb_registry.sv.j2",
            file_name="common_scb_registry.sv",
        )
    )

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

    assert re.search(r"\bnames\.sort[ \t]*\([ \t]*\)[ \t]*;", registry), (
        "registry names must be sorted deterministically"
    )
    assert not re.search(r"\baip_|AIP_", registry), (
        "registry must not depend on AIP identifiers or tokens"
    )
    assert "{{" not in registry and "{%" not in registry, (
        "registry render must not retain Jinja markers"
    )


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
