# UVM Template Refinement Design

## Summary

Refine the generated UVM environment after the Common UVM Scoreboard v2 and
AIP runtime work. The result keeps two deliberately different platform
templates, removes obsolete common utilities, standardizes interface wiring,
adds a safe transaction object contract, moves harness and bind content into a
consistent layout, and repairs the generated VCS configuration examples.

This design supersedes earlier decisions that retained the legacy scoreboard,
retained the AIP activity subscriber, installed a custom report server, or used
`AIP_CORE_HOME`. The implemented scoreboard v2 remains the default public
`common_uvm_scb` class.

## Goals

- Keep a conventional PORT platform and a separate task-oriented Advance
  platform instead of mixing both data-flow styles in one template.
- Make generated transaction retention, cloning, comparison, printing, and
  diagnostics safe and explicit.
- Provide protocol-independent, fixed-order signal connection macros.
- Reduce agent modes to the three behaviors that are actually distinct.
- Keep AIP activity tracking explicit and let users opt individual monitors
  into bus-idle tracking.
- Remove common files and configuration fields that provide no working
  behavior.
- Use one harness location and one documented bind layout in both platforms.
- Generate VCS configuration and filelists that match the reviewed VCS
  W-2024.09-SP1 syntax.
- Preserve the existing compact scoreboard report: ten problem streams by
  default, an omitted-row count, and an explicit all-rows override.

## Non-goals

- Add a generated base virtual sequence, smoke-test framework, RAL adapter,
  functional coverage component, transaction recorder, callback framework, or
  package/namespace reorganization.
- Add driver-only `MASTER_NO_MONITOR` or `SLAVE_NO_MONITOR` modes.
- Add protocol-specific interface signals, drivers, monitors, reference-model
  logic, or comparison fields.
- Add transaction IDs or tags to protocols that do not provide them.
- Add time-based scoreboard expiry or persistent full-detail report files.
- Split AIP command progress and observed bus activity into separate counters.
- Change the `aip_core` repository API.

## 1. Platform architectures

### 1.1 PORT platform

PORT remains the conventional UVM implementation:

- monitor analysis ports connect through environment-owned TLM FIFOs;
- the environment connects agent monitor output to the reference model and
  checker;
- the reference model publishes expected transactions;
- the checker feeds typed `common_uvm_scb` instances;
- the existing environment-owned FIFO reset and worker lifecycle remains in
  place.

PORT does not adopt the task-only Advance APIs as its primary data path.

### 1.2 Advance platform

Advance becomes a task-oriented shell with no environment-level transaction
routing. The environment creates the agent, reference model, checker, and
virtual sequencer but does not automatically connect agent-to-RM-to-checker
analysis paths.

The generated APIs are:

```systemverilog
task agent::get_mon_item(output trans tr);
function bit agent::try_get_mon_item(output trans tr);

virtual task rm::predict(
    input trans observed,
    ref trans expected_q[$]
);

task checker::send_actual(input trans tr);
task checker::send_expected(input trans tr);
```

The agent may connect its own monitor to its own FIFO internally. Only one
external consumer may call `get_mon_item()` for that FIFO. The template does
not duplicate a transaction to multiple task consumers.

User code in a testcase, virtual sequence, or custom component performs the
workflow explicitly:

```text
get_mon_item -> predict -> send_actual/send_expected
```

The generated Advance environment contains a short commented usage example
but starts no automatic routing worker.

## 2. Agent modes and interface roles

Both platforms use only:

```systemverilog
typedef enum {
    AGENT_MASTER,
    AGENT_SLAVE,
    AGENT_ONLY_MONITOR
} agent_mode_e;
```

The construction behavior is:

| Mode | Driver | Sequencer | Monitor |
|---|---:|---:|---:|
| `AGENT_MASTER` | yes | yes | yes |
| `AGENT_SLAVE` | yes | yes | yes |
| `AGENT_ONLY_MONITOR` | no | no | yes |

`AGENT_ONLY_MASTER` and `AGENT_ONLY_SLAVE` are removed. In the current
templates they are behaviorally identical to their non-`ONLY` counterparts
because the monitor is always created. Driver-only modes are not generated;
an active agent should normally monitor the bus result actually accepted by
the DUT.

