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
| `-t, --type`    | Platform type: `advance` (default, task-only routing at env level) or `port` (environment-owned TLM/FIFO routing) |
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
├── common/                # scoreboard, macros, assertions, and package
├── env/                   # env.sv, env_cfg.sv, rm.sv, checker.sv, vsqr.sv, sys_if.sv
│   ├── ral/               # placeholder for register model
│   └── agents/
│       ├── axi_agent/{src/*.sv, axi_agent.f, test_env/...}
│       └── apb_agent/{...}
├── th/
│   ├── harness.sv
│   └── bind/
│       ├── bind_example.sv
│       └── common_sva.svh
├── tc/                    # tc_base.sv, tc.f (+ tc_tcl.sv when --aip-core)
├── cfg/                   # dut.f, env.f, tb.f, initreg.cfg, xprop.cfg, coverage.cfg, wave.tcl
└── doc/                   # placeholder
```

---

## Platform Types

Both templates generate the same major directories and support exactly three
agent modes: `AGENT_MASTER`, `AGENT_SLAVE`, and `AGENT_ONLY_MONITOR`. There are
no separate no-monitor variants; an active master or slave always includes its
monitor.

### Advance task-only routing

Advance keeps one monitor FIFO inside each agent. The environment does not add
transaction analysis connections or automatically connect the agent, reference
model, and checker. User code explicitly consumes the single agent stream and
calls the typed task APIs. The example belongs inside a task of a
`tc_base`-derived test, or another UVM component that owns or otherwise has
access to the `m_env` handle:

```systemverilog
axi_trans observed;
axi_trans expected_q[$];

m_env.m_axi_agt.get_mon_item(observed);
m_env.m_rm.predict_axi(observed, expected_q);
m_env.m_scb.send_axi_actual(observed);
foreach (expected_q[i])
    m_env.m_scb.send_axi_expected(expected_q[i]);
```

Use `try_get_mon_item()` when polling is preferable to the blocking
`get_mon_item()` call. The agent-local FIFO has one external consumer; do not
start competing consumers for the same monitor stream.

### PORT TLM/FIFO routing

PORT keeps conventional environment-owned TLM/FIFO wiring. The environment
connects monitor output to the reference model and checker, connects predicted
output to the checker, and owns reset-time worker stop, FIFO flush, scoreboard
reset, and restart. No task-only routing loop is needed for this template.

Select the template with `-t advance` (default) or `-t port`.

## Transactions and comparison

Generated transactions register with `uvm_object_utils` and explicitly provide
`do_copy`, `do_compare`, `convert2string`, and `do_print`. Add every protocol
field to those methods. The generated typed comparison is deliberately
fail-safe: it returns a mismatch with `comparison not implemented` until the
user implements protocol-field comparison, so an empty transaction cannot
silently pass.

The default scoreboard has one stream in `SCB_UNORDERED` mode. It does not
invent an ID or tag. `get_scb_stream_id()` initially routes every transaction
to the same stream and `get_scb_kind()` returns the default comparison kind;
override them only when the protocol itself provides meaningful routing or
comparison semantics.

---

## Common Scoreboard v2

Each generated checker owns one explicitly typed
`common_uvm_scb#(<agent>_trans)` instance per agent. Generated transactions
provide virtual `get_scb_stream_id()` and `get_scb_kind()` methods, which
default to `'1` and `-1`.

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
number of omitted problem streams; the full unmatched list is off by default.
Invalid values produce a warning and leave
the configured or default limit in effect. Reporting is console summary/table
output; it does not create a full CSV or text dump. Runtime mismatch detail has
its own `m_err_limit`, followed by a suppression summary when messages exceed
that limit.

`reset_state(0)` clears live stream queues and state while retaining cumulative
diagnostics and counters; `reset_state(1)` also clears counter and diagnostic
history. Generated PORT reset hooks invoke the scoreboard reset as part of the
environment-owned reset lifecycle.

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

## Interface and harness helpers

Use the connection macro once per protocol signal:

```systemverilog
`UVG_IF_CONNECT(ROLE, FLOW, RTL_SIG, VIF_SIG)
```

The argument order is always RTL before VIF. `ROLE` is `MASTER`, `SLAVE`, or
`MONITOR`; `FLOW` is `M2S` or `S2M` and describes the protocol direction.
Master drives M2S and samples S2M, slave samples M2S and drives S2M, while a
monitor samples both. Each expansion includes a width check. The common package
also provides `UVG_VIF_SET`, `UVG_VIF_GET`, `UVG_CLK`, `UVG_RSTN`, and
`UVG_STATIC_ASSERT`; `UVG_SVA_NO_X` and `UVG_SVA_HOLD` are available from the
generated bind helper.

`th/harness.sv` is the final active source in `cfg/env.f`. The optional
`th/bind/bind_example.sv` line follows it but is commented out, so bind checks
are disabled by default. Uncomment that line and define or edit the examples in
`th/bind/bind_example.sv` when the DUT hierarchy is known.

## aip_core Integration

Use `--aip-core` (CLI) or `aip_core: true` (YAML). `AIP_HOME` is the parent
installation directory and `aip_core` is its child. The sole supported layout
is `$AIP_HOME/aip_core`; generated `cfg/tb.f` uses exactly:

```text
+incdir+$AIP_HOME/aip_core
$AIP_HOME/aip_core/aip_core_pkg.sv
```

The generated TCL demo loads:

```tcl
source $env(AIP_HOME)/aip_core/aip_cmd.tcl
```

Generated base-sequence helpers call `aip_activity::tick()` only after real
completion boundaries. `send_trans_with_rsp()` ticks after request completion
and again after response completion. If monitor-observed bus or C-driven
traffic must extend the AIP idle window, enable the commented monitor tick once
per completed transaction or accepted beat, never once per clock. The AIP
`end_test timeout` remains the safeguard for a source that never becomes idle.

## Optional VCS Makefile

`Makefile.uvm_template` can be copied to a generated project root. Its compile
path uses one uppercase `-F cfg/tb.f`, allowing the nested filelists to resolve
relative to their containing directories. Wave dumping defaults to
`WAVE=none`; FSDB is opt-in with `WAVE=fsdb` and performs a `VERDI_HOME`/PLI
preflight before compilation.

---

## Python Version Compatibility

| Python | Status | Notes |
|--------|--------|-------|
| 3.6    | Supported | Requires `dataclasses` backport (`pip install dataclasses`) |
| 3.7+   | Supported | `dataclasses` is stdlib |
| 3.8 - 3.13 | Tested | |

Verified via static AST parse with `feature_version=(3, N)` for each.
