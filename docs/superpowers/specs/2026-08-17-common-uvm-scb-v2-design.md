# Common UVM Scoreboard v2 Design

## Summary

Replace the generated scoreboard implementation with a production-oriented
v2 while preserving the current implementation under a legacy name.

- The current class becomes `common_uvm_scb_legacy`.
- The new class uses the public name `common_uvm_scb`.
- Newly generated checkers instantiate v2 by default.
- The v2 core has no dependency on AIP Core.
- When AIP Core is enabled, a thin adapter exposes non-destructive status and
  reporting commands.

Implementation begins only after the AIP runtime integration fixes have passed
their VCS gate.

## Problems in the current implementation

The existing class has useful concepts—per-stream state, three comparison
modes, counters, comparison hooks, and a report—but it combines too many
responsibilities and is not wired into generated checkers.

Correctness and integration issues include:

- Generated checker methods contain unimplemented comparison placeholders and
  never invoke the common scoreboard.
- The public input APIs are tasks, so Advance-mode analysis `write()` functions
  cannot call them.
- Some mismatch paths report an error without incrementing mismatch counters.
- Queues retain producer-owned transaction handles instead of clones.
- Actual data arriving before expected data can be treated as an error because
  of scheduling order rather than functional behavior.
- Reset clearing is manual and omits the suppressed-error total.
- Empty stream managers remain allocated after `clear_all()`.
- Runtime error suppression is per stream, allowing total log volume to grow
  with the number of failing stream IDs.
- Report output iterates every stream, uses inconsistent column layouts, and
  is followed by another per-stream queue check.
- Unordered matching performs a linear scan for each input and has no pending
  queue guardrail.

## Goals

- Make generated checkers perform real expected-versus-actual comparisons.
- Accept expected and actual transactions in either arrival order.
- Provide deterministic semantics for ordered, lossy ordered, and unordered
  comparison modes.
- Clone inputs before retaining them.
- Centralize match, mismatch, drop, and suppression accounting.
- Separate comparison, state, reporting, and optional AIP control.
- Print a compact global summary and at most ten problem streams by default.
- Report how many problem streams were omitted.
- Support `+SCB_REPORT_LIMIT=N`, with `0` meaning summary only and `-1`
  meaning all problem streams.
- Bound runtime error output globally without losing failure counts.
- Support multiple typed scoreboard instances in one generated environment.
- Preserve the old implementation as explicitly named legacy code.

## Non-goals

- Rewriting existing user projects outside generated output.
- Protocol-specific matching keys or packet parsing.
- Time-based transaction expiry in the first v2 release.
- A persistent CSV or text dump of all problem streams.
- Automatically clearing failures through TCL commands.
- Making AIP Core mandatory for reporting or configuration.

## File and class layout

### Legacy

- Generated file: `common_uvm_scb_legacy.sv`
- Class: `common_uvm_scb_legacy`
- Guard: `COMMON_UVM_SCB_LEGACY__SV`

The legacy implementation receives only the mechanical renames required to
coexist with v2. Its supporting declarations are renamed as well:

- `scb_cmp_mode` becomes `legacy_scb_cmp_mode_e`;
- `common_uvm_scb_cfg` becomes `common_uvm_scb_legacy_cfg`;
- `stream_trans_manager` becomes `common_scb_legacy_stream_manager`.

No new features are added to the legacy implementation.

### V2 core

- `common_uvm_scb.sv`: UVM component and public API.
- `common_scb_types.sv`: enums, result object, configuration, and per-stream
  state.
- `common_scb_reporter.sv`: structured summary and problem-table rendering.
- `common_scb_registry.sv`: AIP-independent registry of control proxies.
- `common_scb_aip_adapter.sv`: generated only with AIP Core enabled.

`common_lib_pkg.sv` includes the types, reporter, registry, legacy class, and
v2 class in dependency order. The AIP adapter is compiled after both
`aip_core_pkg.sv` and `common_lib_pkg.sv`.

## Public configuration

`common_uvm_scb_cfg` contains:

| Field | Default | Meaning |
|---|---:|---|
| `m_cmp_mode` | unordered | Comparison policy |
| `m_report_limit` | 10 | Maximum problem rows; `0` summary, `-1` all |
| `m_err_limit` | 10 | Global detailed runtime mismatch messages |
| `m_pending_limit` | 0 | Optional per-stream pending guard; `0` unlimited |
| `m_report_en` | 1 | Enable final summary |
| `m_clone_en` | 1 | Clone retained input transactions |
| `m_strict_arrival` | 0 | Optional diagnostic for actual-before-expected |

