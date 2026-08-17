# Common UVM Scoreboard v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the current scoreboard as `common_uvm_scb_legacy` and make a production-oriented, typed, bounded-reporting `common_uvm_scb` the default in newly generated Advance and PORT environments.

**Architecture:** Split comparison state/types, ASCII rendering, AIP-independent control registry, the typed scoreboard core, and the optional AIP adapter into focused templates. The core clones retained transactions, accepts expected/actual in either order through function APIs, centralizes accounting and finalization, and exposes only non-destructive control through a registry; generated checkers own one typed scoreboard per agent.

**Tech Stack:** Python 3, pytest, Jinja2, SystemVerilog/UVM 1.2, Synopsys VCS W-2024.09-SP1, optional AIP Core at reviewed `main@5a9edbb`

---

## Entry gate and file map

Begin this plan only after every check in `docs/superpowers/plans/2026-08-17-aip-runtime-integration-fixes.md` passes, including the four VCS compile/base runs and two AIP TCL runs on `10.11.10.53`.

- Rename `uvm_gen/templates/common/base_scb.sv.j2` to `uvm_gen/templates/common/legacy_scb.sv.j2`: mechanically renamed legacy implementation.
- Create `uvm_gen/templates/common/common_scb_types.sv.j2`: enums, config, pending/result objects, stream state, and report row.
- Create `uvm_gen/templates/common/common_scb_reporter.sv.j2`: structured, per-column ASCII rendering.
- Create `uvm_gen/templates/common/common_scb_registry.sv.j2`: AIP-independent proxy/registry API.
- Create a new `uvm_gen/templates/common/base_scb.sv.j2`: v2 core and typed control proxy.
- Create `uvm_gen/templates/common/common_scb_aip_adapter.sv.j2`: optional four-command AIP bridge.
- Modify `uvm_gen/templates/common/common_pkg.sv.j2`: dependency-ordered includes.
- Modify `uvm_gen/generators/common.py`: generate all v2/legacy files and conditionally generate the adapter.
- Modify Advance/PORT transaction templates: default stream-ID and kind hooks.
- Modify Advance/PORT RM, checker, and environment templates: typed expected/actual paths and v2 instances.
- Create `tests/test_common_scb_v2_generation.py`: generation and wiring contracts.
- Create `tests/vcs/common_scb_unit_tb.sv`: simulator-level semantic/report test.
- Create `tests/vcs/run_common_scb_v2.sh`: remote compile and integration gate.
- Create `tests/vcs/scb_adapter_smoke.tcl`: non-destructive AIP command smoke input.
- Create `tests/vcs/run_generated_scb_matrix.sh`: generated Advance/PORT compile/runtime matrix.

### Task 1: Lock down legacy/v2 coexistence with failing tests

**Files:**
- Create: `tests/test_common_scb_v2_generation.py`

- [ ] **Step 1: Add the initial common-file and naming tests**

Create the module with these helpers and tests; later tasks extend this same file:

```python
from pathlib import Path

import pytest

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator


@pytest.fixture(params=[PlatformType.ADVANCE, PlatformType.PORT])
def platform_type(request):
    return request.param


def generate(tmp_path: Path, platform_type: PlatformType, aip_core: bool = False) -> Path:
    cfg = ProjectConfig(
        block_name="top",
        author="test",
        platform_type=platform_type,
        agents=[AgentConfig(name="axi"), AgentConfig(name="apb")],
        output_dir=str(tmp_path),
        aip_core=aip_core,
    )
    return Path(PlatformGenerator(cfg).generate())


def read(project: Path, relative_path: str) -> str:
    return (project / relative_path).read_text(encoding="utf-8")


def test_common_generates_legacy_and_v2_files(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    expected = {
        "common_uvm_scb_legacy.sv",
        "common_scb_types.sv",
        "common_scb_reporter.sv",
        "common_scb_registry.sv",
        "common_uvm_scb.sv",
    }
    assert expected <= {path.name for path in (project / "common").iterdir()}


def test_legacy_names_do_not_collide_with_v2(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    legacy = read(project, "common/common_uvm_scb_legacy.sv")
    v2 = read(project, "common/common_uvm_scb.sv")
    assert "class common_uvm_scb_legacy" in legacy
    assert "legacy_scb_cmp_mode_e" in legacy
    assert "common_uvm_scb_legacy_cfg" in legacy
    assert "common_scb_legacy_stream_manager" in legacy
    assert "COMMON_UVM_SCB_LEGACY__SV" in legacy
    assert "class common_uvm_scb #(" in v2
    assert "class common_uvm_scb #(" not in legacy


def test_common_package_dependency_order(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    package = read(project, "common/common_lib_pkg.sv")
    includes = [
        '`include "common_scb_types.sv"',
        '`include "common_scb_reporter.sv"',
        '`include "common_scb_registry.sv"',
        '`include "common_uvm_scb_legacy.sv"',
        '`include "common_uvm_scb.sv"',
    ]
    positions = [package.index(item) for item in includes]
    assert positions == sorted(positions)
```

- [ ] **Step 2: Run the initial contract and verify it fails**

```bash
python3 -m pytest tests/test_common_scb_v2_generation.py -q
```

Expected: six failures because the new generated files and renamed declarations do not exist.

- [ ] **Step 3: Commit the red contract**

```bash
git add tests/test_common_scb_v2_generation.py
git commit -m "test: define scoreboard v2 generation layout"
```

### Task 2: Preserve the existing scoreboard under explicit legacy names

**Files:**
- Rename: `uvm_gen/templates/common/base_scb.sv.j2` -> `uvm_gen/templates/common/legacy_scb.sv.j2`
- Modify: `uvm_gen/templates/common/legacy_scb.sv.j2`
- Modify: `uvm_gen/generators/common.py:7-15`
- Modify: `uvm_gen/templates/common/common_pkg.sv.j2:9-14`
- Test: `tests/test_common_scb_v2_generation.py`

- [ ] **Step 1: Rename the template file without changing behavior**

```bash
git mv uvm_gen/templates/common/base_scb.sv.j2 \
       uvm_gen/templates/common/legacy_scb.sv.j2
```

- [ ] **Step 2: Apply only the approved mechanical symbol mapping**

Apply these exact whole-word replacements throughout `legacy_scb.sv.j2`:

```text
COMMON_UVM_SCB__SV                 -> COMMON_UVM_SCB_LEGACY__SV
scb_cmp_mode                       -> legacy_scb_cmp_mode_e
common_uvm_scb_cfg                 -> common_uvm_scb_legacy_cfg
stream_trans_manager               -> common_scb_legacy_stream_manager
common_uvm_scb                     -> common_uvm_scb_legacy
```

Then verify no old declaration remains:

```bash
rg -n 'class (common_uvm_scb_cfg|stream_trans_manager|common_uvm_scb)(\s|#)|typedef enum.*scb_cmp_mode|COMMON_UVM_SCB__SV' \
  uvm_gen/templates/common/legacy_scb.sv.j2
```

Expected: no matches. References to legacy task names such as `send_rm_trans_to_cmp` remain unchanged.

- [ ] **Step 3: Keep generation runnable in a legacy-only interim state**

Set `CommonGenerator.TEMPLATES` to this complete interim list:

```python
TEMPLATES = [
    ("common_lib_pkg.sv", "common/common_pkg.sv.j2"),
    ("common_dec.sv", "common/common_dec.sv.j2"),
    ("common_report_server.sv", "common/report_server.sv.j2"),
    ("common_self_debug_scb.sv", "common/self_debug_scb.sv.j2"),
    ("common_draw_table.sv", "common/draw_table.sv.j2"),
    ("common_uvm_scb_legacy.sv", "common/legacy_scb.sv.j2"),
]
```

- [ ] **Step 4: Include only the renamed legacy class during the interim**

The package include body becomes:

```systemverilog
    `include "common_dec.sv"
    `include "common_draw_table.sv"
    `include "common_report_server.sv"
    `include "common_self_debug_scb.sv"
    `include "common_uvm_scb_legacy.sv"
```

- [ ] **Step 5: Smoke-generate the interim layout and commit the isolated rename**

```bash
python3 - <<'PY'
import tempfile
from pathlib import Path
from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator

with tempfile.TemporaryDirectory() as output_dir:
    cfg = ProjectConfig(block_name="top", platform_type=PlatformType.ADVANCE,
                        agents=[AgentConfig(name="axi")], output_dir=output_dir)
    project = Path(PlatformGenerator(cfg).generate())
    legacy = project / "common/common_uvm_scb_legacy.sv"
    assert legacy.exists()
    assert "class common_uvm_scb_legacy" in legacy.read_text(encoding="utf-8")
PY
```

Expected: exit code `0`.

```bash
git add uvm_gen/generators/common.py \
        uvm_gen/templates/common/common_pkg.sv.j2 \
        uvm_gen/templates/common/legacy_scb.sv.j2
git commit -m "refactor: preserve scoreboard as explicit legacy class"
```

### Task 3: Add shared v2 types and structured table rendering

**Files:**
- Create: `uvm_gen/templates/common/common_scb_types.sv.j2`
- Create: `uvm_gen/templates/common/common_scb_reporter.sv.j2`
- Test: `tests/test_common_scb_v2_generation.py`

- [ ] **Step 1: Extend the Python contract for defaults and structured reporting**

Append:

```python
def test_v2_types_expose_approved_defaults(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    types = read(project, "common/common_scb_types.sv")
    assert "SCB_ORDERED_EXACT" in types
    assert "SCB_ORDERED_LOSSY" in types
    assert "SCB_UNORDERED" in types
    assert "m_report_limit = 10" in types
    assert "m_err_limit = 10" in types
    assert "m_pending_limit = 0" in types
    assert "m_clone_en = 1" in types
    assert "m_strict_arrival = 0" in types


def test_reporter_uses_structured_cells_and_per_column_widths(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    reporter = read(project, "common/common_scb_reporter.sv")
    assert "class common_scb_reporter" in reporter
    assert "string m_headers[$]" in reporter
    assert "int m_widths[$]" in reporter
    assert "function void add_row" in reporter
    assert "function string render" in reporter
    assert "insert_line_content" not in reporter
```

- [ ] **Step 2: Create the shared types template**

Define these exact public types and defaults; all counters are `longint unsigned` so large regressions do not wrap at 32 bits:

