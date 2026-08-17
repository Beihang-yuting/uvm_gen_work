# AIP Runtime Integration Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated Advance and PORT projects with optional AIP Core compile and terminate normally, while keeping non-AIP projects free of AIP references.

**Architecture:** Keep AIP Core external and change only generator tests and generated UVM templates. Empty driver/monitor hooks become reset-blocking placeholders, reset ends released, and watchdog activity is emitted only by sequence helpers after command-owned progress; a remote VCS matrix is the release gate.

**Tech Stack:** Python 3, pytest, Jinja2, SystemVerilog/UVM 1.2, Synopsys VCS W-2024.09-SP1, Bash/SSH

---

## File map

- Create `tests/test_aip_runtime_integration.py`: generation-level contract tests for Advance/PORT and AIP off/on.
- Modify `uvm_gen/templates/advance/agent/drv.sv.j2`: safe default master/slave hooks.
- Modify `uvm_gen/templates/advance/agent/mon.sv.j2`: safe default monitor hook.
- Modify `uvm_gen/templates/port/agent/drv.sv.j2`: safe default master/slave hooks.
- Modify `uvm_gen/templates/port/agent/mon.sv.j2`: safe default monitor hook.
- Modify `uvm_gen/templates/advance/agent/base_seq.sv.j2`: command-owned activity ticks.
- Modify `uvm_gen/templates/port/agent/base_seq.sv.j2`: add the same helpers and activity contract.
- Modify `uvm_gen/templates/advance/env/env.sv.j2`: remove automatic subscriber ownership and wiring.
- Modify `uvm_gen/templates/port/env/env.sv.j2`: remove automatic subscriber ownership and wiring.
- Modify `uvm_gen/templates/common/aip_activity_subscriber.sv.j2`: retain as an explicit opt-in utility with a masking warning.
- Modify `uvm_gen/templates/tc/base_test.sv.j2`: deterministic active-low reset lifecycle.
- Modify `uvm_gen/templates/tc/tc_tcl_demo.tcl.j2`: current UCLI invocation example.
- Create `tests/vcs/run_aip_runtime_smoke.sh`: repeatable VCS compile/runtime matrix for the designated host.

### Task 1: Add the failing generation contract

**Files:**
- Create: `tests/test_aip_runtime_integration.py`

- [ ] **Step 1: Create the focused generation tests**

Add this complete test module:

```python
from pathlib import Path

import pytest

from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
from uvm_gen.generators.platform import PlatformGenerator


@pytest.fixture(params=[PlatformType.ADVANCE, PlatformType.PORT])
def platform_type(request):
    return request.param


def generate(tmp_path: Path, platform_type: PlatformType, aip_core: bool) -> Path:
    cfg = ProjectConfig(
        block_name="top",
        author="test",
        platform_type=platform_type,
        agents=[AgentConfig(name="axi")],
        aip_core=aip_core,
        output_dir=str(tmp_path),
    )
    return Path(PlatformGenerator(cfg).generate())


def read(project: Path, relative_path: str) -> str:
    return (project / relative_path).read_text(encoding="utf-8")


def test_empty_protocol_hooks_block_until_reset(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    driver = read(project, "env/agents/axi_agent/src/axi_drv.sv")
    monitor = read(project, "env/agents/axi_agent/src/axi_mon.sv")
    assert driver.count("@(negedge m_vif.rst_n);") >= 3
    assert "AXI_DRV_PLACEHOLDER" in driver
    assert "AXI_MON_PLACEHOLDER" in monitor
    assert "@(negedge m_vif.rst_n);" in monitor


def test_reset_finishes_deasserted(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    test = read(project, "tc/tc_base.sv")
    assert "harness.rst_n = 1'b0;" in test
    assert "repeat(i) @(posedge harness.clk);" in test
    assert "harness.rst_n = 1'b1;" in test
    assert test.rfind("harness.rst_n = 1'b1;") < test.rfind("phase.drop_objection(this);")
    assert "repeat(2) @(posedge harness.clk);" in test


def test_aip_activity_is_command_owned(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    sequence = read(project, "env/agents/axi_agent/src/axi_base_seq.sv")
    environment = read(project, "env/top_env.sv")
    assert "virtual task send_trans" in sequence
    assert "virtual task send_trans_with_rsp" in sequence
    assert sequence.count("aip_activity::tick();") == 2
    assert "aip_activity_subscriber" not in environment
    assert "m_axi_act_sub" not in environment


def test_activity_subscriber_is_explicit_opt_in(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    subscriber = read(project, "common/aip_activity_subscriber.sv")
    assert "EXPLICIT OPT-IN" in subscriber
    assert "mask a stuck AIP command" in subscriber
    assert "aip_activity::tick();" in subscriber


def test_tcl_demo_uses_ucli_input_script(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    demo = read(project, "tc/tcl/tc_tcl_demo.tcl")
    assert "./simv -ucli -i ../tc/tcl/tc_tcl_demo.tcl" in demo
    assert "end_test idle=1us timeout=10us" in demo


def test_non_aip_output_has_no_aip_symbols(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=False)
    generated_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in project.rglob("*")
        if path.is_file()
    )
    assert "aip_activity" not in generated_text
    assert "aip_tcl_bridge" not in generated_text
    assert "aip_core_pkg.sv" not in generated_text
    assert not (project / "tc/tc_tcl.sv").exists()


def test_aip_filelist_keeps_external_package_boundary(tmp_path, platform_type):
    project = generate(tmp_path, platform_type, aip_core=True)
    filelist = read(project, "cfg/tb.f")
    assert "+incdir+$AIP_CORE_HOME" in filelist
    assert "$AIP_CORE_HOME/aip_core_pkg.sv" in filelist
```

