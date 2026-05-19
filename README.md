# UVM Testbench Generator

Generate complete UVM (Universal Verification Methodology) testbench skeletons
in SystemVerilog from Jinja2 templates. Supports two platform styles
(`advance`, `port`) and arbitrary numbers of agents.

---

## Layout

```
uvm_gen_work/
├── setup                  # install/uninstall helper (run with ./setup ...)
├── README.md
├── .gitignore
└── uvm_gen/               # Python package
    ├── __init__.py
    ├── gen_tb             # Launcher script (symlinked into ~/.local/bin)
    ├── cli.py             # argparse + interactive mode
    ├── config.py          # PlatformType / AgentConfig / ProjectConfig
    ├── generators/        # Generator classes (one per output area)
    │   ├── base.py
    │   ├── platform.py
    │   ├── agent.py
    │   ├── env.py
    │   ├── common.py
    │   ├── harness.py
    │   └── testcase.py
    └── templates/         # Jinja2 templates
        ├── advance/ {agent,env,test_env}/
        ├── port/    {agent,env,test_env}/
        ├── common/, cfg/, harness/, tc/
        └── _header.sv.j2
```

---

## Requirements

- Python **3.6+**
- [PyYAML](https://pypi.org/project/PyYAML/)
- [Jinja2](https://pypi.org/project/Jinja2/)
- On Python 3.6 only: the [`dataclasses`](https://pypi.org/project/dataclasses/) backport

The `setup` script verifies these and prints the install command — it never
installs packages itself.

---

## Install

```bash
git clone https://github.com/Beihang-yuting/uvm_gen_work.git
cd uvm_gen_work
./setup install
```

`./setup install` will:

1. Verify Python >= 3.6.
2. Check that PyYAML and Jinja2 are importable. If missing, print the
   `pip install ...` command and stop (no automatic install).
3. Make `uvm_gen/gen_tb` executable.
4. Create the symlink `~/.local/bin/gen_tb` -> `<repo>/uvm_gen/gen_tb`.
5. Warn if `~/.local/bin` is not on your `PATH` and print the `export`
   line to add to your shell rc.

After install, run `gen_tb` from anywhere.

### Uninstall

```bash
./setup uninstall
```

Removes only the `~/.local/bin/gen_tb` symlink. Repo files are untouched.

### Check environment only

```bash
./setup check
```

Reports Python version + dependency status without modifying anything.

---

## Usage

```bash
gen_tb -b <block> [-a <agents>] [-t advance|port] [-o <dir>]   # full platform
gen_tb -a <agent_name> [-t advance|port] [-o <dir>]            # standalone agent
gen_tb -f <config.yaml>                                         # from YAML
gen_tb                                                          # interactive
```

### Options

| Flag | Description |
|---|---|
| `-b, --block`   | Block name (required for platform mode) |
| `-a, --agent`   | Agent name(s), comma-separated (e.g. `"axi,apb,pcie"`) |
| `-t, --type`    | Platform type: `advance` (default, self-contained, FIFO in agent) or `port` (standard UVM, FIFO in env) |
| `-f, --config`  | YAML configuration file |
| `-o, --output`  | Output directory (default: current directory) |
| `--aip-core`    | Enable aip_core integration (TCL bridge, aip_log, aip_clk) |
| `-h, --help`    | Show help |

### Examples

```bash
gen_tb -b top -a "axi,apb"               # full platform with 2 agents
gen_tb -b top                             # full platform, no agents
gen_tb -b top -a "axi,apb" -t port        # port platform
gen_tb -a axi                             # standalone agent with test_env
gen_tb -b top -a axi --aip-core           # with aip_core hooks/templates
gen_tb -f my_project.yaml                 # from YAML
```

### YAML config

```yaml
block: top
author: alice                # optional, defaults to $USER
type: advance                # advance | port
aip_core: false
agents:
  - axi
  - apb
output_dir: ./out            # optional
```

---

## Output Tree

For `gen_tb -b mytop -a "axi,apb"`:

```
mytop/
├── common/                # common_lib_pkg.sv + report_server + scbs
├── env/                   # env.sv, env_cfg.sv, rm.sv, checker.sv, vsqr.sv, sys_if.sv
│   ├── ral/               # placeholder for register model
│   └── agents/
│       ├── axi_agent/{src/*.sv, axi_agent.f, test_env/...}
│       └── apb_agent/{...}
├── th/                    # harness.sv
├── tc/                    # tc_base.sv, tc.f (+ tc_tcl.sv when --aip-core)
├── cfg/                   # dut.f, env.f, tb.f, initreg.cfg, xprop.cfg, coverage.cfg, wave.tcl
└── doc/                   # placeholder
```

---

## Platform Types

| Type      | Description |
|-----------|-------------|
| `advance` | Self-contained agents (FIFO inside each agent), faster bring-up. |
| `port`    | Standard UVM topology (FIFO inside env), aligns with most UVM training material. |

Same set of generated files; only template internals differ. Selected via
`-t advance` (default) or `-t port`.

---

## aip_core Integration

Use `--aip-core` (CLI) or `aip_core: true` (YAML) to add:

- `common/aip_activity_subscriber.sv` — activity subscriber stub
- `tc/tc_tcl.sv` + `tc/tcl/tc_tcl_demo.tcl` — TCL bridge harness
- Wiring inside generated cfg/env headers for `aip_log` / `aip_clk`

---

## Python Version Compatibility

| Python | Status | Notes |
|--------|--------|-------|
| 3.6    | Supported | Requires `dataclasses` backport (`pip install dataclasses`) |
| 3.7+   | Supported | `dataclasses` is stdlib |
| 3.8 - 3.13 | Tested | |

Verified via static AST parse with `feature_version=(3, N)` for each.
