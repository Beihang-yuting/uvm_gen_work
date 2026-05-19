import argparse
import os
import re
import sys

import yaml

from .config import AgentConfig, PlatformType, ProjectConfig
from .generators.agent import AgentGenerator
from .generators.platform import PlatformGenerator

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

Install/uninstall the gen_tb shortcut via the setup script at the repo root:
  ./setup install     Create ~/.local/bin/gen_tb symlink
  ./setup uninstall   Remove the symlink

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

def _c256(code, text):
    if _use_color:
        return "\033[38;5;%dm%s\033[0m" % (code, text)
    return text

def _bold(text):     return _c("1", text)
def _green(text):    return _c("32", text)
def _cyan(text):     return _c("36", text)
def _yellow(text):   return _c("33", text)
def _red(text):      return _c("31", text)
def _dim(text):      return _c("2", text)
def _magenta(text):  return _c("35", text)

# Cyan -> magenta gradient for banner / accents
_GRADIENT = [51, 45, 39, 33, 99, 135, 171, 207, 201, 165]

def _grad(text, hue_idx=0):
    return _c256(_GRADIENT[hue_idx % len(_GRADIENT)], text)


def _term_width(default=78):
    try:
        return max(40, min(120, os.get_terminal_size().columns))
    except (OSError, ValueError):
        return default


def _hr(char="─", hue=4):
    return _c256(_GRADIENT[hue], char * _term_width())


def _step_header(num, title):
    w = _term_width()
    label = " STEP %d " % num
    bar = "▰" * 3
    head = "%s%s  %s" % (
        _c256(_GRADIENT[num % len(_GRADIENT)], bar),
        _bold(_c256(_GRADIENT[(num + 2) % len(_GRADIENT)], label)),
        _bold(title),
    )
    line_len = max(4, w - len(label) - len(title) - 8)
    print("")
    print("  %s %s" % (head, _c256(_GRADIENT[(num + 4) % len(_GRADIENT)], "─" * line_len)))
    print("")


def _menu_item(num, label, hint="", selected_hint=False):
    bullet = "●" if selected_hint else "○"
    marker = _c256(_GRADIENT[num % len(_GRADIENT)], bullet)
    idx = _bold(_c256(_GRADIENT[(num + 3) % len(_GRADIENT)], "[%d]" % num))
    if hint:
        return "   %s %s %s  %s" % (marker, idx, _bold(label), _dim(hint))
    return "   %s %s %s" % (marker, idx, _bold(label))


def _box(title, rows):
    """Draw a rounded box around `rows` (list of plain or ANSI strings)."""
    title_w = len(_strip_ansi(title))
    body_w = max((len(_strip_ansi(r)) for r in rows), default=0)
    inner = max(title_w + 4, body_w + 2)   # space inside the borders
    accent = lambda s: _c256(_GRADIENT[3], s)

    # Top:    "╭─ <title> <fill>╮"   total inner chars between ╭ ╮ = inner
    used = 2 + title_w + 1            # "─ " + title + " "
    fill = max(0, inner - used)
    top = accent("╭") + accent("─ ") + title + accent(" " + "─" * fill + "╮")

    print("  " + top)
    for r in rows:
        pad = inner - len(_strip_ansi(r)) - 2
        print("  %s %s%s %s" % (accent("│"), r, " " * max(0, pad), accent("│")))
    print("  " + accent("╰" + "─" * inner + "╯"))


_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
def _strip_ansi(s):
    return _ANSI_RE.sub("", s)


def _spinner(msg, fn):
    """Run fn() while showing a spinner. Returns fn()'s result. Re-raises on error."""
    import threading
    import time
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    done = {"flag": False, "ok": False, "result": None, "err": None}

    def _worker():
        try:
            done["result"] = fn()
            done["ok"] = True
        except BaseException as e:
            done["err"] = e
        finally:
            done["flag"] = True

    t = threading.Thread(target=_worker)
    t.start()
    i = 0
    try:
        while not done["flag"]:
            sys.stdout.write("\r  %s  %s" % (
                _c256(_GRADIENT[i % len(_GRADIENT)], frames[i % len(frames)]),
                _dim(msg),
            ))
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1
    finally:
        t.join()
        sys.stdout.write("\r" + " " * (_term_width() - 1) + "\r")
        sys.stdout.flush()
    if done["err"] is not None:
        raise done["err"]
    return done["result"]


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
    parser.add_argument("--aip-core", action="store_true", default=False,
                        help="Enable aip_core integration (TCL bridge, aip_log, aip_clk)")
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
            aip_core=args.aip_core,
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
            aip_core=args.aip_core,
        )
        gen = AgentGenerator(cfg)
        gen.generate_agent(agent_cfg, args.output)
        print("\n  %s %s/%s_agent/\n" % (_green("Agent generated:"), args.output, agent_cfg.name))


def _prompt(label, hint=""):
    arrow = _c256(_GRADIENT[5], "▸")
    if hint:
        return input("  %s %s %s " % (arrow, _cyan(label), _dim(hint))).strip()
    return input("  %s %s " % (arrow, _cyan(label))).strip()


