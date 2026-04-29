from __future__ import annotations
import argparse
import sys
from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.agent import AgentGenerator
from uvm_gen.generators.platform import PlatformGenerator

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uvm_gen", description="UVM Testbench Generator")
    parser.add_argument("-f", "--config-file", dest="config_file", help="YAML config file")
    subparsers = parser.add_subparsers(dest="command")

    p_platform = subparsers.add_parser("platform", help="Generate full UVM platform")
    p_platform.add_argument("--type", required=True, choices=["self-contained", "standard"])
    p_platform.add_argument("--block", required=True)
    p_platform.add_argument("--agents", required=True, help='e.g. "axi,apb,pcie"')
    p_platform.add_argument("--author", required=True)
    p_platform.add_argument("--project", required=True)
    p_platform.add_argument("--output", default=".")

    p_agent = subparsers.add_parser("agent", help="Generate standalone agent")
    p_agent.add_argument("--type", required=True, choices=["self-contained", "standard"])
    p_agent.add_argument("--name", required=True)
    p_agent.add_argument("--author", required=True)
    p_agent.add_argument("--project", required=True)
    p_agent.add_argument("--output", default=".")
    return parser

def parse_agents_string(agents_str: str) -> list[AgentConfig]:
    agents = []
    for name in agents_str.split(","):
        name = name.strip()
        if name:
            agents.append(AgentConfig(name=name))
    return agents

def run_from_args(args: argparse.Namespace) -> None:
    if hasattr(args, "config_file") and args.config_file:
        with open(args.config_file) as f:
            cfg = ProjectConfig.from_yaml(f.read())
        gen = PlatformGenerator(cfg)
        project_dir = gen.generate()
        print(f"Platform generated: {project_dir}")
        return

    if args.command == "platform":
        agents = parse_agents_string(args.agents)
        cfg = ProjectConfig(project_name=args.project, author=args.author, block_name=args.block,
            platform_type=PlatformType(args.type), agents=agents, output_dir=args.output)
        gen = PlatformGenerator(cfg)
        project_dir = gen.generate()
        print(f"Platform generated: {project_dir}")
    elif args.command == "agent":
        agent_cfg = AgentConfig(name=args.name)
        cfg = ProjectConfig(project_name=args.project, author=args.author, block_name="",
            platform_type=PlatformType(args.type), agents=[agent_cfg])
        gen = AgentGenerator(cfg)
        gen.generate_agent(agent_cfg, args.output)
        print(f"Agent generated: {args.output}/{args.name}_agent/")
    elif args.command is None:
        interactive_mode()
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)

def interactive_mode() -> None:
    print("=== UVM Gen Interactive Mode ===")
    print("Choose generation type:")
    print("  1) Full platform")
    print("  2) Standalone agent")
    choice = input("Enter choice [1/2]: ").strip()
    print("\nPlatform type:")
    print("  1) self-contained")
    print("  2) standard")
    ptype_choice = input("Enter choice [1/2]: ").strip()
    platform_type = PlatformType.SELF_CONTAINED if ptype_choice == "1" else PlatformType.STANDARD
    project = input("Project name: ").strip()
    author = input("Author: ").strip()
    if choice == "1":
        block = input("Block name: ").strip()
        agents_str = input('Agents (e.g. "axi,apb,pcie"): ').strip()
        output = input("Output directory [.]: ").strip() or "."
        agents = parse_agents_string(agents_str)
        cfg = ProjectConfig(project_name=project, author=author, block_name=block,
            platform_type=platform_type, agents=agents, output_dir=output)
        gen = PlatformGenerator(cfg)
        print(f"\nPlatform generated: {gen.generate()}")
    elif choice == "2":
        name = input("Agent name: ").strip()
        output = input("Output directory [.]: ").strip() or "."
        agent_cfg = AgentConfig(name=name)
        cfg = ProjectConfig(project_name=project, author=author, block_name="",
            platform_type=platform_type, agents=[agent_cfg])
        AgentGenerator(cfg).generate_agent(agent_cfg, output)
        print(f"\nAgent generated: {output}/{name}_agent/")

def main():
    parser = build_parser()
    args = parser.parse_args()
    run_from_args(args)

if __name__ == "__main__":
    main()