```systemverilog
{{ header(file_name) }}
`ifndef COMMON_SCB_TYPES__SV
`define COMMON_SCB_TYPES__SV

typedef enum int {
    SCB_ORDERED_EXACT,
    SCB_ORDERED_LOSSY,
    SCB_UNORDERED
} common_scb_cmp_mode_e;

typedef enum int {SCB_PASS, SCB_WARN, SCB_FAIL} scb_status_e;

class common_uvm_scb_cfg extends uvm_object;
    `uvm_object_utils(common_uvm_scb_cfg)
    common_scb_cmp_mode_e m_cmp_mode = SCB_UNORDERED;
    int m_report_limit = 10;
    int m_err_limit = 10;
    int m_pending_limit = 0;
    bit m_report_en = 1;
    bit m_clone_en = 1;
    bit m_strict_arrival = 0;

    function new(string name="common_uvm_scb_cfg");
        super.new(name);
    endfunction
endclass

class common_scb_pending_item #(type TRANS_TYPE=uvm_sequence_item);
    TRANS_TYPE tr;
    int kind;
    function new(TRANS_TYPE tr=null, int kind=-1);
        this.tr = tr;
        this.kind = kind;
    endfunction
endclass

class common_scb_result #(type TRANS_TYPE=uvm_sequence_item) extends uvm_object;
    `uvm_object_param_utils(common_scb_result #(TRANS_TYPE))
    TRANS_TYPE expected;
    TRANS_TYPE actual;
    longint unsigned stream_id;
    int kind;
    bit matched;
    string diff;
    function new(string name="common_scb_result");
        super.new(name);
    endfunction
endclass

class common_scb_stream_state #(type TRANS_TYPE=uvm_sequence_item);
    typedef common_scb_pending_item#(TRANS_TYPE) pending_t;
    pending_t expected_q[$];
    pending_t actual_q[$];
    longint unsigned stream_id;
    longint unsigned expected_inputs;
    longint unsigned actual_inputs;
    longint unsigned matches;
    longint unsigned mismatches;
    longint unsigned allowed_drops;
    longint unsigned unexpected_actuals;
    longint unsigned overflows;
    longint unsigned peak_pending;
    longint unsigned suppressed_details;
    function new(longint unsigned stream_id=0);
        this.stream_id = stream_id;
    endfunction
    function longint unsigned issue_count();
        return mismatches + unexpected_actuals + overflows
             + expected_q.size() + actual_q.size();
    endfunction
endclass

class common_scb_problem_row;
    scb_status_e status;
    longint unsigned stream_id;
    longint unsigned issue_count;
    string cells[$];
endclass

`endif
```

- [ ] **Step 3: Create the structured reporter template**

Implement `common_scb_reporter` with this public contract and rendering rules:

```systemverilog
{{ header(file_name) }}
`ifndef COMMON_SCB_REPORTER__SV
`define COMMON_SCB_REPORTER__SV

class common_scb_report_row;
    string cells[$];
endclass

class common_scb_reporter;
    string m_headers[$];
    bit m_numeric[$];
    int m_widths[$];
    common_scb_report_row m_rows[$];

    function void set_columns(input string headers[$], input bit numeric[$]);
        m_headers = headers;
        m_numeric = numeric;
        m_widths.delete();
        foreach (m_headers[i]) m_widths.push_back(m_headers[i].len());
    endfunction

    function void add_row(input string cells[$]);
        common_scb_report_row row = new();
        if (cells.size() != m_headers.size())
            return;
        row.cells = cells;
        foreach (cells[i])
            if (cells[i].len() > m_widths[i]) m_widths[i] = cells[i].len();
        m_rows.push_back(row);
    endfunction

    local function string repeat_char(string value, int count);
        string result = "";
        repeat (count) result = {result, value};
        return result;
    endfunction

    local function string format_cell(string value, int width, bit numeric);
        int padding = width - value.len();
        if (numeric) return {repeat_char(" ", padding), value};
        return {value, repeat_char(" ", padding)};
    endfunction

    local function string border();
        string line = "+";
        foreach (m_widths[i]) line = {line, repeat_char("-", m_widths[i]+2), "+"};
        return line;
    endfunction

    local function string render_cells(input string cells[$]);
        string line = "|";
        foreach (cells[i])
            line = {line, " ", format_cell(cells[i], m_widths[i], m_numeric[i]), " |"};
        return line;
    endfunction

    function string render();
        string text;
        text = {border(), "\n", render_cells(m_headers), "\n", border()};
        foreach (m_rows[i]) text = {text, "\n", render_cells(m_rows[i].cells)};
        return {text, "\n", border()};
    endfunction
endclass

`endif
```

- [ ] **Step 4: Statically verify both focused templates before integration**

```bash
rg -n 'SCB_ORDERED_EXACT|m_report_limit = 10|class common_scb_result|class common_scb_stream_state' \
  uvm_gen/templates/common/common_scb_types.sv.j2
rg -n 'string m_headers\[\$\]|int m_widths\[\$\]|function void add_row|function string render' \
  uvm_gen/templates/common/common_scb_reporter.sv.j2
```

Expected: the first command reports all four declarations and the second reports all four structured-renderer members. Generation tests remain red until Task 6 integrates every new template at once.

- [ ] **Step 5: Commit shared v2 declarations**

```bash
git add uvm_gen/templates/common/common_scb_types.sv.j2 \
        uvm_gen/templates/common/common_scb_reporter.sv.j2
git commit -m "feat: add scoreboard v2 types and reporter"
```

### Task 4: Add the AIP-independent control registry

**Files:**
- Create: `uvm_gen/templates/common/common_scb_registry.sv.j2`

- [ ] **Step 1: Create the non-parameterized proxy and registry contract**