The interface template provides three role-specific clocking block shells:

```systemverilog
clocking mst_drv_cb @(posedge clk);
    // M2S fields are outputs; S2M fields are inputs.
endclocking

clocking slv_drv_cb @(posedge clk);
    // M2S fields are inputs; S2M fields are outputs.
endclocking

clocking mon_cb @(posedge clk);
    // Every observed protocol field is an input.
endclocking
```

Protocol users fill the field lists. `M2S` and `S2M` are defined relative to
the protocol master, not relative to the generated agent instance.

## 3. Transaction object contract

Every generated transaction uses explicit UVM object methods rather than
field-automation macros:

```systemverilog
`uvm_object_utils(<agent>_trans)

virtual function void do_copy(uvm_object rhs);
virtual function bit do_compare(uvm_object rhs,
                                uvm_comparer comparer);
virtual function string convert2string();
virtual function void do_print(uvm_printer printer);
```

Each method contains a small commented field example. `do_copy()` calls
`super.do_copy()`, validates the typed cast, and is the path used by `clone()`.
`do_print()` calls `super.do_print()` before printing protocol fields.

`self_define_do_compare()` remains the single typed, kind-aware comparison
implementation used by the scoreboard. `do_compare()` validates the typed
cast and delegates to it so UVM `compare()` and the common scoreboard do not
develop separate field rules.

An unimplemented generated comparison returns failure and supplies a clear
`comparison not implemented` diff. It never returns success merely because
the user has not added protocol fields. This deliberately fails safe.

## 4. Scoreboard policy for protocols without ID or tag

The generated transaction defaults remain:

```systemverilog
get_scb_stream_id() = '1;
get_scb_kind()      = -1;
```

The generated checker configures `SCB_UNORDERED`. Matching is therefore a
single-stream multiset comparison based on `self_define_do_compare()`.

If several transactions have identical comparison content, the scoreboard
matches arbitrary occurrences one-for-one and validates only multiplicity.
Without an ID, tag, timestamp, or another protocol key it cannot attribute a
particular occurrence or check per-occurrence latency.

The existing report policy is retained:

- print the aggregate summary;
- print at most ten problem streams by default;
- state how many problem streams were omitted;
- `m_report_limit = 0` prints only the summary;
- `m_report_limit = -1` prints all problem streams;
- `+SCB_REPORT_LIMIT=<value>` remains the command-line override;
- no full-detail file is produced automatically.

## 5. AIP activity ownership

No wrapper macro is added for `aip_activity::tick()`. Direct calls remain
easy to search and make watchdog semantics visible.

When AIP is enabled, every agent base sequence owns the default progress
calls:

- `send_trans()` ticks after `finish_item()` returns;
- `send_trans_with_rsp()` ticks after request completion and again after the
  requested response returns;
- response-sending helpers tick after the response item completes;
- a custom sequence that bypasses the helpers must tick at its own real
  progress boundary.

Driver and sequence code must not both tick for the same owned progress point.
The generated default assigns ownership to the sequence helpers.

Monitor activity is an explicit user option. The AIP-enabled monitor template
shows a commented direct call immediately after a complete transaction is
published:

```systemverilog
m_ap.write(tr);
// aip_activity::tick();
```

Uncommenting it means any observed bus transaction, including traffic driven
through C or DPI instead of the UVM driver, extends `end_test idle=N`. Users
must call it once per completed transaction, or once per accepted beat for a
burst whose duration may exceed the watchdog interval. It must not run every
clock cycle or repeatedly while a level remains asserted.

Because AIP Core currently uses one counter for both command watchdog progress
and end-test idle detection, monitor ticks may also keep a stalled command
alive when unrelated background traffic exists. This trade-off is documented.
Users enabling monitor ticks should use `end_test ... timeout=N` if the bus may
never become idle.

## 6. Common library cleanup

The following generated files are deleted:

- `common_uvm_scb_legacy.sv`;
- `common_draw_table.sv`;
- `common_self_debug_scb.sv`;
- `aip_activity_subscriber.sv`;
- `common_report_server.sv`.

All generator lists, package includes, filelists, documentation, and tests are
updated accordingly. Agent configuration fields, handles, and wiring used only
by the self-debug scoreboard are removed.

`common_report_server` currently changes only message formatting. Removing it
also removes its construction and `uvm_report_server::set_server()` call from
`tc_base`. Standard UVM report formatting returns; severity counts and the
generated PASS/FAIL decision are unchanged. `$timeformat()` remains.

`common_scb_registry.sv` and `common_scb_aip_adapter.sv` are generated only for
AIP-enabled projects. The registry-facing parts of `common_uvm_scb` are also
conditional on AIP generation: the typed proxy class, `m_proxy` member,
registry-error local state, proxy construction, and `build_phase()`
registration do not appear in a non-AIP project. A non-AIP scoreboard neither
includes nor references `common_scb_registry`; its matching and reporting
behavior remains otherwise identical. This keeps the core scoreboard usable
without an undeclared registry dependency.

## 7. Common macros

Macros use the `UVG_` prefix because preprocessor names are global across the
compilation unit.

### 7.1 Signal connection

The public macro is:

```systemverilog
`UVG_IF_CONNECT(ROLE, FLOW, RTL_SIG, VIF_SIG)
```

