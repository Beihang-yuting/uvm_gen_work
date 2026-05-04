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

# --- ANSI colors ---
_use_color = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _c(code, text):
    if _use_color:
        return "\033[%sm%s\033[0m" % (code, text)
    return text

def _bold(text):     return _c("1", text)
def _green(text):    return _c("32", text)
def _cyan(text):     return _c("36", text)
def _yellow(text):   return _c("33", text)
def _red(text):      return _c("31", text)
def _dim(text):      return _c("2", text)
def _magenta(text):  return _c("35", text)


def error_exit(msg):
    print("%s %s" % (_red("Error:"), msg), file=sys.stderr)
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
    print("\n  %s %s\n" % (_green("Platform generated:"), _bold(project_dir)))


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
        print("\n  %s %s\n" % (_green("Platform generated:"), _bold(project_dir)))
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
        print("\n  %s %s/%s_agent/\n" % (_green("Agent generated:"), args.output, agent_cfg.name))


def _prompt(label, hint=""):
    if hint:
        return input("  %s %s " % (_cyan(label), _dim(hint))).strip()
    return input("  %s " % _cyan(label)).strip()


def _print_banner():
    banner = r"""
  %s
  %s

  %s  Generate UVM testbench platforms and agents
  %s  Type: advance (self-contained) | port (standard UVM)
""" % (
        _bold(_cyan("  UVM Testbench Generator")),
        _dim("  " + "=" * 36),
        _dim("  "),
        _dim("  "),
    )
    print(banner)


def _print_summary(cfg, agents):
    print("")
    print("  %s" % _bold("Configuration Summary"))
    print("  %s" % ("-" * 30))
    print("  %-16s %s" % (_dim("Block:"), _bold(cfg.block_name)))
    print("  %-16s %s" % (_dim("Type:"), _magenta(cfg.platform_type.value)))
    if agents:
        agent_names = ", ".join(a.name for a in agents)
        print("  %-16s %s" % (_dim("Agents:"), _yellow(agent_names)))
    else:
        print("  %-16s %s" % (_dim("Agents:"), _dim("(none)")))
    print("  %-16s %s" % (_dim("Output:"), cfg.output_dir or "."))
    print("")


def interactive_mode():
    _print_banner()

    # Step 1: Generation type
    print("  %s" % _bold("Step 1: Generation Type"))
    print("    %s  Full platform" % _green("1)"))
    print("    %s  Standalone agent" % _green("2)"))
    print("")
    choice = _prompt("Select [1/2]:")

    # Step 2: Platform type
    print("")
    print("  %s" % _bold("Step 2: Platform Type"))
    print("    %s  advance %s" % (_green("1)"), _dim("(self-contained, FIFO in agent)")))
    print("    %s  port    %s" % (_green("2)"), _dim("(standard UVM, FIFO in env)")))
    print("")
    ptype_choice = _prompt("Select [1/2]:", "(default: 1)")
    if not ptype_choice or ptype_choice == "1":
        platform_type = PlatformType.ADVANCE
    else:
        platform_type = PlatformType.PORT

    if choice == "1":
        # Step 3: Platform details
        print("")
        print("  %s" % _bold("Step 3: Platform Details"))
        print("")
        block = _prompt("Block name:")
        if not block:
            error_exit("block name is required.")
        agents_str = _prompt("Agents:", "(comma-separated, Enter to skip)")
        output = _prompt("Output directory:", "(default: .)") or "."
        agents = parse_agents_string(agents_str) if agents_str else []
        cfg = ProjectConfig(
            block_name=block,
            platform_type=platform_type,
            agents=agents,
            output_dir=output,
        )

        _print_summary(cfg, agents)

        confirm = _prompt("Confirm? [Y/n]:")
        if confirm.lower() in ("n", "no"):
            print("\n  %s\n" % _yellow("Cancelled."))
            return

        gen = PlatformGenerator(cfg)
        try:
            project_dir = gen.generate()
        except FileExistsError as e:
            error_exit(str(e))
        print("\n  %s %s\n" % (_green("Platform generated:"), _bold(project_dir)))

    elif choice == "2":
        # Step 3: Agent details
        print("")
        print("  %s" % _bold("Step 3: Agent Details"))
        print("")
        name = _prompt("Agent name:")
        if not name:
            error_exit("agent name is required.")
        validate_agent_name(name)
        output = _prompt("Output directory:", "(default: .)") or "."
        agent_cfg = AgentConfig(name=name)
        cfg = ProjectConfig(
            block_name=name,
            platform_type=platform_type,
            agents=[agent_cfg],
        )

        print("")
        print("  %s" % _bold("Configuration Summary"))
        print("  %s" % ("-" * 30))
        print("  %-16s %s" % (_dim("Agent:"), _bold(name)))
        print("  %-16s %s" % (_dim("Type:"), _magenta(platform_type.value)))
        print("  %-16s %s" % (_dim("Output:"), output))
        print("")

        confirm = _prompt("Confirm? [Y/n]:")
        if confirm.lower() in ("n", "no"):
            print("\n  %s\n" % _yellow("Cancelled."))
            return

        AgentGenerator(cfg).generate_agent(agent_cfg, output)
        print("\n  %s %s/%s_agent/\n" % (_green("Agent generated:"), output, name))
    else:
        error_exit("invalid choice '%s'. Enter 1 or 2." % choice)


def main():
    parser = build_parser()
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
