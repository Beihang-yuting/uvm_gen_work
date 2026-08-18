import re
import subprocess
from pathlib import Path

import pytest

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.common import CommonGenerator
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


def generate_with_agents(
    tmp_path: Path,
    platform_type: PlatformType,
    agents: tuple[str, ...],
    aip_core: bool = False,
) -> Path:
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig(agent) for agent in agents],
        platform_type=platform_type,
        aip_core=aip_core,
        output_dir=str(tmp_path),
    )
    return Path(PlatformGenerator(config).generate())


def read(project: Path, relative_path: str) -> str:
    return (project / relative_path).read_text(encoding="utf-8")


EXPECTED_COMMON_TEMPLATES = [
    ("common_lib_pkg.sv", "common/common_pkg.sv.j2"),
    ("common_dec.sv", "common/common_dec.sv.j2"),
    ("common_report_server.sv", "common/report_server.sv.j2"),
    ("common_self_debug_scb.sv", "common/self_debug_scb.sv.j2"),
    ("common_draw_table.sv", "common/draw_table.sv.j2"),
    ("common_scb_types.sv", "common/common_scb_types.sv.j2"),
    ("common_scb_reporter.sv", "common/common_scb_reporter.sv.j2"),
    ("common_scb_registry.sv", "common/common_scb_registry.sv.j2"),
    ("common_uvm_scb_legacy.sv", "common/legacy_scb.sv.j2"),
    ("common_uvm_scb.sv", "common/base_scb.sv.j2"),
]

EXPECTED_COMMON_INCLUDES = [
    "common_dec.sv",
    "common_draw_table.sv",
    "common_report_server.sv",
    "common_self_debug_scb.sv",
    "common_scb_types.sv",
    "common_scb_reporter.sv",
    "common_scb_registry.sv",
    "common_uvm_scb_legacy.sv",
    "common_uvm_scb.sv",
]


def assert_final_common_layout(templates, package: str) -> None:
    assert templates == EXPECTED_COMMON_TEMPLATES
    active_includes = re.findall(
        r'(?m)^[ \t]*`include[ \t]+"([^"\r\n]+)"[ \t]*$',
        strip_sv_comments(package),
    )
    assert active_includes == EXPECTED_COMMON_INCLUDES


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


def adapter_task_body(adapter: str, task_name: str) -> str:
    match = re.search(
        rf"(?ms)^[ \t]*(?:protected[ \t]+)?static[ \t]+task[ \t]+"
        rf"{re.escape(task_name)}\b"
        rf"[^;]*;(?P<body>.*?)^[ \t]*endtask",
        adapter,
    )
    assert match, f"missing adapter {task_name} task body"
    return match.group("body")


def assert_aip_generation_contract(
    aip_core: bool, common_file_names: set[str], filelist: str
) -> None:
    adapter_name = "common_scb_aip_adapter.sv"
    adapter_entry = f"./{adapter_name}"
    assert (adapter_name in common_file_names) is aip_core
    assert (adapter_entry in filelist) is aip_core

    active_lines = [
        line.strip()
        for line in filelist.splitlines()
        if line.strip() and not line.lstrip().startswith("+")
    ]
    expected_lines = ["./common_lib_pkg.sv"]
    if aip_core:
        expected_lines.extend(
            ["./aip_activity_subscriber.sv", adapter_entry]
        )
    assert active_lines == expected_lines


def assert_aip_adapter_contract(adapter_raw: str) -> None:
    adapter = strip_sv_comments(adapter_raw)

    assert re.search(
        r"(?m)^[ \t]*import[ \t]+aip_core_pkg::\*[ \t]*;[ \t]*$",
        adapter,
    ), "adapter must import AIP Core"
    assert re.search(
        r"(?m)^[ \t]*import[ \t]+common_lib_pkg::\*[ \t]*;[ \t]*$",
        adapter,
    ), "adapter must import the AIP-independent scoreboard control package"
    assert re.search(
        r"(?m)^[ \t]*class[ \t]+common_scb_aip_adapter[ \t]*;",
        adapter,
    ), "missing adapter class"

    finish = adapter_task_body(adapter, "finish")
    finish_status = registry_match_position(
        finish,
        r"aip_cmd::__aip_cmd_last_status\s*=\s*status\s*;",
        "finish status forwarding",
    )
    finish_result = registry_match_position(
        finish,
        r"aip_cmd::__aip_cmd_last_result\s*=\s*result\s*;",
        "finish result forwarding",
    )
    assert finish_status < finish_result
    assert adapter.count("aip_cmd::__aip_cmd_last_status") == 1
    assert adapter.count("aip_cmd::__aip_cmd_last_result") == 1

    lookup = registry_function_body(
        adapter,
        (
            r"^[ \t]*protected[ \t]+static[ \t]+function[ \t]+"
            r"common_scb_control_proxy[ \t]+lookup\s*\([^;]*;"
        ),
        "adapter lookup",
    )
    assert re.search(
        r"common_scb_registry::find\s*\(\s*name\s*\)", lookup
    ), "adapter lookup must use the non-parameterized registry"
    assert re.search(
        r"proxy\s*==\s*null.*unknown scoreboard.*error\s*=\s*\"\"",
        lookup,
        flags=re.DOTALL,
    ), "adapter lookup must return a useful exact-name failure"

    parser = registry_function_body(
        adapter,
        (
            r"^[ \t]*protected[ \t]+static[ \t]+function[ \t]+bit[ \t]+"
            r"parse_int_exact\s*\([^;]*;"
        ),
        "exact integer parser",
    )
    assert re.fullmatch(
        r"\s*return\s+common_scb_parse_int_exact\s*\(\s*text\s*,\s*value\s*\)\s*;\s*",
        parser,
    ), "adapter parser wrapper must only delegate to the shared utility"

    list_body = adapter_task_body(adapter, "list")
    assert re.search(r"common_scb_registry::get_names\s*\(\s*names\s*\)", list_body)
    assert re.search(r"names\s*\[\s*i\s*\]", list_body)
    assert r'"\n"' in list_body
    assert re.search(r"finish\s*\(\s*0\s*,\s*result\s*\)", list_body)

    status_body = adapter_task_body(adapter, "status")
    assert re.search(r"lookup\s*\(\s*name\s*,\s*error\s*\)", status_body)
    assert re.search(r"finish\s*\(\s*-1\s*,\s*error\s*\)", status_body)
    assert re.search(
        r"finish\s*\(\s*0\s*,\s*proxy\.summary\s*\(\s*\)\s*\)",
        status_body,
    )

    report_body = adapter_task_body(adapter, "report")
    assert re.search(r"lookup\s*\(\s*name\s*,\s*error\s*\)", report_body)
    assert re.search(
        r"parse_int_exact\s*\(\s*limit_text\s*,\s*limit\s*\)",
        report_body,
    )
    assert re.search(r"limit\s*<\s*-2", report_body)
    assert re.search(r"proxy\.report\s*\(\s*limit\s*\)", report_body)
    assert re.search(r"proxy\.summary\s*\(\s*\)", report_body)

    set_limit_body = adapter_task_body(adapter, "set_limit")
    assert re.search(r"lookup\s*\(\s*name\s*,\s*error\s*\)", set_limit_body)
    assert re.search(
        r"parse_int_exact\s*\(\s*limit_text\s*,\s*limit\s*\)",
        set_limit_body,
    )
    assert re.search(
        r"proxy\.set_report_limit\s*\(\s*limit\s*,\s*error\s*\)",
        set_limit_body,
    )
    assert "%s report_limit=%0d" in set_limit_body

    registrations = re.findall(
        r"(?m)^[ \t]*`(aip_cmd_str_[12]i_status)\s*\(\s*"
        r"(scb_[A-Za-z0-9_]+)\s*,",
        adapter,
    )
    assert registrations == [
        ("aip_cmd_str_1i_status", "scb_list"),
        ("aip_cmd_str_1i_status", "scb_status"),
        ("aip_cmd_str_2i_status", "scb_report"),
        ("aip_cmd_str_2i_status", "scb_set_limit"),
    ]
    all_registrations = re.findall(
        r"(?m)^[ \t]*`aip_cmd[A-Za-z0-9_]*\s*\(\s*"
        r"([A-Za-z_][A-Za-z0-9_:]*)\s*,",
        adapter,
    )
    assert all_registrations == [
        "scb_list",
        "scb_status",
        "scb_report",
        "scb_set_limit",
    ], "adapter must register exactly the four approved commands"
    assert re.search(
        r"`aip_cmd_str_1i_status\s*\(\s*scb_list\s*,.*?unused\s*,\s*\"\"\s*\)",
        adapter,
        flags=re.DOTALL,
    )
    assert re.search(
        r"`aip_cmd_str_2i_status\s*\(\s*scb_report\s*,.*?"
        r"name\s*,\s*\"\"\s*,\s*limit\s*,\s*\"-2\"\s*\)",
        adapter,
        flags=re.DOTALL,
    )
    assert re.search(
        r"`aip_cmd_str_2i_status\s*\(\s*scb_set_limit\s*,.*?"
        r"name\s*,\s*\"\"\s*,\s*limit\s*,\s*\"\"\s*\)",
        adapter,
        flags=re.DOTALL,
    )

    forbidden = (
        "scb_clear",
        "reset_state",
        ".delete(",
        "clear(",
        "push_expected",
        "push_actual",
    )
    for token in forbidden:
        assert token not in adapter, f"adapter exposes destructive capability: {token}"
    assert "common_uvm_scb" not in adapter
    assert "common_scb_registry::" in adapter
    assert "common_scb_control_proxy" in adapter
    assert "{{" not in adapter_raw and "{%" not in adapter_raw



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
        "common_dec.sv",
        "common_draw_table.sv",
        "common_report_server.sv",
        "common_self_debug_scb.sv",
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
    assert active_includes == required_includes, (
        "common package include sequence mismatch: "
        f"expected {required_includes}, got {active_includes}"
    )