```systemverilog
{{ header(file_name) }}
`ifndef COMMON_SCB_REGISTRY__SV
`define COMMON_SCB_REGISTRY__SV

virtual class common_scb_control_proxy extends uvm_object;
    function new(string name="common_scb_control_proxy");
        super.new(name);
    endfunction
    pure virtual function string scoreboard_name();
    pure virtual function scb_status_e status();
    pure virtual function string summary();
    pure virtual function void report(int limit=-2);
    pure virtual function bit set_report_limit(int limit, output string error);
endclass

class common_scb_registry;
    local static common_scb_control_proxy m_proxies[string];

    static function bit register_proxy(common_scb_control_proxy proxy,
                                       output string error);
        string name;
        if (proxy == null) begin
            error = "cannot register a null scoreboard proxy";
            return 0;
        end
        name = proxy.scoreboard_name();
        if (name == "") begin
            error = "cannot register a scoreboard with an empty name";
            return 0;
        end
        if (m_proxies.exists(name)) begin
            error = $sformatf("scoreboard '%s' is already registered", name);
            return 0;
        end
        m_proxies[name] = proxy;
        error = "";
        return 1;
    endfunction

    static function common_scb_control_proxy find(string name);
        if (!m_proxies.exists(name)) return null;
        return m_proxies[name];
    endfunction

    static function void get_names(ref string names[$]);
        names.delete();
        foreach (m_proxies[name]) names.push_back(name);
        names.sort();
    endfunction

    static function int size();
        return m_proxies.num();
    endfunction
endclass

`endif
```

- [ ] **Step 2: Verify the registry has no AIP dependency**

```bash
rg -n '\baip_|AIP_' uvm_gen/templates/common/common_scb_registry.sv.j2
```

Expected: no matches.

- [ ] **Step 3: Commit the registry boundary**

```bash
git add uvm_gen/templates/common/common_scb_registry.sv.j2
git commit -m "feat: add AIP-independent scoreboard registry"
```

### Task 5: Implement the v2 core, cloning, and comparison modes

**Files:**
- Create: `uvm_gen/templates/common/base_scb.sv.j2`
- Modify: `uvm_gen/templates/common/common_scb_types.sv.j2`
- Test: `tests/test_common_scb_v2_generation.py`

- [ ] **Step 1: Extend the generation contract for the public API and policy hooks**

Append:

```python
def test_v2_core_has_function_api_and_result_port(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core = read(project, "common/common_uvm_scb.sv")
    assert "function void push_expected" in core
    assert "function void push_actual" in core
    assert "virtual function bit compare_items" in core
    assert "function scb_status_e get_status" in core
    assert "function bit is_clean" in core
    assert "function string get_summary" in core
    assert "function void print_report" in core
    assert "function void reset_state" in core
    assert "uvm_analysis_port#(result_t) m_result_ap" in core


def test_v2_core_clones_and_bounds_pending_state(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core = read(project, "common/common_uvm_scb.sv")
    assert "source.clone()" in core
    assert "$cast(retained, cloned)" in core
    assert "m_pending_limit" in core
    assert "SCB_PENDING_OVERFLOW" in core
    assert "SCB_REPORT_LIMIT=%d" in core


def test_v2_core_keeps_legacy_task_wrappers(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core = read(project, "common/common_uvm_scb.sv")
    assert "task send_rm_trans_to_cmp" in core
    assert "task send_dut_trans_to_cmp" in core
    assert "push_expected(rm_tr" in core
    assert "push_actual(dut_tr" in core
```

- [ ] **Step 2: Add per-stream diagnostic warnings to the state type**

Add this counter beside `overflows` and include it in warning severity/report sorting:

```systemverilog
    longint unsigned diagnostic_warnings;
```

Change `issue_count()` to:

```systemverilog
function longint unsigned issue_count();
    return mismatches + allowed_drops + unexpected_actuals + overflows
         + diagnostic_warnings + expected_q.size() + actual_q.size();
endfunction
```

- [ ] **Step 3: Declare the v2 component and all public/private methods**

The new `base_scb.sv.j2` starts with this complete class contract:

```systemverilog
{{ header(file_name) }}
`ifndef COMMON_UVM_SCB__SV
`define COMMON_UVM_SCB__SV

class common_uvm_scb #(type TRANS_TYPE=uvm_sequence_item,
                       int STREAM_ID_WIDTH=64) extends uvm_scoreboard;
    typedef bit [STREAM_ID_WIDTH-1:0] stream_id_t;
    typedef common_scb_pending_item#(TRANS_TYPE) pending_t;
    typedef common_scb_stream_state#(TRANS_TYPE) state_t;
    typedef common_scb_result#(TRANS_TYPE) result_t;

    `uvm_component_param_utils(common_uvm_scb #(TRANS_TYPE, STREAM_ID_WIDTH))

    common_uvm_scb_cfg m_cfg;
    uvm_analysis_port#(result_t) m_result_ap;
    protected state_t m_streams[stream_id_t];
    protected longint unsigned m_expected_inputs;
    protected longint unsigned m_actual_inputs;
    protected longint unsigned m_matches;
    protected longint unsigned m_mismatches;
    protected longint unsigned m_allowed_drops;
    protected longint unsigned m_unexpected_actuals;
    protected longint unsigned m_overflows;
    protected longint unsigned m_peak_pending;
    protected longint unsigned m_detail_emitted;
    protected longint unsigned m_suppressed_details;
    protected bit m_strict_arrival_warned;
    protected bit m_finalized;

    extern function new(string name="common_uvm_scb", uvm_component parent=null);
    extern virtual function void build_phase(uvm_phase phase);
    extern virtual function bit compare_items(TRANS_TYPE expected,
                                               TRANS_TYPE actual,
                                               int kind,
                                               output string diff);
    extern function void push_expected(TRANS_TYPE tr,
                                       stream_id_t stream_id='1,
                                       int kind=-1);
    extern function void push_actual(TRANS_TYPE tr,
                                     stream_id_t stream_id='1,
                                     int kind=-1);
    extern function scb_status_e get_status();
    extern function bit is_clean();
    extern function string get_summary();
    extern function void print_report(int limit=-2);
    extern function void reset_state(bit clear_counters=1);
    extern virtual function void check_phase(uvm_phase phase);
    extern virtual function void report_phase(uvm_phase phase);

    extern virtual task send_rm_trans_to_cmp(TRANS_TYPE rm_tr,
                                              stream_id_t stream_id='1,
                                              int kind=-1);
    extern virtual task send_dut_trans_to_cmp(TRANS_TYPE dut_tr,
                                               stream_id_t stream_id='1,
                                               int kind=-1);

    protected extern function state_t state_for(stream_id_t stream_id);
    protected extern function bit retained_copy(TRANS_TYPE source,
                                                 stream_id_t stream_id,
                                                 string side,
                                                 output TRANS_TYPE retained);
    protected extern function bit can_enqueue(state_t state,
                                               stream_id_t stream_id,
                                               string side,
                                               int depth);
    protected extern function void reconcile_ordered_exact(state_t state);
    protected extern function void reconcile_ordered_lossy(state_t state);
    protected extern function void reconcile_unordered_expected(state_t state);
    protected extern function void reconcile_unordered_actual(state_t state);
    protected extern function void record_match(state_t state,
                                                 pending_t expected,
                                                 pending_t actual,
                                                 string diff="");
    protected extern function void record_mismatch(state_t state,
                                                    pending_t expected,
                                                    pending_t actual,
                                                    string diff);
    protected extern function void record_drop(state_t state, pending_t expected);
    protected extern function void record_unexpected(state_t state, pending_t actual,
                                                      string reason);
    protected extern function void record_overflow(state_t state,
                                                    stream_id_t stream_id,
                                                    string side,
                                                    TRANS_TYPE tr,
                                                    int kind);
    protected extern function void emit_detail(stream_id_t stream_id,
                                                string id,
                                                string message);
    protected extern function void publish_result(state_t state,
                                                  pending_t expected,
                                                  pending_t actual,
                                                  bit matched,
                                                  string diff);
    protected extern function void update_peak(state_t state);
    protected extern function void finalize_pending();
endclass
```

- [ ] **Step 4: Implement construction, configuration validation, cloning, and queue admission**

Use `uvm_config_db` when supplied, otherwise retain the constructor default. The report plusarg overrides only `m_report_limit`:

```systemverilog
function common_uvm_scb::new(string name="common_uvm_scb", uvm_component parent=null);
    super.new(name, parent);
    m_cfg = new();
    m_result_ap = new("m_result_ap", this);
endfunction

function void common_uvm_scb::build_phase(uvm_phase phase);
    common_uvm_scb_cfg configured;
    int value;
    super.build_phase(phase);
    if (uvm_config_db#(common_uvm_scb_cfg)::get(this, "", "cfg", configured))
        m_cfg = configured;
    if ($value$plusargs("SCB_REPORT_LIMIT=%d", value)) begin
        if (value >= -1) m_cfg.m_report_limit = value;
        else `uvm_warning("SCB_CFG", $sformatf("invalid SCB_REPORT_LIMIT=%0d; using 10", value))
    end
    if (m_cfg.m_report_limit < -1) m_cfg.m_report_limit = 10;
    if (m_cfg.m_err_limit < 0) begin
        `uvm_warning("SCB_CFG", "m_err_limit must be non-negative; using 10")
        m_cfg.m_err_limit = 10;
    end
    if (m_cfg.m_pending_limit < 0) begin
        `uvm_warning("SCB_CFG", "m_pending_limit must be non-negative; using 0")
        m_cfg.m_pending_limit = 0;
    end
endfunction

function common_uvm_scb::state_t common_uvm_scb::state_for(stream_id_t stream_id);
    if (!m_streams.exists(stream_id)) m_streams[stream_id] = new(stream_id);
    return m_streams[stream_id];
endfunction

function bit common_uvm_scb::retained_copy(TRANS_TYPE source,
                                           stream_id_t stream_id,
                                           string side,
                                           output TRANS_TYPE retained);
    uvm_object cloned;
    state_t state = state_for(stream_id);
    retained = null;
    if (source == null) begin
        record_overflow(state, stream_id, side, source, -1);
        emit_detail(stream_id, "SCB_NULL_INPUT", {side, " input is null"});
        return 0;
    end
    if (!m_cfg.m_clone_en) begin
        retained = source;
        return 1;
    end
    cloned = source.clone();
    if ((cloned == null) || !$cast(retained, cloned)) begin
        record_overflow(state, stream_id, side, source, -1);
        emit_detail(stream_id, "SCB_CLONE_FAILED", {side, " input clone failed typed cast"});
        return 0;
    end
    return 1;
endfunction

function bit common_uvm_scb::can_enqueue(state_t state,
                                         stream_id_t stream_id,
                                         string side,
                                         int depth);
    if ((m_cfg.m_pending_limit != 0) && (depth >= m_cfg.m_pending_limit)) begin
        record_overflow(state, stream_id, side, null, -1);
        emit_detail(stream_id, "SCB_PENDING_OVERFLOW",
                    $sformatf("%s pending depth=%0d limit=%0d",
                              side, depth, m_cfg.m_pending_limit));
        return 0;
    end
    return 1;
endfunction
```

Clone failure is accounted as `overflows` in the shared definitive-failure path; the emitted ID distinguishes null, clone, and capacity failures without adding public counters not present in the design.

- [ ] **Step 5: Implement the non-blocking input functions**

```systemverilog
function void common_uvm_scb::push_expected(TRANS_TYPE tr,
                                            stream_id_t stream_id='1,
                                            int kind=-1);
    TRANS_TYPE retained;
    state_t state = state_for(stream_id);
    m_expected_inputs++;
    state.expected_inputs++;
    if (!retained_copy(tr, stream_id, "expected", retained)) return;
    if (!can_enqueue(state, stream_id, "expected", state.expected_q.size())) return;
    state.expected_q.push_back(new(retained, kind));
    update_peak(state);
    case (m_cfg.m_cmp_mode)
        SCB_ORDERED_EXACT: reconcile_ordered_exact(state);
        SCB_ORDERED_LOSSY: reconcile_ordered_lossy(state);
        SCB_UNORDERED:     reconcile_unordered_expected(state);
    endcase
endfunction

function void common_uvm_scb::push_actual(TRANS_TYPE tr,
                                          stream_id_t stream_id='1,
                                          int kind=-1);
    TRANS_TYPE retained;
    state_t state = state_for(stream_id);
    m_actual_inputs++;
    state.actual_inputs++;
    if (m_cfg.m_strict_arrival && (state.expected_q.size() == 0)) begin
        state.diagnostic_warnings++;
        if (!m_strict_arrival_warned) begin
            `uvm_warning("SCB_ACTUAL_FIRST",
                         "actual input arrived before expected; comparison remains order-independent")
            m_strict_arrival_warned = 1;
        end
    end
    if (!retained_copy(tr, stream_id, "actual", retained)) return;
    if (!can_enqueue(state, stream_id, "actual", state.actual_q.size())) return;
    state.actual_q.push_back(new(retained, kind));
    update_peak(state);
    case (m_cfg.m_cmp_mode)
        SCB_ORDERED_EXACT: reconcile_ordered_exact(state);
        SCB_ORDERED_LOSSY: reconcile_ordered_lossy(state);
        SCB_UNORDERED:     reconcile_unordered_actual(state);
    endcase
endfunction

function void common_uvm_scb::update_peak(state_t state);
    longint unsigned depth = state.expected_q.size() + state.actual_q.size();
    longint unsigned total_depth = 0;
    if (depth > state.peak_pending) state.peak_pending = depth;
    foreach (m_streams[id])
        total_depth += m_streams[id].expected_q.size()
                     + m_streams[id].actual_q.size();
    if (total_depth > m_peak_pending) m_peak_pending = total_depth;
endfunction
```

- [ ] **Step 6: Implement the default compare contract and all three policies**

```systemverilog
function bit common_uvm_scb::compare_items(TRANS_TYPE expected,
                                           TRANS_TYPE actual,
                                           int kind,
                                           output string diff);
    return expected.self_define_do_compare(actual, diff, kind);
endfunction

function void common_uvm_scb::reconcile_ordered_exact(state_t state);
    pending_t expected;
    pending_t actual;
    string diff;
    while ((state.expected_q.size() != 0) && (state.actual_q.size() != 0)) begin
        expected = state.expected_q.pop_front();
        actual = state.actual_q.pop_front();
        if (compare_items(expected.tr, actual.tr, expected.kind, diff))
            record_match(state, expected, actual, diff);
        else
            record_mismatch(state, expected, actual, diff);
    end
endfunction

function void common_uvm_scb::reconcile_ordered_lossy(state_t state);
    int match_index;
    string diff;
    while ((state.actual_q.size() != 0) && (state.expected_q.size() != 0)) begin
        match_index = -1;
        foreach (state.expected_q[i]) begin
            if (compare_items(state.expected_q[i].tr,
                              state.actual_q[0].tr,
                              state.expected_q[i].kind,
                              diff)) begin
                match_index = i;
                break;
            end
        end
        if (match_index < 0) return;
        repeat (match_index) record_drop(state, state.expected_q.pop_front());
        record_match(state, state.expected_q.pop_front(),
                     state.actual_q.pop_front(), diff);
    end
endfunction

function void common_uvm_scb::reconcile_unordered_expected(state_t state);
    int match_index = -1;
    string diff;
    pending_t expected = state.expected_q[state.expected_q.size()-1];
    foreach (state.actual_q[i]) begin
        if (compare_items(expected.tr, state.actual_q[i].tr, expected.kind, diff)) begin
            match_index = i;
            break;
        end
    end
    if (match_index >= 0) begin
        void'(state.expected_q.pop_back());
        record_match(state, expected, state.actual_q[match_index], diff);
        state.actual_q.delete(match_index);
    end
endfunction

function void common_uvm_scb::reconcile_unordered_actual(state_t state);
    int match_index = -1;
    string diff;
    pending_t actual = state.actual_q[state.actual_q.size()-1];
    foreach (state.expected_q[i]) begin
        if (compare_items(state.expected_q[i].tr, actual.tr,
                          state.expected_q[i].kind, diff)) begin
            match_index = i;
            break;
        end
    end
    if (match_index >= 0) begin
        void'(state.actual_q.pop_back());
        record_match(state, state.expected_q[match_index], actual, diff);
        state.expected_q.delete(match_index);
    end
endfunction
```

The lossy policy deliberately retains an unmatched oldest actual until later expected input arrives; only check-phase finalization can classify it as unexpected.

- [ ] **Step 7: Implement centralized result publication and accounting**

```systemverilog
function void common_uvm_scb::publish_result(state_t state,
                                             pending_t expected,
                                             pending_t actual,
                                             bit matched,
                                             string diff);
    result_t result = new("result");
    result.stream_id = state.stream_id;
    result.expected = (expected == null) ? null : expected.tr;
    result.actual = (actual == null) ? null : actual.tr;
    result.kind = (expected != null) ? expected.kind
                                     : ((actual != null) ? actual.kind : -1);
    result.matched = matched;
    result.diff = diff;
    m_result_ap.write(result);
endfunction

function void common_uvm_scb::record_match(state_t state,
                                           pending_t expected,
                                           pending_t actual,
                                           string diff="");
    state.matches++;
    m_matches++;
    publish_result(state, expected, actual, 1, diff);
endfunction

function void common_uvm_scb::record_mismatch(state_t state,
                                              pending_t expected,
                                              pending_t actual,
                                              string diff);
    state.mismatches++;
    m_mismatches++;
    publish_result(state, expected, actual, 0, diff);
    emit_detail(state.stream_id, "SCB_MISMATCH", diff);
endfunction

function void common_uvm_scb::record_drop(state_t state, pending_t expected);
    state.allowed_drops++;
    m_allowed_drops++;
endfunction

function void common_uvm_scb::record_unexpected(state_t state,
                                                pending_t actual,
                                                string reason);
    state.unexpected_actuals++;
    m_unexpected_actuals++;
    publish_result(state, null, actual, 0, reason);
    emit_detail(state.stream_id, "SCB_UNEXPECTED_ACTUAL", reason);
endfunction

function void common_uvm_scb::record_overflow(state_t state,
                                              stream_id_t stream_id,
                                              string side,
                                              TRANS_TYPE tr,
                                              int kind);
    state.overflows++;
    m_overflows++;
endfunction

function void common_uvm_scb::emit_detail(stream_id_t stream_id,
                                          string id,
                                          string message);
    state_t state = state_for(stream_id);
    if (m_detail_emitted < m_cfg.m_err_limit) begin
        m_detail_emitted++;
        `uvm_error(id, $sformatf("stream=0x%0h %s", stream_id, message))
    end else begin
        m_suppressed_details++;
        state.suppressed_details++;
    end
endfunction
```

- [ ] **Step 8: Implement legacy task wrappers**

```systemverilog
task common_uvm_scb::send_rm_trans_to_cmp(TRANS_TYPE rm_tr,
                                          stream_id_t stream_id='1,
                                          int kind=-1);
    push_expected(rm_tr, stream_id, kind);
endtask

task common_uvm_scb::send_dut_trans_to_cmp(TRANS_TYPE dut_tr,
                                           stream_id_t stream_id='1,
                                           int kind=-1);
    push_actual(dut_tr, stream_id, kind);
endtask
```

- [ ] **Step 9: Commit the comparison engine before adding reporting/lifecycle**

```bash
git add uvm_gen/templates/common/base_scb.sv.j2 \
        uvm_gen/templates/common/common_scb_types.sv.j2 \
        tests/test_common_scb_v2_generation.py
git commit -m "feat: implement scoreboard v2 comparison engine"
```

### Task 6: Add lifecycle finalization, bounded reports, and typed proxies

**Files:**
- Modify: `uvm_gen/templates/common/base_scb.sv.j2`
- Modify: `uvm_gen/generators/common.py`
- Modify: `uvm_gen/templates/common/common_pkg.sv.j2`
- Test: `tests/test_common_scb_v2_generation.py`

- [ ] **Step 1: Extend tests for lifecycle, suppression, and Top-N reporting**

Append:

```python
def test_v2_finalizes_in_check_and_only_renders_in_report(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core = read(project, "common/common_uvm_scb.sv")
    check_body = core[core.index("function void common_uvm_scb::check_phase"):]
    report_body = core[core.index("function void common_uvm_scb::report_phase"):]
    assert "finalize_pending();" in check_body
    assert "print_report();" in report_body
    assert report_body.index("print_report();") < report_body.index("endfunction")


def test_v2_report_has_limit_and_omission_accounting(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    core = read(project, "common/common_uvm_scb.sv")
    assert "Problem streams: total=%0d shown=%0d omitted=%0d" in core
    assert "limit == -2" in core
    assert "limit == -1" in core
    assert "m_suppressed_details" in core
    assert "normal streams" not in core.lower()


def test_non_aip_common_has_no_adapter(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=False)
    assert not (project / "common/common_scb_aip_adapter.sv").exists()
    common_files = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (project / "common").glob("*.sv")
    )
    assert "aip_cmd" not in common_files
```

- [ ] **Step 2: Add a stable row ordering helper and report-row builder**

Add these protected declarations to the component contract:

```systemverilog
    protected common_scb_control_proxy m_proxy;
    protected extern function bit row_before(common_scb_problem_row left,
                                              common_scb_problem_row right);
    protected extern function common_scb_problem_row make_row(state_t state);
```

Implement deterministic severity/issue/ID ordering:

```systemverilog
function bit common_uvm_scb::row_before(common_scb_problem_row left,
                                        common_scb_problem_row right);
    if (left.status != right.status) return left.status > right.status;
    if (left.issue_count != right.issue_count)
        return left.issue_count > right.issue_count;
    return left.stream_id < right.stream_id;
endfunction

function common_scb_problem_row common_uvm_scb::make_row(state_t state);
    common_scb_problem_row row = new();
    longint unsigned pending_expected = state.expected_q.size();
    longint unsigned pending_actual = state.actual_q.size();
    if ((state.mismatches + state.unexpected_actuals + state.overflows) != 0)
        row.status = SCB_FAIL;
    else if ((state.allowed_drops + state.diagnostic_warnings
              + pending_expected + pending_actual) != 0)
        row.status = SCB_WARN;
    else
        row.status = SCB_PASS;
    row.stream_id = state.stream_id;
    row.issue_count = state.issue_count();
    row.cells = '{
        row.status.name(),
        $sformatf("0x%0h", state.stream_id),
        $sformatf("%0d", state.matches),
        $sformatf("%0d", state.mismatches),
        $sformatf("%0d", state.allowed_drops),
        $sformatf("%0d", state.unexpected_actuals),
        $sformatf("%0d", pending_expected),
        $sformatf("%0d", pending_actual),
        $sformatf("%0d", state.overflows),
        $sformatf("%0d", state.peak_pending)
    };
    return row;
endfunction
```

- [ ] **Step 3: Implement status, summary, clean-state, and non-destructive rendering**

```systemverilog
function scb_status_e common_uvm_scb::get_status();
    longint unsigned diagnostics = 0;
    foreach (m_streams[id]) diagnostics += m_streams[id].diagnostic_warnings;
    if ((m_mismatches + m_unexpected_actuals + m_overflows) != 0)
        return SCB_FAIL;
    if ((m_allowed_drops + diagnostics) != 0) return SCB_WARN;
    return SCB_PASS;
endfunction

function bit common_uvm_scb::is_clean();
    foreach (m_streams[id]) begin
        if ((m_streams[id].expected_q.size() != 0)
            || (m_streams[id].actual_q.size() != 0)) return 0;
    end
    return get_status() == SCB_PASS;
endfunction

function string common_uvm_scb::get_summary();
    longint unsigned pending_expected = 0;
    longint unsigned pending_actual = 0;
    foreach (m_streams[id]) begin
        pending_expected += m_streams[id].expected_q.size();
        pending_actual += m_streams[id].actual_q.size();
    end
    return $sformatf(
        "status=%s expected=%0d actual=%0d match=%0d mismatch=%0d "
        "drop=%0d unexpected=%0d pending_expected=%0d pending_actual=%0d "
        "overflow=%0d peak_pending=%0d suppressed=%0d",
        get_status().name(), m_expected_inputs, m_actual_inputs, m_matches,
        m_mismatches, m_allowed_drops, m_unexpected_actuals,
        pending_expected, pending_actual, m_overflows, m_peak_pending,
        m_suppressed_details);
endfunction

function void common_uvm_scb::print_report(int limit=-2);
    common_scb_problem_row rows[$];
    common_scb_reporter reporter = new();
    string headers[$] = '{"Status", "Stream", "Match", "Mismatch", "Drop",
                          "Unexpected", "PendExp", "PendAct", "Overflow", "Peak"};
    bit numeric[$] = '{0, 0, 1, 1, 1, 1, 1, 1, 1, 1};
    int effective_limit;
    int shown;
    int omitted;

    effective_limit = (limit == -2) ? m_cfg.m_report_limit : limit;
    if (effective_limit < -1) begin
        `uvm_warning("SCB_REPORT_LIMIT",
                     $sformatf("invalid report limit=%0d; using configured limit=%0d",
                               effective_limit, m_cfg.m_report_limit))
        effective_limit = m_cfg.m_report_limit;
    end
    foreach (m_streams[id]) begin
        common_scb_problem_row row = make_row(m_streams[id]);
        if (row.issue_count != 0) begin
            int insert_at = rows.size();
            foreach (rows[i]) begin
                if (row_before(row, rows[i])) begin
                    insert_at = i;
                    break;
                end
            end
            rows.insert(insert_at, row);
        end
    end
    shown = (effective_limit == -1) ? rows.size()
          : ((effective_limit < rows.size()) ? effective_limit : rows.size());
    omitted = rows.size() - shown;
    `uvm_info("SCB_REPORT", get_summary(), UVM_NONE)
    `uvm_info("SCB_REPORT",
              $sformatf("Problem streams: total=%0d shown=%0d omitted=%0d",
                        rows.size(), shown, omitted), UVM_NONE)
    if (shown != 0) begin
        reporter.set_columns(headers, numeric);
        for (int i=0; i<shown; i++) reporter.add_row(rows[i].cells);
        `uvm_info("SCB_REPORT", {"\n", reporter.render()}, UVM_NONE)
    end
endfunction
```

- [ ] **Step 4: Finalize pending entries exactly once in check phase**

```systemverilog
function void common_uvm_scb::finalize_pending();
    if (m_finalized) return;
    foreach (m_streams[id]) begin
        state_t state = m_streams[id];
        if (m_cfg.m_cmp_mode == SCB_ORDERED_LOSSY) begin
            while (state.expected_q.size() != 0)
                record_drop(state, state.expected_q.pop_front());
        end else begin
            while (state.expected_q.size() != 0)
                record_mismatch(state, state.expected_q.pop_front(), null,
                                "expected transaction has no actual match at check phase");
        end
        while (state.actual_q.size() != 0)
            record_unexpected(state, state.actual_q.pop_front(),
                              "actual transaction has no expected match at check phase");
    end
    m_finalized = 1;
endfunction

function void common_uvm_scb::check_phase(uvm_phase phase);
    super.check_phase(phase);
    finalize_pending();
    case (get_status())
        SCB_FAIL: `uvm_error("SCB_FINAL", get_summary())
        SCB_WARN: `uvm_warning("SCB_FINAL", get_summary())
        default:  `uvm_info("SCB_FINAL", get_summary(), UVM_LOW)
    endcase
endfunction

function void common_uvm_scb::report_phase(uvm_phase phase);
    super.report_phase(phase);
    if (m_cfg.m_report_en) print_report();
    if (m_suppressed_details != 0)
        `uvm_warning("SCB_SUPPRESSED",
                     $sformatf("%0d runtime detail messages suppressed (limit=%0d)",
                               m_suppressed_details, m_cfg.m_err_limit))
endfunction
```

- [ ] **Step 5: Implement complete reset semantics**

```systemverilog
function void common_uvm_scb::reset_state(bit clear_counters=1);
    m_streams.delete();
    m_finalized = 0;
    m_strict_arrival_warned = 0;
    if (clear_counters) begin
        m_expected_inputs = 0;
        m_actual_inputs = 0;
        m_matches = 0;
        m_mismatches = 0;
        m_allowed_drops = 0;
        m_unexpected_actuals = 0;
        m_overflows = 0;
        m_peak_pending = 0;
        m_detail_emitted = 0;
        m_suppressed_details = 0;
    end
endfunction
```

- [ ] **Step 6: Define and register a typed proxy without importing AIP**

After the core class declaration and before its out-of-class method bodies, add:

```systemverilog
class common_scb_typed_proxy #(type TRANS_TYPE=uvm_sequence_item,
                               int STREAM_ID_WIDTH=64)
    extends common_scb_control_proxy;
    typedef common_uvm_scb#(TRANS_TYPE, STREAM_ID_WIDTH) scoreboard_t;
    protected scoreboard_t m_scoreboard;

    function new(string name, scoreboard_t scoreboard);
        super.new(name);
        m_scoreboard = scoreboard;
    endfunction
    virtual function string scoreboard_name();
        return m_scoreboard.get_full_name();
    endfunction
    virtual function scb_status_e status();
        return m_scoreboard.get_status();
    endfunction
    virtual function string summary();
        return m_scoreboard.get_summary();
    endfunction
    virtual function void report(int limit=-2);
        m_scoreboard.print_report(limit);
    endfunction
    virtual function bit set_report_limit(int limit, output string error);
        if (limit < -1) begin
            error = $sformatf("report limit must be -1 or non-negative, got %0d", limit);
            return 0;
        end
        m_scoreboard.m_cfg.m_report_limit = limit;
        error = "";
        return 1;
    endfunction