- [ ] **Step 2: Run the focused module and confirm the baseline failures**

Run:

```bash
python3 -m pytest tests/test_aip_runtime_integration.py -q
```

Expected: failures for the placeholder tags/blocking counts, released reset, PORT helpers, command-owned ticks, removed environment subscribers, explicit opt-in warning, and `-ucli -i`; the non-AIP and external-package assertions may already pass.

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_aip_runtime_integration.py
git commit -m "test: define AIP runtime generation contract"
```

### Task 2: Make empty driver and monitor hooks time-safe

**Files:**
- Modify: `uvm_gen/templates/advance/agent/drv.sv.j2:60-68`
- Modify: `uvm_gen/templates/advance/agent/mon.sv.j2:57-70`
- Modify: `uvm_gen/templates/port/agent/drv.sv.j2:60-68`
- Modify: `uvm_gen/templates/port/agent/mon.sv.j2:57-70`
- Test: `tests/test_aip_runtime_integration.py`

- [ ] **Step 1: Replace both driver placeholder bodies in both platform templates**

Use these exact task bodies in both driver templates:

```systemverilog
task {{ name }}_drv::master_drive();
    `uvm_warning("{{ name_upper }}_DRV_PLACEHOLDER",
                 "master_drive() is not implemented; blocking until reset assertion")
    @(negedge m_vif.rst_n);
endtask : master_drive

task {{ name }}_drv::slave_drive();
    `uvm_warning("{{ name_upper }}_DRV_PLACEHOLDER",
                 "slave_drive() is not implemented; blocking until reset assertion")
    @(negedge m_vif.rst_n);
endtask : slave_drive
```

The existing reset-aware `fork...join_any` lifecycle remains unchanged. One hook invocation occurs per reset epoch, so each placeholder warning is bounded.

- [ ] **Step 2: Replace the monitor placeholder body in both platform templates**

Use this exact task body in both monitor templates:

```systemverilog
task {{ name }}_mon::mon_transaction();
    `uvm_warning("{{ name_upper }}_MON_PLACEHOLDER",
                 "mon_transaction() is not implemented; blocking until reset assertion")
    @(negedge m_vif.rst_n);
endtask : mon_transaction
```

- [ ] **Step 3: Run only the placeholder contract**

```bash
python3 -m pytest tests/test_aip_runtime_integration.py::test_empty_protocol_hooks_block_until_reset -q
```

Expected: `2 passed` (Advance and PORT).

- [ ] **Step 4: Commit the safe lifecycle change**

```bash
git add uvm_gen/templates/advance/agent/drv.sv.j2 \
        uvm_gen/templates/advance/agent/mon.sv.j2 \
        uvm_gen/templates/port/agent/drv.sv.j2 \
        uvm_gen/templates/port/agent/mon.sv.j2
git commit -m "fix: block empty agent hooks until reset"
```