The scoreboard reads `+SCB_REPORT_LIMIT=<integer>` during build and uses it to
override `m_report_limit`. AIP is not involved in this override.

Invalid values below `-1` produce a UVM warning and fall back to the default.
`m_err_limit` and `m_pending_limit` must be non-negative.

## Comparison modes

### Ordered exact

Expected and actual transactions are stored independently. Whenever both
queues are non-empty, the two heads are compared. Arrival order does not affect
the result. A head mismatch is definitive and is recorded once.

At check phase, either residual queue is a failure.

### Ordered with DUT loss

For the oldest actual item, expected items are searched in order. Expected
items before the first match are counted as allowed DUT drops. A matching item
and its expected counterpart are consumed.

At check phase:

- residual expected items are counted as allowed drops and produce WARN;
- residual actual items are unexpected output and produce FAIL.

This mode allows loss only from expected-to-DUT observation. It does not allow
additional DUT packets.

### Unordered

Each new item scans the opposite pending queue for the first successful match.
The matching pair is removed. An item with no current match is retained.

At check phase, any residual item is a failure. The initial v2 release keeps
the generic linear scan; `m_pending_limit` provides a safety guard. A future
key-index policy can be added without changing the public input API.

## Transaction comparison contract

The v2 component provides one overridable function:

```systemverilog
virtual function bit compare_items(
    TRANS_TYPE expected,
    TRANS_TYPE actual,
    int kind,
    output string diff
);
```

The default implementation calls the generated transaction's existing
`self_define_do_compare()` method. A protocol-specific scoreboard subclass can
override `compare_items()` without replacing queue or reporting logic.

Comparison is non-blocking. Timing behavior belongs outside scoreboard input
functions.

## Input and result APIs

The primary APIs are functions so both analysis callbacks and task-based PORT
workers can use them:

```systemverilog
function void push_expected(TRANS_TYPE tr,
                            bit [STREAM_ID_WIDTH-1:0] stream_id = '1,
                            int kind = -1);
function void push_actual(TRANS_TYPE tr,
                          bit [STREAM_ID_WIDTH-1:0] stream_id = '1,
                          int kind = -1);
function scb_status_e get_status();
function bit is_clean();
function string get_summary();
function void print_report(int limit = -2);
function void reset_state(bit clear_counters = 1);
```

`print_report(-2)` uses the configured `m_report_limit`; `-1` prints all
problem streams. The value `-2` is an API-only sentinel and is never accepted
as a configuration value.

V2 provides legacy-named task wrappers that call the new functions, but all
newly generated code uses the function API.

When retaining an input, v2 clones it. A null input or failed typed clone is a
UVM error and is counted as a scoreboard failure. The original producer handle
is never placed in a pending queue when cloning is enabled.

Each match or mismatch creates a `common_scb_result#(TRANS_TYPE)` object and
writes it to a result analysis port. Users who need side effects subscribe to
that port instead of overriding a timing task inside the comparison engine.

## Generated checker integration

For each generated agent type, the checker owns one typed instance:

```systemverilog
common_uvm_scb#(axi_trans) m_axi_scb;
```

- RM input calls `m_axi_scb.push_expected()`.
- Agent monitor input calls `m_axi_scb.push_actual()`.
- Advance-mode analysis callbacks and PORT-mode worker tasks use the same API.
- The generated transaction provides default `get_scb_stream_id()` and
  `get_scb_kind()` hooks. Their defaults return the single-stream ID `'1` and
  kind `-1`; protocol users override them when needed.

This makes a generated single-stream project compare immediately while leaving
protocol-specific stream extraction explicit.

## Accounting and status

All outcome accounting passes through centralized methods:

- `record_match()`
- `record_mismatch()`
- `record_drop()`
- `record_unexpected()`

Per-stream and global counters include inputs, matches, mismatches, allowed
drops, unexpected actuals, pending expected, pending actual, peak pending, and
suppressed detail messages.

Status is defined as:

- `SCB_PASS`: no mismatch, unexpected actual, queue overflow, or residual
  disallowed item.