endclass
```

At the end of `build_phase()`, register it:

```systemverilog
    begin
        common_scb_typed_proxy#(TRANS_TYPE, STREAM_ID_WIDTH) typed_proxy;
        string registry_error;
        typed_proxy = new({get_name(), "_proxy"}, this);
        m_proxy = typed_proxy;
        if (!common_scb_registry::register_proxy(m_proxy, registry_error))
            `uvm_error("SCB_REGISTRY", registry_error)
    end
```

- [ ] **Step 7: Switch the generator/package from the interim legacy-only state to the final layout**

Set `CommonGenerator.TEMPLATES` to:

```python
TEMPLATES = [
    ("common_lib_pkg.sv", "common/common_pkg.sv.j2"),
    ("common_dec.sv", "common/common_dec.sv.j2"),
    ("common_report_server.sv", "common/report_server.sv.j2"),
    ("common_self_debug_scb.sv", "common/self_debug_scb.sv.j2"),
    ("common_draw_table.sv", "common/draw_table.sv.j2"),
    ("common_scb_types.sv", "common/common_scb_types.sv.j2"),
    ("common_scb_reporter.sv", "common/common_scb_reporter.sv.j2"),
    ("common_scb_registry.sv", "common/common_scb_registry.sv.j2"),
    ("common_uvm_scb_legacy.sv", "common/legacy_scb.sv.j2"),
    ("common_uvm_scb.sv", "common/base_scb.sv.j2"),
]
```