def test_final_common_layout_contract_rejects_generator_or_package_reordering():
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=PlatformType.ADVANCE,
        aip_core=False,
    )
    package = PlatformGenerator(config).render_template(
        "common/common_pkg.sv.j2",
        file_name="common_lib_pkg.sv",
    )
    assert_final_common_layout(CommonGenerator.TEMPLATES, package)

    wrong_templates = list(EXPECTED_COMMON_TEMPLATES)
    wrong_templates[-1], wrong_templates[-2] = (
        wrong_templates[-2],
        wrong_templates[-1],
    )
    with pytest.raises(AssertionError):
        assert_final_common_layout(wrong_templates, package)

    wrong_package = package.replace(
        '    `include "common_scb_reporter.sv"\n'
        '    `include "common_scb_registry.sv"',
        '    `include "common_scb_registry.sv"\n'
        '    `include "common_scb_reporter.sv"',
    )
    assert wrong_package != package, "failed to construct package-order mutation"
    with pytest.raises(AssertionError):
        assert_final_common_layout(EXPECTED_COMMON_TEMPLATES, wrong_package)


def test_v2_finalizes_in_check_and_only_renders_in_report(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core = read(project, "common/common_uvm_scb.sv")
    check_body = core[core.index("function void common_uvm_scb::check_phase") :]
    report_body = core[core.index("function void common_uvm_scb::report_phase") :]
    assert "finalize_pending();" in check_body
    assert "print_report();" in report_body
    assert report_body.index("print_report();") < report_body.index("endfunction")


def test_v2_report_has_limit_and_omission_accounting(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core = read(project, "common/common_uvm_scb.sv")
    assert "Problem streams: total=%0d shown=%0d omitted=%0d" in core
    assert "limit == -2" in core
    assert "limit == -1" in core
    assert "m_suppressed_details" in core
    assert "normal streams" not in core.lower()


def test_non_aip_common_has_no_adapter_or_aip_commands(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=False)
    common_dir = project / "common"
    assert_aip_generation_contract(
        False,
        {path.name for path in common_dir.glob("*.sv")},
        read(project, "common/common_lib_pkg.f"),
    )
    common_files = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (project / "common").glob("*.sv")
    )
    assert "aip_cmd" not in common_files


def test_aip_output_has_exact_non_destructive_scb_adapter(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type, aip_core=True)
    adapter_path = project / "common/common_scb_aip_adapter.sv"
    assert adapter_path.is_file()
    assert_aip_adapter_contract(adapter_path.read_text(encoding="utf-8"))


def test_aip_adapter_is_compiled_after_its_dependencies(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    filelist = read(project, "common/common_lib_pkg.f")
    assert_aip_generation_contract(
        True,
        {path.name for path in (project / "common").glob("*.sv")},
        filelist,
    )

    tb_filelist = read(project, "cfg/tb.f")
    assert tb_filelist.index("$AIP_CORE_HOME/aip_core_pkg.sv") < (
        tb_filelist.index("-F   ./env.f")
    )


def test_aip_adapter_registration_contract_rejects_mutations():
    config = ProjectConfig(
        block_name="top",
        author="test",
        agents=[AgentConfig("axi")],
        platform_type=PlatformType.ADVANCE,
        aip_core=True,
    )
    adapter_raw = PlatformGenerator(config).render_template(
        "common/common_scb_aip_adapter.sv.j2",
        file_name="common_scb_aip_adapter.sv",
    )
    mutations = {
        "parser wrapper bypasses shared utility": (
            r"return\s+common_scb_parse_int_exact\s*\(\s*text\s*,\s*value\s*\)\s*;",
            r'return $sscanf(text, "%d", value) == 1;',
        ),
        "wrong report sentinel": (
            r"(name\s*,\s*\"\"\s*,\s*limit\s*,\s*)\"-2\"",
            r'\1"-1"',
        ),
        "missing command": (
            r"(?m)^`aip_cmd_str_1i_status\s*\(\s*scb_status[^\n]*\)\n",
            "",
        ),
        "extra command": (
            r"(?m)^(`aip_cmd_str_1i_status\s*\(\s*scb_list[^\n]*\))$",
            r"\1\n`aip_cmd_str_1i_status(scb_debug, common_scb_aip_adapter::list, unused, \"\")",
        ),
        "destructive reset command": (
            r"(?m)^(`aip_cmd_str_1i_status\s*\(\s*scb_list[^\n]*\))$",
            r"\1\n`aip_cmd_str_1i_status(scb_clear, common_scb_aip_adapter::list, unused, \"\")",
        ),
    }
    for description, (pattern, replacement) in mutations.items():
        broken, replacements = re.subn(
            pattern,
            replacement,
            adapter_raw,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert replacements == 1, f"failed to construct {description} mutation"
        with pytest.raises(AssertionError):
            assert_aip_adapter_contract(broken)


def test_aip_generation_contract_rejects_guard_and_order_regressions():
    non_aip_files = {"common_lib_pkg.sv", "common_uvm_scb.sv"}
    non_aip_filelist = "+incdir+./\n./common_lib_pkg.sv\n"
    aip_files = non_aip_files | {
        "aip_activity_subscriber.sv",
        "common_scb_aip_adapter.sv",
    }
    aip_filelist = (
        "+incdir+./\n"
        "./common_lib_pkg.sv\n"
        "./aip_activity_subscriber.sv\n"
        "./common_scb_aip_adapter.sv\n"
    )

    assert_aip_generation_contract(False, non_aip_files, non_aip_filelist)
    assert_aip_generation_contract(True, aip_files, aip_filelist)

    with pytest.raises(AssertionError):
        assert_aip_generation_contract(
            False,
            non_aip_files | {"common_scb_aip_adapter.sv"},
            non_aip_filelist + "./common_scb_aip_adapter.sv\n",
        )
    with pytest.raises(AssertionError):
        assert_aip_generation_contract(
            True,
            aip_files,
            aip_filelist.replace(
                "./common_lib_pkg.sv\n./aip_activity_subscriber.sv",
                "./aip_activity_subscriber.sv\n./common_lib_pkg.sv",
            ),
        )


def test_aip_adapter_vcs_behavioral_assets_cover_runtime_contract():
    repository = Path(__file__).parent.parent
    harness_path = repository / "tests/vcs/common_scb_aip_adapter_tb.sv"
    runner_path = repository / "tests/vcs/run_common_scb_aip_adapter.sh"
    assert harness_path.is_file(), "missing adapter VCS behavioral harness"
    assert runner_path.is_file(), "missing adapter VCS behavioral runner"

    harness = harness_path.read_text(encoding="utf-8")
    runner = runner_path.read_text(encoding="utf-8")
    for command in ("list", "status", "report", "set_limit"):
        assert f"common_scb_aip_adapter::{command}" in harness
    for boundary in (
        '"-2147483648"',
        '"2147483647"',
        '"-2147483649"',
        '"2147483648"',
        '"1.0"',
        '"1junk"',
        '"+"',
        '"-"',
        '""',
    ):
        assert boundary in harness
    assert "STALE_RESULT" in harness
    assert "SCB_AIP_ADAPTER_TB_PASS" in harness
    assert "scb_clear" not in harness and "reset_state" not in harness
    for command in ("scb_list", "scb_status", "scb_report", "scb_set_limit"):
        assert f'aip_cmd::get_handle("{command}")' in harness
    assert '"9999999999999999999999999999999999999999"' in harness

    assert "timeout" in runner
    assert "SCB_AIP_ADAPTER_TB_PASS" in runner
    assert "UVM_(ERROR|FATAL)" in runner
    assert r"\[ERROR\]" in runner
    assert "aip_core_pkg.sv" in runner
    assert "common_lib_pkg.f" in runner


def test_v2_vcs_semantic_assets_cover_runtime_contract():
    repository = Path(__file__).parent.parent
    harness_path = repository / "tests/vcs/common_scb_unit_tb.sv"
    runner_path = repository / "tests/vcs/run_common_scb_v2.sh"
    assert harness_path.is_file(), "missing scoreboard v2 VCS semantic harness"
    assert runner_path.is_file(), "missing scoreboard v2 VCS semantic runner"

    harness = harness_path.read_text(encoding="utf-8")
    runner = runner_path.read_text(encoding="utf-8")
    readme = (repository / "README.md").read_text(encoding="utf-8")
    for contract in (
        "SCB_UNIT_PASS",
        "SCB_CLONE_DISABLED_OWNERSHIP_PASS",
        "uvm_report_catcher",
        "common_scb_reporter",
        "class scb_report_expectation",
        "expect_report(",
        "unexpected_guarded_events",
        "all_expectations_consumed",
        "m_cfg_seven",
        "m_cfg_invalid",
        "m_clone_disabled",
        "m_clone_en = 0",
        "uvm_config_db#(common_uvm_scb_cfg)::set",
        "SCB_EXPECT_CFG_TEXT",
        "SCB_EXPECT_CONFIG_WARN",
        "configured m_report_limit=-2 is below -1; using 10",
        "m_reset_counters",
        "probe_finalize_pending()",
        "reset_state(0)",
        "reset_state(1)",
        "print_report(-1)",
        "m_report_en = 0",
        "64'hf000_0000_0000_0001",
    ):
        assert contract in harness

    assert runner_path.stat().st_mode & 0o111, "scoreboard v2 runner is not executable"
    for mode in (
        "+SCB_REPORT_LIMIT=0",
        "+SCB_REPORT_LIMIT=-1",
        "+SCB_REPORT_LIMIT=20",
        "+SCB_REPORT_LIMIT=-2",
        "+SCB_REPORT_LIMIT=malformed",
        "+SCB_REPORT_LIMIT=+17",
        "+SCB_REPORT_LIMIT=2147483647",
        "+SCB_REPORT_LIMIT=2147483648",
        "+SCB_REPORT_LIMIT=1junk",
        '"+SCB_REPORT_LIMIT="',
        '"+SCB_REPORT_LIMIT=+"',
        "+SCB_REPORT_LIMIT=-",
        "+SCB_REPORT_LIMIT=9999999999999999999999999999999999999999",
    ):
        assert mode in runner
    for gate in (
        "timeout --kill-after",
        "SCB_UNIT_PASS",
        "SCB_UNIT_FAIL",
        "UVM_ERROR",
        "UVM_FATAL",
    ):
        assert gate in runner
    assert "SCB_CLONE_DISABLED_OWNERSHIP_PASS" in runner
    assert "+SCB_EXPECT_CONFIG_WARN=1" in runner
    assert re.search(
        r'expect_cfg_warning\("uvm_test_top\.m_clone_disabled"\s*,',
        harness,
    )
    assert "17 * expected_cfg_warn" in harness
    assert "does not copy the transaction or take ownership" in readme
    assert "retains the original producer-owned transaction handle" in readme
    assert "Callers must keep that handle stable" in readme


def test_v2_vcs_runner_rejects_ambiguous_uvm_logs(tmp_path):
    runner = Path(__file__).parent.parent / "tests/vcs/run_common_scb_v2.sh"

    def validate(name: str, contents: str) -> subprocess.CompletedProcess[str]:
        log = tmp_path / name
        log.write_text(contents, encoding="utf-8")
        return subprocess.run(
            [str(runner), "--validate-log", str(log)],
            check=False,
            capture_output=True,
            text=True,
        )

    clean = validate(
        "clean.log",
        "ordinary output\nUVM_ERROR : 0\nUVM_FATAL : 0\n",
    )
    assert clean.returncode == 0, clean.stderr

    ansi_clean = validate(
        "ansi-clean.log",
        "\x1b[31mUVM_ERROR : 0\x1b[0m\r\n"
        "\x1b[32mUVM_FATAL : 0\x1b[0m\r\n",
    )
    assert ansi_clean.returncode == 0, ansi_clean.stderr

    mixed = validate(
        "mixed.log",
        "UVM_ERROR : 0\nUVM_ERROR : 3\nUVM_FATAL : 0\n",
    )
    assert mixed.returncode != 0

    source_error = validate(
        "source-error.log",
        "UVM_ERROR file.sv(12) @ 0: top [INJECTED] unexpected\n"
        "UVM_ERROR : 0\nUVM_FATAL : 0\n",
    )
    assert source_error.returncode != 0

    duplicate = validate(
        "duplicate.log",
        "UVM_ERROR : 0\nUVM_ERROR : 0\nUVM_FATAL : 0\n",
    )
    assert duplicate.returncode != 0


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

    assert re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+match_count\s*;",
        types,
    ), "stream state must use the VCS-portable match_count field"
    assert not re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+matches\s*;",
        types,
    ), "matches is a reserved SystemVerilog identifier"

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
        "SCB_REPORT_LIMIT=%s",
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


SCB_WIRING_AGENTS = ("axi", "apb")


def sv_function_body(systemverilog: str, declaration: str, description: str) -> str:
    source = strip_sv_comments(systemverilog)
    match = re.search(
        rf"(?ms){declaration}(?P<body>.*?)^[ \t]*endfunction\b", source
    )
    assert match, f"missing {description} function body"
    return match.group("body")


def sv_task_body(systemverilog: str, declaration: str, description: str) -> str:
    source = strip_sv_comments(systemverilog)
    match = re.search(rf"(?ms){declaration}(?P<body>.*?)^[ \t]*endtask\b", source)
    assert match, f"missing {description} task body"
    return match.group("body")


def assert_scb_push(body: str, agent: str, direction: str):
    match = re.search(
        rf"\bm_{agent}_scb\.push_{direction}\s*\(\s*tr\s*,\s*"
        r"tr\.get_scb_stream_id\s*\(\s*\)\s*,\s*"
        r"tr\.get_scb_kind\s*\(\s*\)\s*\)\s*;",
        body,
    )
    assert match, f"{agent} {direction} callback must pass both routing hooks"
    return match


def assert_checker_v2_wiring(checker_raw: str, platform_type: PlatformType) -> None:
    checker = strip_sv_comments(checker_raw)
    for agent in SCB_WIRING_AGENTS:
        scoreboard_declaration = (
            rf"(?m)^[ \t]*common_uvm_scb\s*#\s*\(\s*{agent}_trans\s*\)\s+"
            rf"m_{agent}_scb\s*;"
        )
        assert len(re.findall(scoreboard_declaration, checker)) == 1, (
            f"checker must own exactly one typed {agent} scoreboard"
        )
        scoreboard_construction = (
            rf"m_{agent}_scb\s*=\s*common_uvm_scb\s*#\s*\(\s*{agent}_trans\s*\)"
            rf"\s*::\s*type_id\s*::\s*create\s*\(\s*\"m_{agent}_scb\"\s*,\s*this\s*\)\s*;"
        )
        assert len(re.findall(scoreboard_construction, checker)) == 1, (
            f"checker must construct exactly one typed {agent} scoreboard"
        )

        if platform_type is PlatformType.ADVANCE:
            for endpoint, suffix in (("rm", "rm"), ("agt", "agt")):
                declaration = (
                    rf"(?m)^[ \t]*uvm_analysis_imp_from_{endpoint}_{agent}\s*#\s*"
                    rf"\(\s*{agent}_trans\s*,\s*top_checker\s*\)\s*"
                    rf"m_from_{endpoint}_{agent}_imp\s*;"
                )
                assert len(re.findall(declaration, checker)) == 1, (
                    f"missing typed Advance {agent} {suffix} analysis imp"
                )
                construction = (
                    rf"m_from_{endpoint}_{agent}_imp\s*=\s*new\s*\(\s*"
                    rf"\"m_from_{endpoint}_{agent}_imp\"\s*,\s*this\s*\)\s*;"
                )
                assert len(re.findall(construction, checker)) == 1, (
                    f"missing Advance {agent} {suffix} analysis imp construction"
                )
            expected_body = sv_function_body(
                checker,
                rf"^[ \t]*function\s+void\s+top_checker::write_from_rm_{agent}\s*\(\s*"
                rf"{agent}_trans\s+tr\s*\)\s*;",
                f"Advance {agent} expected callback",
            )
            actual_body = sv_function_body(
                checker,
                rf"^[ \t]*function\s+void\s+top_checker::write_from_agt_{agent}\s*\(\s*"
                rf"{agent}_trans\s+tr\s*\)\s*;",
                f"Advance {agent} actual callback",
            )
        else:
            for direction in ("rm", "agt"):
                declaration = (
                    rf"(?m)^[ \t]*uvm_blocking_get_port\s*#\s*\(\s*"
                    rf"{agent}_trans\s*\)\s*m_from_{direction}_{agent}_trans_port\s*;"
                )
                assert len(re.findall(declaration, checker)) == 1, (
                    f"PORT {agent} {direction} FIFO get-port topology changed"
                )
            expected_body = sv_task_body(
                checker,
                rf"^[ \t]*task\s+top_checker::process_{agent}_trans_from_rm\s*\(\s*\)\s*;",
                f"PORT {agent} expected worker",
            )
            actual_body = sv_task_body(
                checker,
                rf"^[ \t]*task\s+top_checker::process_{agent}_trans_from_agt\s*\(\s*\)\s*;",
                f"PORT {agent} actual worker",
            )
            expected_get = re.search(
                rf"(?:this\s*\.\s*)?m_from_rm_{agent}_trans_port\s*\.\s*get\s*\(\s*tr\s*\)\s*;",
                expected_body,
            )
            assert expected_get, f"PORT {agent} expected worker must retain its blocking get"
            actual_get = re.search(
                rf"(?:this\s*\.\s*)?m_from_agt_{agent}_trans_port\s*\.\s*get\s*\(\s*tr\s*\)\s*;",
                actual_body,
            )
            assert actual_get, f"PORT {agent} actual worker must retain its blocking get"

        assert "m_scb_rec_rm_trans_total_cnt++" in expected_body
        assert "m_scb_rec_dut_trans_total_cnt++" in actual_body
        expected_push = assert_scb_push(expected_body, agent, "expected")
        actual_push = assert_scb_push(actual_body, agent, "actual")
        assert expected_body.index("m_scb_rec_rm_trans_total_cnt++") < expected_push.start()
        assert actual_body.index("m_scb_rec_dut_trans_total_cnt++") < actual_push.start()
        if platform_type is PlatformType.PORT:
            assert expected_get.start() < expected_push.start()
            assert actual_get.start() < actual_push.start()

    reset_state = sv_function_body(
        checker,
        r"^[ \t]*function\s+void\s+top_checker::reset_state\s*\(\s*\)\s*;",
        "checker reset_state",
    )
    for agent in SCB_WIRING_AGENTS:
        assert re.search(
            rf"\bm_{agent}_scb\s*\.\s*reset_state\s*\(\s*\)\s*;", reset_state
        ), f"checker reset_state must propagate to {agent}"
    reset_phase = sv_task_body(
        checker,
        r"^[ \t]*task\s+top_checker::reset_phase\s*\(\s*uvm_phase\s+phase\s*\)\s*;",
        "checker reset_phase",
    )
    assert re.search(r"\bsuper\s*\.\s*reset_phase\s*\(\s*phase\s*\)\s*;", reset_phase)
    if platform_type is PlatformType.ADVANCE:
        assert re.search(r"\breset_state\s*\(\s*\)\s*;", reset_phase)
    else:
        assert not re.search(r"\breset_state\s*\(\s*\)\s*;", reset_phase), (
            "PORT env must perform the sole reset after quiescing FIFO workers"
        )

    assert "uvm_sequence_item" not in checker
    assert "$cast" not in checker
    assert "TODO" not in checker_raw


def assert_advance_rm_and_env_wiring(rm_raw: str, env_raw: str) -> None:
    rm = strip_sv_comments(rm_raw)
    for agent in SCB_WIRING_AGENTS:
        assert re.search(
            rf"(?m)^[ \t]*uvm_analysis_imp_from_{agent}_agt\s*#\s*\(\s*"
            rf"{agent}_trans\s*,\s*top_rm\s*\)\s*m_from_{agent}_agt_imp\s*;",
            rm,
        ), f"missing typed Advance RM {agent} analysis imp"
        assert re.search(
            rf"(?m)^[ \t]*uvm_analysis_port\s*#\s*\(\s*{agent}_trans\s*\)\s*"
            rf"m_{agent}_expected_ap\s*;",
            rm,
        ), f"missing typed Advance RM {agent} expected port"
        for member in (
            f"m_from_{agent}_agt_imp",
            f"m_{agent}_expected_ap",
        ):
            assert re.search(
                rf"\b{member}\s*=\s*new\s*\(\s*\"{member}\"\s*,\s*this\s*\)\s*;",
                rm,
            ), f"Advance RM must construct {member}"
        callback = sv_function_body(
            rm,
            rf"^[ \t]*function\s+void\s+top_rm::write_from_{agent}_agt\s*\(\s*"
            rf"{agent}_trans\s+tr\s*\)\s*;",
            f"Advance RM {agent} callback",
        )
        assert re.search(
            rf"\bm_{agent}_expected_ap\s*\.\s*write\s*\(\s*null\s*\)\s*;",
            callback,
        ), f"Advance RM must preserve null {agent} predictions"
        assert re.search(
            rf"\bm_{agent}_expected_ap\s*\.\s*write\s*\(\s*prediction\s*\)\s*;",
            callback,
        ), f"Advance RM must publish isolated {agent} predictions"

    env = sv_function_body(
        env_raw,
        r"^[ \t]*function\s+void\s+top_env::connect_phase\s*\(\s*uvm_phase\s+phase\s*\)\s*;",
        "Advance env connect_phase",
    )
    for agent in SCB_WIRING_AGENTS:
        expected_connections = (
            rf"\bm_{agent}_agt\s*\.\s*m_mon\s*\.\s*m_ap\s*\.\s*connect\s*\(\s*"
            rf"m_rm\s*\.\s*m_from_{agent}_agt_imp\s*\)\s*;",
            rf"\bm_rm\s*\.\s*m_{agent}_expected_ap\s*\.\s*connect\s*\(\s*"
            rf"m_scb\s*\.\s*m_from_rm_{agent}_imp\s*\)\s*;",
            rf"\bm_{agent}_agt\s*\.\s*m_mon\s*\.\s*m_ap\s*\.\s*connect\s*\(\s*"
            rf"m_scb\s*\.\s*m_from_agt_{agent}_imp\s*\)\s*;",
        )
        for connection in expected_connections:
            assert re.search(connection, env), f"missing Advance {agent} data path"

    assert "uvm_sequence_item" not in rm
    assert "cast_tr" not in rm
    assert "TODO" not in rm_raw


def test_generated_transactions_expose_default_scb_routing_hooks(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    for agent in SCB_WIRING_AGENTS:
        trans = read(project, f"env/agents/{agent}_agent/src/{agent}_trans.sv")
        uncommented = strip_sv_comments(trans)
        comparison = re.search(
            rf"(?ms)^[ \t]*function\s+bit\s+self_define_do_compare\s*\(\s*"
            rf"{agent}_trans\s+cmp_trans\s*,.*?^[ \t]*endfunction\b",
            uncommented,
        )
        assert comparison, f"missing {agent} comparison hook"
        stream_id = sv_function_body(
            trans,
            r"^[ \t]*virtual\s+function\s+longint\s+unsigned\s+"
            r"get_scb_stream_id\s*\(\s*\)\s*;",
            f"{agent} stream-id hook",
        )
        kind = sv_function_body(
            trans,
            r"^[ \t]*virtual\s+function\s+int\s+get_scb_kind\s*\(\s*\)\s*;",
            f"{agent} kind hook",
        )
        assert re.search(r"\breturn\s+'1\s*;", stream_id)
        assert re.search(r"\breturn\s+-1\s*;", kind)
        assert comparison.end() < uncommented.index("function longint unsigned get_scb_stream_id")


def test_generated_transactions_make_scb_routing_hooks_virtual(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    for agent in SCB_WIRING_AGENTS:
        trans = strip_sv_comments(
            read(project, f"env/agents/{agent}_agent/src/{agent}_trans.sv")
        )
        assert re.search(
            r"(?m)^[ \t]*virtual\s+function\s+longint\s+unsigned\s+"
            r"get_scb_stream_id\s*\(\s*\)\s*;",
            trans,
        ), f"{agent} stream-id hook must support protocol overrides"
        assert re.search(
            r"(?m)^[ \t]*virtual\s+function\s+int\s+get_scb_kind\s*\(\s*\)\s*;",
            trans,
        ), f"{agent} kind hook must support protocol overrides"


def checker_direction_body(
    checker: str, platform_type: PlatformType, agent: str, direction: str
) -> str:
    if platform_type is PlatformType.ADVANCE:
        source = "rm" if direction == "expected" else "agt"
        return sv_function_body(
            checker,
            rf"^[ \t]*function\s+void\s+top_checker::write_from_{source}_{agent}\s*"
            rf"\(\s*{agent}_trans\s+tr\s*\)\s*;",
            f"Advance {agent} {direction} callback",
        )
    source = "rm" if direction == "expected" else "agt"
    return sv_task_body(
        checker,
        rf"^[ \t]*task\s+top_checker::process_{agent}_trans_from_{source}\s*"
        r"\(\s*\)\s*;",
        f"PORT {agent} {direction} worker",
    )


def assert_null_safe_scb_routing(checker_raw: str, platform_type: PlatformType) -> None:
    checker = strip_sv_comments(checker_raw)
    for agent in SCB_WIRING_AGENTS:
        for direction in ("expected", "actual"):
            body = checker_direction_body(checker, platform_type, agent, direction)
            guard = re.search(
                r"(?ms)if\s*\(\s*tr\s*==\s*null\s*\)\s*begin"
                r"(?P<null_branch>.*?)^[ \t]*end\s*else\s*begin"
                r"(?P<non_null_branch>.*?)^[ \t]*end\b",
                body,
            )
            assert guard, f"{agent} {direction} path must guard null transactions"
            assert "get_scb_stream_id" not in body[: guard.start()]
            assert "get_scb_kind" not in body[: guard.start()]
            assert "get_scb_stream_id" not in guard.group("null_branch")
            assert "get_scb_kind" not in guard.group("null_branch")
            assert re.search(
                rf"\bm_{agent}_scb\.push_{direction}\s*\(\s*tr\s*,\s*'1\s*,\s*-1\s*\)\s*;",
                guard.group("null_branch"),
            ), f"{agent} {direction} null input must reach the core defaults"
            assert_scb_push(guard.group("non_null_branch"), agent, direction)


def test_generated_checkers_route_null_transactions_without_hook_dereference(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    assert_null_safe_scb_routing(read(project, "env/top_checker.sv"), platform_type)


def test_null_routing_contract_rejects_missing_expected_or_actual_guards(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    checker = read(project, "env/top_checker.sv")
    assert_null_safe_scb_routing(checker, platform_type)
    for direction in ("expected", "actual"):
        source = "rm" if direction == "expected" else "agt"
        marker = (
            f"write_from_{source}_axi"
            if platform_type is PlatformType.ADVANCE
            else f"process_axi_trans_from_{source}"
        )
        marker_position = checker.index(marker)
        prefix = checker[:marker_position]
        suffix = checker[marker_position:]
        broken_suffix, replacements = re.subn(
            r"if\s*\(\s*tr\s*==\s*null\s*\)\s*begin",
            "if (tr != null) begin",
            suffix,
            count=1,
        )
        assert replacements == 1, f"failed to mutate {direction} null guard"
        with pytest.raises(AssertionError):
            assert_null_safe_scb_routing(prefix + broken_suffix, platform_type)


def rm_prediction_body(rm: str, platform_type: PlatformType, agent: str) -> str:
    if platform_type is PlatformType.ADVANCE:
        return sv_function_body(
            rm,
            rf"^[ \t]*function\s+void\s+top_rm::write_from_{agent}_agt\s*"
            rf"\(\s*{agent}_trans\s+tr\s*\)\s*;",
            f"Advance RM {agent} prediction callback",
        )
    return sv_task_body(
        rm,
        rf"^[ \t]*task\s+top_rm::process_trans_from_{agent}_agt\s*\(\s*\)\s*;",
        f"PORT RM {agent} prediction worker",
    )


def assert_rm_prediction_handle_isolation(
    rm_raw: str, platform_type: PlatformType
) -> None:
    rm = strip_sv_comments(rm_raw)
    for agent in SCB_WIRING_AGENTS:
        body = rm_prediction_body(rm, platform_type, agent)
        output = (
            f"m_{agent}_expected_ap"
            if platform_type is PlatformType.ADVANCE
            else f"m_rm_{agent}_trans_to_scb_port"
        )
        assert re.search(
            rf"(?m)^[ \t]*uvm_object\s+cloned\s*;", body
        ), f"{agent} RM must store the clone as an object before casting"
        assert re.search(
            rf"(?m)^[ \t]*{agent}_trans\s+prediction\s*;", body
        ), f"{agent} RM must use a typed prediction handle"
        null_publish = re.search(
            rf"(?ms)if\s*\(\s*tr\s*==\s*null\s*\)\s*begin.*?"
            rf"\b{output}\s*\.\s*write\s*\(\s*null\s*\)\s*;.*?"
            r"^[ \t]*end\b",
            body,
        )
        assert null_publish, f"{agent} RM must preserve null for core handling"
        clone = re.search(r"\bcloned\s*=\s*tr\s*\.\s*clone\s*\(\s*\)\s*;", body)
        clone_guard = re.search(
            rf"if\s*\(\s*cloned\s*==\s*null\s*\|\|\s*!\s*\$cast\s*"
            rf"\(\s*prediction\s*,\s*cloned\s*\)\s*\)\s*begin.*?"
            r"`uvm_error\b",
            body,
            flags=re.DOTALL,
        )
        prediction_publish = re.search(
            rf"\b{output}\s*\.\s*write\s*\(\s*prediction\s*\)\s*;", body
        )
        assert clone, f"{agent} RM must clone the monitor transaction"
        assert clone_guard, f"{agent} RM must report clone/cast failures"
        assert prediction_publish, f"{agent} RM must publish the typed prediction"
        assert clone.start() < clone_guard.start() < prediction_publish.start()
        assert not re.search(
            rf"\b{output}\s*\.\s*write\s*\(\s*tr\s*\)\s*;", body
        ), f"{agent} RM must never publish the monitor handle directly"

    assert "uvm_sequence_item" not in rm
    assert "cast_tr" not in rm
    assert "TODO" not in rm_raw


def test_generated_rms_isolate_prediction_handles_from_actual_fanout(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    assert_rm_prediction_handle_isolation(read(project, "env/top_rm.sv"), platform_type)


def test_rm_isolation_contract_rejects_direct_publish_or_missing_clone(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    rm = read(project, "env/top_rm.sv")
    assert_rm_prediction_handle_isolation(rm, platform_type)
    output = (
        "m_axi_expected_ap"
        if platform_type is PlatformType.ADVANCE
        else "m_rm_axi_trans_to_scb_port"
    )
    direct_publish = rm.replace(
        f"{output}.write(prediction);", f"{output}.write(tr);", 1
    )
    assert direct_publish != rm, "failed to construct direct-publish mutation"
    with pytest.raises(AssertionError):
        assert_rm_prediction_handle_isolation(direct_publish, platform_type)

    missing_clone = rm.replace("cloned = tr.clone();", "cloned = null;", 1)
    assert missing_clone != rm, "failed to construct missing-clone mutation"
    with pytest.raises(AssertionError):
        assert_rm_prediction_handle_isolation(missing_clone, platform_type)


def required_match_position(body: str, pattern: str, description: str) -> int:
    match = re.search(pattern, body, flags=re.MULTILINE | re.DOTALL)
    assert match, f"missing {description}"
    return match.start()


def assert_port_worker_lifecycle(
    component_raw: str, component: str, agents: tuple[str, ...]
) -> None:
    source = strip_sv_comments(component_raw)
    assert re.search(
        r"(?m)^[ \t]*int\s+m_active_worker_count\s*;",
        source,
    ), f"{component} must acknowledge every graceful FIFO-worker stop"
    assert re.search(
        r"(?m)^[ \t]*bit\s+m_workers_running\s*;", source
    ), f"{component} must prevent duplicate worker starts"
    assert re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+m_worker_epoch\s*;", source
    ), f"{component} must invalidate workers across reset epochs"
    assert re.search(
        r"(?m)^[ \t]*bit\s+m_run_phase_started\s*;", source
    ), f"{component} must only restart workers after run_phase begins"
    assert re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+"
        r"m_worker_restart_request_epoch\s*;",
        source,
    ), f"{component} must retain restart requests until its run_phase supervisor handles them"
    assert re.search(
        r"(?m)^[ \t]*longint\s+unsigned\s+"
        r"m_worker_start_ack_epoch\s*;",
        source,
    ), f"{component} must acknowledge supervisor-owned worker restarts"

    run = sv_task_body(
        source,
        rf"^[ \t]*task\s+top_{component}::run_phase\s*\(\s*uvm_phase\s+phase\s*\)\s*;",
        f"PORT {component} run_phase",
    )
    run_positions = [
        required_match_position(
            run,
            r"\bsuper\s*\.\s*run_phase\s*\(\s*phase\s*\)\s*;",
            f"{component} run_phase super call",
        ),
        required_match_position(
            run,
            r"m_run_phase_started\s*=\s*1\s*;",
            f"{component} run_phase start mark",
        ),
        required_match_position(
            run,
            r"this\s*\.\s*supervise_workers\s*\(\s*\)\s*;",
            f"{component} persistent worker supervisor",
        ),
    ]
    assert run_positions == sorted(run_positions), (
        f"{component} run_phase must own the long-lived worker supervisor"
    )

    supervisor = sv_task_body(
        source,
        rf"^[ \t]*task\s+top_{component}::supervise_workers\s*\(\s*\)\s*;",
        f"PORT {component} supervisor",
    )
    supervisor_positions = [
        required_match_position(
            supervisor,
            r"this\s*\.\s*start_workers\s*\(\s*\)\s*;",
            f"{component} supervisor initial worker start",
        ),
        required_match_position(
            supervisor,
            r"forever\s+begin",
            f"{component} persistent supervisor loop",
        ),
        required_match_position(
            supervisor,
            r"wait\s*\(\s*m_worker_restart_request_epoch\s*!=\s*"
            r"handled_restart_epoch\s*\)\s*;",
            f"{component} retained restart request wait",
        ),
    ]
    assert supervisor_positions == sorted(supervisor_positions), (
        f"{component} supervisor must start once then wait persistently for restarts"
    )
    assert len(re.findall(r"this\s*\.\s*start_workers\s*\(\s*\)\s*;", supervisor)) == 2, (
        f"{component} supervisor must be the only restart owner"
    )
    assert re.search(
        r"m_worker_start_ack_epoch\s*=\s*handled_restart_epoch\s*;",
        supervisor,
    ), f"{component} supervisor must publish an explicit startup acknowledgement"

    request = sv_task_body(
        source,
        rf"^[ \t]*task\s+top_{component}::request_workers_restart\s*\(\s*\)\s*;",
        f"PORT {component} restart request",
    )
    assert re.search(
        r"m_worker_restart_request_epoch\s*\+\+\s*;", request
    ), f"{component} restart request must advance a retained epoch"
    assert "start_workers" not in request, (
        f"{component} restart request must not spawn reset-phase descendants"
    )

    started = sv_task_body(
        source,
        rf"^[ \t]*task\s+top_{component}::wait_for_workers_started\s*\(\s*\)\s*;",
        f"PORT {component} startup acknowledgement",
    )
    assert re.search(
        r"requested_restart_epoch\s*=\s*m_worker_restart_request_epoch\s*;",
        started,
    ), f"{component} startup wait must bind to the requested restart epoch"
    assert re.search(
        r"wait\s*\(\s*m_run_phase_started\s*&&\s*"
        r"m_worker_start_ack_epoch\s*>=\s*requested_restart_epoch\s*\)\s*;",
        started,
    ), f"{component} startup wait must not accept a stale acknowledgement"

    start = sv_task_body(
        source,
        rf"^[ \t]*task\s+top_{component}::start_workers\s*\(\s*\)\s*;",
        f"PORT {component} start_workers",
    )
    start_positions = [
        required_match_position(
            start,
            r"if\s*\(\s*m_workers_running\s*\)\s*return\s*;",
            f"{component} duplicate-start guard",
        ),
        required_match_position(
            start,
            r"m_workers_running\s*=\s*1\s*;",
            f"{component} worker-running mark",
        ),
        required_match_position(
            start,
            r"m_worker_epoch\s*\+\+\s*;",
            f"{component} worker epoch increment",
        ),
        required_match_position(
            start,
            r"m_active_worker_count\s*=\s*0\s*;",
            f"{component} worker-count reset",
        ),
        required_match_position(start, r"\bfork\b", f"{component} worker fork"),
    ]
    assert start_positions == sorted(start_positions), (
        f"{component} must mark and epoch workers before spawning them"
    )
    worker_count = len(agents) * (1 if component == "rm" else 2)
    assert len(re.findall(r"m_active_worker_count\s*\+\+\s*;", start)) == worker_count, (
        f"{component} must count every worker before it blocks"
    )
    assert len(re.findall(r"m_active_worker_count\s*-\-\s*;", start)) == worker_count, (
        f"{component} must acknowledge every worker exit"
    )
    for agent in agents:
        workers = (
            (f"process_trans_from_{agent}_agt",)
            if component == "rm"
            else (
                f"process_{agent}_trans_from_rm",
                f"process_{agent}_trans_from_agt",
            )
        )
        for worker in workers:
            assert worker in start, f"{component} must restart {agent} workers"
    if agents:
        assert re.search(
            rf"wait\s*\(\s*launch_epoch\s*!=\s*m_worker_epoch\s*\|\|\s*"
            rf"m_active_worker_count\s*==\s*{worker_count}\s*\)\s*;", start
        ), f"{component} must wait until every worker can acknowledge reset"

    stop = sv_task_body(
        source,
        rf"^[ \t]*task\s+top_{component}::stop_workers\s*\(\s*\)\s*;",
        f"PORT {component} stop_workers",
    )
    stop_positions = [
        required_match_position(
            stop,
            r"m_workers_running\s*=\s*0\s*;",
            f"{component} stop mark",
        ),
        required_match_position(
            stop,
            r"m_worker_epoch\s*\+\+\s*;",
            f"{component} stop epoch increment",
        ),
    ]
    assert stop_positions == sorted(stop_positions), (
        f"{component} must invalidate workers before their null wake-up"
    )
    assert ".kill(" not in stop, (
        "killing a blocked uvm_tlm_fifo.get leaks the FIFO blocked-get count"
    )
    stopped = sv_task_body(
        source,
        rf"^[ \t]*task\s+top_{component}::wait_for_workers_stopped\s*\(\s*\)\s*;",
        f"PORT {component} wait_for_workers_stopped",
    )
    assert re.search(
        r"wait\s*\(\s*m_active_worker_count\s*==\s*0\s*\)\s*;", stopped
    ), f"{component} must wait for blocked gets to return before FIFO flush"

    for agent in agents:
        workers = (
            (f"process_trans_from_{agent}_agt",)
            if component == "rm"
            else (
                f"process_{agent}_trans_from_rm",
                f"process_{agent}_trans_from_agt",
            )
        )
        for worker in workers:
            body = sv_task_body(
                source,
                rf"^[ \t]*task\s+top_{component}::{worker}\s*\(\s*\)\s*;",
                f"PORT {component} {worker}",
            )
            epoch = required_match_position(
                body,
                r"worker_epoch\s*=\s*m_worker_epoch\s*;",
                f"{component} {worker} pre-get epoch capture",
            )
            get = required_match_position(
                body,
                r"\.\s*get\s*\(\s*tr\s*\)\s*;",
                f"{component} {worker} blocking get",
            )
            stop_guard = required_match_position(
                body,
                r"if\s*\(\s*!\s*m_workers_running\s*\|\|\s*"
                r"worker_epoch\s*!=\s*m_worker_epoch\s*\)\s*break\s*;",
                f"{component} {worker} post-get reset guard",
            )
            assert epoch < get < stop_guard, (
                f"{component} {worker} must drop a reset wake-up before processing it"
            )


def assert_port_reset_epoch(
    rm_raw: str, checker_raw: str, env_raw: str, agents: tuple[str, ...]
) -> None:
    assert_port_worker_lifecycle(rm_raw, "rm", agents)
    assert_port_worker_lifecycle(checker_raw, "checker", agents)

    checker_reset = sv_task_body(
        checker_raw,
        r"^[ \t]*task\s+top_checker::reset_phase\s*\(\s*uvm_phase\s+phase\s*\)\s*;",
        "PORT checker reset_phase",
    )
    assert re.search(r"\bsuper\s*\.\s*reset_phase\s*\(\s*phase\s*\)\s*;", checker_reset)
    assert not re.search(r"\breset_state\s*\(\s*\)\s*;", checker_reset), (
        "PORT env must own the single reset cut; checker reset_phase cannot race it"
    )

    env = sv_task_body(
        env_raw,
        r"^[ \t]*task\s+top_env::reset_phase\s*\(\s*uvm_phase\s+phase\s*\)\s*;",
        "PORT env reset_phase",
    )
    positions = [
        required_match_position(
            env, r"m_reset_epoch\s*\+\+\s*;", "PORT reset epoch increment"
        ),
        required_match_position(
            env, r"m_rm\s*\.\s*stop_workers\s*\(\s*\)\s*;", "RM quiesce"
        ),
        required_match_position(
            env, r"m_scb\s*\.\s*stop_workers\s*\(\s*\)\s*;", "checker quiesce"
        ),
    ]
    for agent in agents:
        for fifo in (
            f"m_{agent}_agt_mon_to_rm_fifo",
            f"m_rm_{agent}_trans_to_scb_fifo",
            f"m_agt_{agent}_trans_to_scb_fifo",
        ):
            positions.append(
                required_match_position(
                    env,
                    rf"\b{fifo}\s*\.\s*write\s*\(\s*null\s*\)\s*;",
                    f"{agent} {fifo} graceful-stop wake-up",
                )
            )
    positions.extend(
        [
            required_match_position(
                env,
                r"m_rm\s*\.\s*wait_for_workers_stopped\s*\(\s*\)\s*;",
                "RM graceful-stop acknowledgement",
            ),
            required_match_position(
                env,
                r"m_scb\s*\.\s*wait_for_workers_stopped\s*\(\s*\)\s*;",
                "checker graceful-stop acknowledgement",
            ),
        ]
    )
    for agent in agents:
        for fifo in (
            f"m_{agent}_agt_mon_to_rm_fifo",
            f"m_rm_{agent}_trans_to_scb_fifo",
            f"m_agt_{agent}_trans_to_scb_fifo",
        ):
            positions.append(
                required_match_position(
                    env,
                    rf"\b{fifo}\s*\.\s*flush\s*\(\s*\)\s*;",
                    f"{agent} {fifo} stale-epoch flush",
                )
            )
    positions.extend(
        [
            required_match_position(
                env,
                r"m_scb\s*\.\s*reset_state\s*\(\s*\)\s*;",
                "typed-scoreboard reset",
            ),
            required_match_position(
                env,
                r"m_rm\s*\.\s*request_workers_restart\s*\(\s*\)\s*;",
                "RM supervisor restart request",
            ),
            required_match_position(
                env,
                r"m_scb\s*\.\s*request_workers_restart\s*\(\s*\)\s*;",
                "checker supervisor restart request",
            ),
            required_match_position(
                env,
                r"m_rm\s*\.\s*wait_for_workers_started\s*\(\s*\)\s*;",
                "RM supervisor startup acknowledgement",
            ),
            required_match_position(
                env,
                r"m_scb\s*\.\s*wait_for_workers_started\s*\(\s*\)\s*;",
                "checker supervisor startup acknowledgement",
            ),
        ]
    )
    assert positions == sorted(positions), (
        "PORT reset must epoch, quiesce, wake and await workers, flush every FIFO, "
        "reset cores, then request and await supervisor-owned restarts"
    )
    assert not re.search(r"\b(?:m_rm|m_scb)\s*\.\s*start_workers\s*\(", env), (
        "PORT env.reset_phase must never spawn long-lived workers itself"
    )


@pytest.mark.parametrize(
    "agents",
    [(), ("axi",), ("axi", "apb")],
    ids=["zero_agents", "one_agent", "two_agents"],
)
def test_generated_port_reset_starts_a_clean_epoch(tmp_path, agents):
    project = generate_with_agents(tmp_path, PlatformType.PORT, agents)
    assert_port_reset_epoch(
        read(project, "env/top_rm.sv"),
        read(project, "env/top_checker.sv"),
        read(project, "env/top_env.sv"),
        agents,
    )


def test_port_reset_contract_rejects_unquiesced_or_racing_fifo_flush(tmp_path):
    agents = ("axi", "apb")
    project = generate_with_agents(tmp_path, PlatformType.PORT, agents)
    rm = read(project, "env/top_rm.sv")
    checker = read(project, "env/top_checker.sv")
    env = read(project, "env/top_env.sv")
    assert_port_reset_epoch(rm, checker, env, agents)

    unquiesced = env.replace("m_scb.stop_workers();", "", 1)
    assert unquiesced != env, "failed to construct missing-checker-quiesce mutation"
    with pytest.raises(AssertionError):
        assert_port_reset_epoch(rm, checker, unquiesced, agents)

    racing_flush = env.replace(
        "m_scb.wait_for_workers_stopped();\n    m_axi_agt_mon_to_rm_fifo.flush();",
        "m_axi_agt_mon_to_rm_fifo.flush();\n    m_scb.wait_for_workers_stopped();",
        1,
    )
    assert racing_flush != env, "failed to construct racing-flush mutation"
    with pytest.raises(AssertionError):
        assert_port_reset_epoch(rm, checker, racing_flush, agents)

    phase_owned_restart = env.replace(
        "m_rm.request_workers_restart();", "m_rm.start_workers();", 1
    )
    assert phase_owned_restart != env, (
        "failed to construct reset-phase-owned worker restart mutation"
    )
    with pytest.raises(AssertionError):
        assert_port_reset_epoch(rm, checker, phase_owned_restart, agents)


def test_generated_checkers_own_and_feed_typed_v2_scoreboards(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    assert_checker_v2_wiring(read(project, "env/top_checker.sv"), platform_type)


def test_generated_advance_rm_and_env_have_typed_expected_actual_paths(tmp_path):
    project = generate(tmp_path, PlatformType.ADVANCE)
    assert_advance_rm_and_env_wiring(
        read(project, "env/top_rm.sv"), read(project, "env/top_env.sv")
    )


def test_wiring_contracts_reject_swaps_missing_agents_and_disconnected_paths(
    tmp_path,
):
    advance = generate(tmp_path / "advance", PlatformType.ADVANCE)
    checker = read(advance, "env/top_checker.sv")
    env = read(advance, "env/top_env.sv")
    rm = read(advance, "env/top_rm.sv")

    swapped = checker.replace(
        "m_axi_scb.push_expected(", "m_axi_scb.push_actual(", 2
    )
    assert swapped != checker, "failed to construct expected/actual swap mutation"
    with pytest.raises(AssertionError):
        assert_checker_v2_wiring(swapped, PlatformType.ADVANCE)

    missing_agent = checker.replace(
        "common_uvm_scb#(apb_trans) m_apb_scb;", "", 1
    )
    assert missing_agent != checker, "failed to construct missing-agent mutation"
    with pytest.raises(AssertionError):
        assert_checker_v2_wiring(missing_agent, PlatformType.ADVANCE)

    disconnected = env.replace(
        "m_rm.m_apb_expected_ap.connect(", "m_rm.m_apb_expected_ap.disconnect(", 1
    )
    assert disconnected != env, "failed to construct disconnected-path mutation"
    with pytest.raises(AssertionError):
        assert_advance_rm_and_env_wiring(rm, disconnected)
