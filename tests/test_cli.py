import os
import tempfile
import pytest
from uvm_gen.cli import build_parser, run_from_args, parse_agents_string, validate_agent_name


def test_parser_platform_mode():
    parser = build_parser()
    args = parser.parse_args(["-b", "top", "-a", "axi,apb"])
    assert args.block == "top"
    assert args.agent == "axi,apb"
    assert args.type == "advance"


def test_parser_agent_mode():
    parser = build_parser()
    args = parser.parse_args(["-a", "axi"])
    assert args.agent == "axi"
    assert args.block is None


def test_parser_type_port():
    parser = build_parser()
    args = parser.parse_args(["-b", "top", "-a", "axi", "-t", "port"])
    assert args.type == "port"


def test_parser_yaml_mode():
    parser = build_parser()
    args = parser.parse_args(["-f", "config.yaml"])
    assert args.config_file == "config.yaml"


def test_parse_agents_string():
    agents = parse_agents_string("axi,apb,pcie")
    assert len(agents) == 3
    assert agents[0].name == "axi"


def test_validate_agent_name_valid():
    validate_agent_name("axi")
    validate_agent_name("axi_master")
    validate_agent_name("a0")


def test_validate_agent_name_invalid():
    with pytest.raises(SystemExit):
        validate_agent_name("AXI")
    with pytest.raises(SystemExit):
        validate_agent_name("axi-master")
    with pytest.raises(SystemExit):
        validate_agent_name("0axi")


def test_run_platform_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = build_parser()
        args = parser.parse_args(["-b", "top", "-a", "axi", "-o", tmpdir])
        run_from_args(args)
        assert os.path.isdir(os.path.join(tmpdir, "top"))
        assert os.path.exists(os.path.join(tmpdir, "top", "env", "top_env.sv"))


def test_run_agent_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = build_parser()
        args = parser.parse_args(["-a", "spi", "-o", tmpdir])
        run_from_args(args)
        assert os.path.exists(os.path.join(tmpdir, "spi_agent", "src", "spi_agent.sv"))


def test_run_yaml_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "config.yaml")
        with open(yaml_path, "w") as f:
            f.write(f"block: sub\ntype: port\noutput_dir: {tmpdir}\nagents:\n  - name: uart\n")
        parser = build_parser()
        args = parser.parse_args(["-f", yaml_path])
        run_from_args(args)
        assert os.path.isdir(os.path.join(tmpdir, "sub"))


def test_run_platform_no_agents():
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = build_parser()
        args = parser.parse_args(["-b", "top", "-o", tmpdir])
        run_from_args(args)
        assert os.path.isdir(os.path.join(tmpdir, "top"))
        assert os.path.exists(os.path.join(tmpdir, "top", "env", "top_env.sv"))


def test_run_yaml_missing_file():
    parser = build_parser()
    args = parser.parse_args(["-f", "/nonexistent.yaml"])
    with pytest.raises(SystemExit):
        run_from_args(args)


def test_run_invalid_type():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-b", "top", "-a", "axi", "-t", "xxx"])


def test_aip_core_flag():
    parser = build_parser()
    args = parser.parse_args(["-b", "top", "-a", "axi", "--aip-core"])
    assert args.aip_core == True


def test_aip_core_flag_default():
    parser = build_parser()
    args = parser.parse_args(["-b", "top", "-a", "axi"])
    assert args.aip_core == False
