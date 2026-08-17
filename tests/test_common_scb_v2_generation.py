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


def test_common_output_contains_legacy_and_v2_scoreboard_files(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    common_files = {path.name for path in (project / "common").iterdir()}
    required_files = {
        "common_uvm_scb_legacy.sv",
        "common_scb_types.sv",
        "common_scb_reporter.sv",
        "common_scb_registry.sv",
        "common_uvm_scb.sv",
    }

    missing_files = sorted(required_files - common_files)
    assert not missing_files, f"missing generated common files: {missing_files}"


def test_legacy_and_v2_scoreboards_have_distinct_names(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    legacy_path = project / "common/common_uvm_scb_legacy.sv"
    v2_path = project / "common/common_uvm_scb.sv"
    missing_files = [
        path.name for path in (legacy_path, v2_path) if not path.is_file()
    ]
    assert not missing_files, f"missing generated scoreboard files: {missing_files}"

    legacy = read(project, "common/common_uvm_scb_legacy.sv")
    v2 = read(project, "common/common_uvm_scb.sv")

    assert "class common_uvm_scb_legacy" in legacy
    assert "legacy_scb_cmp_mode_e" in legacy
    assert "common_uvm_scb_legacy_cfg" in legacy
    assert "common_scb_legacy_stream_manager" in legacy
    assert "COMMON_UVM_SCB_LEGACY__SV" in legacy
    assert "class common_uvm_scb #(" not in legacy
    assert "class common_uvm_scb #(" in v2


def test_common_package_includes_scoreboard_dependencies_in_order(
    tmp_path, platform_type
):
    project = generate(tmp_path, platform_type)
    common_package = read(project, "common/common_lib_pkg.sv")
    required_includes = [
        '`include "common_scb_types.sv"',
        '`include "common_scb_reporter.sv"',
        '`include "common_scb_registry.sv"',
        '`include "common_uvm_scb_legacy.sv"',
        '`include "common_uvm_scb.sv"',
    ]

    missing_includes = [
        include for include in required_includes if include not in common_package
    ]
    assert not missing_includes, f"missing common package includes: {missing_includes}"

    include_positions = [common_package.index(include) for include in required_includes]
    assert include_positions == sorted(include_positions)
