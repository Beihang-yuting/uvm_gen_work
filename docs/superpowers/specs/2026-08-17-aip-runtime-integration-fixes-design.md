# AIP Runtime Integration Fixes Design

## Summary

Repair the generated `--aip-core` runtime path before introducing the new
scoreboard. The generated Advance and PORT projects already compile against
the current `aip_core/main`, but the shipped TCL test cannot make forward
progress because the placeholder driver and monitor create a zero-time loop,
the reset phase finishes with reset asserted, and activity tracking is fed by
all monitor traffic rather than command-owned progress.

This phase changes only the generated UVM environment. It does not modify the
`aip_core` repository and does not introduce scoreboard v2.

## Evidence

The current generated projects were checked with VCS W-2024.09-SP1 on the
designated simulation host.

- Advance plus AIP Core compiles successfully.
- PORT plus AIP Core compiles successfully.
- Running `tc_tcl` does not advance simulation time and is terminated by an
  external 20-second timeout.
- The log repeatedly prints the driver and monitor startup messages at
  `0.00ns`.

The causes are visible in the templates:

1. `master_drive()`, `slave_drive()`, and `mon_transaction()` return
   immediately while their callers are inside a `forever` loop.
2. `tc_base::reset_phase()` drives `rst_n` low at the end, while `tc_tcl`
   waits for `rst_n === 1'b1`.
3. Every generated monitor analysis port is connected to an
   `aip_activity_subscriber`, so unrelated background bus traffic can keep the
   global AIP watchdog alive while the command that owns the watchdog is
   actually stuck.

## Goals

- A generated AIP-enabled Advance or PORT project must compile and complete a
  TCL smoke test without user protocol code.
- Empty protocol hooks must block safely instead of spinning in zero time.
- Active-low reset must finish deasserted.
- AIP watchdog activity must represent progress made by the executing
  sequence or driver, not arbitrary monitor traffic.
- Projects generated without `--aip-core` must not reference AIP symbols.
- AIP integration must continue to use the public APIs from
  `aip_core_pkg.sv`.

## Non-goals

- Implementing protocol-specific driver or monitor behavior.
- Changing AIP Core's watchdog implementation.
- Adding scoreboard v2 or AIP scoreboard commands in this phase.
- Making the demonstration clock frequency configurable; the existing 100 MHz
  AIP clock remains a documented example.

## Design

### 1. Safe placeholder behavior

The default implementations of `master_drive()`, `slave_drive()`, and
`mon_transaction()` will log one explanatory warning and then block until the
next assertion of active-low reset:

```systemverilog
@(negedge m_vif.rst_n);
```

The surrounding reset-aware `fork...join_any` remains responsible for
terminating protocol work on reset. A user implementation can replace the
placeholder body without changing the lifecycle wrapper.

This makes an unimplemented generated agent inert and debuggable rather than
an infinite zero-time process.

### 2. Deterministic reset lifecycle

`tc_base::reset_phase()` will perform a single valid active-low reset:

1. Drive `rst_n = 0`.
2. Hold reset for a randomized 10 to 20 clock cycles.
3. Drive `rst_n = 1`.
4. Wait two clock cycles for components to observe release.
5. Drop the reset-phase objection.

The reset phase will not randomly begin in the released state and will never
finish with reset asserted. `tc_tcl` will retain its explicit wait for reset
release.

### 3. Command-owned AIP activity

Automatic creation and connection of `aip_activity_subscriber` instances in
the environment will be removed. The subscriber template remains available
as an explicit opt-in utility, with documentation warning that unrelated
traffic can mask a stuck command.

When AIP Core is enabled, the standard sequence helpers will call
`aip_activity::tick()` after a transaction completes:

- `send_trans()` ticks after `finish_item()` returns.
- `send_trans_with_rsp()` ticks after the response is received.
- PORT base sequences receive the same helper methods as Advance sequences so
  both modes have one supported progress path.

Custom long-running sequences that bypass these helpers must tick explicitly,
as required by the AIP Core watchdog contract. The generated comments will
show the required call at a real progress boundary, normally after
`item_done()` or after a completed transaction.

No scoreboard callback will feed the watchdog automatically.

### 4. TCL smoke-test behavior

The demo TCL script will continue to source
`$AIP_CORE_HOME/aip_cmd.tcl`, but its usage comment will use the interactive
script form supported by the current AIP documentation:

```text
./simv -ucli -i tc/tcl/tc_tcl_demo.tcl +UVM_TESTNAME=tc_tcl
```

The no-protocol smoke path executes `end_test`, lets UVM traverse check and
report phases, and exits normally. It does not require a registered protocol
sequence.

### 5. Compatibility boundary

- `aip_core_pkg.sv` remains the only AIP compilation entry.
- The generator continues to use `$AIP_CORE_HOME` in `tb.f`.
- No AIP source is copied into generated projects.
- Non-AIP output contains neither AIP imports nor AIP progress calls.
- Current public calls such as `aip_tcl_bridge::run_loop()` and
  `aip_activity::tick()` remain unchanged.

## Error handling

- A placeholder driver or monitor emits one warning per reset epoch, not an
  unbounded stream of messages.
- Missing `$AIP_CORE_HOME` remains a compile-time filelist failure with the
  missing path visible in the VCS log.
- A custom long sequence with no activity remains subject to the AIP watchdog;
  the generator does not disable the watchdog to hide integration mistakes.
- Reset release is deterministic, so a TCL bridge that fails to start is a
  real integration error rather than random template behavior.

## Verification

### Python and generation tests

- Assert that non-AIP output contains no AIP references.
- Assert that AIP output includes the package, TCL test, and progress hooks.
- Assert that generated environment code does not auto-connect activity
  subscribers.
- Assert that placeholder tasks contain a blocking event control.
- Assert that reset finishes with `rst_n = 1`.

### VCS checks on `10.11.10.53`

For both Advance and PORT:

1. Generate a one-agent project with `--aip-core`.
2. Compile against the reviewed AIP Core revision.
3. Run `tc_base` as a non-TCL smoke test.
4. Run `tc_tcl` with the generated demo TCL script.
5. Require finite simulation time progression, normal UVM phase completion,
   and process exit code zero.

The AIP runtime phase is complete only when all four generated configurations
(Advance/PORT multiplied by AIP off/on) compile, and both AIP-enabled TCL smoke
tests terminate normally.
