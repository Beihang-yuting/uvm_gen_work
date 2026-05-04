from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.agent import AgentGenerator
from uvm_gen.generators.platform import PlatformGenerator

USAGE = """\
UVM Testbench Generator

Usage:
  gen_tb -b <block> [-a <agents>] [-t advance|port] [-o <dir>]  Generate full platform
  gen_tb -a <agent_name> [-t advance|port] [-o <dir>]           Generate standalone agent
  gen_tb -f <config.yaml>                                        Generate from YAML config
  gen_tb                                                         Interactive mode

Options:
  -b, --block   Block name (omit for standalone agent mode)
  -a, --agent   Agent name(s), comma-separated (e.g. "axi,apb,pcie")
  -t, --type    Platform type: advance (default) or port
  -f, --config  YAML configuration file
  -o, --output  Output directory (default: current directory)
  -h, --help    Show this help message

Examples:
  gen_tb -b top -a "axi,apb"              # Full platform with agents
  gen_tb -b top                            # Full platform without agents
  gen_tb -b top -a "axi,apb" -t port      # Full platform, port mode
  gen_tb -a axi                            # Standalone agent with test env
  gen_tb -f my_project.yaml                # From YAML config
"""

AGENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def error_exit(msg):
    print("Error: %s" % msg, file=sys.stderr)
    sys.exit(1)


def validate_agent_name(name):
    if not AGENT_NAME_RE.match(name):
        error_exit(
            "agent name '%s' is invalid. Use only [a-z0-9_], must start with a letter." % name
        )


def parse_agents_string(agents_str):
    agents = []
    for name in agents_str.split(","):
        name = name.strip()
        if name:
            validate_agent_name(name)
            agents.append(AgentConfig(name=name))
    return agents


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gen_tb",
        description="UVM Testbench Generator",
        usage=USAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-b", "--block", default=None, help="Block name")
    parser.add_argument("-a", "--agent", default=None, help="Agent name(s), comma-separated")
    parser.add_argument(
        "-t", "--type", default="advance", choices=["advance", "port"],
        help="Platform type (default: advance)",
    )
    parser.add_argument("-f", "--config", dest="config_file", default=None, help="YAML config file")
    parser.add_argument("-o", "--output", default=".", help="Output directory")
    return parser


def run_from_yaml(yaml_path):
    if not os.path.exists(yaml_path):
        error_exit("config file '%s' not found." % yaml_path)
    try:
        with open(yaml_path) as f:
            cfg = ProjectConfig.from_yaml(f.read())
    except yaml.YAMLError as e:
        error_exit("failed to parse '%s': %s" % (yaml_path, e))
    except ValueError as e:
        error_exit(str(e))
    gen = PlatformGenerator(cfg)
    try:
        project_dir = gen.generate()
    except FileExistsError as e:
        error_exit(str(e))
    print("Platform generated: %s" % project_dir)


def run_from_args(args):
    if args.config_file:
        run_from_yaml(args.config_file)
        return

    if args.agent is None and args.block is None:
        interactive_mode()
        return

    platform_type = PlatformType(args.type)

    if args.agent is not None:
        agents = parse_agents_string(args.agent)
    else:
        agents = []

    if args.block:
        # Full platform mode (-a is optional)
        cfg = ProjectConfig(
            block_name=args.block,
            platform_type=platform_type,
            agents=agents,
            output_dir=args.output,
        )
        gen = PlatformGenerator(cfg)
        try:
            project_dir = gen.generate()
        except FileExistsError as e:
            error_exit(str(e))
        print("Platform generated: %s" % project_dir)
    else:
        # Standalone agent mode (requires -a)
        if not agents:
            error_exit("-a/--agent is required for standalone agent mode. Use -b for platform mode, or -h for help.")
        if len(agents) > 1:
            error_exit("standalone agent mode supports only one agent. Use -b for platform mode.")
        agent_cfg = agents[0]
        cfg = ProjectConfig(
            block_name=agent_cfg.name,
            platform_type=platform_type,
            agents=[agent_cfg],
        )
        gen = AgentGenerator(cfg)
        gen.generate_agent(agent_cfg, args.output)
        print("Agent generated: %s/%s_agent/" % (args.output, agent_cfg.name))


def interactive_mode():
    print("=== UVM Testbench Generator - Interactive Mode ===")
    print("Choose generation type:")
    print("  1) Full platform")
    print("  2) Standalone agent")
    choice = input("Enter choice [1/2]: ").strip()

    print("\nPlatform type:")
    print("  1) advance")
    print("  2) port")
    ptype_choice = input("Enter choice [1/2]: ").strip()
    platform_type = PlatformType.ADVANCE if ptype_choice == "1" else PlatformType.PORT

    if choice == "1":
        block = input("Block name: ").strip()
        if not block:
            error_exit("block name is required.")
        agents_str = input('Agents (comma-separated, press Enter to skip): ').strip()
        output = input("Output directory [.]: ").strip() or "."
        agents = parse_agents_string(agents_str) if agents_str else []
        cfg = ProjectConfig(
            block_name=block,
            platform_type=platform_type,
            agents=agents,
            output_dir=output,
        )
        gen = PlatformGenerator(cfg)
        try:
            print("\nPlatform generated: %s" % gen.generate())
        except FileExistsError as e:
            error_exit(str(e))
    elif choice == "2":
        name = input("Agent name: ").strip()
        validate_agent_name(name)
        output = input("Output directory [.]: ").strip() or "."
        agent_cfg = AgentConfig(name=name)
        cfg = ProjectConfig(
            block_name=name,
            platform_type=platform_type,
            agents=[agent_cfg],
        )
        AgentGenerator(cfg).generate_agent(agent_cfg, output)
        print("\nAgent generated: %s/%s_agent/" % (output, name))
    else:
        error_exit("invalid choice '%s'. Enter 1 or 2." % choice)


def main():
    parser = build_parser()
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
