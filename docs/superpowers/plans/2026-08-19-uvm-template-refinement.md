# UVM Template Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine both generated UVM platforms so PORT keeps its conventional FIFO topology, Advance exposes task-only transaction routing, obsolete common code is removed, transaction behavior is explicit, AIP uses `$AIP_HOME/aip_core`, and generated VCS configuration is directly usable.

**Architecture:** Shared generators continue to produce the common library, harness, testcase, and cfg areas. PORT retains environment-owned TLM FIFOs and its reset-worker lifecycle; Advance retains only an agent-local monitor FIFO and exposes per-agent task APIs, with no environment-level RM/checker transaction connections. AIP registry/proxy code is generated only when `aip_core` is enabled, while all protocol-independent connection and utility macros remain in `common_dec.sv`.

**Tech Stack:** Python 3, Jinja2, pytest, SystemVerilog/UVM 1.2, Synopsys VCS W-2024.09-SP1, Tcl, Bash

---

## Fixed naming and execution conventions

- The design's conceptual `predict`, `send_actual`, and `send_expected` APIs are specialized per generated agent because one environment may contain unrelated transaction types. For agent `axi`, the exact names are `predict_axi`, `send_axi_actual`, and `send_axi_expected`.
- Each Advance agent itself has the unsuffixed `get_mon_item()` and `try_get_mon_item()` methods because its class owns only one transaction type.
- PORT transaction routing and reset sequencing are regression-protected and are not replaced with these task APIs.
- Local pytest commands use the existing test interpreter:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest
  ```

- VCS verification runs only on `10.11.10.53` in a bash login shell. No credential is stored in this repository or in a command-line URL.

## File responsibility map

- `uvm_gen/generators/common.py`: selects core common files and AIP-only registry/adapter files.
- `uvm_gen/generators/harness.py`: creates `th/harness.sv` plus the optional `th/bind/` examples.
- `uvm_gen/templates/common/common_dec.sv.j2`: owns all `UVG_` connection, VIF, clock, reset, and static-assert macros.
- `uvm_gen/templates/common/base_scb.sv.j2`: owns the AIP-conditional scoreboard proxy registration.
- `uvm_gen/templates/{port,advance}/agent/`: owns modes, VIF propagation, transactions, clocking blocks, sequence helpers, and monitor activity guidance.
- `uvm_gen/templates/advance/env/`: owns only the Advance task-oriented RM/checker shell and its usage example.
- `uvm_gen/templates/port/env/`: keeps the existing TLM/FIFO routing and reset lifecycle.
- `uvm_gen/templates/harness/`: owns the top harness and optional bind/SVA examples.
- `uvm_gen/templates/cfg/`: owns the single-root filelist and reviewed VCS examples.
- `tests/test_template_refinement.py`: contains the new cross-platform generation contract.
- `tests/test_common_scb_v2_*.py` and `tests/test_aip_runtime_integration.py`: retain existing scoreboard/AIP regression coverage with obsolete expectations removed.
- `tests/vcs/template_refinement_tb.sv` and `tests/vcs/run_template_refinement.sh`: provide the new VCS semantic gate.

### Task 1: Remove obsolete common code and isolate AIP scoreboard control

**Files:**

- Create: `tests/test_template_refinement.py`
- Modify: `tests/test_common_scb_v2_generation.py`
- Modify: `tests/test_common_scb_v2_core_template.py`
- Modify: `uvm_gen/generators/common.py`
- Modify: `uvm_gen/templates/common/common_pkg.sv.j2`
- Modify: `uvm_gen/templates/common/base_scb.sv.j2`
- Modify: `uvm_gen/templates/tc/base_test.sv.j2`
- Delete: `uvm_gen/templates/common/legacy_scb.sv.j2`
- Delete: `uvm_gen/templates/common/draw_table.sv.j2`
- Delete: `uvm_gen/templates/common/self_debug_scb.sv.j2`
- Delete: `uvm_gen/templates/common/aip_activity_subscriber.sv.j2`
- Delete: `uvm_gen/templates/common/report_server.sv.j2`

- [ ] **Step 1: Write generation tests for the final common layout**

  Start `tests/test_template_refinement.py` with these complete shared helpers, then add the assertions below:

  ```python
  import re
  from pathlib import Path

  import pytest

  from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
  from uvm_gen.generators.platform import PlatformGenerator


  REPOSITORY = Path(__file__).resolve().parents[1]


  @pytest.fixture(
      params=[PlatformType.ADVANCE, PlatformType.PORT],
      ids=lambda platform_type: platform_type.value,
  )
  def platform_type(request):
      return request.param


  def generate(tmp_path: Path, platform_type: PlatformType, aip_core: bool) -> Path:
      config = ProjectConfig(
          block_name="top",
          author="test",
          agents=[AgentConfig("axi"), AgentConfig("apb")],
          platform_type=platform_type,
          aip_core=aip_core,
          output_dir=str(tmp_path),
      )
      return Path(PlatformGenerator(config).generate())


  def read(project: Path, relative_path: str) -> str:
      return (project / relative_path).read_text(encoding="utf-8")


  def strip_sv_comments(source: str) -> str:
      return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)


  def function_body(source: str, name: str) -> str:
      match = re.search(
          rf"(?ms)^[ \t]*(?:virtual[ \t]+)?function\b[^;]*\b{name}\b"
          rf"[^;]*;(?P<body>.*?)^[ \t]*endfunction\b",
          source,
      )
      assert match, f"missing function {name}"
      return match.group("body")


  def active_filelist_lines(source: str) -> list[str]:
      return [
          line.rstrip()
          for line in source.splitlines()
          if line.strip() and not line.lstrip().startswith(("#", "//"))
      ]
  ```

  Add these exact assertions:

  ```python
  OBSOLETE_COMMON = {
      "common_uvm_scb_legacy.sv",
      "common_draw_table.sv",
      "common_self_debug_scb.sv",
      "aip_activity_subscriber.sv",
      "common_report_server.sv",
  }

  @pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
  def test_common_layout_is_minimal(tmp_path, platform_type, aip_core):
      project = generate(tmp_path, platform_type, aip_core=aip_core)
      common_names = {path.name for path in (project / "common").iterdir()}
      assert common_names.isdisjoint(OBSOLETE_COMMON)
      package = read(project, "common/common_lib_pkg.sv")
      filelist = read(project, "common/common_lib_pkg.f")
      for obsolete in OBSOLETE_COMMON:
          assert obsolete not in package
          assert obsolete not in filelist
      assert ("common_scb_registry.sv" in common_names) is aip_core
      assert ("common_scb_aip_adapter.sv" in common_names) is aip_core

  @pytest.mark.parametrize("aip_core", [False, True], ids=["aip_off", "aip_on"])
  def test_scoreboard_proxy_is_aip_conditional(tmp_path, platform_type, aip_core):
      project = generate(tmp_path, platform_type, aip_core=aip_core)
      core = read(project, "common/common_uvm_scb.sv")
      proxy_tokens = (
          "common_scb_control_proxy",
          "common_scb_typed_proxy",
          "m_proxy",
          "common_scb_registry::register_proxy",
      )
      for token in proxy_tokens:
          assert (token in core) is aip_core

  def test_tc_base_uses_standard_uvm_report_server(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=False)
      base_test = read(project, "tc/tc_base.sv")
      assert "common_report_server" not in base_test
      assert "uvm_report_server::set_server" not in base_test
      assert "$timeformat(-9,2,\"ns\",12);" in base_test
      assert "get_severity_count(UVM_ERROR)" in base_test
  ```

  Update `tests/test_common_scb_v2_generation.py` so `EXPECTED_COMMON_TEMPLATES` and `EXPECTED_COMMON_INCLUDES` contain only `common_dec`, `common_scb_types`, `common_scb_reporter`, and `common_uvm_scb` for AIP-off generation; insert `common_scb_registry` immediately before `common_uvm_scb` only for AIP-on generation. Remove the tests that require two public scoreboard classes and replace them with absence assertions for the deleted filenames.

- [ ] **Step 2: Run the new and affected tests to confirm the old layout fails**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py \
    tests/test_common_scb_v2_generation.py \
    tests/test_common_scb_v2_core_template.py -q
  ```

  Expected: FAIL because the obsolete files still exist and AIP-off `common_uvm_scb` still references the registry proxy.