The final two arguments are always ordered RTL first and VIF second. Users
never reverse them when the agent role changes.

| Role | Flow | Expanded direction |
|---|---|---|
| `MASTER` | `M2S` | `RTL_SIG = VIF_SIG` |
| `MASTER` | `S2M` | `VIF_SIG = RTL_SIG` |
| `SLAVE` | `M2S` | `VIF_SIG = RTL_SIG` |
| `SLAVE` | `S2M` | `RTL_SIG = VIF_SIG` |
| `MONITOR` | either | `VIF_SIG = RTL_SIG` |

`ROLE` is a generation/elaboration-time choice, never the runtime class field
`m_cfg.m_mode`. The macro checks `$bits(RTL_SIG) == $bits(VIF_SIG)` and fails
elaboration on an accidental width mismatch. Intentional narrowing must use
explicit, equal-width slices.

True bidirectional pins are not passed through this macro. They are split into
input, output, and output-enable signals and connected individually.

### 7.2 Remaining core macros

`common_dec.sv` provides:

```systemverilog
`UVG_VIF_SET(IF_TYPE, PATH, VIF)
`UVG_VIF_GET(IF_TYPE, VIF)
`UVG_CLK(CLK, PERIOD, OFFSET)
`UVG_RSTN(RST_N, CLK, CYCLES)
`UVG_STATIC_ASSERT(NAME, EXPR, MESSAGE)
```

VIF configuration uses the fixed field name `m_vif`. The agent gets the VIF
once and passes the handle to its driver and monitor. A failed get is fatal and
identifies the type, component, and field.

`UVG_CLK` drives an explicitly declared signal and interprets its second
argument as a full period. It never declares a hidden `reg`. `UVG_RSTN`
asserts active-low reset at startup, holds it for a clock-cycle count, and
deasserts away from the active sampling edge.

The bind directory provides two small reusable SVA macros in
`common_sva.svh`:

```systemverilog
`UVG_SVA_NO_X(NAME, CLK, RST_N, SIGNAL)
`UVG_SVA_HOLD(NAME, CLK, RST_N, VALID, READY, PAYLOAD)
```

Protocol-specific latency and burst assertions remain user code.

## 8. Harness, bind, and filelist layout

Both platforms generate:

```text
th/
├── harness.sv
└── bind/
    ├── bind_example.sv
    └── common_sva.svh
```

`cfg/env.f` lists `../th/harness.sv` as its final default source entry.
`cfg/tb.f` does not list the harness directly. The bind example is disabled by
default. To enable it, the user appends it after the harness entry:

```text
../th/harness.sv
../th/bind/bind_example.sv
```

The bind example is guarded and compilable when enabled. It demonstrates:

- binding to every instance of a module type;
- binding to one hierarchical instance;
- a parameterized checker;
- an interface;
- an SVA module or checker;
- a generate hierarchy;
- multiple checkers;
- required compilation order.

## 9. AIP installation layout

Generated projects use only `AIP_HOME`:

```text
$AIP_HOME/
└── aip_core/
    ├── aip_core_pkg.sv
    ├── aip_cmd.tcl
    └── ...
