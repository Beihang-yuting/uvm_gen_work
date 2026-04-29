import os
import tempfile
import pytest
from uvm_gen.cli import build_parser, run_from_args

@pytest.fixture
def parser():
    return build_parser()

def test_parser_platform_subcommand(parser):
    args = parser.parse_args(["platform", "--type", "self-contained", "--block", "top",
        "--agents", "axi:master,apb:slave", "--author", "ryan", "--project", "bootis"])
    assert args.command == "platform"
    assert args.type == "self-contained"

def test_parser_agent_subcommand(parser):
    args = parser.parse_args(["agent", "--type", "standard", "--name", "axi",
        "--mode", "master", "--author", "ryan", "--project", "bootis"])
    assert args.command == "agent"
    assert args.name == "axi"

def test_parser_yaml_mode(parser):
    args = parser.parse_args(["-f", "config.yaml"])
    assert args.config_file == "config.yaml"

def test_run_platform_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = build_parser()
        args = parser.parse_args(["platform", "--type", "self-contained", "--block", "top",
            "--agents", "axi:master", "--author", "ryan", "--project", "testprj", "--output", tmpdir])
        run_from_args(args)
        assert os.path.isdir(os.path.join(tmpdir, "testprj_top"))
        assert os.path.exists(os.path.join(tmpdir, "testprj_top", "env", "top_env.sv"))

def test_run_agent_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = build_parser()
        args = parser.parse_args(["agent", "--type", "self-contained", "--name", "spi",
            "--mode", "slave", "--author", "ryan", "--project", "testprj", "--output", tmpdir])
        run_from_args(args)
        assert os.path.exists(os.path.join(tmpdir, "spi_agent", "src", "spi_agent.sv"))

def test_run_yaml_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "config.yaml")
        with open(yaml_path, "w") as f:
            f.write(f"project: yamlprj\nauthor: test\nblock: sub\ntype: standard\noutput_dir: {tmpdir}\nagents:\n  - name: uart\n    mode: master\n")
        parser = build_parser()
        args = parser.parse_args(["-f", yaml_path])
        run_from_args(args)
        assert os.path.isdir(os.path.join(tmpdir, "yamlprj_sub"))