Set the package include body to:

```systemverilog
    `include "common_dec.sv"
    `include "common_draw_table.sv"
    `include "common_report_server.sv"
    `include "common_self_debug_scb.sv"
    `include "common_scb_types.sv"
    `include "common_scb_reporter.sv"
    `include "common_scb_registry.sv"
    `include "common_uvm_scb_legacy.sv"
    `include "common_uvm_scb.sv"
```

At this point every referenced template exists, so generation must be runnable.

- [ ] **Step 8: Run the complete generation contract**

```bash
python3 -m pytest tests/test_common_scb_v2_generation.py -q
```

Expected: all tests added through this task pass for both platform parameters.

- [ ] **Step 9: Commit lifecycle/reporting and final common generation layout**

```bash
git add uvm_gen/templates/common/base_scb.sv.j2 \
        uvm_gen/templates/common/common_pkg.sv.j2 \
        uvm_gen/generators/common.py \
        tests/test_common_scb_v2_generation.py
git commit -m "feat: add bounded scoreboard lifecycle reporting"
```

### Task 7: Wire typed v2 scoreboards into Advance and PORT

**Files:**
- Modify: `uvm_gen/templates/advance/agent/trans.sv.j2`
- Modify: `uvm_gen/templates/port/agent/trans.sv.j2`
- Modify: `uvm_gen/templates/advance/env/rm.sv.j2`
- Modify: `uvm_gen/templates/advance/env/checker.sv.j2`
- Modify: `uvm_gen/templates/advance/env/env.sv.j2`
- Modify: `uvm_gen/templates/port/env/checker.sv.j2`
- Test: `tests/test_common_scb_v2_generation.py`

- [ ] **Step 1: Add failing typed-wiring and transaction-hook tests**

Append:

```python
def test_transactions_expose_default_scb_routing_hooks(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    for agent in ("axi", "apb"):
        trans = read(project, f"env/agents/{agent}_agent/src/{agent}_trans.sv")
        assert "function longint unsigned get_scb_stream_id" in trans
        assert "return '1;" in trans
        assert "function int get_scb_kind" in trans
        assert "return -1;" in trans


def test_checker_owns_one_typed_v2_instance_per_agent(tmp_path, platform_type):
    project = generate(tmp_path, platform_type)
    checker = read(project, "env/top_checker.sv")
    assert "common_uvm_scb#(axi_trans) m_axi_scb" in checker
    assert "common_uvm_scb#(apb_trans) m_apb_scb" in checker
    assert "m_axi_scb.push_expected" in checker
    assert "m_axi_scb.push_actual" in checker
    assert "get_scb_stream_id()" in checker
    assert "get_scb_kind()" in checker
    assert "function void reset_state" in checker


def test_advance_rm_and_env_have_real_expected_actual_paths(tmp_path):
    project = generate(tmp_path, PlatformType.ADVANCE)
    rm = read(project, "env/top_rm.sv")
    env = read(project, "env/top_env.sv")
    assert "uvm_analysis_port#(axi_trans) m_axi_expected_ap" in rm
    assert "m_axi_expected_ap.write" in rm
    assert "m_rm.m_axi_expected_ap.connect(m_scb.m_from_rm_axi_imp)" in env
    assert "m_axi_agt.m_mon.m_ap.connect(m_scb.m_from_agt_axi_imp)" in env


def test_port_checker_workers_feed_v2(tmp_path):
    project = generate(tmp_path, PlatformType.PORT)
    checker = read(project, "env/top_checker.sv")
    assert "m_from_rm_axi_trans_port.get(tr);" in checker
    assert "m_axi_scb.push_expected(tr" in checker
    assert "m_from_agt_axi_trans_port.get(tr);" in checker
    assert "m_axi_scb.push_actual(tr" in checker
```

- [ ] **Step 2: Add default stream/kind hooks to both transaction templates**

Insert immediately after `self_define_do_compare()` in both templates:

```systemverilog
function longint unsigned get_scb_stream_id();
    return '1;
endfunction

function int get_scb_kind();
    return -1;
endfunction
```

- [ ] **Step 3: Make the Advance RM publish typed predictions**

For each generated agent, declare typed input and expected output endpoints:

```systemverilog
{% for agent in agents %}
    `uvm_analysis_imp_decl(_from_{{ agent.name }}_agt)
    uvm_analysis_imp_from_{{ agent.name }}_agt#({{ agent.name }}_trans,
                                                {{ block_name }}_rm)
        m_from_{{ agent.name }}_agt_imp;
    uvm_analysis_port#({{ agent.name }}_trans) m_{{ agent.name }}_expected_ap;
{% endfor %}
```

Construct each output port in `build_phase()`:

```systemverilog
{% for agent in agents %}
    m_from_{{ agent.name }}_agt_imp = new("m_from_{{ agent.name }}_agt_imp", this);
    m_{{ agent.name }}_expected_ap = new("m_{{ agent.name }}_expected_ap", this);
{% endfor %}
```

Use a typed callback and make the generated skeleton's identity prediction explicit and functional:

```systemverilog
{% for agent in agents %}
function void {{ block_name }}_rm::write_from_{{ agent.name }}_agt(
    {{ agent.name }}_trans tr);
    // Identity prediction keeps the generated environment runnable. Replace
    // the value written here with the protocol/reference-model prediction.
    m_{{ agent.name }}_expected_ap.write(tr);
endfunction
{% endfor %}
```

- [ ] **Step 4: Replace the Advance checker placeholders with typed v2 instances**

For each agent, declare typed analysis imps and a typed scoreboard:

```systemverilog
{% for agent in agents %}
    `uvm_analysis_imp_decl(_from_rm_{{ agent.name }})
    `uvm_analysis_imp_decl(_from_agt_{{ agent.name }})
    uvm_analysis_imp_from_rm_{{ agent.name }}#({{ agent.name }}_trans,
                                                {{ block_name }}_checker)
        m_from_rm_{{ agent.name }}_imp;
    uvm_analysis_imp_from_agt_{{ agent.name }}#({{ agent.name }}_trans,
                                                 {{ block_name }}_checker)
        m_from_agt_{{ agent.name }}_imp;
    common_uvm_scb#({{ agent.name }}_trans) m_{{ agent.name }}_scb;
{% endfor %}
```

Construct all three objects per agent:

```systemverilog
{% for agent in agents %}
    m_from_rm_{{ agent.name }}_imp = new("m_from_rm_{{ agent.name }}_imp", this);
    m_from_agt_{{ agent.name }}_imp = new("m_from_agt_{{ agent.name }}_imp", this);
    m_{{ agent.name }}_scb = common_uvm_scb#({{ agent.name }}_trans)::type_id::create(
        "m_{{ agent.name }}_scb", this);
{% endfor %}
```

Use typed function callbacks; they are legal because the core input APIs are functions:

```systemverilog
{% for agent in agents %}
function void {{ block_name }}_checker::write_from_rm_{{ agent.name }}(
    {{ agent.name }}_trans tr);
    m_scb_rec_rm_trans_total_cnt++;
    m_{{ agent.name }}_scb.push_expected(
        tr, tr.get_scb_stream_id(), tr.get_scb_kind());
endfunction

function void {{ block_name }}_checker::write_from_agt_{{ agent.name }}(
    {{ agent.name }}_trans tr);
    m_scb_rec_dut_trans_total_cnt++;
    m_{{ agent.name }}_scb.push_actual(
        tr, tr.get_scb_stream_id(), tr.get_scb_kind());
endfunction
{% endfor %}
```

Add the explicit reset hook and invoke it from the UVM reset phase:

```systemverilog
extern virtual function void reset_state();
extern virtual task reset_phase(uvm_phase phase);

function void {{ block_name }}_checker::reset_state();
{% for agent in agents %}
    m_{{ agent.name }}_scb.reset_state();
{% endfor %}
endfunction

task {{ block_name }}_checker::reset_phase(uvm_phase phase);
    super.reset_phase(phase);
    reset_state();
endtask
```

- [ ] **Step 5: Connect the Advance monitor, RM, and checker**

Replace the connection placeholders with:

```systemverilog
{% for agent in agents %}
    m_{{ agent.name }}_agt.m_mon.m_ap.connect(m_rm.m_from_{{ agent.name }}_agt_imp);
    m_rm.m_{{ agent.name }}_expected_ap.connect(
        m_scb.m_from_rm_{{ agent.name }}_imp);
    m_{{ agent.name }}_agt.m_mon.m_ap.connect(
        m_scb.m_from_agt_{{ agent.name }}_imp);
{% endfor %}
```

- [ ] **Step 6: Make PORT checker workers feed the same v2 API**

Declare one typed instance per agent:

```systemverilog
{% for agent in agents %}
    common_uvm_scb#({{ agent.name }}_trans) m_{{ agent.name }}_scb;
{% endfor %}
```

Construct it after the existing blocking-get ports:

```systemverilog
{% for agent in agents %}
    m_from_rm_{{ agent.name }}_trans_port = new(
        "m_from_rm_{{ agent.name }}_trans_port", this);
    m_from_agt_{{ agent.name }}_trans_port = new(
        "m_from_agt_{{ agent.name }}_trans_port", this);
    m_{{ agent.name }}_scb = common_uvm_scb#({{ agent.name }}_trans)::type_id::create(
        "m_{{ agent.name }}_scb", this);
{% endfor %}
```

Replace the expected worker placeholder with:

```systemverilog
this.m_{{ agent.name }}_scb.push_expected(
    tr, tr.get_scb_stream_id(), tr.get_scb_kind());
```

and:

```systemverilog
this.m_{{ agent.name }}_scb.push_actual(
    tr, tr.get_scb_stream_id(), tr.get_scb_kind());
```

Add these declarations and complete implementations:

```systemverilog
extern virtual function void reset_state();
extern virtual task reset_phase(uvm_phase phase);

function void {{ block_name }}_checker::reset_state();
{% for agent in agents %}
    m_{{ agent.name }}_scb.reset_state();
{% endfor %}
endfunction

task {{ block_name }}_checker::reset_phase(uvm_phase phase);
    super.reset_phase(phase);
    reset_state();
endtask
```

Keep the existing PORT FIFO topology and RM identity-prediction output unchanged.

- [ ] **Step 7: Run typed-wiring tests and all generation tests**

```bash
python3 -m pytest tests/test_common_scb_v2_generation.py -q
python3 -m pytest -q
```

Expected: all collected Python tests pass; AIP runtime generation tests remain green.

- [ ] **Step 8: Commit generated-environment integration**

```bash
git add uvm_gen/templates/advance/agent/trans.sv.j2 \
        uvm_gen/templates/port/agent/trans.sv.j2 \
        uvm_gen/templates/advance/env/rm.sv.j2 \
        uvm_gen/templates/advance/env/checker.sv.j2 \
        uvm_gen/templates/advance/env/env.sv.j2 \
        uvm_gen/templates/port/env/checker.sv.j2 \
        tests/test_common_scb_v2_generation.py
git commit -m "feat: wire generated checkers to scoreboard v2"
```

### Task 8: Add the optional four-command AIP adapter

**Files:**
- Create: `uvm_gen/templates/common/common_scb_aip_adapter.sv.j2`
- Modify: `uvm_gen/generators/common.py:17-37`
- Test: `tests/test_common_scb_v2_generation.py`

- [ ] **Step 1: Add failing adapter-presence and command tests**

Append:

```python
def test_aip_output_has_non_destructive_scb_adapter(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    adapter_path = project / "common/common_scb_aip_adapter.sv"
    assert adapter_path.exists()
    adapter = adapter_path.read_text(encoding="utf-8")
    for command in ("scb_list", "scb_status", "scb_report", "scb_set_limit"):
        assert command in adapter
    assert "scb_clear" not in adapter
    assert "reset_state" not in adapter


def test_aip_adapter_is_compiled_after_common_package(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    filelist = read(project, "common/common_lib_pkg.f")
    assert filelist.index("./common_lib_pkg.sv") < filelist.index(
        "./common_scb_aip_adapter.sv"
    )
    tb_filelist = read(project, "cfg/tb.f")
    assert tb_filelist.index("$AIP_CORE_HOME/aip_core_pkg.sv") < tb_filelist.index(
        "-F   ./env.f"
    )
```

- [ ] **Step 2: Create the adapter with explicit status/result forwarding**

```systemverilog
{{ header(file_name) }}
`ifndef COMMON_SCB_AIP_ADAPTER__SV
`define COMMON_SCB_AIP_ADAPTER__SV

import aip_core_pkg::*;
import common_lib_pkg::*;

class common_scb_aip_adapter;
    protected static task finish(int status, string result);
        aip_cmd::__aip_cmd_last_status = status;
        aip_cmd::__aip_cmd_last_result = result;
    endtask

    protected static function common_scb_control_proxy lookup(string name,
                                                               output string error);
        common_scb_control_proxy proxy = common_scb_registry::find(name);
        if (proxy == null)
            error = $sformatf("unknown scoreboard '%s'", name);
        else
            error = "";
        return proxy;
    endfunction

    static task list(string unused);
        string names[$];
        string result = "";
        common_scb_registry::get_names(names);
        foreach (names[i])
            result = {result, (i == 0) ? "" : "\n", names[i]};
        finish(0, result);
    endtask

    static task status(string name);
        string error;
        common_scb_control_proxy proxy = lookup(name, error);
        if (proxy == null) begin
            finish(-1, error);
            return;
        end
        finish(0, proxy.summary());
    endtask

    static task report(string name, string limit_text);
        string error;
        int limit;
        common_scb_control_proxy proxy = lookup(name, error);
        if (proxy == null) begin
            finish(-1, error);
            return;
        end
        if (($sscanf(limit_text, "%d", limit) != 1) || (limit < -2)) begin
            finish(-1, $sformatf("invalid report limit '%s'", limit_text));
            return;
        end
        proxy.report(limit);
        finish(0, proxy.summary());
    endtask

    static task set_limit(string name, string limit_text);
        string error;
        int limit;
        common_scb_control_proxy proxy = lookup(name, error);
        if (proxy == null) begin
            finish(-1, error);
            return;
        end
        if ($sscanf(limit_text, "%d", limit) != 1) begin
            finish(-1, $sformatf("invalid report limit '%s'", limit_text));
            return;
        end
        if (!proxy.set_report_limit(limit, error)) begin
            finish(-1, error);
            return;
        end
        finish(0, $sformatf("%s report_limit=%0d", name, limit));
    endtask
endclass

`aip_cmd_str_1i_status(scb_list, common_scb_aip_adapter::list, unused, "")
`aip_cmd_str_1i_status(scb_status, common_scb_aip_adapter::status, name, "")
`aip_cmd_str_2i_status(scb_report, common_scb_aip_adapter::report,
                       name, "", limit, "-2")
`aip_cmd_str_2i_status(scb_set_limit, common_scb_aip_adapter::set_limit,
                       name, "", limit, "")

`endif
```

Calling `scb_list` with no arguments uses the macro's empty default. `scb_report` accepts API sentinel `-2`, while `scb_set_limit` accepts only `-1` or non-negative values through the proxy validation.

- [ ] **Step 3: Generate and compile the adapter only when AIP is enabled**

After the existing activity-subscriber generation in `CommonGenerator.generate()`, add:

```python
        if self.cfg.aip_core:
            content = self.render_template(
                "common/common_scb_aip_adapter.sv.j2",
                file_name="common_scb_aip_adapter.sv",
            )
            self.write_file(
                os.path.join(output_dir, "common_scb_aip_adapter.sv"), content
            )
```

Build the AIP portion of `common_lib_pkg.f` in this order:

```python
        if self.cfg.aip_core:
            f_content += "./aip_activity_subscriber.sv\n"
            f_content += "./common_scb_aip_adapter.sv\n"
```

- [ ] **Step 4: Run AIP-on/off generation tests**

```bash
python3 -m pytest tests/test_common_scb_v2_generation.py \
  -k 'aip or adapter' -q
python3 -m pytest tests/test_aip_runtime_integration.py -q
```

Expected: adapter tests pass for both platforms; all earlier AIP runtime contracts remain green.

- [ ] **Step 5: Commit the optional adapter**

```bash
git add uvm_gen/templates/common/common_scb_aip_adapter.sv.j2 \
        uvm_gen/generators/common.py \
        tests/test_common_scb_v2_generation.py
git commit -m "feat: expose scoreboard status through optional AIP adapter"
```

### Task 9: Add simulator-level semantic and reporting tests

**Files:**
- Create: `tests/vcs/common_scb_unit_tb.sv`
- Create: `tests/vcs/run_common_scb_v2.sh`

- [ ] **Step 1: Create a self-checking UVM unit test**

```systemverilog
`timescale 1ns/1ps

module common_scb_unit_tb;
    import uvm_pkg::*;
    import common_lib_pkg::*;
    `include "uvm_macros.svh"

    class scb_item extends uvm_sequence_item;
        rand int value;
        `uvm_object_utils_begin(scb_item)
            `uvm_field_int(value, UVM_ALL_ON)
        `uvm_object_utils_end
        function new(string name="scb_item");
            super.new(name);
        endfunction
        function bit self_define_do_compare(scb_item actual,
                                            output string diff,
                                            input int kind=-1);
            if ((actual != null) && (value == actual.value)) begin
                diff = "";
                return 1;
            end
            diff = $sformatf("expected=%0d actual=%0d",
                             value, (actual == null) ? 'x : actual.value);
            return 0;
        endfunction
    endclass

    class common_scb_unit_test extends uvm_test;
        `uvm_component_utils(common_scb_unit_test)
        common_uvm_scb#(scb_item) m_exact_pass;
        common_uvm_scb#(scb_item) m_exact_fail;
        common_uvm_scb#(scb_item) m_lossy;
        common_uvm_scb#(scb_item) m_unordered;
        common_uvm_scb#(scb_item) m_overflow;
        common_uvm_scb#(scb_item) m_many;
        common_uvm_scb#(scb_item) m_strict;
        common_uvm_scb#(scb_item) m_reset;
        common_uvm_scb#(scb_item) m_clone_error;

        function new(string name="common_scb_unit_test", uvm_component parent=null);
            super.new(name, parent);
        endfunction

        function scb_item item(int value);
            scb_item result = new($sformatf("item_%0d", value));
            result.value = value;
            return result;
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            m_exact_pass = common_uvm_scb#(scb_item)::type_id::create(
                "m_exact_pass", this);
            m_exact_fail = common_uvm_scb#(scb_item)::type_id::create(
                "m_exact_fail", this);
            m_lossy = common_uvm_scb#(scb_item)::type_id::create(
                "m_lossy", this);
            m_unordered = common_uvm_scb#(scb_item)::type_id::create(
                "m_unordered", this);
            m_overflow = common_uvm_scb#(scb_item)::type_id::create(
                "m_overflow", this);
            m_many = common_uvm_scb#(scb_item)::type_id::create(
                "m_many", this);
            m_strict = common_uvm_scb#(scb_item)::type_id::create(
                "m_strict", this);
            m_reset = common_uvm_scb#(scb_item)::type_id::create(
                "m_reset", this);
            m_clone_error = common_uvm_scb#(scb_item)::type_id::create(
                "m_clone_error", this);

            m_exact_pass.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_exact_fail.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_lossy.m_cfg.m_cmp_mode = SCB_ORDERED_LOSSY;
            m_unordered.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_overflow.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_overflow.m_cfg.m_pending_limit = 1;
            m_many.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_many.m_cfg.m_err_limit = 0;
            m_strict.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_strict.m_cfg.m_strict_arrival = 1;
            m_clone_error.m_cfg.m_err_limit = 0;
        endfunction

        task run_phase(uvm_phase phase);
            scb_item mutable;
            phase.raise_objection(this);

            mutable = item(7);
            m_exact_pass.push_actual(mutable);
            mutable.value = 99;
            m_exact_pass.push_expected(item(7));

            m_exact_fail.push_expected(item(1));
            m_exact_fail.push_actual(item(2));

            m_lossy.push_expected(item(10));
            m_lossy.push_expected(item(20));
            m_lossy.push_actual(item(20));

            m_unordered.push_expected(item(1));
            m_unordered.push_expected(item(2));
            m_unordered.push_actual(item(2));
            m_unordered.push_actual(item(1));

            m_overflow.push_expected(item(30));
            m_overflow.push_expected(item(31));

            for (int i=0; i<15; i++)
                m_many.push_actual(item(i), i);

            m_strict.push_actual(item(40));
            m_strict.push_expected(item(40));

            m_reset.push_expected(item(50));
            m_reset.reset_state();

            m_clone_error.push_expected(null);

            phase.drop_objection(this);
        endtask

        function void final_phase(uvm_phase phase);
            super.final_phase(phase);
            if (m_exact_pass.get_status() != SCB_PASS)
                `uvm_fatal("SCB_UNIT", "actual-before-expected or clone test failed")
            if (m_exact_fail.get_status() != SCB_FAIL)
                `uvm_fatal("SCB_UNIT", "ordered mismatch was not a failure")
            if (m_lossy.get_status() != SCB_WARN)
                `uvm_fatal("SCB_UNIT", "lossy expected drop was not a warning")
            if (m_unordered.get_status() != SCB_PASS)
                `uvm_fatal("SCB_UNIT", "unordered matching failed")
            if (m_overflow.get_status() != SCB_FAIL)
                `uvm_fatal("SCB_UNIT", "pending guard did not fail")
            if (m_many.get_status() != SCB_FAIL)
                `uvm_fatal("SCB_UNIT", "residual actuals were not finalized")
            if (m_strict.get_status() != SCB_WARN)
                `uvm_fatal("SCB_UNIT", "strict actual-first diagnostic was not a warning")
            if (!m_reset.is_clean())
                `uvm_fatal("SCB_UNIT", "reset_state left pending data or counters")
            if (m_clone_error.get_status() != SCB_FAIL)
                `uvm_fatal("SCB_UNIT", "null/clone input failure was not counted")
            $display("SCB_UNIT_PASS");
        endfunction
    endclass

    initial run_test("common_scb_unit_test");
endmodule
```