_BANNER_ART = [
    "  ██╗   ██╗██╗   ██╗███╗   ███╗      ██████╗ ███████╗███╗   ██╗",
    "  ██║   ██║██║   ██║████╗ ████║     ██╔════╝ ██╔════╝████╗  ██║",
    "  ██║   ██║██║   ██║██╔████╔██║     ██║  ███╗█████╗  ██╔██╗ ██║",
    "  ██║   ██║╚██╗ ██╔╝██║╚██╔╝██║     ██║   ██║██╔══╝  ██║╚██╗██║",
    "  ╚██████╔╝ ╚████╔╝ ██║ ╚═╝ ██║     ╚██████╔╝███████╗██║ ╚████║",
    "   ╚═════╝   ╚═══╝  ╚═╝     ╚═╝      ╚═════╝ ╚══════╝╚═╝  ╚═══╝",
]


def _print_banner():
    print("")
    print(_hr("━", hue=2))
    for i, line in enumerate(_BANNER_ART):
        print(_c256(_GRADIENT[i % len(_GRADIENT)], line))
    tag = "  %s  %s  %s" % (
        _bold(_c256(_GRADIENT[7], "UVM Testbench Generator")),
        _dim("•"),
        _dim("advance / port  •  agents  •  aip_core"),
    )
    print("")
    print(tag)
    print(_hr("━", hue=2))


def _print_summary(cfg, agents):
    agent_names = ", ".join(a.name for a in agents) if agents else "(none)"
    rows = [
        "%s  %s" % (_dim("Block   :"), _bold(cfg.block_name)),
        "%s  %s" % (_dim("Type    :"), _magenta(cfg.platform_type.value)),
        "%s  %s" % (_dim("Agents  :"), _yellow(agent_names)),
        "%s  %s" % (_dim("Output  :"), cfg.output_dir or "."),
        "%s  %s" % (_dim("aip_core:"), _green("enabled") if cfg.aip_core else _dim("disabled")),
    ]
    print("")
    _box(_bold(_c256(_GRADIENT[6], "Configuration")), rows)
    print("")


def interactive_mode():
    _print_banner()

    # Step 1: Generation type
    _step_header(1, "Generation Type")
    print(_menu_item(1, "Full platform",     "block + agents + env + tc + cfg"))
    print(_menu_item(2, "Standalone agent",  "single agent + minimal test_env"))
    print("")
    choice = _prompt("Select [1/2]:")

    # Step 2: Platform type
    _step_header(2, "Platform Type")
    print(_menu_item(1, "advance", "self-contained, FIFO in agent  (recommended)"))
    print(_menu_item(2, "port",    "standard UVM, FIFO in env"))
    print("")
    ptype_choice = _prompt("Select [1/2]:", "(default: 1)")
    if not ptype_choice or ptype_choice == "1":
        platform_type = PlatformType.ADVANCE
    else:
        platform_type = PlatformType.PORT

    # Step 3: aip_core toggle
    _step_header(3, "aip_core Integration")
    print("    %s" % _dim("Adds TCL bridge, aip_log, aip_clk, activity subscriber"))
    print("")
    aip_choice = _prompt("Enable aip_core? [y/N]:", "(default: N)")
    aip_core = aip_choice.lower() in ("y", "yes")

    if choice == "1":
        # Step 4: Platform details
        _step_header(4, "Platform Details")
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
            aip_core=aip_core,
        )

        _print_summary(cfg, agents)

        confirm = _prompt("Confirm? [Y/n]:")
        if confirm.lower() in ("n", "no"):
            print("\n  %s\n" % _yellow("✗ Cancelled."))
            return

        gen = PlatformGenerator(cfg)
        try:
            project_dir = _spinner("Generating platform...", gen.generate)
        except FileExistsError as e:
            error_exit(str(e))
        _success_card("Platform Generated", [
            ("Block",   cfg.block_name),
            ("Type",    cfg.platform_type.value),
            ("Agents",  ", ".join(a.name for a in agents) or "(none)"),
            ("Path",    project_dir),
            ("aip_core", "enabled" if aip_core else "disabled"),
        ])

    elif choice == "2":
        # Step 4: Agent details
        _step_header(4, "Agent Details")
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
            aip_core=aip_core,
        )

        _box("Configuration", [
            "%s  %s" % (_dim("Agent  :"), _bold(name)),
            "%s  %s" % (_dim("Type   :"), _magenta(platform_type.value)),
            "%s  %s" % (_dim("Output :"), output),
            "%s  %s" % (_dim("aip_core:"), _green("enabled") if aip_core else _dim("disabled")),
        ])
        print("")

        confirm = _prompt("Confirm? [Y/n]:")
        if confirm.lower() in ("n", "no"):
            print("\n  %s\n" % _yellow("✗ Cancelled."))
            return

        def _gen():
            AgentGenerator(cfg).generate_agent(agent_cfg, output)
            return "%s/%s_agent/" % (output, name)
        path = _spinner("Generating agent...", _gen)
        _success_card("Agent Generated", [
            ("Agent",   name),
            ("Type",    platform_type.value),
            ("Path",    path),
            ("aip_core", "enabled" if aip_core else "disabled"),
        ])
    else:
        error_exit("invalid choice '%s'. Enter 1 or 2." % choice)


def _success_card(title, rows):
    icon = _c256(_GRADIENT[1], "✓")
    label = "%s  %s" % (icon, _bold(_c256(_GRADIENT[7], title)))
    body = []
    keymax = max(len(k) for k, _ in rows)
    for k, v in rows:
        body.append("%s  %s" % (_dim(("%-" + str(keymax) + "s :") % k), _bold(v)))
    print("")
    _box(label, body)
    print("")


def main():
    parser = build_parser()
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
