import re
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