- [ ] **Step 2: Create the VCS runner for default, summary-only, and all-row modes**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 GENERATED_COMMON_DIR UNIT_TB" >&2
  exit 2
fi

common_dir=$1
unit_tb=$2
unit_tb=$(realpath "${unit_tb}")

(
  cd "${common_dir}"
  vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    -f common_lib_pkg.f "${unit_tb}" -top common_scb_unit_tb \
    -o simv_scb_unit -l compile_scb_unit.log

  ./simv_scb_unit +UVM_TESTNAME=common_scb_unit_test -l run_scb_default.log
  grep -F "SCB_UNIT_PASS" run_scb_default.log
  grep -F "Problem streams: total=15 shown=10 omitted=5" run_scb_default.log
  grep -F "suppressed=15" run_scb_default.log

  ./simv_scb_unit +UVM_TESTNAME=common_scb_unit_test \
    +SCB_REPORT_LIMIT=0 -l run_scb_summary.log
  grep -F "SCB_UNIT_PASS" run_scb_summary.log
  grep -F "Problem streams: total=15 shown=0 omitted=15" run_scb_summary.log

  ./simv_scb_unit +UVM_TESTNAME=common_scb_unit_test \
    +SCB_REPORT_LIMIT=-1 -l run_scb_all.log
  grep -F "SCB_UNIT_PASS" run_scb_all.log
  grep -F "Problem streams: total=15 shown=15 omitted=0" run_scb_all.log
)