- [ ] **Step 3: Make common generation conditional and remove custom report-server installation**

  Replace the template selection in `uvm_gen/generators/common.py` with this structure:

  ```python
  class CommonGenerator(BaseGenerator):
      CORE_TEMPLATES = [
          ("common_lib_pkg.sv", "common/common_pkg.sv.j2"),
          ("common_dec.sv", "common/common_dec.sv.j2"),
          ("common_scb_types.sv", "common/common_scb_types.sv.j2"),
          ("common_scb_reporter.sv", "common/common_scb_reporter.sv.j2"),
          ("common_uvm_scb.sv", "common/base_scb.sv.j2"),
      ]
      AIP_TEMPLATES = [
          ("common_scb_registry.sv", "common/common_scb_registry.sv.j2"),
      ]

      def generate(self, output_dir: str) -> None:
          os.makedirs(output_dir, exist_ok=True)
          filelist = "+incdir+./\n./common_lib_pkg.sv\n"
          if self.cfg.aip_core:
              filelist += "./common_scb_aip_adapter.sv\n"
          self.write_file(os.path.join(output_dir, "common_lib_pkg.f"), filelist)

          templates = list(self.CORE_TEMPLATES)
          if self.cfg.aip_core:
              templates.extend(self.AIP_TEMPLATES)
          for filename, template in templates:
              content = self.render_template(template, file_name=filename)
              self.write_file(os.path.join(output_dir, filename), content)

          if self.cfg.aip_core:
              content = self.render_template(
                  "common/common_scb_aip_adapter.sv.j2",
                  file_name="common_scb_aip_adapter.sv",
              )
              self.write_file(
                  os.path.join(output_dir, "common_scb_aip_adapter.sv"), content
              )
  ```

  Make the package include order explicit:

  ```systemverilog
      `include "common_dec.sv"
      `include "common_scb_types.sv"
      `include "common_scb_reporter.sv"
  {% if aip_core %}
      `include "common_scb_registry.sv"
  {% endif %}
      `include "common_uvm_scb.sv"
  ```

  Wrap all four registry-facing areas in `base_scb.sv.j2` with `{% if aip_core %}`: the `m_proxy` member, the complete `common_scb_typed_proxy` class, the local `registry_error` state, and proxy construction/registration at the end of `build_phase()`.

  Remove only these lines from the `tc_base` constructor while retaining `$timeformat()`:

  ```systemverilog
  common_report_server my_server;
  my_server = new();
  uvm_report_server::set_server(my_server);
  ```

  Delete the five obsolete Jinja templates listed in this task. Do not delete `common_scb_reporter.sv.j2`, which is the active compact table renderer.

- [ ] **Step 4: Separate generic scoreboard tests from AIP proxy tests**

  In `tests/test_common_scb_v2_core_template.py`, change the renderer to accept the AIP flag and keep the proxy contract in the AIP-on leg only:

  ```python
  def render_task6_sources(aip_core: bool = False) -> tuple[str, str]:
      config = ProjectConfig(
          block_name="top",
          author="test",
          agents=[AgentConfig("axi")],
          platform_type=PlatformType.ADVANCE,
          aip_core=aip_core,
      )
      generator = PlatformGenerator(config)
      return (
          generator.render_template(
              "common/base_scb.sv.j2", file_name="common_uvm_scb.sv"
          ),
          generator.render_template(
              "common/common_scb_types.sv.j2", file_name="common_scb_types.sv"
          ),
      )

  def test_aip_core_template_registers_control_proxy():
      core_raw, _ = render_task6_sources(aip_core=True)
      assert_task6_proxy_contract(strip_sv_comments(core_raw))

  def test_non_aip_core_template_has_no_registry_dependency():
      core_raw, _ = render_task6_sources(aip_core=False)
      core = strip_sv_comments(core_raw)
      for token in (
          "common_scb_control_proxy",
          "common_scb_typed_proxy",
          "m_proxy",
          "common_scb_registry",
      ):
          assert token not in core
  ```

  Remove the proxy-member assertion from the generic lifecycle-report helper; leave the matching, report-limit, omission-count, and final-status checks unchanged.

- [ ] **Step 5: Run the common-library regression and commit**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py \
    tests/test_common_scb_v2_generation.py \
    tests/test_common_scb_v2_core_template.py -q
  ```

  Expected: PASS with no generated reference to any deleted common file.

  Commit:

  ```bash
  git add uvm_gen/generators/common.py uvm_gen/templates/common \
    uvm_gen/templates/tc/base_test.sv.j2 tests/test_template_refinement.py \
    tests/test_common_scb_v2_generation.py tests/test_common_scb_v2_core_template.py
  git commit -m "refactor: remove obsolete common UVM utilities"
  ```

### Task 2: Add reusable connection macros and bind layout

**Files:**

- Modify: `tests/test_template_refinement.py`
- Modify: `uvm_gen/templates/common/common_dec.sv.j2`
- Modify: `uvm_gen/generators/harness.py`
- Modify: `uvm_gen/templates/harness/harness.sv.j2`
- Create: `uvm_gen/templates/harness/common_sva.svh.j2`
- Create: `uvm_gen/templates/harness/bind_example.sv.j2`

- [ ] **Step 1: Add failing tests for macro signatures and bind output**

  Add these tests:

  ```python
  def test_common_macros_have_fixed_public_signatures(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=False)
      common_dec = read(project, "common/common_dec.sv")
      for signature in (
          "`define UVG_IF_CONNECT(ROLE, FLOW, RTL_SIG, VIF_SIG)",
          "`define UVG_VIF_SET(IF_TYPE, PATH, VIF)",
          "`define UVG_VIF_GET(IF_TYPE, VIF)",
          "`define UVG_CLK(CLK, PERIOD, OFFSET)",
          "`define UVG_RSTN(RST_N, CLK, CYCLES)",
          "`define UVG_STATIC_ASSERT(NAME, EXPR, MESSAGE)",
      ):
          assert signature in common_dec
      assert "RTL_SIG, VIF_SIG" in common_dec
      assert "CLK_GEN" not in common_dec
      assert "RST_GEN" not in common_dec

  def test_bind_examples_are_generated_but_disabled(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=False)
      bind_example = read(project, "th/bind/bind_example.sv")
      common_sva = read(project, "th/bind/common_sva.svh")
      assert "`UVG_SVA_NO_X" in common_sva
      assert "`UVG_SVA_HOLD" in common_sva
      for example in (
          "module type",
          "hierarchical instance",
          "parameterized checker",
          "interface instance",
          "generate hierarchy",
          "multiple checkers",
      ):
          assert example in bind_example
      env_filelist = read(project, "cfg/env.f")
      assert "../th/bind/bind_example.sv" not in active_filelist_lines(env_filelist)
  ```

- [ ] **Step 2: Run the macro/bind tests and confirm they fail**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py -k "macro or bind" -q
  ```

  Expected: FAIL because `common_dec.sv` still defines `CLK_GEN`/`RST_GEN` and `th/bind/` is absent.