### Task 3: Make reset deterministic and update the TCL invocation

**Files:**
- Modify: `uvm_gen/templates/tc/base_test.sv.j2:49-67`
- Modify: `uvm_gen/templates/tc/tc_tcl_demo.tcl.j2:1-4`
- Test: `tests/test_aip_runtime_integration.py`

- [ ] **Step 1: Replace the reset phase**

```systemverilog
task tc_base::reset_phase(uvm_phase phase);
    int i;
    phase.raise_objection(this);
    super.reset_phase(phase);

    harness.rst_n = 1'b0;
    i = $urandom_range(10, 20);
    repeat(i) @(posedge harness.clk);

    harness.rst_n = 1'b1;
    repeat(2) @(posedge harness.clk);
    phase.drop_objection(this);
endtask
```

- [ ] **Step 2: Replace the demo usage line**

```tcl
# Usage (run from cfg/): ./simv -ucli -i ../tc/tcl/tc_tcl_demo.tcl +UVM_TESTNAME=tc_tcl
```

- [ ] **Step 3: Run reset and TCL generation tests**

```bash
python3 -m pytest \
  tests/test_aip_runtime_integration.py::test_reset_finishes_deasserted \
  tests/test_aip_runtime_integration.py::test_tcl_demo_uses_ucli_input_script -q
```

Expected: `4 passed`.

- [ ] **Step 4: Commit the deterministic runtime entry path**

```bash
git add uvm_gen/templates/tc/base_test.sv.j2 \
        uvm_gen/templates/tc/tc_tcl_demo.tcl.j2
git commit -m "fix: release reset before AIP TCL control"
```

### Task 4: Move AIP watchdog progress to sequence helpers

**Files:**
- Modify: `uvm_gen/templates/advance/agent/base_seq.sv.j2:15-32`
- Modify: `uvm_gen/templates/port/agent/base_seq.sv.j2:11-17`
- Modify: `uvm_gen/templates/advance/env/env.sv.j2:16-22,47-52,65-76`
- Modify: `uvm_gen/templates/port/env/env.sv.j2:16-22,57-62,92-103`
- Modify: `uvm_gen/templates/common/aip_activity_subscriber.sv.j2:5-7`
- Test: `tests/test_aip_runtime_integration.py`

- [ ] **Step 1: Guard Advance helper ticks with the AIP template condition**

The complete helper bodies become:

```systemverilog
virtual task send_trans(input {{ name }}_trans tr);
    if(!(p_sequencer.m_cfg.m_mode inside {AGENT_MASTER, AGENT_ONLY_MASTER})) begin
        `uvm_fatal(get_full_name, "send_trans only valid in MASTER/ONLY_MASTER mode")
    end
    start_item(tr);
    finish_item(tr);
{% if aip_core %}
    aip_activity::tick();
{% endif %}
endtask : send_trans

virtual task send_trans_with_rsp(input {{ name }}_trans tr, output {{ name }}_trans rsp);
    if(!(p_sequencer.m_cfg.m_mode inside {AGENT_MASTER, AGENT_ONLY_MASTER})) begin
        `uvm_fatal(get_full_name, "send_trans_with_rsp only valid in MASTER/ONLY_MASTER mode")
    end
    start_item(tr);
    finish_item(tr);
    get_response(rsp);
{% if aip_core %}
    aip_activity::tick();
{% endif %}
endtask : send_trans_with_rsp
```

- [ ] **Step 2: Give PORT the same supported helper path**

Insert these complete methods after its constructor:

```systemverilog
virtual task send_trans(input {{ name }}_trans tr);
    if(!(p_sequencer.m_cfg.m_mode inside {AGENT_MASTER, AGENT_ONLY_MASTER})) begin
        `uvm_fatal(get_full_name, "send_trans only valid in MASTER/ONLY_MASTER mode")
    end
    start_item(tr);
    finish_item(tr);
{% if aip_core %}
    aip_activity::tick();
{% endif %}
endtask : send_trans

virtual task send_trans_with_rsp(input {{ name }}_trans tr, output {{ name }}_trans rsp);
    if(!(p_sequencer.m_cfg.m_mode inside {AGENT_MASTER, AGENT_ONLY_MASTER})) begin
        `uvm_fatal(get_full_name, "send_trans_with_rsp only valid in MASTER/ONLY_MASTER mode")
    end
    start_item(tr);
    finish_item(tr);
    get_response(rsp);
{% if aip_core %}
    aip_activity::tick();
{% endif %}
endtask : send_trans_with_rsp
```