echo "Scoreboard v2 unit matrix passed"
```

- [ ] **Step 3: Syntax-check the shell runner**

```bash
chmod +x tests/vcs/run_common_scb_v2.sh
bash -n tests/vcs/run_common_scb_v2.sh
```

Expected: exit code `0`, no output.

- [ ] **Step 4: Commit simulator-level tests before running them remotely**

```bash
git add tests/vcs/common_scb_unit_tb.sv tests/vcs/run_common_scb_v2.sh
git commit -m "test: add scoreboard v2 VCS semantic matrix"
```

### Task 10: Add and run the generated-project VCS matrix

**Files:**
- Create: `tests/vcs/run_generated_scb_matrix.sh`
- Create: `tests/vcs/scb_adapter_smoke.tcl`

- [ ] **Step 1: Add the fixed AIP adapter smoke input**

```tcl
source $env(AIP_CORE_HOME)/aip_cmd.tcl
scb_list
scb_status name=uvm_test_top.m_env.m_scb.m_axi_scb
scb_report name=uvm_test_top.m_env.m_scb.m_axi_scb limit=0
scb_set_limit name=uvm_test_top.m_env.m_scb.m_axi_scb limit=-1
end_test idle=1us timeout=10us
```

- [ ] **Step 2: Add a remote-host runner for Advance/PORT × AIP off/on**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 6 ]]; then
  echo "usage: $0 ADVANCE_OFF ADVANCE_ON PORT_OFF PORT_ON AIP_CORE_DIR ADAPTER_TCL" >&2
  exit 2
fi

advance_off=$1
advance_on=$2
port_off=$3
port_on=$4
aip_core_dir=$5
adapter_tcl=$6
adapter_tcl=$(realpath "${adapter_tcl}")

compile_and_run_base() {
  local project_dir=$1
  local label=$2
  (
    cd "${project_dir}/cfg"
    vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
      -f tb.f -top harness -o simv -l "compile_${label}.log"
    timeout 60s ./simv +UVM_TESTNAME=tc_base -l "run_${label}_base.log"
    grep -F "TC PASSED." "run_${label}_base.log"
  )
}

run_adapter_smoke() {
  local project_dir=$1
  local label=$2
  (
    cd "${project_dir}/cfg"
    timeout 60s ./simv -ucli -i "${adapter_tcl}" \
      +UVM_TESTNAME=tc_tcl -l "run_${label}_adapter.log"
    grep -F "TC PASSED." "run_${label}_adapter.log"
    grep -F "uvm_test_top.m_env.m_scb.m_axi_scb" "run_${label}_adapter.log"
  )
}

export AIP_CORE_HOME="${aip_core_dir}"
compile_and_run_base "${advance_off}" advance_off
compile_and_run_base "${advance_on}" advance_on
run_adapter_smoke "${advance_on}" advance_on
compile_and_run_base "${port_off}" port_off
compile_and_run_base "${port_on}" port_on
run_adapter_smoke "${port_on}" port_on

echo "Generated scoreboard v2 matrix passed"
```

- [ ] **Step 3: Syntax-check and commit the matrix runner**

```bash
chmod +x tests/vcs/run_generated_scb_matrix.sh
bash -n tests/vcs/run_generated_scb_matrix.sh
git add tests/vcs/run_generated_scb_matrix.sh tests/vcs/scb_adapter_smoke.tcl
git commit -m "test: add generated scoreboard integration matrix"
```