- [ ] **Step 3: Replace `common_dec.sv.j2` with the fixed macro contract**

  Use this implementation, preserving the generated header and include guard:

  ```systemverilog
  `define UVG_STATIC_ASSERT(NAME, EXPR, MESSAGE) \
      if (!(EXPR)) begin : NAME \
          UVG_STATIC_ASSERTION_FAILED #(.MESSAGE(MESSAGE)) \
              u_uvg_static_assertion_failed(); \
      end

  `define UVG_IF_WIDTH_ASSERT(RTL_SIG, VIF_SIG) \
      if ($bits(RTL_SIG) != $bits(VIF_SIG)) begin \
          UVG_STATIC_ASSERTION_FAILED #( \
              .MESSAGE("UVG_IF_CONNECT width mismatch") \
          ) u_uvg_if_width_mismatch(); \
      end

  `define UVG_IF_CONNECT_MASTER_M2S(RTL_SIG, VIF_SIG) \
      `UVG_IF_WIDTH_ASSERT(RTL_SIG, VIF_SIG) \
      assign RTL_SIG = VIF_SIG
  `define UVG_IF_CONNECT_MASTER_S2M(RTL_SIG, VIF_SIG) \
      `UVG_IF_WIDTH_ASSERT(RTL_SIG, VIF_SIG) \
      assign VIF_SIG = RTL_SIG
  `define UVG_IF_CONNECT_SLAVE_M2S(RTL_SIG, VIF_SIG) \
      `UVG_IF_WIDTH_ASSERT(RTL_SIG, VIF_SIG) \
      assign VIF_SIG = RTL_SIG
  `define UVG_IF_CONNECT_SLAVE_S2M(RTL_SIG, VIF_SIG) \
      `UVG_IF_WIDTH_ASSERT(RTL_SIG, VIF_SIG) \
      assign RTL_SIG = VIF_SIG
  `define UVG_IF_CONNECT_MONITOR_M2S(RTL_SIG, VIF_SIG) \
      `UVG_IF_WIDTH_ASSERT(RTL_SIG, VIF_SIG) \
      assign VIF_SIG = RTL_SIG
  `define UVG_IF_CONNECT_MONITOR_S2M(RTL_SIG, VIF_SIG) \
      `UVG_IF_WIDTH_ASSERT(RTL_SIG, VIF_SIG) \
      assign VIF_SIG = RTL_SIG

  `define UVG_IF_CONNECT(ROLE, FLOW, RTL_SIG, VIF_SIG) \
      `UVG_IF_CONNECT_``ROLE``_``FLOW(RTL_SIG, VIF_SIG)

  `define UVG_VIF_SET(IF_TYPE, PATH, VIF) \
      uvm_config_db#(virtual IF_TYPE)::set(null, PATH, "m_vif", VIF)

  `define UVG_VIF_GET(IF_TYPE, VIF) \
      if (!uvm_config_db#(virtual IF_TYPE)::get(this, "", "m_vif", VIF)) begin \
          `uvm_fatal("UVG_VIF_GET", \
              $sformatf("missing virtual interface type=%s component=%s field=m_vif", \
                        `"IF_TYPE`", get_full_name())) \
      end

  `define UVG_CLK(CLK, PERIOD, OFFSET) \
      initial begin \
          CLK = 1'b0; \
          #(OFFSET); \
          forever #((PERIOD)/2.0) CLK = ~CLK; \
      end

  `define UVG_RSTN(RST_N, CLK, CYCLES) \
      initial begin \
          RST_N = 1'b0; \
          repeat (CYCLES) @(posedge CLK); \
          @(negedge CLK); \
          RST_N = 1'b1; \
      end
  ```

  Invalid role/flow tokens deliberately expand to an undefined macro. Width and explicit static-assert failures deliberately elaborate the undefined `UVG_STATIC_ASSERTION_FAILED` module only in the failing generate branch.

- [ ] **Step 4: Generate the bind directory and update the harness to use core macros**

  Extend `HarnessGenerator.generate()` with:

  ```python
  bind_dir = os.path.join(output_dir, "bind")
  os.makedirs(bind_dir, exist_ok=True)
  for template_name, file_name in (
      ("common_sva.svh.j2", "common_sva.svh"),
      ("bind_example.sv.j2", "bind_example.sv"),
  ):
      content = self.render_template(
          f"harness/{template_name}",
          file_name=file_name,
          agents=self.cfg.agents,
      )
      self.write_file(os.path.join(bind_dir, file_name), content)
  ```

  Define the two SVA macros as:

  ```systemverilog
  `define UVG_SVA_NO_X(NAME, CLK, RST_N, SIGNAL) \
      NAME: assert property (@(posedge CLK) disable iff (!(RST_N)) \
                             !$isunknown(SIGNAL)) \
          else $error("%s contains X/Z", `"SIGNAL`")

  `define UVG_SVA_HOLD(NAME, CLK, RST_N, VALID, READY, PAYLOAD) \
      NAME: assert property (@(posedge CLK) disable iff (!(RST_N)) \
                             (VALID && !READY) |=> \
                             (VALID && $stable(PAYLOAD))) \
          else $error("%s changed while stalled", `"PAYLOAD`")
  ```

  Use this complete structure for `bind_example.sv.j2`; all target-dependent
  statements remain disabled until users replace the example target names and
  define `UVG_BIND_EXAMPLE_ENABLE`:

  ```systemverilog
  {{ header(file_name) }}
  `ifndef UVG_BIND_EXAMPLE__SV
  `define UVG_BIND_EXAMPLE__SV

  `include "../th/bind/common_sva.svh"

  module uvg_bind_checker #(
      parameter int WIDTH = 1
  ) (
      input logic             clk,
      input logic             rst_n,
      input logic [WIDTH-1:0] payload
  );
      `UVG_SVA_NO_X(p_payload_no_x, clk, rst_n, payload)
  endmodule

  // Compile order: target RTL modules/interfaces first, harness second, this
  // file last. Merely adding this file is safe because example binds are gated.
  `ifdef UVG_BIND_EXAMPLE_ENABLE
      // module type: bind every instance of dut_module.
      bind dut_module uvg_bind_checker #(.WIDTH(32)) u_type_check (
          .clk(clk), .rst_n(rst_n), .payload(data)
      );

      // hierarchical instance: bind one DUT instance only.
      bind harness.u_dut uvg_bind_checker #(.WIDTH(32)) u_instance_check (
          .clk(clk), .rst_n(rst_n), .payload(data)
      );

      // parameterized checker and interface instance.
      bind protocol_if uvg_bind_checker #(.WIDTH(DATA_WIDTH)) u_if_check (
          .clk(clk), .rst_n(rst_n), .payload(payload)
      );

      // SVA module/checker attached below a generate hierarchy.
      bind harness.u_dut.g_lane[0].u_lane
          uvg_bind_checker #(.WIDTH(8)) u_lane_check (
              .clk(clk), .rst_n(rst_n), .payload(lane_data)
          );

      // multiple checkers on the same module type.
      bind dut_module uvg_bind_checker #(.WIDTH(8)) u_header_check (
          .clk(clk), .rst_n(rst_n), .payload(header)
      );
      bind dut_module uvg_bind_checker #(.WIDTH(16)) u_payload_check (
          .clk(clk), .rst_n(rst_n), .payload(payload)
      );
  `endif

  `endif
  ```

  For non-AIP harnesses declare `logic clk`, call `` `UVG_CLK(clk, 10ns, 1ns) ``, and declare `logic rst_n`. For every agent replace the direct config call with:

  ```systemverilog
  `UVG_VIF_SET({{ agent.name }}_if,
               "uvm_test_top.m_env.m_{{ agent.name }}_agt*",
               m_{{ agent.name }}_if);
  ```

  Keep the AIP clock creation branch, and remove the harness's `FSDB` initial block so waveform dumping has one owner.

- [ ] **Step 5: Run tests and commit the macro/bind unit**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py -k "macro or bind" -q
  ```

  Expected: PASS.

  Commit:

  ```bash
  git add uvm_gen/generators/harness.py uvm_gen/templates/common/common_dec.sv.j2 \
    uvm_gen/templates/harness tests/test_template_refinement.py
  git commit -m "feat: add UVM wiring and bind helpers"
  ```

### Task 3: Standardize agent modes, VIF ownership, transactions, and AIP ticks

**Files:**

- Modify: `tests/test_template_refinement.py`
- Modify: `tests/test_aip_runtime_integration.py`
- Modify: `uvm_gen/templates/port/agent/{cfg,agent,drv,mon,sqr,base_seq,if,trans}.sv.j2`
- Modify: `uvm_gen/templates/advance/agent/{cfg,agent,drv,mon,sqr,base_seq,if,trans}.sv.j2`

- [ ] **Step 1: Add failing cross-platform agent-contract tests**

  Add tests that generate both platforms with AIP off/on and assert:

  ```python
  def test_agent_has_three_modes_and_no_self_debug(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=False)
      agent_dir = project / "env/agents/axi_agent/src"
      generated = "\n".join(
          path.read_text(encoding="utf-8") for path in agent_dir.glob("*.sv")
      )
      for mode in ("AGENT_MASTER", "AGENT_SLAVE", "AGENT_ONLY_MONITOR"):
          assert mode in generated
      for removed in (
          "AGENT_ONLY_MASTER",
          "AGENT_ONLY_SLAVE",
          "MASTER_NO_MONITOR",
          "SLAVE_NO_MONITOR",
          "m_self_debug_en",
          "m_debug_scb",
          "common_self_debug_scb",
      ):
          assert removed not in generated

  def test_transaction_has_explicit_fail_safe_object_contract(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=False)
      trans = read(project, "env/agents/axi_agent/src/axi_trans.sv")
      assert "`uvm_object_utils(axi_trans)" in trans
      assert "uvm_object_utils_begin" not in trans
      for method in ("do_copy", "do_compare", "convert2string", "do_print"):
          assert f"function" in trans and method in trans
      assert "super.do_copy(rhs);" in trans
      assert "super.do_compare(rhs, comparer)" in trans
      assert "super.do_print(printer);" in trans
      assert "comparison not implemented" in trans
      assert "return 1;" not in function_body(trans, "self_define_do_compare")

  def test_interface_has_role_clocking_blocks(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=False)
      interface = read(project, "env/agents/axi_agent/src/axi_if.sv")
      for clocking in ("mst_drv_cb", "slv_drv_cb", "mon_cb"):
          assert f"clocking {clocking} @(posedge clk);" in interface
      assert "clocking drv_cb" not in interface
  ```

  Update the AIP tick test to require one tick after `finish_item()` and a second tick after `get_response()` in `send_trans_with_rsp`, and one post-`finish_item()` tick in `send_response` where that helper exists. Require the monitor template to contain a commented optional tick only for AIP-on output.

- [ ] **Step 2: Run the agent tests and confirm the old contract fails**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py \
    tests/test_aip_runtime_integration.py -k "agent or transaction or interface or activity" -q
  ```

  Expected: FAIL on five agent modes, self-debug members, field automation, and the missing second response tick.