Add this AIP-only comment beside the command-registration example:

```systemverilog
// Helpers tick only after a completed transaction. A custom long-running
// sequence that bypasses them must call aip_activity::tick() at a real
// progress boundary, such as after item_done() or a completed transfer.
```

- [ ] **Step 3: Remove subscriber declarations, construction, and connections from both environments**

Delete the three `{% if aip_core %}` blocks that declare `m_*_act_sub`, construct them, and connect monitor analysis ports to them. Preserve the existing AIP-only static sequencer assignments:

```systemverilog
{% if aip_core %}
    // assign static sqr handles for aip_cmd_seq
{% for agent in agents %}
    {{ block_name }}_vsqr::s_{{ agent.name }}_sqr = this.m_{{ agent.name }}_agt.m_sqr;
{% endfor %}
{% endif %}
```

- [ ] **Step 4: Make the retained subscriber's risk explicit**

Replace its header comment with:

```systemverilog
// EXPLICIT OPT-IN utility. Do not connect this to general monitor traffic by
// default: unrelated transactions can mask a stuck AIP command. Prefer
// aip_activity::tick() at the progress boundary owned by the active command.
// Explicit usage: agent.m_mon.m_ap.connect(subscriber.analysis_export);
```

- [ ] **Step 5: Run the complete Python contract**

```bash
python3 -m pytest tests/test_aip_runtime_integration.py -q
```

Expected: `14 passed` (seven tests across two platform parameters).

- [ ] **Step 6: Commit command-owned activity**

```bash
git add uvm_gen/templates/advance/agent/base_seq.sv.j2 \
        uvm_gen/templates/port/agent/base_seq.sv.j2 \
        uvm_gen/templates/advance/env/env.sv.j2 \
        uvm_gen/templates/port/env/env.sv.j2 \
        uvm_gen/templates/common/aip_activity_subscriber.sv.j2
git commit -m "fix: track AIP progress at sequence boundaries"
```

### Task 5: Add a repeatable VCS runtime gate

**Files:**
- Create: `tests/vcs/run_aip_runtime_smoke.sh`

- [ ] **Step 1: Add the remote-host smoke runner**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: $0 ADVANCE_OFF ADVANCE_ON PORT_OFF PORT_ON AIP_CORE_DIR" >&2
  exit 2
fi

advance_off=$1
advance_on=$2
port_off=$3
port_on=$4
aip_core_dir=$5

compile_and_run_base() {
  local project_dir=$1
  local label=$2
  local cfg_dir="${project_dir}/cfg"
  (
    cd "${cfg_dir}"
    vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
      -f tb.f -top harness -o simv -l "compile_${label}.log"
    timeout 60s ./simv +UVM_TESTNAME=tc_base -l "run_${label}_base.log"
    grep -F "TC PASSED." "run_${label}_base.log"
  )
}

run_tcl() {
  local project_dir=$1
  local label=$2
  local cfg_dir="${project_dir}/cfg"
  (
    cd "${cfg_dir}"
    timeout 60s ./simv -ucli -i ../tc/tcl/tc_tcl_demo.tcl \
      +UVM_TESTNAME=tc_tcl -l "run_${label}_tcl.log"
    grep -F "TC PASSED." "run_${label}_tcl.log"
  )
}

export AIP_CORE_HOME="${aip_core_dir}"
compile_and_run_base "${advance_off}" advance_off
compile_and_run_base "${advance_on}" advance_on
run_tcl "${advance_on}" advance_on
compile_and_run_base "${port_off}" port_off
compile_and_run_base "${port_on}" port_on
run_tcl "${port_on}" port_on