```

The filelist entries are:

```text
+incdir+$AIP_HOME/aip_core
$AIP_HOME/aip_core/aip_core_pkg.sv
```

TCL scripts source:

```tcl
source $env(AIP_HOME)/aip_core/aip_cmd.tcl
```

`AIP_CORE_HOME` is removed from generated templates, README examples, tests,
and VCS gates. No compatibility alias is retained.

## 10. VCS configuration repair

The generated cfg directory is validated against VCS W-2024.09-SP1 on
`10.11.10.53`.

### xprop

Examples use supported forms such as:

```text
merge=tmerge;
tree {harness} {xpropOn};
instance {harness.u_dut.u0} {xpropOff};
module {sram_model} {xpropOff};
```

Documentation states that `xmerge` is more pessimistic and `tmerge` evaluates
both 0 and 1 paths before merging results.

### initreg

Only options accepted by the designated VCS release are documented, including
the `+vcs+initreg+...` family confirmed by a minimal compile. Unsupported
`+initreg+...` and `-initreg+cfg/...` examples are removed.

### coverage

Unsupported `-cm_cond obsv` examples are removed. No enabled default rule
assumes that `harness.u_dut` exists. DUT hierarchy filters are commented
examples until the user instantiates a DUT.

### wave

The Tcl file contains no corrupted text, uses `harness` as the generated top,
and does not compete with a second always-enabled FSDB dump path. One waveform
entry point is selected per run.

### filelists

Relative paths are defined from the documented `cfg/` invocation directory.
Harness movement preserves interface-before-harness compilation order. A
build command compiles the root `tb.f` hierarchy once; it does not also pass
the nested `dut.f` and `env.f` independently.

## 11. Error handling

- An unimplemented transaction comparison fails with an actionable diff.
- An invalid interface connection role or flow fails preprocessing or
  elaboration instead of silently choosing a direction.
- A connection width mismatch is fatal before simulation.
- A missing VIF is fatal during agent build.
- A monitor tick remains opt-in and its watchdog/idle implications are stated
  next to the call.
- A placeholder driver or monitor blocks on reset and never creates a
  zero-time loop.
- Removing the report server never changes UVM severity accounting.

## 12. Verification

### Local generation tests

Tests generate PORT and Advance projects with AIP disabled and enabled. They
verify:

- each platform has only its intended data-flow architecture;
- Advance has task APIs and no environment transaction routing;
- PORT retains TLM/FIFO routing and reset lifecycle;
- only the three supported agent modes appear;
- transaction methods and fail-safe comparison appear in both agent variants;
- deleted common files, includes, fields, and filelist entries are absent;
- AIP-only files and imports appear only when AIP is enabled;
- AIP-off scoreboards contain no proxy type, `m_proxy`, or registry reference,
  while AIP-on scoreboards retain the complete proxy-registration contract;
- every AIP path uses `$AIP_HOME/aip_core`;
- harness and optional bind entries have the specified order;
- macro signatures and fixed RTL/VIF ordering are stable;
- obsolete VCS syntax is absent.

### VCS semantic tests

On `10.11.10.53`, minimal tests cover:

- all six role/flow combinations of `UVG_IF_CONNECT`;
- a deliberate width mismatch that must fail elaboration;
- VIF set/get success and missing-VIF failure;
- clock and active-low reset macro timing;
- transaction clone, compare, print, and fail-safe unimplemented comparison;
- PORT and Advance generated-project compile for AIP off/on;
- existing scoreboard unit behavior and compact report limits;
- AIP TCL smoke behavior and optional monitor tick compilation;
- xprop, initreg, coverage hierarchy, wave Tcl, and root filelist syntax.

The implementation is complete only after the local test suite passes and all
required VCS checks pass on the designated host.
