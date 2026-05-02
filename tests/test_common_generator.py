import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.common import CommonGenerator


@pytest.fixture
def project_cfg():
    return ProjectConfig(
        block_name="top",
        author="ryan.yu",
        platform_type=PlatformType.ADVANCE,
        agents=[AgentConfig(name="axi")],
    )


def test_generate_common_creates_all_files(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        expected_files = [
            "common_lib_pkg.f",
            "common_lib_pkg.sv",
            "common_dec.sv",
            "common_report_server.sv",
            "common_self_debug_scb.sv",
            "common_uvm_scb.sv",
            "common_draw_table.sv",
        ]
        for fname in expected_files:
            path = os.path.join(tmpdir, fname)
            assert os.path.exists(path), f"Missing: {fname}"


def test_common_pkg_includes(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_lib_pkg.sv")) as f:
            content = f.read()
        assert "common_lib_pkg" in content
        assert "uvm_pkg" in content
        assert '`include "common_dec.sv"' in content
        assert '`include "common_report_server.sv"' in content


def test_common_dec_has_clk_rst_macros(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_dec.sv")) as f:
            content = f.read()
        assert "CLK_GEN" in content
        assert "RST_GEN" in content


def test_common_report_server_class(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_report_server.sv")) as f:
            content = f.read()
        assert "common_report_server extends uvm_report_server" in content
        assert "compose_message" in content


def test_common_filelist_content(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_lib_pkg.f")) as f:
            content = f.read()
        assert "+incdir+./" in content
        assert "./common_lib_pkg.sv" in content


def test_common_draw_table_class(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_draw_table.sv")) as f:
            content = f.read()
        assert "common_draw_table" in content
        assert "display_table" in content
        assert "insert_line_content" in content


def test_common_uvm_scb_class(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_uvm_scb.sv")) as f:
            content = f.read()
        assert "common_uvm_scb" in content
        assert "send_rm_trans_to_cmp" in content
        assert "send_dut_trans_to_cmp" in content


def test_common_self_debug_scb_class(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_self_debug_scb.sv")) as f:
            content = f.read()
        assert "common_self_debug_scb" in content
        assert "send_rm_trans_to_cmp" in content
        assert "send_dut_trans_to_cmp" in content


def test_sv_files_have_include_guards(project_cfg):
    sv_files = [
        "common_lib_pkg.sv",
        "common_dec.sv",
        "common_report_server.sv",
        "common_self_debug_scb.sv",
        "common_uvm_scb.sv",
        "common_draw_table.sv",
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        for fname in sv_files:
            with open(os.path.join(tmpdir, fname)) as f:
                content = f.read()
            assert "`ifndef" in content, f"{fname} missing `ifndef guard"
            assert "`define" in content, f"{fname} missing `define guard"
            assert "`endif" in content, f"{fname} missing `endif guard"


def test_sv_files_have_header(project_cfg):
    sv_files = [
        "common_dec.sv",
        "common_report_server.sv",
        "common_self_debug_scb.sv",
        "common_uvm_scb.sv",
        "common_draw_table.sv",
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        for fname in sv_files:
            with open(os.path.join(tmpdir, fname)) as f:
                content = f.read()
            assert "top" in content, f"{fname} missing block_name in header"
            assert "ryan.yu" in content, f"{fname} missing author in header"


def test_common_uvm_scb_disorder_renamed(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "common_uvm_scb.sv")) as f:
            content = f.read()
        assert "DISORDER_CMP" in content
        assert "DISSORDER_CMP" not in content
        assert "m_err_print_threshold" in content
        assert "m_err_print_threadhold" not in content