- [ ] **Step 3: Reduce both agent cfg and construction paths to three modes**

  Use this enum in both cfg templates:

  ```systemverilog
  typedef enum {
      AGENT_MASTER,
      AGENT_SLAVE,
      AGENT_ONLY_MONITOR
  } agent_mode_e;
  ```

  Delete `m_self_debug_en` and every self-debug handle/construction/connection. Keep the Advance FIFO reset control because it still governs its internal monitor FIFO.

  In both agent build phases, get the VIF exactly once and pass it to children:

  ```systemverilog
  `UVG_VIF_GET({{ name }}_if, m_vif)
  m_mon = {{ name }}_mon::type_id::create("m_mon", this);
  m_mon.m_cfg = m_cfg;
  m_mon.m_vif = m_vif;
  case (m_cfg.m_mode)
      AGENT_MASTER, AGENT_SLAVE: begin
          m_sqr = {{ name }}_sqr::type_id::create("m_sqr", this);
          m_drv = {{ name }}_drv::type_id::create("m_drv", this);
          m_sqr.m_cfg = m_cfg;
          m_drv.m_cfg = m_cfg;
          m_drv.m_vif = m_vif;
      end
      AGENT_ONLY_MONITOR: begin
      end
      default: `uvm_fatal("AGENT_MODE", "unsupported agent mode")
  endcase
  ```

  Child build phases no longer call `uvm_config_db::get`; they check that the parent-provided `m_vif` is non-null and report an internal propagation fatal otherwise. Driver dispatch becomes exactly:

  ```systemverilog
  case (m_cfg.m_mode)
      AGENT_MASTER: master_drive();
      AGENT_SLAVE:  slave_drive();
      default: `uvm_fatal("AGENT_MODE", "monitor-only mode has no driver")
  endcase
  ```

- [ ] **Step 4: Add role-specific interface clocking blocks**

  Replace `drv_cb` with:

  ```systemverilog
  clocking mst_drv_cb @(posedge clk);
      // default input #1step output #0.1ns;
      // M2S protocol fields are outputs; S2M fields are inputs.
  endclocking

  clocking slv_drv_cb @(posedge clk);
      // default input #1step output #0.1ns;
      // M2S protocol fields are inputs; S2M fields are outputs.
  endclocking

  clocking mon_cb @(posedge clk);
      // default input #1step;
      // Every observed protocol field is an input.
  endclocking

  modport mst_drv_mp (clocking mst_drv_cb);
  modport slv_drv_mp (clocking slv_drv_cb);
  modport mon_mp     (clocking mon_cb);
  ```

  Update driver comments to show `mst_drv_cb` and `slv_drv_cb` explicitly rather than an ambiguous `drv_cb`.

- [ ] **Step 5: Replace each generated transaction with the explicit UVM object contract**

  Use the same typed Jinja implementation in both transaction templates:

  ```systemverilog
  `uvm_object_utils({{ name }}_trans)

  virtual function void do_copy(uvm_object rhs);
      {{ name }}_trans typed_rhs;
      super.do_copy(rhs);
      if (!$cast(typed_rhs, rhs))
          `uvm_fatal("TRANS_COPY", "{{ name }}_trans do_copy type mismatch")
      // Field example: this.addr = typed_rhs.addr;
  endfunction

  virtual function bit do_compare(uvm_object rhs, uvm_comparer comparer);
      {{ name }}_trans typed_rhs;
      string diff;
      if (!$cast(typed_rhs, rhs)) begin
          if (comparer != null)
              comparer.print_msg("{{ name }}_trans compare type mismatch");
          return 0;
      end
      if (!super.do_compare(rhs, comparer))
          return 0;
      if (!self_define_do_compare(typed_rhs, diff, -1)) begin
          if (comparer != null)
              comparer.print_msg(diff);
          return 0;
      end
      return 1;
  endfunction

  virtual function string convert2string();
      return "{{ name }}_trans{}";
      // Field example: return $sformatf("addr=0x%0h", addr);
  endfunction

  virtual function void do_print(uvm_printer printer);
      super.do_print(printer);
      printer.print_string("summary", convert2string());
      // Field example: printer.print_field_int("addr", addr, $bits(addr), UVM_HEX);
  endfunction

  virtual function bit self_define_do_compare(
      {{ name }}_trans cmp_trans,
      output string diff,
      input int kind = -1
  );
      diff = "comparison not implemented: add protocol fields to {{ name }}_trans";
      return 0;
      // Field example: compare addr/data here and replace the fail-safe return.
  endfunction
  ```

  Keep `get_scb_stream_id()` returning `'1` and `get_scb_kind()` returning `-1`, so the default checker remains one unordered multiset stream without an invented ID/tag.

- [ ] **Step 6: Correct AIP activity boundaries in sequence and monitor templates**

  For AIP-on output, `send_trans()` ticks once after `finish_item()`. `send_trans_with_rsp()` uses:

  ```systemverilog
  finish_item(tr);
  aip_activity::tick();
  get_response(rsp);
  aip_activity::tick();
  ```

  Any generated `send_response()` helper ticks once after its `finish_item()`. Do not add a tick macro and do not add driver ticks.

  In the AIP-only monitor comment, show the optional placement immediately after publication:

  ```systemverilog
  // After assembling one complete transaction:
  // m_ap.write(tr);
  // aip_activity::tick();
  // Enable the tick only when observed bus activity should extend end_test idle.
  // Call it once per completed transaction/accepted beat, never every clock cycle.
  ```

