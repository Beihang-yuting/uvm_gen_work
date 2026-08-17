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
