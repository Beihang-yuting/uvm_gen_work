# aip_core 深度集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 uvm_gen 现有 ADVANCE/PORT 模式上叠加 `aip_core: true` 开关，生成原生集成 aip_core 的 UVM 环境。

**Architecture:** 通过 `ProjectConfig.aip_core` 布尔字段控制，Jinja2 模板用 `{% if aip_core %}` 条件分支。现有模板就地添加条件块，新增 3 个模板文件（tc_tcl、aip_activity_subscriber、tc_tcl_demo）。Python 层只改 config/cli/base/testcase/common 五个文件。

**Tech Stack:** Python 3, Jinja2, SystemVerilog, pytest

---

## File Map

### Python (Modify)
- `uvm_gen/config.py` — 加 `aip_core: bool` 字段 + YAML 解析
- `uvm_gen/cli.py` — 加 `--aip-core` CLI 参数 + 交互模式选项
- `uvm_gen/generators/base.py` — 模板上下文加 `aip_core` 变量
- `uvm_gen/generators/testcase.py` — 生成 tc_tcl.sv + tcl/ 目录
- `uvm_gen/generators/common.py` — aip_core 模式加生成 aip_activity_subscriber.sv

### Templates (Modify)
- `templates/port/env/vsqr.sv.j2` — 加 static 成员
- `templates/advance/env/vsqr.sv.j2` — 同上
- `templates/port/agent/trans.sv.j2` — 加 set_path() 骨架
- `templates/advance/agent/trans.sv.j2` — 同上
- `templates/port/agent/base_seq.sv.j2` — 加 aip_cmd_seq 注册示例
- `templates/advance/agent/base_seq.sv.j2` — 同上
- `templates/port/env/env.sv.j2` — 加 activity_subscriber 连接
- `templates/advance/env/env.sv.j2` — 同上
- `templates/harness/harness.sv.j2` — 加 aip_clk demo
- `templates/tc/tc_f.j2` — 加 tc_tcl.sv
- `templates/cfg/tb_f.j2` — 加 AIP_CORE_HOME

### Templates (Create)
- `templates/tc/tc_tcl.sv.j2` — TCL bridge test
- `templates/tc/tc_tcl_demo.tcl.j2` — TCL 示例脚本
- `templates/common/aip_activity_subscriber.sv.j2` — activity subscriber

### Tests (Create)
- `tests/test_aip_core_integration.py` — 集成测试

---

### Task 1: config.py — 加 aip_core 字段

**Files:**
- Modify: `uvm_gen/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

在 `tests/test_config.py` 末尾添加：

```python
def test_aip_core_default_false():
    cfg = ProjectConfig(block_name="top")
    assert cfg.aip_core == False

