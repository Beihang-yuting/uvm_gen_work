import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.base import BaseGenerator


@pytest.fixture
def project_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[AgentConfig(name="axi")],
    )


@pytest.fixture
def gen(project_cfg):
    return BaseGenerator(project_cfg)


def test_base_generator_init(gen):
    assert gen.jinja_env is not None
    assert gen.cfg.project_name == "bootis"


def test_render_template_string(gen):
    result = gen.render_string("Hello {{ name }}!", name="world")
    assert result == "Hello world!"


def test_render_header(gen):
    header = gen.render_header("test_file.sv")
    assert "bootis" in header
    assert "ryan.yu" in header
    assert "test_file.sv" in header


def test_write_file(gen):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.sv")
        gen.write_file(path, "// test content\n")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "// test content\n"


def test_write_file_creates_parent_dirs(gen):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "sub", "dir", "test.sv")
        gen.write_file(path, "content")
        assert os.path.exists(path)


def test_get_template_path_self_contained(gen):
    path = gen.get_template_path("agent", "agent.sv.j2")
    assert "self_contained/agent/agent.sv.j2" in path


def test_get_template_path_common(gen):
    path = gen.get_template_path("common", "common_pkg.sv.j2")
    assert "common/common_pkg.sv.j2" in path