- `SCB_WARN`: only allowed drops or configured diagnostic warnings occurred.
- `SCB_FAIL`: any definitive mismatch, unexpected actual, clone failure,
  pending-limit violation, or disallowed residual item occurred.

`check_phase()` finalizes pending state and emits the UVM errors that determine
test failure. `report_phase()` does not create new comparison errors; it only
prints the final report.

## Reporting

The v2 reporter does not use the legacy space-tokenizing table API. It accepts
structured headers and cells, calculates width per column, left-aligns labels,
right-aligns numbers, and renders plain ASCII suitable for regression logs.

Default output contains:

1. One PASS/WARN/FAIL summary.
2. Aggregate expected, actual, match, mismatch, drop, and pending counts.
3. Up to `m_report_limit` problem streams.
4. An omission line when additional problem streams exist.

Example omission text:

```text
Problem streams: total=125 shown=10 omitted=115
```

Normal streams never appear in the detail table. Problem rows sort by severity,
then descending issue count, then ascending stream ID for deterministic output.
No full-detail file is produced.

Runtime mismatch detail is governed separately by the global `m_err_limit`.
After the limit, counters continue to update and one final summary reports the
number of suppressed messages.

## Reset and lifecycle

`reset_state()` deletes all per-stream queues and stream-state objects. With
`clear_counters=1`, it also resets every global counter, including suppressed
errors and high-water marks.

The generated environment calls reset through an explicit checker reset hook.
Reset behavior is not inferred from transaction arrival. A reset during a test
starts a clean comparison epoch and cannot leave stale expected or actual
handles behind.

## Optional AIP adapter

The core registry stores non-parameterized control proxies keyed by scoreboard
full name. A typed proxy holds each parameterized scoreboard handle and exposes
only status, reporting, and report-limit methods. The registry and proxies do
not import AIP Core.

When `--aip-core` is enabled, `common_scb_aip_adapter.sv` registers:

| Command | Behavior |
|---|---|
| `scb_list` | List registered scoreboard paths |
| `scb_status name=<path>` | Return status and aggregate summary |
| `scb_report name=<path> limit=<N>` | Print a non-destructive snapshot |
| `scb_set_limit name=<path> limit=<N>` | Change the runtime report limit |

The adapter does not expose queue or counter clearing. Unknown names and
invalid limits return command failure without changing scoreboard state.

## Error handling

- Null or unclonable input: count failure and emit a bounded UVM error.
- Invalid configuration: warn and use a safe default.
- Pending-limit violation: mark FAIL, report stream and depth, increment an
  overflow counter, and reject the item that would exceed the configured
  bound. The scoreboard continues running without unbounded queue growth.
- Report-limit overflow: omit rows and report the omitted count.
- AIP command for an unknown scoreboard: return a descriptive command error.
- Multiple errors after `m_err_limit`: suppress detail only; retain all counts
  and final FAIL status.

## Verification

### Generator tests

- New common files are generated and included in dependency order.
- Legacy and v2 class names coexist without guard collisions.
- Advance and PORT checkers instantiate and feed typed v2 scoreboards.
- Non-AIP output contains no adapter or AIP symbols.
- AIP output includes the adapter and four command registrations.
- Plusarg configuration is emitted independently of AIP.

### VCS scoreboard unit matrix

Run on `10.11.10.53`:

- Ordered exact: expected-first, actual-first, match, mismatch, and residue.
- Ordered DUT loss: middle loss, tail loss, and unexpected actual.
- Unordered: shuffled matches and unmatched residues.
- Multiple stream IDs with independent state.
- Transaction handle reuse proving clone isolation.
- Reset clearing queues, stream objects, and every counter.
- Pending-limit and global error-limit behavior.
- Report limits `10`, `0`, and `-1`, including exact omitted counts.
- Deterministic severity and stream ordering.
- PASS, WARN, and FAIL status transitions.

### Generated integration matrix

Compile and run Advance and PORT, each with AIP disabled and enabled. The
integration tests feed both RM and DUT paths, require real comparison counts,
and verify that AIP commands can query the same scoreboard state without
changing it.

### Completion gates

1. AIP runtime-fix verification is green before v2 implementation begins.
2. All Python tests pass.
3. All VCS scoreboard unit tests pass on the designated host.
4. All four generated integration configurations compile and run.
5. No unbounded runtime log or full problem-stream dump is produced by
   default.