def test_aip_core_from_yaml():
    yaml_str = """
block: top
type: port
aip_core: true
agents:
  - name: axi
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.aip_core == True
    assert cfg.platform_type == PlatformType.PORT

def test_aip_core_yaml_default():
    yaml_str = "block: top\nagents:\n  - name: spi\n"
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.aip_core == False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_config.py::test_aip_core_default_false -v`
Expected: FAIL — `ProjectConfig` has no `aip_core` field

- [ ] **Step 3: Implement — add aip_core field to ProjectConfig**

In `uvm_gen/config.py`, modify `ProjectConfig`:

```python
@dataclass
class ProjectConfig:
    block_name: str
    author: str = ""
    platform_type: PlatformType = PlatformType.ADVANCE
    agents: list[AgentConfig] = field(default_factory=list)
    output_dir: Optional[str] = None
    aip_core: bool = False

    def __post_init__(self):
        if not self.author:
            self.author = getpass.getuser()

    @classmethod
    def from_yaml(cls, yaml_str: str) -> ProjectConfig:
        data = yaml.safe_load(yaml_str)
        if "block" not in data:
            raise ValueError("missing required field 'block' in config file.")
        agents = []
        for a in data.get("agents", []):
            name = a if isinstance(a, str) else a["name"]
            agents.append(AgentConfig(name=name))
        return cls(
            block_name=data["block"],
            author=data.get("author", ""),
            platform_type=PlatformType(data.get("type", "advance")),
            agents=agents,
            output_dir=data.get("output_dir"),
            aip_core=data.get("aip_core", False),
        )
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/config.py tests/test_config.py && git commit -m "feat: add aip_core bool field to ProjectConfig"
```

---

### Task 2: cli.py — 加 --aip-core 参数

**Files:**
- Modify: `uvm_gen/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

在 `tests/test_cli.py` 末尾添加：

```python
def test_aip_core_flag():
    parser = build_parser()
    args = parser.parse_args(["-b", "top", "-a", "axi", "--aip-core"])
    assert args.aip_core == True

def test_aip_core_flag_default():
    parser = build_parser()
    args = parser.parse_args(["-b", "top", "-a", "axi"])
    assert args.aip_core == False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_cli.py::test_aip_core_flag -v`
Expected: FAIL — no `--aip-core` argument

- [ ] **Step 3: Implement**

In `uvm_gen/cli.py`, add to `build_parser()` after line 94:

```python
    parser.add_argument("--aip-core", action="store_true", default=False,
                        help="Enable aip_core integration (TCL bridge, aip_log, aip_clk)")
```

In `run_from_args()`, pass `aip_core` to `ProjectConfig`. Change the platform creation block (around line 134):

```python
        cfg = ProjectConfig(
            block_name=args.block,
            platform_type=platform_type,
            agents=agents,
            output_dir=args.output,
            aip_core=args.aip_core,
        )
```

And standalone agent block (around line 153):

```python
        cfg = ProjectConfig(
            block_name=agent_cfg.name,
            platform_type=platform_type,
            agents=[agent_cfg],
            aip_core=args.aip_core,
        )
```

Also update `_print_summary()` to show aip_core status — add after the output line:

```python
    if cfg.aip_core:
        print("  %-16s %s" % (_dim("aip_core:"), _green("enabled")))
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/cli.py tests/test_cli.py && git commit -m "feat: add --aip-core CLI flag"
```

---

### Task 3: base.py — 模板上下文加 aip_core

**Files:**
- Modify: `uvm_gen/generators/base.py`

- [ ] **Step 1: Modify render_template to pass aip_core**

In `uvm_gen/generators/base.py`, change `render_template`:

```python
    def render_template(self, template_path: str, **kwargs) -> str:
        tmpl = self.jinja_env.get_template(template_path)
        return tmpl.render(
            author=self.cfg.author,
            block_name=self.cfg.block_name,
            date=time.strftime("%Y-%m-%d %X"),
            header=self.render_header,
            aip_core=self.cfg.aip_core,
            **kwargs,
        )
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/ -v`
Expected: ALL PASS (aip_core=False by default, no template changes yet)

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/generators/base.py && git commit -m "feat: pass aip_core to all template contexts"
```

---

### Task 4: vsqr 模板 — 加 static 成员

**Files:**
- Modify: `uvm_gen/templates/port/env/vsqr.sv.j2`
- Modify: `uvm_gen/templates/advance/env/vsqr.sv.j2`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_aip_core_integration.py`:

```python
import os
import tempfile
import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig
from uvm_gen.generators.platform import PlatformGenerator


@pytest.fixture
def aip_port_cfg():
    return ProjectConfig(
        block_name="top", author="test",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="axi"), AgentConfig(name="apb")],
        aip_core=True,
    )

@pytest.fixture
def aip_adv_cfg():
    return ProjectConfig(
        block_name="top", author="test",
        platform_type=PlatformType.ADVANCE,
        agents=[AgentConfig(name="axi"), AgentConfig(name="apb")],
        aip_core=True,
    )

@pytest.fixture
def no_aip_cfg():
    return ProjectConfig(
        block_name="top", author="test",
        platform_type=PlatformType.PORT,
        agents=[AgentConfig(name="axi")],
        aip_core=False,
    )


def test_vsqr_static_member_port(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_vsqr.sv")) as f:
            content = f.read()
        assert "static axi_sqr" in content
        assert "static apb_sqr" in content
        assert "s_axi_sqr" in content
        assert "s_apb_sqr" in content


def test_vsqr_no_static_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_vsqr.sv")) as f:
            content = f.read()
        assert "static" not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_vsqr_static_member_port -v`
Expected: FAIL — no `static` in generated vsqr

- [ ] **Step 3: Modify both vsqr templates**

Replace content of both `templates/port/env/vsqr.sv.j2` AND `templates/advance/env/vsqr.sv.j2` with:

```jinja2
{{ header(file_name) }}
`ifndef  {{ block_name | upper }}_VSQR__SV
`define  {{ block_name | upper }}_VSQR__SV

class {{ block_name }}_vsqr extends uvm_sequencer;

    `uvm_component_utils_begin({{ block_name }}_vsqr)
    `uvm_component_utils_end

    // dec agt_sqr
{% for agent in agents %}
    {{ agent.name }}_sqr    m_{{ agent.name }}_sqr;
{% endfor %}
{% if aip_core %}

    // static sqr handles for aip_cmd_seq macro registration
{% for agent in agents %}
    static {{ agent.name }}_sqr    s_{{ agent.name }}_sqr;
{% endfor %}
{% endif %}

    extern function new(string name, uvm_component parent=null);

endclass

function {{ block_name }}_vsqr::new(string name, uvm_component parent=null);
    super.new(name, parent);
endfunction

`endif
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/port/env/vsqr.sv.j2 uvm_gen/templates/advance/env/vsqr.sv.j2 tests/test_aip_core_integration.py && git commit -m "feat: vsqr static members for aip_cmd_seq registration"
```

---

### Task 5: trans 模板 — 加 set_path() 骨架

**Files:**
- Modify: `uvm_gen/templates/port/agent/trans.sv.j2`
- Modify: `uvm_gen/templates/advance/agent/trans.sv.j2`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_aip_core_integration.py`:

```python
def test_trans_set_path(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_trans.sv")) as f:
            content = f.read()
        assert "set_path" in content
        assert "aip_int" in content


def test_trans_no_set_path_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_trans.sv")) as f:
            content = f.read()
        assert "set_path" not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_trans_set_path -v`
Expected: FAIL

- [ ] **Step 3: Modify both trans templates**

In both `templates/port/agent/trans.sv.j2` AND `templates/advance/agent/trans.sv.j2`, add before `endclass`:

```jinja2
{% if aip_core %}

    // --- aip_cmdline parameter loading ---
    // Usage: in seq body, call tr.set_path("seq_name") to load fields from TCL set_param
    // Example:
    //   `aip_int(path, bit[31:0], addr, 0)
    //   `aip_int(path, bit[31:0], data, 0)
    function void set_path(string path);
        // TODO: add `aip_int / `aip_string calls for your protocol fields
    endfunction
{% endif %}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/port/agent/trans.sv.j2 uvm_gen/templates/advance/agent/trans.sv.j2 tests/test_aip_core_integration.py && git commit -m "feat: trans set_path() skeleton for aip_cmdline"
```

---

### Task 6: base_seq 模板 — 加 aip_cmd_seq 注册示例

**Files:**
- Modify: `uvm_gen/templates/port/agent/base_seq.sv.j2`
- Modify: `uvm_gen/templates/advance/agent/base_seq.sv.j2`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_aip_core_integration.py`:

```python
def test_base_seq_cmd_seq_example(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "agents", "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "aip_cmd_seq" in content
        assert "top_vsqr::s_axi_sqr" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_base_seq_cmd_seq_example -v`
Expected: FAIL

- [ ] **Step 3: Modify both base_seq templates**

In `templates/port/agent/base_seq.sv.j2`, add before final `` `endif ``:

```jinja2
{% if aip_core %}

// --- aip_cmd_seq registration example ---
// Uncomment and modify to register sequences for TCL control:
// `aip_cmd_seq({{ name }}_write, {{ name }}_wr_seq, {{ block_name }}_vsqr::s_{{ name }}_sqr)
// `aip_cmd_seq({{ name }}_read,  {{ name }}_rd_seq, {{ block_name }}_vsqr::s_{{ name }}_sqr)
{% endif %}
```

Add same block in `templates/advance/agent/base_seq.sv.j2` before final `` `endif ``.

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/port/agent/base_seq.sv.j2 uvm_gen/templates/advance/agent/base_seq.sv.j2 tests/test_aip_core_integration.py && git commit -m "feat: aip_cmd_seq registration example in base_seq"
```

---

### Task 7: env 模板 — activity_subscriber 连接 + static sqr 赋值

**Files:**
- Modify: `uvm_gen/templates/port/env/env.sv.j2`
- Modify: `uvm_gen/templates/advance/env/env.sv.j2`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_aip_core_integration.py`:

```python
def test_env_activity_subscriber(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            content = f.read()
        assert "aip_activity_subscriber" in content
        assert "m_axi_act_sub" in content
        assert "m_apb_act_sub" in content
        assert "s_axi_sqr" in content


def test_env_no_subscriber_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            content = f.read()
        assert "aip_activity_subscriber" not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_env_activity_subscriber -v`
Expected: FAIL

- [ ] **Step 3: Modify PORT env template**

In `templates/port/env/env.sv.j2`:

After member declarations (after `{{ block_name }}_vsqr m_vsqr;`), add:
```jinja2
{% if aip_core %}

    // aip_activity subscriber — auto tick on monitor activity
{% for agent in agents %}
    aip_activity_subscriber #({{ agent.name }}_trans) m_{{ agent.name }}_act_sub;
{% endfor %}
{% endif %}
```

In build_phase, after vsqr create, add:
```jinja2
{% if aip_core %}
    // create activity subscribers
{% for agent in agents %}
    m_{{ agent.name }}_act_sub = new("m_{{ agent.name }}_act_sub", this);
{% endfor %}
{% endif %}
```

In connect_phase, after vsqr sqr assignment, add:
```jinja2
{% if aip_core %}
    // connect activity subscribers to monitor AP
{% for agent in agents %}
    m_{{ agent.name }}_agt.m_mon.m_ap.connect(m_{{ agent.name }}_act_sub.analysis_export);
{% endfor %}
    // User: add more subscribers for rm/scb after implementation

    // assign static sqr handles for aip_cmd_seq
{% for agent in agents %}
    {{ block_name }}_vsqr::s_{{ agent.name }}_sqr = this.m_{{ agent.name }}_agt.m_sqr;
{% endfor %}
{% endif %}
```

Apply same pattern to `templates/advance/env/env.sv.j2`.

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/port/env/env.sv.j2 uvm_gen/templates/advance/env/env.sv.j2 tests/test_aip_core_integration.py && git commit -m "feat: env activity_subscriber + static sqr assignment"
```

---

### Task 8: common — aip_activity_subscriber 模板 + generator

**Files:**
- Create: `uvm_gen/templates/common/aip_activity_subscriber.sv.j2`
- Modify: `uvm_gen/generators/common.py`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_aip_core_integration.py`:

```python
def test_common_activity_subscriber(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        sub_path = os.path.join(project_dir, "common", "aip_activity_subscriber.sv")
        assert os.path.exists(sub_path)
        with open(sub_path) as f:
            content = f.read()
        assert "aip_activity::tick()" in content
        assert "uvm_subscriber" in content


def test_no_activity_subscriber_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        assert not os.path.exists(os.path.join(project_dir, "common", "aip_activity_subscriber.sv"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_common_activity_subscriber -v`
Expected: FAIL

- [ ] **Step 3: Create template**

Create `uvm_gen/templates/common/aip_activity_subscriber.sv.j2`:

```jinja2
{{ header(file_name) }}
`ifndef  AIP_ACTIVITY_SUBSCRIBER__SV
`define  AIP_ACTIVITY_SUBSCRIBER__SV

// Generic activity subscriber — connect to any analysis port
// write() auto-calls aip_activity::tick() for idle detection
// Usage in env: agent.m_mon.m_ap.connect(subscriber.analysis_export);

class aip_activity_subscriber #(type T = uvm_sequence_item) extends uvm_subscriber #(T);

    `uvm_component_param_utils(aip_activity_subscriber #(T))

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void write(T t);
        aip_activity::tick();
    endfunction

endclass

`endif
```

- [ ] **Step 4: Modify common generator**

In `uvm_gen/generators/common.py`, add at end of `generate()`:

```python
        # aip_core: generate activity subscriber
        if self.cfg.aip_core:
            content = self.render_template(
                "common/aip_activity_subscriber.sv.j2",
                file_name="aip_activity_subscriber.sv",
            )
            self.write_file(os.path.join(output_dir, "aip_activity_subscriber.sv"), content)
```

- [ ] **Step 5: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/common/aip_activity_subscriber.sv.j2 uvm_gen/generators/common.py tests/test_aip_core_integration.py && git commit -m "feat: aip_activity_subscriber common template"
```

---

### Task 9: harness 模板 — aip_clk 100MHz demo

**Files:**
- Modify: `uvm_gen/templates/harness/harness.sv.j2`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_aip_core_integration.py`:

```python
def test_harness_aip_clk(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "th", "harness.sv")) as f:
            content = f.read()
        assert "aip_clk_create" in content
        assert "100e6" in content


def test_harness_no_aip_clk_without(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        with open(os.path.join(project_dir, "th", "harness.sv")) as f:
            content = f.read()
        assert "aip_clk_create" not in content
        assert "CLK_GEN" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_harness_aip_clk -v`
Expected: FAIL

- [ ] **Step 3: Modify harness template**

In `templates/harness/harness.sv.j2`, replace the clock/reset section:

```jinja2
{% if aip_core %}
// aip_core clock generation (100MHz demo)
`aip_clk_create(clk0, 100e6)
wire clk = clk0_if.clk;
reg rst_n;
{% else %}
//reg clk;
reg rst_n;
`CLK_GEN(clk,5,1);
{% endif %}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/harness/harness.sv.j2 tests/test_aip_core_integration.py && git commit -m "feat: harness aip_clk 100MHz demo"
```

---

### Task 10: tc_tcl + tc_base + TCL demo + testcase generator

**Files:**
- Create: `uvm_gen/templates/tc/tc_tcl.sv.j2`
- Create: `uvm_gen/templates/tc/tc_tcl_demo.tcl.j2`
- Modify: `uvm_gen/templates/tc/tc_f.j2`
- Modify: `uvm_gen/generators/testcase.py`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_aip_core_integration.py`:

```python
def test_tc_tcl_generated(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        tc_tcl = os.path.join(project_dir, "tc", "tc_tcl.sv")
        assert os.path.exists(tc_tcl)
        with open(tc_tcl) as f:
            content = f.read()
        assert "aip_tcl_bridge::run_loop()" in content
        assert "tc_tcl" in content

        tc_base = os.path.join(project_dir, "tc", "tc_base.sv")
        assert os.path.exists(tc_base)

        tc_f = os.path.join(project_dir, "tc", "tc.f")
        with open(tc_f) as f:
            content = f.read()
        assert "tc_tcl.sv" in content
        assert "tc_base.sv" in content


def test_tcl_demo_generated(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        demo = os.path.join(project_dir, "tc", "tcl", "tc_tcl_demo.tcl")
        assert os.path.exists(demo)
        with open(demo) as f:
            content = f.read()
        assert "AIP_CORE_HOME" in content
        assert "end_test" in content


def test_no_tc_tcl_without_aip(no_aip_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_aip_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(no_aip_cfg).generate()
        assert not os.path.exists(os.path.join(project_dir, "tc", "tc_tcl.sv"))
        assert not os.path.exists(os.path.join(project_dir, "tc", "tcl"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_tc_tcl_generated -v`
Expected: FAIL

- [ ] **Step 3: Create tc_tcl.sv.j2**

Create `uvm_gen/templates/tc/tc_tcl.sv.j2`:

```jinja2
{{ header(file_name) }}
`ifndef  TC_TCL__SV
`define  TC_TCL__SV


class tc_tcl extends tc_base;

    `uvm_component_utils(tc_tcl)

    function new(string name="tc_tcl", uvm_component parent=null);
        super.new(name, parent);
    endfunction

    virtual task main_phase(uvm_phase phase);
        phase.raise_objection(this);

        // Wait for reset release
        wait(harness.rst_n === 1'b1);
        repeat(2) @(posedge harness.clk);
        `aip_info(("Entering TCL bridge mode"));

        // TCL takes control — all seq calls via TCL scripts
        aip_tcl_bridge::run_loop();

        phase.drop_objection(this);
    endtask

endclass

`endif
```

- [ ] **Step 4: Create tc_tcl_demo.tcl.j2**

Create `uvm_gen/templates/tc/tc_tcl_demo.tcl.j2`:

```jinja2
# ============================================
# {{ block_name }} TCL Test Demo
# Usage: ./simv -ucli -do tc/tcl/tc_tcl_demo.tcl +UVM_TESTNAME=tc_tcl
# ============================================
source $env(AIP_CORE_HOME)/aip_cmd.tcl

puts "=========================================="
puts " {{ block_name }} TCL Test"
puts "=========================================="

# --- Example: set parameters and run sequences ---
# Uncomment and modify for your protocol:
#
{% for agent in agents %}
# set_param {
#     {{ agent.name }}.wr.addr  [0:0xFF]
#     {{ agent.name }}.wr.data  [0:0xFFFFFFFF]
# }
# {{ agent.name }}_write count=10
#
{% endfor %}
# --- Parallel execution ---
# fork
{% for agent in agents %}
#     {{ agent.name }}_write count=5
{% endfor %}
# join

# --- Exit ---
end_test idle=1us timeout=10us
```

- [ ] **Step 5: Update tc_f.j2**

Replace `templates/tc/tc_f.j2`:

```jinja2
+incdir+./
./tc_base.sv
{% if aip_core %}
./tc_tcl.sv
{% endif %}
```

- [ ] **Step 6: Update testcase generator**

Replace `uvm_gen/generators/testcase.py`:

```python
from __future__ import annotations
import os
from uvm_gen.generators.base import BaseGenerator


class TestcaseGenerator(BaseGenerator):
    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        # tc_base.sv (always generated)
        template_path = self.get_template_path("tc", "base_test.sv.j2")
        content = self.render_template(template_path, file_name="tc_base.sv", agents=self.cfg.agents)
        self.write_file(os.path.join(output_dir, "tc_base.sv"), content)

        # tc_tcl.sv (aip_core only)
        if self.cfg.aip_core:
            content = self.render_template("tc/tc_tcl.sv.j2", file_name="tc_tcl.sv", agents=self.cfg.agents)
            self.write_file(os.path.join(output_dir, "tc_tcl.sv"), content)

            # tcl/ demo script
            tcl_dir = os.path.join(output_dir, "tcl")
            os.makedirs(tcl_dir, exist_ok=True)
            content = self.render_template("tc/tc_tcl_demo.tcl.j2", file_name="tc_tcl_demo.tcl", agents=self.cfg.agents)
            self.write_file(os.path.join(tcl_dir, "tc_tcl_demo.tcl"), content)

        # tc.f
        template_path = self.get_template_path("tc", "tc_f.j2")
        content = self.render_template(template_path, file_name="tc.f")
        self.write_file(os.path.join(output_dir, "tc.f"), content)
```

- [ ] **Step 7: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/tc/tc_tcl.sv.j2 uvm_gen/templates/tc/tc_tcl_demo.tcl.j2 uvm_gen/templates/tc/tc_f.j2 uvm_gen/generators/testcase.py tests/test_aip_core_integration.py && git commit -m "feat: tc_tcl + tc_tcl_demo + testcase generator update"
```

---

### Task 11: tb.f — 加 AIP_CORE_HOME

**Files:**
- Modify: `uvm_gen/templates/cfg/tb_f.j2`
- Test: `tests/test_aip_core_integration.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_aip_core_integration.py`:

```python
def test_tb_f_aip_core_home(aip_port_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        aip_port_cfg.output_dir = tmpdir
        project_dir = PlatformGenerator(aip_port_cfg).generate()
        with open(os.path.join(project_dir, "cfg", "tb.f")) as f:
            content = f.read()
        assert "AIP_CORE_HOME" in content
        assert "aip_core_pkg.sv" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py::test_tb_f_aip_core_home -v`
Expected: FAIL

- [ ] **Step 3: Modify tb_f.j2**

Replace `templates/cfg/tb_f.j2`:

```jinja2
{% if aip_core %}
+incdir+$AIP_CORE_HOME
$AIP_CORE_HOME/aip_core_pkg.sv
{% endif %}
-F   ./dut.f
-F   ./env.f
-F   ../tc/tc.f
../th/harness.sv
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_aip_core_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add uvm_gen/templates/cfg/tb_f.j2 tests/test_aip_core_integration.py && git commit -m "feat: tb.f includes AIP_CORE_HOME when aip_core enabled"
```

---

### Task 12: 全量回归 + 推送

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/ -v`
Expected: ALL PASS — existing tests + new aip_core tests

- [ ] **Step 2: Verify non-aip generation is unchanged**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_integration.py -v`
Expected: ALL 4 original tests PASS (no regression)

- [ ] **Step 3: Manual smoke test**

```bash
cd /tmp && rm -rf test_gen
mkdir test_gen && cd test_gen
gen_tb -b top -a "axi,apb" -t port --aip-core -o .
ls top/tc/tc_tcl.sv top/tc/tc_base.sv top/tc/tcl/tc_tcl_demo.tcl top/common/aip_activity_subscriber.sv
grep "aip_clk_create" top/th/harness.sv
grep "static.*s_axi_sqr" top/env/top_vsqr.sv
grep "AIP_CORE_HOME" top/cfg/tb.f
```

- [ ] **Step 4: Commit and push**

```bash
cd /home/ubuntu/ryan/uvm_gen && git add -A && git status
git commit -m "feat: uvm_gen × aip_core deep integration — complete"
git push origin master
```