- [ ] **Step 7: Run the focused agent/AIP tests and commit**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py tests/test_aip_runtime_integration.py -q
  ```

  Expected: PASS.

  Commit:

  ```bash
  git add uvm_gen/templates/port/agent uvm_gen/templates/advance/agent \
    tests/test_template_refinement.py tests/test_aip_runtime_integration.py
  git commit -m "feat: harden generated UVM agent contracts"
  ```

### Task 4: Convert Advance to task-only transaction routing

**Files:**

- Modify: `tests/test_template_refinement.py`
- Modify: `tests/test_common_scb_v2_generation.py`
- Modify: `uvm_gen/templates/advance/agent/agent.sv.j2`
- Modify: `uvm_gen/templates/advance/agent/sqr.sv.j2`
- Modify: `uvm_gen/templates/advance/agent/base_seq.sv.j2`
- Modify: `uvm_gen/templates/advance/env/rm.sv.j2`
- Modify: `uvm_gen/templates/advance/env/checker.sv.j2`
- Modify: `uvm_gen/templates/advance/env/env.sv.j2`

- [ ] **Step 1: Replace Advance analysis-path expectations with task-API tests**

  Add this generated contract:

  ```python
  def test_advance_uses_only_explicit_transaction_tasks(tmp_path):
      project = generate(tmp_path, PlatformType.ADVANCE, aip_core=False)
      agent = read(project, "env/agents/axi_agent/src/axi_agent.sv")
      sequencer = read(project, "env/agents/axi_agent/src/axi_sqr.sv")
      rm = read(project, "env/top_rm.sv")
      checker = read(project, "env/top_checker.sv")
      env = read(project, "env/top_env.sv")

      assert "task axi_agent::get_mon_item" in agent
      assert "function bit axi_agent::try_get_mon_item" in agent
      assert agent.count("uvm_tlm_analysis_fifo#(axi_trans)") == 1
      assert "m_req_fifo" not in agent + sequencer
      assert "m_rsp_fifo" not in agent + sequencer
      assert "m_mon_fifo" not in sequencer
      assert "task top_rm::predict_axi" in rm
      assert "task top_checker::send_axi_actual" in checker
      assert "task top_checker::send_axi_expected" in checker

      executable_env = strip_sv_comments(env)
      for routed_connection in (
          "m_ap.connect(m_rm",
          "m_ap.connect(m_scb",
          "m_expected_ap.connect",
      ):
          assert routed_connection not in executable_env
      assert "get_mon_item -> predict_axi -> send_axi_actual/send_axi_expected" in env

  def test_port_keeps_fifo_routing_and_reset_workers(tmp_path):
      project = generate(tmp_path, PlatformType.PORT, aip_core=False)
      env = read(project, "env/top_env.sv")
      assert "m_axi_agt_mon_to_rm_fifo" in env
      assert "m_rm_axi_trans_to_scb_fifo" in env
      assert "m_agt_axi_trans_to_scb_fifo" in env
      assert "m_rm.stop_workers();" in env
      assert "m_scb.wait_for_workers_stopped();" in env
      assert "m_rm.request_workers_restart();" in env
  ```

  Rewrite the Advance-specific wiring helpers in `tests/test_common_scb_v2_generation.py` to inspect these tasks rather than analysis imps/ports. Leave all PORT lifecycle helpers unchanged.

- [ ] **Step 2: Run the Advance/PORT topology tests and confirm failure**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py \
    tests/test_common_scb_v2_generation.py -k "advance or port" -q
  ```

  Expected: FAIL because Advance still auto-connects monitor, RM, and checker analysis paths.

- [ ] **Step 3: Expose one agent-local monitor consumer API**

  Keep only `m_mon_fifo` inside the Advance agent, connect `m_mon.m_ap` to it, and add:

  ```systemverilog
  task {{ name }}_agent::get_mon_item(output {{ name }}_trans tr);
      m_mon_fifo.get(tr);
  endtask

  function bit {{ name }}_agent::try_get_mon_item(output {{ name }}_trans tr);
      return m_mon_fifo.try_get(tr);
  endfunction
  ```

  State next to these methods that only one external consumer may drain this FIFO. Remove `m_req_fifo`, `m_rsp_fifo`, `m_mon_ap`, and every FIFO handle from the Advance sequencer. Remove `wait_trans()` and `wait_request()` from the base sequence; keep `send_trans()`, `send_trans_with_rsp()`, and `send_response()` for active protocol behavior.