echo "AIP runtime matrix passed"
```

- [ ] **Step 2: Make the runner executable and syntax-check it**

```bash
chmod +x tests/vcs/run_aip_runtime_smoke.sh
bash -n tests/vcs/run_aip_runtime_smoke.sh
```

Expected: exit code `0`, no output.

- [ ] **Step 3: Commit the release gate**

```bash
git add tests/vcs/run_aip_runtime_smoke.sh
git commit -m "test: add AIP VCS runtime matrix"
```

### Task 6: Run local regression and the required VCS matrix

**Files:**
- Verify only; no source changes expected.

- [ ] **Step 1: Run all available Python tests**

```bash
python3 -m pytest -q
```

Expected: all collected tests pass. If pytest is absent, create a disposable environment outside the repository and rerun:

```bash
python3 -m venv /tmp/uvm-gen-plan-venv
/tmp/uvm-gen-plan-venv/bin/pip install pytest jinja2 pyyaml
/tmp/uvm-gen-plan-venv/bin/python -m pytest -q
```

- [ ] **Step 2: Generate the four validation projects locally**

```bash
rm -rf /tmp/uvm-gen-aip-matrix
mkdir -p /tmp/uvm-gen-aip-matrix/{advance_off,advance_on,port_off,port_on}
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
        output_dir=f"/tmp/uvm-gen-aip-matrix/{leaf}",
        aip_core=aip_core,
    )
    PlatformGenerator(cfg).generate()
PY
```

Expected: each leaf contains `top/cfg/tb.f`; only `advance_on/top` and `port_on/top` contain `tc/tc_tcl.sv`.

- [ ] **Step 3: Transfer the generator outputs, reviewed AIP checkout, and runner**

Use the required simulation host. Enter the provided SSH password interactively; do not place it in a command, URL, script, or credential helper.

```bash
ssh ubuntu@10.11.10.53 'mkdir -p /tmp/uvm-gen-aip-validation'
scp -r /tmp/uvm-gen-aip-matrix ubuntu@10.11.10.53:/tmp/uvm-gen-aip-validation/
scp -r /home/ryan/workspace/ryan/aip_core ubuntu@10.11.10.53:/tmp/uvm-gen-aip-validation/
scp tests/vcs/run_aip_runtime_smoke.sh ubuntu@10.11.10.53:/tmp/uvm-gen-aip-validation/
```

- [ ] **Step 4: Run the matrix in a login shell on `10.11.10.53`**

```bash
ssh -t ubuntu@10.11.10.53 \
  'bash -lc "/tmp/uvm-gen-aip-validation/run_aip_runtime_smoke.sh \
  /tmp/uvm-gen-aip-validation/uvm-gen-aip-matrix/advance_off/top \
  /tmp/uvm-gen-aip-validation/uvm-gen-aip-matrix/advance_on/top \
  /tmp/uvm-gen-aip-validation/uvm-gen-aip-matrix/port_off/top \
  /tmp/uvm-gen-aip-validation/uvm-gen-aip-matrix/port_on/top \
  /tmp/uvm-gen-aip-validation/aip_core"'
```

Expected: four compile/base runs and two TCL runs exit zero, every run log contains `TC PASSED.`, simulation time advances beyond `0.00ns`, and the final line is `AIP runtime matrix passed`.

- [ ] **Step 5: Record the exact validated revisions in the implementation handoff**

```bash
git rev-parse HEAD
git -C /home/ryan/workspace/ryan/aip_core rev-parse HEAD
```

Expected AIP baseline: reviewed `main` revision `5a9edbb...`; record the full hashes and VCS version printed by the remote compile log.

- [ ] **Step 6: Commit any test-only corrections discovered by VCS**

If VCS exposed a portability correction, rerun Tasks 1–5 and commit only the focused correction:

```bash
git add tests/test_aip_runtime_integration.py \
        tests/vcs/run_aip_runtime_smoke.sh \
        uvm_gen/templates/advance/agent/drv.sv.j2 \
        uvm_gen/templates/advance/agent/mon.sv.j2 \
        uvm_gen/templates/advance/agent/base_seq.sv.j2 \
        uvm_gen/templates/port/agent/drv.sv.j2 \
        uvm_gen/templates/port/agent/mon.sv.j2 \
        uvm_gen/templates/port/agent/base_seq.sv.j2 \
        uvm_gen/templates/advance/env/env.sv.j2 \
        uvm_gen/templates/port/env/env.sv.j2 \
        uvm_gen/templates/common/aip_activity_subscriber.sv.j2 \
        uvm_gen/templates/tc/base_test.sv.j2 \
        uvm_gen/templates/tc/tc_tcl_demo.tcl.j2
git commit -m "fix: make AIP runtime templates VCS portable"
```

Do not begin the scoreboard-v2 plan until this task's full matrix passes.