- [ ] **Step 4: Generate all four projects from the implementation revision**

```bash
rm -rf /tmp/uvm-gen-scb-matrix
mkdir -p /tmp/uvm-gen-scb-matrix/{advance_off,advance_on,port_off,port_on}
python3 - <<'PY'
from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator

for platform, aip_core, leaf in (
    (PlatformType.ADVANCE, False, "advance_off"),
    (PlatformType.ADVANCE, True,  "advance_on"),
    (PlatformType.PORT,    False, "port_off"),
    (PlatformType.PORT,    True,  "port_on"),
):
    cfg = ProjectConfig(
        block_name="top",
        author="vcs-smoke",
        platform_type=platform,
        agents=[AgentConfig(name="axi")],
        output_dir=f"/tmp/uvm-gen-scb-matrix/{leaf}",
        aip_core=aip_core,
    )
    PlatformGenerator(cfg).generate()
PY
```

- [ ] **Step 5: Transfer artifacts without persisting credentials**

Enter the supplied SSH password interactively. Do not put it in the scripts or git configuration.

```bash
ssh ubuntu@10.11.10.53 'mkdir -p /tmp/uvm-gen-scb-validation'
scp -r /tmp/uvm-gen-scb-matrix ubuntu@10.11.10.53:/tmp/uvm-gen-scb-validation/
scp -r /home/ryan/workspace/ryan/aip_core ubuntu@10.11.10.53:/tmp/uvm-gen-scb-validation/
scp tests/vcs/common_scb_unit_tb.sv \
    tests/vcs/run_common_scb_v2.sh \
    tests/vcs/run_generated_scb_matrix.sh \
    tests/vcs/scb_adapter_smoke.tcl \
    ubuntu@10.11.10.53:/tmp/uvm-gen-scb-validation/
```

- [ ] **Step 6: Run semantic/report tests in a remote login shell**

```bash
ssh -t ubuntu@10.11.10.53 \
  'bash -lc "/tmp/uvm-gen-scb-validation/run_common_scb_v2.sh \
  /tmp/uvm-gen-scb-validation/uvm-gen-scb-matrix/advance_off/top/common \
  /tmp/uvm-gen-scb-validation/common_scb_unit_tb.sv"'
```

Expected: `SCB_UNIT_PASS` appears in all three runs; default is `total=15 shown=10 omitted=5`, `+SCB_REPORT_LIMIT=0` is `shown=0 omitted=15`, and `-1` is `shown=15 omitted=0`.

- [ ] **Step 7: Run the generated integration/AIP-adapter matrix**

```bash
ssh -t ubuntu@10.11.10.53 \
  'bash -lc "/tmp/uvm-gen-scb-validation/run_generated_scb_matrix.sh \
  /tmp/uvm-gen-scb-validation/uvm-gen-scb-matrix/advance_off/top \
  /tmp/uvm-gen-scb-validation/uvm-gen-scb-matrix/advance_on/top \
  /tmp/uvm-gen-scb-validation/uvm-gen-scb-matrix/port_off/top \
  /tmp/uvm-gen-scb-validation/uvm-gen-scb-matrix/port_on/top \
  /tmp/uvm-gen-scb-validation/aip_core \
  /tmp/uvm-gen-scb-validation/scb_adapter_smoke.tcl"'
```

Expected: four generated projects compile and pass `tc_base`; both AIP-enabled projects execute all four adapter commands and pass `tc_tcl`; final line is `Generated scoreboard v2 matrix passed`.

- [ ] **Step 8: Correct simulator portability issues with focused commits**

For each VCS-discovered issue, add a minimal Python/static regression when possible, make the correction, rerun Tasks 9–10 completely, then commit the exact files:

```bash
git add uvm_gen/generators/common.py \
        uvm_gen/templates/common/common_pkg.sv.j2 \
        uvm_gen/templates/common/common_scb_types.sv.j2 \
        uvm_gen/templates/common/common_scb_reporter.sv.j2 \
        uvm_gen/templates/common/common_scb_registry.sv.j2 \
        uvm_gen/templates/common/base_scb.sv.j2 \
        uvm_gen/templates/common/common_scb_aip_adapter.sv.j2 \
        uvm_gen/templates/advance/agent/trans.sv.j2 \
        uvm_gen/templates/port/agent/trans.sv.j2 \
        uvm_gen/templates/advance/env/rm.sv.j2 \
        uvm_gen/templates/advance/env/checker.sv.j2 \
        uvm_gen/templates/advance/env/env.sv.j2 \
        uvm_gen/templates/port/env/checker.sv.j2 \
        tests/test_common_scb_v2_generation.py \
        tests/vcs/common_scb_unit_tb.sv \
        tests/vcs/run_common_scb_v2.sh \
        tests/vcs/scb_adapter_smoke.tcl \
        tests/vcs/run_generated_scb_matrix.sh
git commit -m "fix: make scoreboard v2 VCS portable"
```

### Task 11: Document public behavior and perform final verification

**Files:**
- Modify: `README.md`
- Verify: all source and test files in this plan

- [ ] **Step 1: Add concise user-facing scoreboard documentation**

Add a `Common Scoreboard v2` section that states:

```markdown
## Common Scoreboard v2

Generated checkers create one typed `common_uvm_scb` per agent. Transactions
default to stream ID `'1` and kind `-1`; override `get_scb_stream_id()` and
`get_scb_kind()` for protocol-specific routing. The core supports ordered
exact, ordered with DUT loss, and unordered comparison, and clones retained
transactions by default.

Final reports print aggregate totals and at most 10 problem streams. Override
the row count with `+SCB_REPORT_LIMIT=N`: `0` prints only the summary and `-1`
prints all problem streams. Omitted rows are always counted; no complete
CSV/text dump is produced by default. Runtime mismatch detail uses the
separate global `m_err_limit`.

The previous implementation remains available as `common_uvm_scb_legacy`.
With `--aip-core`, `scb_list`, `scb_status`, `scb_report`, and
`scb_set_limit` provide non-destructive runtime inspection. Scoreboard reset
or clear is intentionally not exposed through AIP commands.
```

- [ ] **Step 2: Scan naming, placeholder, and AIP-boundary invariants**

```bash
rg -n 'class common_uvm_scb#|class common_uvm_scb\s' \
  uvm_gen/templates/common/legacy_scb.sv.j2
rg -n '\baip_|AIP_' \
  uvm_gen/templates/common/base_scb.sv.j2 \
  uvm_gen/templates/common/common_scb_types.sv.j2 \
  uvm_gen/templates/common/common_scb_reporter.sv.j2 \
  uvm_gen/templates/common/common_scb_registry.sv.j2
rg -n 'compare expected vs actual|send expected to compare queue|send actual to compare queue' \
  uvm_gen/templates/advance/env uvm_gen/templates/port/env
```

Expected: no matches from any command.

- [ ] **Step 3: Run the full local regression**

```bash
python3 -m pytest -q
bash -n tests/vcs/run_aip_runtime_smoke.sh
bash -n tests/vcs/run_common_scb_v2.sh
bash -n tests/vcs/run_generated_scb_matrix.sh
git diff --check
```

Expected: all tests pass; shell scripts parse; `git diff --check` is silent.

- [ ] **Step 4: Re-run both remote gates from clean generated output**

Regenerate the four projects:

```bash
rm -rf /tmp/uvm-gen-scb-matrix
mkdir -p /tmp/uvm-gen-scb-matrix/{advance_off,advance_on,port_off,port_on}
python3 - <<'PY'
from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator

for platform, aip_core, leaf in (
    (PlatformType.ADVANCE, False, "advance_off"),
    (PlatformType.ADVANCE, True,  "advance_on"),
    (PlatformType.PORT,    False, "port_off"),
    (PlatformType.PORT,    True,  "port_on"),
):
    cfg = ProjectConfig(
        block_name="top", author="final-vcs",
        platform_type=platform, agents=[AgentConfig(name="axi")],
        output_dir=f"/tmp/uvm-gen-scb-matrix/{leaf}", aip_core=aip_core,
    )
    PlatformGenerator(cfg).generate()
PY
```

Replace the remote validation directory with these fresh artifacts and the reviewed AIP checkout:

```bash
ssh ubuntu@10.11.10.53 'rm -rf /tmp/uvm-gen-scb-final && mkdir -p /tmp/uvm-gen-scb-final'
scp -r /tmp/uvm-gen-scb-matrix ubuntu@10.11.10.53:/tmp/uvm-gen-scb-final/
scp -r /home/ryan/workspace/ryan/aip_core ubuntu@10.11.10.53:/tmp/uvm-gen-scb-final/
scp tests/vcs/common_scb_unit_tb.sv \
    tests/vcs/run_aip_runtime_smoke.sh \
    tests/vcs/run_common_scb_v2.sh \
    tests/vcs/run_generated_scb_matrix.sh \
    tests/vcs/scb_adapter_smoke.tcl \
    ubuntu@10.11.10.53:/tmp/uvm-gen-scb-final/
```

Run all three gates through the host's login shell:

```bash
ssh -t ubuntu@10.11.10.53 \
  'bash -lc "/tmp/uvm-gen-scb-final/run_aip_runtime_smoke.sh \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/advance_off/top \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/advance_on/top \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/port_off/top \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/port_on/top \
  /tmp/uvm-gen-scb-final/aip_core"'
ssh -t ubuntu@10.11.10.53 \
  'bash -lc "/tmp/uvm-gen-scb-final/run_common_scb_v2.sh \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/advance_off/top/common \
  /tmp/uvm-gen-scb-final/common_scb_unit_tb.sv"'
ssh -t ubuntu@10.11.10.53 \
  'bash -lc "/tmp/uvm-gen-scb-final/run_generated_scb_matrix.sh \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/advance_off/top \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/advance_on/top \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/port_off/top \
  /tmp/uvm-gen-scb-final/uvm-gen-scb-matrix/port_on/top \
  /tmp/uvm-gen-scb-final/aip_core \
  /tmp/uvm-gen-scb-final/scb_adapter_smoke.tcl"'
```

Expected final lines: `AIP runtime matrix passed`, `Scoreboard v2 unit matrix passed`, and `Generated scoreboard v2 matrix passed` under VCS W-2024.09-SP1.

- [ ] **Step 5: Commit documentation and report final evidence**

```bash
git add README.md
git commit -m "docs: describe common scoreboard v2 controls"
git status --short
git log --oneline --decorate -15
```

Expected: clean working tree. The handoff records Python test count, three scoreboard unit modes, four generated compile/base results, two adapter TCL results, generator commit hash, full AIP Core commit hash, and VCS version.