- [ ] **Step 4: Replace Advance RM/checker callbacks with per-agent tasks**

  For each agent, generate this RM shell:

  ```systemverilog
  virtual task predict_{{ agent.name }}(
      input {{ agent.name }}_trans observed,
      ref {{ agent.name }}_trans expected_q[$]
  );
      expected_q.delete();
      // Field-model example:
      // {{ agent.name }}_trans expected;
      // if (!$cast(expected, observed.clone()))
      //     `uvm_fatal("RM_CLONE", "failed to clone {{ agent.name }} transaction")
      // Update expected from the reference model, then expected_q.push_back(expected).
  endtask
  ```

  The checker owns the same typed `common_uvm_scb` instances as today and generates:

  ```systemverilog
  task {{ block_name }}_checker::send_{{ agent.name }}_actual(
      input {{ agent.name }}_trans tr
  );
      m_scb_rec_dut_trans_total_cnt++;
      if (tr == null)
          m_{{ agent.name }}_scb.push_actual(tr, '1, -1);
      else
          m_{{ agent.name }}_scb.push_actual(
              tr, tr.get_scb_stream_id(), tr.get_scb_kind());
  endtask

  task {{ block_name }}_checker::send_{{ agent.name }}_expected(
      input {{ agent.name }}_trans tr
  );
      m_scb_rec_rm_trans_total_cnt++;
      if (tr == null)
          m_{{ agent.name }}_scb.push_expected(tr, '1, -1);
      else
          m_{{ agent.name }}_scb.push_expected(
              tr, tr.get_scb_stream_id(), tr.get_scb_kind());
  endtask
  ```

  Remove Advance analysis imp/port declarations, construction, and callbacks.

- [ ] **Step 5: Remove only transaction routing from Advance env**

  Keep agent/RM/checker/vsqr construction and sequencer-handle assignment. Remove monitor-to-RM, monitor-to-checker, and RM-to-checker connections. Add a non-executable per-agent usage example:

  ```systemverilog
  // User-owned transaction loop:
  // {{ agent.name }}_trans observed;
  // {{ agent.name }}_trans expected_q[$];
  // m_{{ agent.name }}_agt.get_mon_item(observed);
  // m_rm.predict_{{ agent.name }}(observed, expected_q);
  // m_scb.send_{{ agent.name }}_actual(observed);
  // foreach (expected_q[i])
  //     m_scb.send_{{ agent.name }}_expected(expected_q[i]);
  // Flow: get_mon_item -> predict_{{ agent.name }} -> send_{{ agent.name }}_actual/send_{{ agent.name }}_expected
  ```

- [ ] **Step 6: Run topology, null-routing, and PORT lifecycle tests and commit**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py \
    tests/test_common_scb_v2_generation.py \
    tests/test_vcs_lifecycle_script.py -q
  ```

  Expected: PASS, including the unchanged PORT zero/one/two-agent reset matrix.

  Commit:

  ```bash
  git add uvm_gen/templates/advance tests/test_template_refinement.py \
    tests/test_common_scb_v2_generation.py tests/test_vcs_lifecycle_script.py
  git commit -m "feat: expose task-only Advance transaction flow"
  ```

### Task 5: Move all AIP references to the `AIP_HOME/aip_core` layout

**Files:**

- Modify: `tests/test_aip_runtime_integration.py`
- Modify: `tests/test_common_scb_v2_generation.py`
- Modify: `tests/vcs/scb_adapter_smoke.tcl`
- Modify: `tests/vcs/run_aip_runtime_smoke.sh`
- Modify: `tests/vcs/run_common_scb_aip_adapter.sh`
- Modify: `tests/vcs/run_generated_scb_matrix.sh`
- Modify: `uvm_gen/templates/cfg/tb_f.j2`
- Modify: `uvm_gen/templates/tc/tc_tcl_demo.tcl.j2`

- [ ] **Step 1: Change tests to require one AIP root convention**

  Require the AIP-on root filelist to contain exactly:

  ```text
  +incdir+$AIP_HOME/aip_core
  $AIP_HOME/aip_core/aip_core_pkg.sv
  ```

  Require the Tcl demo and smoke script to contain:

  ```tcl
  source $env(AIP_HOME)/aip_core/aip_cmd.tcl
  ```

  Add a repository-wide generated-output assertion that `AIP_CORE_HOME` is absent. Update runner-contract tests to expect `AIP_HOME` and an `aip_core/` child.

- [ ] **Step 2: Run AIP path tests and confirm the old variable fails**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_aip_runtime_integration.py \
    tests/test_common_scb_v2_generation.py -k "aip" -q
  ```

  Expected: FAIL on the old `$AIP_CORE_HOME` filelist and Tcl source commands.

- [ ] **Step 3: Change generated paths and VCS runner inputs**

  Replace the AIP section of `cfg/tb_f.j2` with:

  ```text
  {% if aip_core %}
  +incdir+$AIP_HOME/aip_core
  $AIP_HOME/aip_core/aip_core_pkg.sv
  {% endif %}
  ```

  Change every runner to accept an AIP root, validate both
  `${aip_home}/aip_core/aip_core_pkg.sv` and
  `${aip_home}/aip_core/aip_cmd.tcl`, and export only `AIP_HOME`. The runtime
  and generated-matrix runners read the root from argument 5:

  ```bash
  aip_home=$(realpath -- "$5")
  aip_core_dir="${aip_home}/aip_core"
  export AIP_HOME="${aip_home}"
  aip_compile_sources=(
      "+incdir+${AIP_HOME}/aip_core"
      "${AIP_HOME}/aip_core/aip_core_pkg.sv"
  )
  ```

  The standalone adapter runner reads the root from argument 2:

  ```bash
  aip_home=$(realpath -- "$2")
  aip_core_dir="${aip_home}/aip_core"
  export AIP_HOME="${aip_home}"
  ```

  Use `"${aip_compile_sources[@]}"` in the standalone adapter compile. Do not create a compatibility alias.

- [ ] **Step 4: Run AIP regression and commit**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_aip_runtime_integration.py \
    tests/test_common_scb_v2_generation.py -q
  ```

  Expected: PASS.

  Commit:

  ```bash
  git add uvm_gen/templates/cfg/tb_f.j2 uvm_gen/templates/tc/tc_tcl_demo.tcl.j2 \
    tests/test_aip_runtime_integration.py tests/test_common_scb_v2_generation.py \
    tests/vcs
  git commit -m "refactor: use AIP_HOME installation root"
  ```

### Task 6: Repair harness/filelist placement and VCS cfg examples

**Files:**

- Modify: `tests/test_template_refinement.py`
- Modify: `Makefile.uvm_template`
- Modify: `uvm_gen/templates/cfg/env_f.j2`
- Modify: `uvm_gen/templates/cfg/tb_f.j2`
- Modify: `uvm_gen/templates/cfg/initreg_cfg.j2`
- Modify: `uvm_gen/templates/cfg/xprop_cfg.j2`
- Modify: `uvm_gen/templates/cfg/coverage_cfg.j2`
- Modify: `uvm_gen/templates/cfg/wave_tcl.j2`

- [ ] **Step 1: Add exact cfg/filelist regression tests**

  Add:

  ```python
  def test_root_filelist_compiles_each_tree_once(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=True)
      env_f = active_filelist_lines(read(project, "cfg/env.f"))
      tb_f = active_filelist_lines(read(project, "cfg/tb.f"))
      assert env_f[-1] == "../th/harness.sv"
      assert "../th/harness.sv" not in tb_f
      assert tb_f == [
          "+incdir+$AIP_HOME/aip_core",
          "$AIP_HOME/aip_core/aip_core_pkg.sv",
          "-F   ./dut.f",
          "-F   ./env.f",
          "-F   ../tc/tc.f",
      ]

  def test_cfg_examples_use_reviewed_vcs_syntax(tmp_path, platform_type):
      project = generate(tmp_path, platform_type, aip_core=False)
      xprop = read(project, "cfg/xprop.cfg")
      initreg = read(project, "cfg/initreg.cfg")
      coverage = read(project, "cfg/coverage.cfg")
      wave = read(project, "cfg/wave.tcl")
      assert "merge = tmerge;" in xprop
      assert "tree {harness} {xpropOn};" in xprop
      assert "xpropMode" not in xprop
      assert "+vcs+initreg+random" in initreg
      assert "+initreg+" not in initreg.replace("+vcs+initreg+", "")
      assert "-cm_cond obsv" not in coverage
      assert not any(
          line.strip().startswith(("+tree harness.u_dut", "-tree harness.u_dut"))
          for line in coverage.splitlines()
      )
      assert 'fsdbDumpvars 0 "harness"' in wave
      assert 'fsdbDumpvars 0 "tb"' not in wave
      assert "�" not in wave
  ```

  Add a Makefile assertion that `VCS_OPTS` uses only `-f $(TB_F)`, not `$(DUT_F)` or `$(ENV_F)`, and that FSDB runtime uses `-ucli -i`.

- [ ] **Step 2: Run cfg tests and confirm failure**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py -k "filelist or cfg or makefile" -q
  ```

  Expected: FAIL on harness placement, duplicate root Makefile inputs, invalid xprop/initreg examples, active nonexistent DUT coverage paths, and the corrupted wave text/top.

- [ ] **Step 3: Move harness to the end of `cfg/env.f` and simplify the root list**

  Append these lines after `../env/{{ block_name }}_env.sv`:

  ```text
  ../th/harness.sv
  # Optional bind checks compile after the harness:
  # ../th/bind/bind_example.sv
  ```

  Remove the harness from `cfg/tb_f.j2`. Keep only the AIP package block followed by `dut.f`, `env.f`, and `tc.f` exactly once. Change `Makefile.uvm_template` to:

  ```make
  VCS_OPTS := -full64 -sverilog \
              -ntb_opts uvm-1.2 \
              -timescale=$(TIMESCALE) \
              -debug_access+all \
              -kdb -lca \
              +define+UVM_NO_DEPRECATED \
              -f $(TB_F) \
              -Mdir=$(BUILD_DIR)/csrc \
              -o $(SIMV) \
              -l $(CMP_LOG)
  ```

  Use `-ucli -i ../../../$(WAVE_TCL)` for FSDB runs.

- [ ] **Step 4: Replace verbose cfg files with short reviewed examples**

  `xprop.cfg` active content:

  ```text
  // Compile with: vcs ... -xprop=xprop.cfg -f tb.f
  // tmerge evaluates the 0 and 1 branches and merges their results.
  // xmerge is more pessimistic and directly propagates X.
  merge = tmerge;
  tree {harness} {xpropOn};
  // instance {harness.u_dut.u0} {xpropOff};
  // module {sram_model} {xpropOff};
  ```

  `initreg.cfg` active content:

  ```text
  // Pass this response file during compile: vcs ... -f initreg.cfg
  +vcs+initreg+random
  // Alternatives, enable one global policy only:
  // +vcs+initreg+0
  // +vcs+initreg+1
  ```

  `coverage.cfg` contains no active hierarchy because a generated shell has no DUT instance. It documents these opt-in examples without `-cm_cond obsv`:

  ```text
  // Compile: vcs ... -cm line+cond+fsm+tgl+branch -cm_hier coverage.cfg
  // Enable after adding a DUT:
  // +tree harness.u_dut
  // -module sram_model
  ```

  `wave.tcl` becomes the sole FSDB entry point:

  ```tcl
  # Run with: ./simv -ucli -i wave.tcl +UVM_TESTNAME=tc_base
  fsdbDumpfile "wave.fsdb"
  fsdbDumpvars 0 "harness"
  run
  quit
  ```

- [ ] **Step 5: Run cfg tests and the complete local suite, then commit**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest -q
  ```

  Expected: all collected tests PASS.

  Commit:

  ```bash
  git add Makefile.uvm_template uvm_gen/templates/cfg tests/test_template_refinement.py
  git commit -m "fix: generate reviewed VCS configuration"
  ```

### Task 7: Add VCS semantic coverage for macros, transactions, and cfg

**Files:**

- Create: `tests/vcs/template_refinement_tb.sv`
- Create: `tests/vcs/run_template_refinement.sh`
- Modify: `tests/test_template_refinement.py`
- Modify: `tests/vcs/run_generated_scb_matrix.sh`

- [ ] **Step 1: Add a test requiring executable VCS assets and closed contracts**

  Assert that the new runner is executable and contains these commands/markers:

  ```python
  def test_template_refinement_vcs_assets_cover_semantics():
      runner = (REPOSITORY / "tests/vcs/run_template_refinement.sh")
      source = (REPOSITORY / "tests/vcs/template_refinement_tb.sv")
      assert runner.is_file() and runner.stat().st_mode & 0o111
      assert source.is_file()
      script = runner.read_text(encoding="utf-8")
      for token in (
          "+define+UVG_WIDTH_MISMATCH",
          "+UVG_SKIP_VIF_SET",
          "-xprop=xprop.cfg",
          "-f initreg.cfg",
          "-cm_hier coverage.cfg",
          "-ucli -i wave.tcl",
          "TEMPLATE_REFINEMENT_VCS_PASS",
      ):
          assert token in script
  ```

- [ ] **Step 2: Run the asset test and confirm files are missing**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py -k "vcs_assets" -q
  ```

  Expected: FAIL because the VCS source and runner do not exist.

- [ ] **Step 3: Create the standalone SystemVerilog semantic fixture**

  Create `tests/vcs/template_refinement_tb.sv` with this complete fixture:

  ```systemverilog
  `timescale 1ns/1ps

  import uvm_pkg::*;
  import common_lib_pkg::*;
  import axi_agent_pkg::*;

  interface uvg_probe_if;
      logic marker;
  endinterface

  class uvg_vif_consumer extends uvm_component;
      `uvm_component_utils(uvg_vif_consumer)
      virtual uvg_probe_if m_vif;

      function new(string name="uvg_vif_consumer", uvm_component parent=null);
          super.new(name, parent);
      endfunction

      function void build_phase(uvm_phase phase);
          super.build_phase(phase);
          `UVG_VIF_GET(uvg_probe_if, m_vif)
      endfunction
  endclass

  class template_refinement_test extends uvm_test;
      `uvm_component_utils(template_refinement_test)
      uvg_vif_consumer m_consumer;

      function new(string name="template_refinement_test", uvm_component parent=null);
          super.new(name, parent);
      endfunction

      function void build_phase(uvm_phase phase);
          super.build_phase(phase);
          m_consumer = uvg_vif_consumer::type_id::create("m_consumer", this);
      endfunction

      task run_phase(uvm_phase phase);
          axi_trans tr;
          axi_trans copied;
          uvm_object cloned;

          phase.raise_objection(this);
          wait (template_refinement_tb.connection_checks_done);
          wait (template_refinement_tb.probe_rst_n === 1'b1);
          if (template_refinement_tb.probe_clk !== 1'b0)
              `uvm_fatal("UVG_RSTN", "reset did not deassert on a falling edge")
          tr = new("tr");
          cloned = tr.clone();
          if ((cloned == null) || !$cast(copied, cloned))
              `uvm_fatal("TRANS_CLONE", "generated transaction clone/cast failed")
          if (tr.compare(copied))
              `uvm_fatal("TRANS_COMPARE", "empty comparison hook passed unexpectedly")
          tr.print();
          $display("TEMPLATE_REFINEMENT_VCS_PASS");
          phase.drop_objection(this);
      endtask
  endclass

  module template_refinement_tb;
      logic probe_clk;
      logic probe_rst_n;
      bit connection_checks_done;
      uvg_probe_if probe_if();

      logic master_m2s_vif;
      wire  master_m2s_rtl;
      logic master_s2m_rtl;
      wire  master_s2m_vif;
      logic slave_m2s_rtl;
      wire  slave_m2s_vif;
      logic slave_s2m_vif;
      wire  slave_s2m_rtl;
      logic monitor_m2s_rtl;
      wire  monitor_m2s_vif;
      logic monitor_s2m_rtl;
      wire  monitor_s2m_vif;

      `UVG_CLK(probe_clk, 10ns, 1ns)
      `UVG_RSTN(probe_rst_n, probe_clk, 2)
      `UVG_STATIC_ASSERT(uvg_positive_assert,
                         $bits(master_m2s_rtl) == $bits(master_m2s_vif),
                         "equal widths required")

      `UVG_IF_CONNECT(MASTER,  M2S, master_m2s_rtl,  master_m2s_vif);
      `UVG_IF_CONNECT(MASTER,  S2M, master_s2m_rtl,  master_s2m_vif);
      `UVG_IF_CONNECT(SLAVE,   M2S, slave_m2s_rtl,   slave_m2s_vif);
      `UVG_IF_CONNECT(SLAVE,   S2M, slave_s2m_rtl,   slave_s2m_vif);
      `UVG_IF_CONNECT(MONITOR, M2S, monitor_m2s_rtl, monitor_m2s_vif);
      `UVG_IF_CONNECT(MONITOR, S2M, monitor_s2m_rtl, monitor_s2m_vif);

  `ifdef UVG_WIDTH_MISMATCH
      logic [1:0] bad_rtl;
      wire        bad_vif;
      `UVG_IF_CONNECT(MONITOR, M2S, bad_rtl, bad_vif);
  `endif

      initial begin
          connection_checks_done = 0;
          master_m2s_vif = 1;
          master_s2m_rtl = 1;
          slave_m2s_rtl = 1;
          slave_s2m_vif = 1;
          monitor_m2s_rtl = 1;
          monitor_s2m_rtl = 1;
          #1ns;
          if ({master_m2s_rtl, master_s2m_vif,
               slave_m2s_vif, slave_s2m_rtl,
               monitor_m2s_vif, monitor_s2m_vif} !== 6'b111111)
              $fatal(1, "UVG_IF_CONNECT direction check failed");
          connection_checks_done = 1;
      end

      initial begin
          if (!$test$plusargs("UVG_SKIP_VIF_SET"))
              `UVG_VIF_SET(uvg_probe_if,
                           "uvm_test_top.m_consumer",
                           probe_if);
          run_test("template_refinement_test");
      end
  endmodule
  ```

- [ ] **Step 4: Create the VCS runner with positive and negative legs**

  Start `run_template_refinement.sh` with strict mode, resolve both arguments,
  validate `${AIP_HOME}/aip_core/aip_core_pkg.sv`, copy the generated project
  and fixture into a `mktemp -d` work area, and install this log guard:

  ```bash
  #!/usr/bin/env bash
  set -euo pipefail

  if [[ $# -ne 2 ]]; then
      echo "Usage: $0 GENERATED_OFF_PROJECT AIP_HOME" >&2
      exit 2
  fi

  repo_root=$(cd "$(dirname "$0")/../.." && pwd)
  project_dir=$(realpath -- "$1")
  aip_home=$(realpath -- "$2")
  if [[ ! -f ${aip_home}/aip_core/aip_core_pkg.sv ]]; then
      echo "AIP package missing below AIP_HOME: ${aip_home}" >&2
      exit 2
  fi

  run_dir=$(mktemp -d "${TMPDIR:-/tmp}/template-refinement.XXXXXX")
  cleanup() { rm -rf -- "${run_dir}"; }
  trap cleanup EXIT
  cp -R "${project_dir}/." "${run_dir}/"
  cp -- "${repo_root}/tests/vcs/template_refinement_tb.sv" "${run_dir}/cfg/"

  reject_bad_log() {
      local log=$1
      if grep -Eiq '\{\{|\{%|%\}|Error-\[[^]]+\]|syntax error|undefined (macro|type)|invalid command name' "${log}"; then
          echo "unexpected compile/runtime diagnostic: ${log}" >&2
          tail -n 100 "${log}" >&2
          return 1
      fi
  }
  ```

  In `${run_dir}/cfg`, execute these positive and negative macro/VIF legs:

  ```bash
  vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
      -F ../common/common_lib_pkg.f \
      -F ../env/agents/axi_agent/axi_agent.f \
      template_refinement_tb.sv -top template_refinement_tb \
      -o simv_template -l compile_template.log
  ./simv_template +UVM_TESTNAME=template_refinement_test -l run_template.log
  grep -Fxq TEMPLATE_REFINEMENT_VCS_PASS run_template.log

  if vcs -full64 -sverilog -ntb_opts uvm-1.2 \
      +define+UVG_WIDTH_MISMATCH \
      -F ../common/common_lib_pkg.f \
      -F ../env/agents/axi_agent/axi_agent.f \
      template_refinement_tb.sv -top template_refinement_tb \
      -o simv_bad_width -l compile_bad_width.log; then
      echo "width mismatch unexpectedly elaborated" >&2
      exit 1
  fi

  ./simv_template +UVM_TESTNAME=template_refinement_test \
      +UVG_SKIP_VIF_SET -l run_missing_vif.log || true
  grep -Eq 'UVG_VIF_GET.*field=m_vif' run_missing_vif.log
  if grep -Fq TEMPLATE_REFINEMENT_VCS_PASS run_missing_vif.log; then
      echo "missing VIF leg reached pass marker" >&2
      exit 1
  fi
  ```

  Call `reject_bad_log compile_template.log` and
  `reject_bad_log run_template.log`, and require exactly one zero `UVM_ERROR`
  and `UVM_FATAL` summary in the positive run. The width mismatch leg is the
  only compile whose unresolved-module error is expected.

  From the generated `cfg/` directory, separately compile:

  ```bash
  vcs -full64 -sverilog -ntb_opts uvm-1.2 -debug_access+all -lca -f tb.f \
      -xprop=xprop.cfg -top harness -o simv_xprop -l compile_xprop.log
  vcs -full64 -sverilog -ntb_opts uvm-1.2 -f initreg.cfg -f tb.f \
      -top harness -o simv_initreg -l compile_initreg.log
  vcs -full64 -sverilog -ntb_opts uvm-1.2 -f tb.f \
      -cm line+cond+fsm+tgl+branch -cm_hier coverage.cfg \
      -top harness -o simv_cov -l compile_cov.log
  ./simv_xprop +UVM_TESTNAME=tc_base -ucli -i wave.tcl -l run_wave.log
  ```

  Run `reject_bad_log` on all three cfg compile logs and `run_wave.log`, require
  `TC PASSED.(warning:<n>,error:0,fatal:0)`, and reject any nonzero UVM
  error/fatal summary. Print exactly
  `TEMPLATE_REFINEMENT_VCS_GATE_PASS` after all legs. Update
  `run_generated_scb_matrix.sh` so its AIP-on validation expects
  registry/adapter but no activity subscriber.

- [ ] **Step 5: Run local script-contract tests and commit VCS assets**

  Run:

  ```bash
  chmod +x tests/vcs/run_template_refinement.sh
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py tests/test_aip_runtime_integration.py -q
  ```

  Expected: PASS.

  Commit:

  ```bash
  git add tests/test_template_refinement.py tests/test_aip_runtime_integration.py \
    tests/vcs/template_refinement_tb.sv tests/vcs/run_template_refinement.sh \
    tests/vcs/run_generated_scb_matrix.sh
  git commit -m "test: add VCS template refinement gate"
  ```

- [ ] **Step 6: Run all required VCS gates on `10.11.10.53`**

  Create four local generated projects (Advance/PORT × AIP off/on) with this exact local step:

  ```bash
  template_project_stage=$(mktemp -d /tmp/uvm-template-projects.XXXXXX)
  export UVG_TEMPLATE_PROJECT_STAGE="${template_project_stage}"
  /home/ryan/workspace/ryan/simflow/.venv/bin/python - <<'PY'
  import os
  from pathlib import Path

  from uvm_gen.config import AgentConfig, PlatformType, ProjectConfig
  from uvm_gen.generators.platform import PlatformGenerator

  stage = Path(os.environ["UVG_TEMPLATE_PROJECT_STAGE"])
  for platform in (PlatformType.ADVANCE, PlatformType.PORT):
      for aip_core in (False, True):
          label = f"{platform.value}_{'on' if aip_core else 'off'}"
          config = ProjectConfig(
              block_name=label,
              author="vcs-gate",
              agents=[AgentConfig("axi")],
              platform_type=platform,
              aip_core=aip_core,
              output_dir=str(stage),
          )
          PlatformGenerator(config).generate()
  PY
  ```

  Stage the repository, generated `top/` project directories, and local
  `../aip_core` checkout under `/tmp/uvm-template-refinement`, then run through
  a login shell:

  ```bash
  rsync -az --exclude .git ./ ubuntu@10.11.10.53:/tmp/uvm-template-refinement/repo/
  rsync -az ../aip_core/ ubuntu@10.11.10.53:/tmp/uvm-template-refinement/aip/aip_core/
  rsync -az "${template_project_stage}"/ \
      ubuntu@10.11.10.53:/tmp/uvm-template-refinement/projects/

  ssh ubuntu@10.11.10.53 'bash -lc "
      source ~/.bashrc
      cd /tmp/uvm-template-refinement/repo
      tests/vcs/run_generated_scb_matrix.sh \
          /tmp/uvm-template-refinement/projects/advance_off \
          /tmp/uvm-template-refinement/projects/advance_on \
          /tmp/uvm-template-refinement/projects/port_off \
          /tmp/uvm-template-refinement/projects/port_on \
          /tmp/uvm-template-refinement/aip \
          tests/vcs/scb_adapter_smoke.tcl
      tests/vcs/run_aip_runtime_smoke.sh \
          /tmp/uvm-template-refinement/projects/advance_off \
          /tmp/uvm-template-refinement/projects/advance_on \
          /tmp/uvm-template-refinement/projects/port_off \
          /tmp/uvm-template-refinement/projects/port_on \
          /tmp/uvm-template-refinement/aip
      tests/vcs/run_common_scb_v2.sh \
          /tmp/uvm-template-refinement/projects/port_off/common \
          tests/vcs/common_scb_unit_tb.sv
      tests/vcs/run_common_scb_aip_adapter.sh \
          /tmp/uvm-template-refinement/projects/port_on \
          /tmp/uvm-template-refinement/aip \
          tests/vcs/common_scb_aip_adapter_tb.sv
      tests/vcs/run_port_reset_lifecycle.sh \
          /tmp/uvm-template-refinement/projects/port_off \
          tests/vcs/port_reset_lifecycle.sv
      tests/vcs/run_template_refinement.sh \
          /tmp/uvm-template-refinement/projects/advance_off \
          /tmp/uvm-template-refinement/aip
  "'
  ```

  Expected: all six runners exit zero and print their unique PASS summaries. If VCS rejects an example that local text tests accepted, preserve the failing log, correct the template and regression first, then rerun the entire affected gate.

### Task 8: Update user documentation and perform final verification

**Files:**

- Modify: `README.md`
- Modify: `tests/test_template_refinement.py`

- [ ] **Step 1: Add documentation assertions before editing README**

  Require README to describe:

  ```python
  def test_readme_describes_final_platform_contract():
      readme = (REPOSITORY / "README.md").read_text(encoding="utf-8")
      for required in (
          "Advance task-only",
          "PORT TLM/FIFO",
          "get_mon_item",
          "predict_axi",
          "send_axi_actual",
          "send_axi_expected",
          "AGENT_ONLY_MONITOR",
          "UVG_IF_CONNECT",
          "th/bind/bind_example.sv",
          "$AIP_HOME/aip_core",
          "+SCB_REPORT_LIMIT=-1",
      ):
          assert required in readme
      for removed in (
          "common_uvm_scb_legacy",
          "aip_activity_subscriber",
          "common_report_server",
          "AIP_CORE_HOME",
          "AGENT_ONLY_MASTER",
          "AGENT_ONLY_SLAVE",
      ):
          assert removed not in readme
  ```

- [ ] **Step 2: Run the README test and confirm stale documentation fails**

  Run:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest \
    tests/test_template_refinement.py -k readme -q
  ```

  Expected: FAIL because README still advertises the legacy scoreboard and activity subscriber.

- [ ] **Step 3: Rewrite the affected README sections**

  Update the output tree to show:

  ```text
  th/
  ├── harness.sv
  └── bind/
      ├── bind_example.sv
      └── common_sva.svh
  ```

  Describe PORT as environment-owned TLM/FIFO routing and Advance as an explicit task-only shell. Include the exact `axi` example:

  ```systemverilog
  m_env.m_axi_agt.get_mon_item(observed);
  m_env.m_rm.predict_axi(observed, expected_q);
  m_env.m_scb.send_axi_actual(observed);
  foreach (expected_q[i])
      m_env.m_scb.send_axi_expected(expected_q[i]);
  ```

  Document the three modes, transaction fail-safe comparison, report limit values `10`, `0`, and `-1`, optional monitor tick behavior and its `end_test timeout` safeguard, `UVG_IF_CONNECT(ROLE, FLOW, RTL_SIG, VIF_SIG)`, disabled bind examples, harness placement at the end of `cfg/env.f`, and the sole AIP installation layout `$AIP_HOME/aip_core`.

- [ ] **Step 4: Run final local verification**

  Run fresh:

  ```bash
  /home/ryan/workspace/ryan/simflow/.venv/bin/python -m pytest -q
  git diff --check
  rg -n 'AIP_CORE_HOME|AGENT_ONLY_MASTER|AGENT_ONLY_SLAVE|common_uvm_scb_legacy|aip_activity_subscriber|common_report_server|m_self_debug_en|m_debug_scb' \
      README.md uvm_gen
  ```

  Expected: pytest exits zero, `git diff --check` prints nothing, and the final `rg` prints nothing. References inside historical design/plan documents are intentionally outside this scan.

- [ ] **Step 5: Commit documentation and record verification evidence**

  Commit:

  ```bash
  git add README.md tests/test_template_refinement.py
  git commit -m "docs: describe refined UVM templates"
  ```

  Re-run the complete local suite and the six remote VCS commands from Task 7 after this commit. Record the pytest count, every remote PASS marker, `git status --short --branch`, and `git log --oneline origin/main..HEAD` in the implementation handoff. Do not claim completion from an earlier run.
