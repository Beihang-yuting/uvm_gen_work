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

## Common Scoreboard v2

Each generated checker owns one explicitly typed
`common_uvm_scb#(<agent>_trans)` instance per agent. Generated transactions
provide virtual `get_scb_stream_id()` and `get_scb_kind()` methods, which
default to `'1` and `-1`; override them to route protocol traffic into the
appropriate stream and comparison kind.

The scoreboard supports ordered exact, ordered with DUT loss, and unordered
comparison. Its core `push_expected()` and `push_actual()` input APIs are
functions, and transactions retained in its queues are cloned by default.
With `m_clone_en=0`, the scoreboard does not copy the transaction or take ownership.
It retains the original producer-owned transaction handle, so later producer
mutation affects comparison.
Callers must keep that handle stable while it is pending in the scoreboard.

The final report always prints aggregate totals and, by default, up to the top 10
problem streams. Normal streams are omitted. `+SCB_REPORT_LIMIT=0` prints the
summary only, `+SCB_REPORT_LIMIT=-1` prints every problem stream, and a finite
non-negative value prints up to that many top rows. The report always states the
number of omitted problem streams. Invalid values produce a warning and leave
the configured or default limit in effect. Reporting is console summary/table
output; it does not create a full CSV or text dump. Runtime mismatch detail has
its own `m_err_limit`, followed by a suppression summary when messages exceed
that limit.

`reset_state(0)` clears live stream queues and state while retaining cumulative
diagnostics and counters; `reset_state(1)` also clears counter and diagnostic
history. Generated reset hooks invoke the scoreboard reset as part of the
platform reset lifecycle. The previous implementation remains available as
`common_uvm_scb_legacy`.

With `--aip-core`, exactly four scoreboard commands provide non-destructive
inspection and report-limit control:

```tcl
scb_list
scb_status name=uvm_test_top.m_env.m_scb.m_axi_scb
scb_report name=uvm_test_top.m_env.m_scb.m_axi_scb limit=0
scb_set_limit name=uvm_test_top.m_env.m_scb.m_axi_scb limit=-1
```

There is no scoreboard reset or clear command in the AIP adapter.

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
