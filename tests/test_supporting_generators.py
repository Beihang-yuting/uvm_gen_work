import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.harness import HarnessGenerator
from uvm_gen.generators.testcase import TestcaseGenerator


@pytest.fixture
def cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[
            AgentConfig(name="axi"),
            AgentConfig(name="apb"),
        ],
    )


def test_harness_generates(cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = HarnessGenerator(cfg)
        gen.generate(tmpdir)
        path = os.path.join(tmpdir, "harness.sv")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "axi_if" in content
        assert "apb_if" in content


def test_testcase_generates(cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestcaseGenerator(cfg)
        gen.generate(tmpdir)
        assert os.path.exists(os.path.join(tmpdir, "base_test.sv"))
        assert os.path.exists(os.path.join(tmpdir, "tc.f"))
        with open(os.path.join(tmpdir, "base_test.sv")) as f:
            content = f.read()
        assert "top_env" in content


def test_testcase_tc_f_includes(cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestcaseGenerator(cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "tc.f")) as f:
            content = f.read()
        assert "base_test.sv" in content
