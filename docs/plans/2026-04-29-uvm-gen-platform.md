# UVM Gen Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild uvm_tb_gen.py into a modular, template-driven CLI tool supporting two platform types (self-contained / standard), five agent modes, and three CLI interaction modes.

**Architecture:** Python CLI with Jinja2 templates. Two independent template sets (self_contained/, standard/) generate different agent+env code. Shared templates for common/harness/tc/cfg/sim. Config via dataclass, CLI via argparse subcommands.

**Tech Stack:** Python 3.10+, Jinja2, PyYAML, argparse

**Spec:** `docs/specs/2026-04-29-uvm-gen-platform-design.md`

---

## File Map

```
uvm_gen/
├── uvm_gen/
│   ├── __init__.py
│   ├── cli.py                          # CLI entry: argparse subcommands + interactive + YAML
│   ├── config.py                       # PlatformType, AgentMode, AgentConfig, ProjectConfig
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── base.py                     # BaseGenerator: Jinja2 env setup, render, write
│   │   ├── agent.py                    # AgentGenerator: dispatches to correct template set
│   │   ├── env.py                      # EnvGenerator: dispatches to correct template set
│   │   ├── common.py                   # CommonGenerator: shared components
│   │   ├── harness.py                  # HarnessGenerator
│   │   ├── testcase.py                 # TestcaseGenerator
│   │   └── platform.py                 # PlatformGenerator: orchestrates all generators
│   └── templates/
│       ├── _header.sv.j2               # shared file header macro
│       ├── self_contained/
│       │   ├── agent/
│       │   │   ├── agent.sv.j2
│       │   │   ├── trans.sv.j2
│       │   │   ├── cfg.sv.j2
│       │   │   ├── drv.sv.j2
│       │   │   ├── mon.sv.j2
│       │   │   ├── sqr.sv.j2
│       │   │   ├── base_seq.sv.j2
│       │   │   ├── if.sv.j2
│       │   │   ├── pkg.sv.j2
│       │   │   └── agent_f.j2
│       │   └── env/
│       │       ├── env.sv.j2
│       │       ├── env_cfg.sv.j2
│       │       ├── rm.sv.j2
│       │       ├── checker.sv.j2
│       │       └── vsqr.sv.j2
│       ├── standard/
│       │   ├── agent/
│       │   │   ├── agent.sv.j2
│       │   │   ├── trans.sv.j2
│       │   │   ├── cfg.sv.j2
│       │   │   ├── drv.sv.j2
│       │   │   ├── mon.sv.j2
│       │   │   ├── sqr.sv.j2
│       │   │   ├── base_seq.sv.j2
│       │   │   ├── if.sv.j2
│       │   │   ├── pkg.sv.j2
│       │   │   └── agent_f.j2
│       │   └── env/
│       │       ├── env.sv.j2
│       │       ├── env_cfg.sv.j2
│       │       ├── rm.sv.j2
│       │       ├── checker.sv.j2
│       │       └── vsqr.sv.j2
│       ├── common/
│       │   ├── common_pkg.sv.j2
│       │   ├── common_dec.sv.j2
│       │   ├── report_server.sv.j2
│       │   ├── self_debug_scb.sv.j2
│       │   └── draw_table.sv.j2
│       ├── harness/
│       │   └── harness.sv.j2
│       ├── tc/
│       │   ├── base_test.sv.j2
│       │   └── tc_f.j2
│       ├── cfg/
│       │   ├── dut_f.j2
│       │   ├── env_f.j2
│       │   └── tb_f.j2
│       └── sim/
│           └── Makefile.j2
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_base_generator.py
│   ├── test_agent_generator.py
│   ├── test_env_generator.py
│   ├── test_common_generator.py
│   ├── test_platform_generator.py
│   └── test_cli.py
├── setup.py
└── README.md
```

---

### Task 1: Project Scaffolding & Config Model

**Files:**
- Create: `uvm_gen/uvm_gen/__init__.py`
- Create: `uvm_gen/uvm_gen/config.py`
- Create: `uvm_gen/tests/__init__.py`
- Create: `uvm_gen/tests/test_config.py`
- Create: `uvm_gen/setup.py`

- [ ] **Step 1: Create setup.py**

```python
# uvm_gen/setup.py
from setuptools import setup, find_packages

setup(
    name="uvm_gen",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={"uvm_gen": ["templates/**/*.j2"]},
    install_requires=["Jinja2>=3.1", "PyYAML>=6.0"],
    entry_points={
        "console_scripts": [
            "uvm_gen=uvm_gen.cli:main",
        ],
    },
    python_requires=">=3.10",
)
```

- [ ] **Step 2: Create __init__.py files**

```python
# uvm_gen/uvm_gen/__init__.py
__version__ = "0.1.0"
```

```python
# uvm_gen/tests/__init__.py
```

- [ ] **Step 3: Write failing test for config model**

```python
# uvm_gen/tests/test_config.py
import pytest
from uvm_gen.config import PlatformType, AgentMode, AgentConfig, ProjectConfig


def test_platform_type_values():
    assert PlatformType.SELF_CONTAINED.value == "self-contained"
    assert PlatformType.STANDARD.value == "standard"


def test_agent_mode_values():
    assert AgentMode.MASTER.value == "master"
    assert AgentMode.SLAVE.value == "slave"
    assert AgentMode.ONLY_MASTER.value == "only-master"
    assert AgentMode.ONLY_SLAVE.value == "only-slave"
    assert AgentMode.ONLY_MONITOR.value == "only-monitor"


def test_agent_config_defaults():
    cfg = AgentConfig(name="axi")
    assert cfg.name == "axi"
    assert cfg.mode == AgentMode.MASTER


def test_project_config_defaults():
    cfg = ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
    )
    assert cfg.platform_type == PlatformType.SELF_CONTAINED
    assert cfg.agents == []
    assert cfg.output_dir is None


def test_project_config_with_agents():
    cfg = ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[
            AgentConfig(name="axi", mode=AgentMode.MASTER),
            AgentConfig(name="apb", mode=AgentMode.SLAVE),
        ],
    )
    assert len(cfg.agents) == 2
    assert cfg.agents[0].name == "axi"
    assert cfg.agents[1].mode == AgentMode.SLAVE
    assert cfg.platform_type == PlatformType.STANDARD


def test_project_config_from_yaml():
    yaml_str = """
project: bootis
author: ryan.yu
block: top
type: self-contained
agents:
  - name: axi
    mode: master
  - name: apb
    mode: slave
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.project_name == "bootis"
    assert cfg.author == "ryan.yu"
    assert cfg.block_name == "top"
    assert cfg.platform_type == PlatformType.SELF_CONTAINED
    assert len(cfg.agents) == 2
    assert cfg.agents[0].mode == AgentMode.MASTER


def test_project_config_from_yaml_standard():
    yaml_str = """
project: chip_a
author: test
block: sub
type: standard
agents:
  - name: pcie
    mode: only-monitor
"""
    cfg = ProjectConfig.from_yaml(yaml_str)
    assert cfg.platform_type == PlatformType.STANDARD
    assert cfg.agents[0].mode == AgentMode.ONLY_MONITOR
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'uvm_gen.config'`

- [ ] **Step 5: Implement config.py**

```python
# uvm_gen/uvm_gen/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml


class PlatformType(Enum):
    SELF_CONTAINED = "self-contained"
    STANDARD = "standard"


class AgentMode(Enum):
    MASTER = "master"
    SLAVE = "slave"
    ONLY_MASTER = "only-master"
    ONLY_SLAVE = "only-slave"
    ONLY_MONITOR = "only-monitor"


@dataclass
class AgentConfig:
    name: str
    mode: AgentMode = AgentMode.MASTER


@dataclass
class ProjectConfig:
    project_name: str
    author: str
    block_name: str
    platform_type: PlatformType = PlatformType.SELF_CONTAINED
    agents: list[AgentConfig] = field(default_factory=list)
    output_dir: Optional[str] = None

    @classmethod
    def from_yaml(cls, yaml_str: str) -> ProjectConfig:
        data = yaml.safe_load(yaml_str)
        agents = []
        for a in data.get("agents", []):
            agents.append(AgentConfig(
                name=a["name"],
                mode=AgentMode(a.get("mode", "master")),
            ))
        return cls(
            project_name=data["project"],
            author=data["author"],
            block_name=data["block"],
            platform_type=PlatformType(data.get("type", "self-contained")),
            agents=agents,
            output_dir=data.get("output_dir"),
        )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_config.py -v`
Expected: All 6 tests PASS

- [ ] **Step 7: Commit**

```bash
git add setup.py uvm_gen/__init__.py uvm_gen/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add project scaffolding and config model with YAML parsing"
```

---

### Task 2: Base Generator (Jinja2 Rendering Engine)

**Files:**
- Create: `uvm_gen/uvm_gen/generators/__init__.py`
- Create: `uvm_gen/uvm_gen/generators/base.py`
- Create: `uvm_gen/uvm_gen/templates/_header.sv.j2`
- Create: `uvm_gen/tests/test_base_generator.py`

- [ ] **Step 1: Write failing test**

```python
# uvm_gen/tests/test_base_generator.py
import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.base import BaseGenerator


@pytest.fixture
def project_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[AgentConfig(name="axi", mode=AgentMode.MASTER)],
    )


@pytest.fixture
def gen(project_cfg):
    return BaseGenerator(project_cfg)


def test_base_generator_init(gen):
    assert gen.jinja_env is not None
    assert gen.cfg.project_name == "bootis"


def test_render_template_string(gen):
    result = gen.render_string("Hello {{ name }}!", name="world")
    assert result == "Hello world!"


def test_render_header(gen):
    header = gen.render_header("test_file.sv")
    assert "bootis" in header
    assert "ryan.yu" in header
    assert "test_file.sv" in header


def test_write_file(gen):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.sv")
        gen.write_file(path, "// test content\n")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "// test content\n"


def test_write_file_creates_parent_dirs(gen):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "sub", "dir", "test.sv")
        gen.write_file(path, "content")
        assert os.path.exists(path)


def test_get_template_path_self_contained(gen):
    path = gen.get_template_path("agent", "agent.sv.j2")
    assert "self_contained/agent/agent.sv.j2" in path


def test_get_template_path_common(gen):
    path = gen.get_template_path("common", "common_pkg.sv.j2")
    assert "common/common_pkg.sv.j2" in path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_base_generator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create header template**

```jinja2
{# uvm_gen/uvm_gen/templates/_header.sv.j2 #}
//===============================================================
//       Copyright(c) -xxx_company, All rights reserved.
//===============================================================
//
//        project     :       {{ project_name }}
//        author      :       {{ author }}
//        Date        :       {{ date }}
//        Filename    :       {{ file_name }}
//        Description :
//
//===============================================================
```

- [ ] **Step 4: Implement base.py**

```python
# uvm_gen/uvm_gen/generators/__init__.py
```

```python
# uvm_gen/uvm_gen/generators/base.py
from __future__ import annotations

import os
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from uvm_gen.config import ProjectConfig, PlatformType

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class BaseGenerator:
    def __init__(self, cfg: ProjectConfig):
        self.cfg = cfg
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_string(self, template_str: str, **kwargs) -> str:
        tmpl = self.jinja_env.from_string(template_str)
        return tmpl.render(**kwargs)

    def render_header(self, file_name: str) -> str:
        tmpl = self.jinja_env.get_template("_header.sv.j2")
        return tmpl.render(
            project_name=self.cfg.project_name,
            author=self.cfg.author,
            date=time.strftime("%Y-%m-%d %X"),
            file_name=file_name,
        )

    def render_template(self, template_path: str, **kwargs) -> str:
        tmpl = self.jinja_env.get_template(template_path)
        return tmpl.render(
            project_name=self.cfg.project_name,
            author=self.cfg.author,
            block_name=self.cfg.block_name,
            date=time.strftime("%Y-%m-%d %X"),
            header=self.render_header,
            **kwargs,
        )

    def get_template_path(self, category: str, template_name: str) -> str:
        if category in ("common", "harness", "tc", "cfg", "sim"):
            return f"{category}/{template_name}"
        type_dir = (
            "self_contained"
            if self.cfg.platform_type == PlatformType.SELF_CONTAINED
            else "standard"
        )
        return f"{type_dir}/{category}/{template_name}"

    def write_file(self, file_path: str, content: str) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_base_generator.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add uvm_gen/generators/__init__.py uvm_gen/generators/base.py uvm_gen/templates/_header.sv.j2 tests/test_base_generator.py
git commit -m "feat: add base generator with Jinja2 rendering engine"
```

---

### Task 3: Common Templates & Generator

**Files:**
- Create: `uvm_gen/uvm_gen/generators/common.py`
- Create: `uvm_gen/uvm_gen/templates/common/common_pkg.sv.j2`
- Create: `uvm_gen/uvm_gen/templates/common/common_dec.sv.j2`
- Create: `uvm_gen/uvm_gen/templates/common/report_server.sv.j2`
- Create: `uvm_gen/uvm_gen/templates/common/self_debug_scb.sv.j2`
- Create: `uvm_gen/uvm_gen/templates/common/draw_table.sv.j2`
- Create: `uvm_gen/tests/test_common_generator.py`

- [ ] **Step 1: Write failing test**

```python
# uvm_gen/tests/test_common_generator.py
import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.common import CommonGenerator


@pytest.fixture
def project_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[AgentConfig(name="axi", mode=AgentMode.MASTER)],
    )


def test_generate_common_creates_all_files(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        expected_files = [
            "common_lib_pkg.f",
            "common_lib_pkg.sv",
            "common_dec.sv",
            "common_report_server.sv",
            "common_self_debug_scb.sv",
            "common_draw_table.sv",
        ]
        for fname in expected_files:
            path = os.path.join(tmpdir, fname)
            assert os.path.exists(path), f"Missing: {fname}"


def test_common_pkg_includes(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_lib_pkg.sv")) as f:
            content = f.read()
        assert "common_lib_pkg" in content
        assert "uvm_pkg" in content
        assert '`include "common_dec.sv"' in content
        assert '`include "common_report_server.sv"' in content


def test_common_dec_has_clk_rst_macros(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_dec.sv")) as f:
            content = f.read()
        assert "CLK_GEN" in content
        assert "RST_GEN" in content


def test_common_report_server_class(project_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = CommonGenerator(project_cfg)
        gen.generate(tmpdir)

        with open(os.path.join(tmpdir, "common_report_server.sv")) as f:
            content = f.read()
        assert "common_report_server extends uvm_report_server" in content
        assert "compose_message" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_common_generator.py -v`
Expected: FAIL

- [ ] **Step 3: Create all common templates**

Port the SV code from existing `gen_uvm_common_*` functions in `uvm_tb_gen.py` into Jinja2 templates. Each template uses the `_header.sv.j2` include and takes `project_name`, `author`, `date` as context.

The five templates to create:
- `templates/common/common_pkg.sv.j2` — from `gen_uvm_common_lib_pkg` (line 678)
- `templates/common/common_dec.sv.j2` — from `gen_uvm_common_dec` (line 711)
- `templates/common/report_server.sv.j2` — from `gen_uvm_common_report_server` (line 773)
- `templates/common/self_debug_scb.sv.j2` — from `gen_uvm_common_self_debug_scb` (line 814)
- `templates/common/draw_table.sv.j2` — from `gen_uvm_common_draw_table` (line 1478)

Each template follows the pattern:
```jinja2
{{ header(file_name) }}
`ifndef GUARD_NAME__SV
`define GUARD_NAME__SV

{# SV code ported from original function #}

`endif
```

- [ ] **Step 4: Implement CommonGenerator**

```python
# uvm_gen/uvm_gen/generators/common.py
from __future__ import annotations

import os

from uvm_gen.config import ProjectConfig
from uvm_gen.generators.base import BaseGenerator


class CommonGenerator(BaseGenerator):
    TEMPLATES = [
        ("common_lib_pkg.sv", "common/common_pkg.sv.j2"),
        ("common_dec.sv", "common/common_dec.sv.j2"),
        ("common_report_server.sv", "common/report_server.sv.j2"),
        ("common_self_debug_scb.sv", "common/self_debug_scb.sv.j2"),
        ("common_draw_table.sv", "common/draw_table.sv.j2"),
    ]

    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        # Generate filelist
        f_content = "+incdir+./\n./common_lib_pkg.sv\n"
        self.write_file(os.path.join(output_dir, "common_lib_pkg.f"), f_content)

        # Generate SV files
        for filename, template in self.TEMPLATES:
            content = self.render_template(template, file_name=filename)
            self.write_file(os.path.join(output_dir, filename), content)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_common_generator.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add uvm_gen/generators/common.py uvm_gen/templates/common/ tests/test_common_generator.py
git commit -m "feat: add common generator with all shared UVM component templates"
```

---

### Task 4: Self-Contained Agent Templates & Generator

**Files:**
- Create: `uvm_gen/uvm_gen/generators/agent.py`
- Create: `uvm_gen/uvm_gen/templates/self_contained/agent/*.j2` (10 files)
- Create: `uvm_gen/tests/test_agent_generator.py`

- [ ] **Step 1: Write failing test**

```python
# uvm_gen/tests/test_agent_generator.py
import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.agent import AgentGenerator


@pytest.fixture
def sc_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[AgentConfig(name="axi", mode=AgentMode.MASTER)],
    )


@pytest.fixture
def std_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[AgentConfig(name="axi", mode=AgentMode.MASTER)],
    )


def test_sc_agent_generates_all_files(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        agent_cfg = sc_cfg.agents[0]
        gen.generate_agent(agent_cfg, tmpdir)

        agent_dir = os.path.join(tmpdir, "axi_agent")
        expected = [
            "axi_agent.f",
            "src/axi_agent_pkg.sv",
            "src/axi_agent.sv",
            "src/axi_trans.sv",
            "src/axi_agt_cfg.sv",
            "src/axi_drv.sv",
            "src/axi_mon.sv",
            "src/axi_sqr.sv",
            "src/axi_base_seq.sv",
            "src/axi_if.sv",
        ]
        for f in expected:
            path = os.path.join(agent_dir, f)
            assert os.path.exists(path), f"Missing: {f}"


def test_sc_agent_has_internal_fifo(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agent.sv")) as f:
            content = f.read()
        assert "m_mon_fifo" in content
        assert "m_req_fifo" in content


def test_sc_base_seq_has_send_trans(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "task send_trans" in content
        assert "task send_trans_with_rsp" in content
        assert "task wait_trans" in content
        assert "task wait_request" in content
        assert "task send_response" in content


def test_sc_drv_has_master_slave_branch(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_drv.sv")) as f:
            content = f.read()
        assert "master_drive" in content
        assert "slave_drive" in content


def test_sc_cfg_has_agent_mode_enum(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agt_cfg.sv")) as f:
            content = f.read()
        assert "agent_mode_e" in content
        assert "AGENT_MASTER" in content
        assert "AGENT_ONLY_MONITOR" in content


def test_std_agent_no_internal_fifo(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(std_cfg)
        gen.generate_agent(std_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_agent.sv")) as f:
            content = f.read()
        assert "m_mon_fifo" not in content
        assert "m_mon_ap" in content


def test_std_base_seq_no_task_wrappers(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(std_cfg)
        gen.generate_agent(std_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
        assert "task send_trans" not in content


def test_agent_filelist(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = AgentGenerator(sc_cfg)
        gen.generate_agent(sc_cfg.agents[0], tmpdir)
        with open(os.path.join(tmpdir, "axi_agent", "axi_agent.f")) as f:
            content = f.read()
        assert "axi_agent_pkg.sv" in content
        assert "+incdir" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_agent_generator.py -v`
Expected: FAIL

- [ ] **Step 3: Create self_contained agent templates**

Create 10 templates under `uvm_gen/uvm_gen/templates/self_contained/agent/`:

**cfg.sv.j2** — contains `agent_mode_e` enum typedef and `{{ name }}_agt_cfg` class with `m_mode`, `m_auto_start_seq`, `m_self_debug_en` fields. Port from spec section 5.3 + 3.1.

**agent.sv.j2** — contains agent class with internal FIFOs (`m_mon_fifo`, `m_req_fifo`, `m_rsp_fifo`), `m_mon_ap`, build/connect phase with mode-based instantiation. Port from spec section 3.2, 5.1, 5.2.

**trans.sv.j2** — transaction class skeleton with `uvm_object_utils`, `do_copy`, `do_compare`, `convert2string`, `self_define_do_compare`. Port from `gen_uvm_agent_trans` (line 1932).

**drv.sv.j2** — driver with `master_drive`/`slave_drive` branch in `run_phase`. Port from spec section 3.3.

**mon.sv.j2** — monitor skeleton with `m_ap` analysis port, `m_cfg` handle, `run_phase`. Port from `gen_uvm_agent_mon` (line 2061).

**sqr.sv.j2** — sequencer with `m_cfg` handle, `m_mon_fifo`/`m_req_fifo` references for self-contained mode. Port from `gen_uvm_agent_sqr` (line 1961).

**base_seq.sv.j2** — base sequence with `send_trans`, `send_trans_with_rsp`, `wait_trans`, `wait_request`, `send_response` tasks with mode validation. Port from spec section 4.1, 4.2.

**if.sv.j2** — interface skeleton. Port from `gen_uvm_agent_if` (line 1865).

**pkg.sv.j2** — package with all includes in correct order. Port from `gen_uvm_agent_pkg` (line 1834).

**agent_f.j2** — filelist file. Port from `gen_uvm_agent_file` (line 1824).

All templates use `{{ name }}` for agent name substitution (e.g., `axi`).

- [ ] **Step 4: Create standard agent templates**

Create the same 10 templates under `uvm_gen/uvm_gen/templates/standard/agent/`, with these differences:
- **agent.sv.j2** — no internal FIFOs, only `m_mon_ap`
- **base_seq.sv.j2** — empty base class, no task wrappers
- **sqr.sv.j2** — standard sqr, no FIFO references
- All other templates (cfg, trans, drv, mon, if, pkg, agent_f) identical to self_contained versions

- [ ] **Step 5: Implement AgentGenerator**

```python
# uvm_gen/uvm_gen/generators/agent.py
from __future__ import annotations

import os

from uvm_gen.config import AgentConfig, ProjectConfig
from uvm_gen.generators.base import BaseGenerator


class AgentGenerator(BaseGenerator):
    AGENT_SRC_TEMPLATES = [
        ("agent_pkg.sv", "pkg.sv.j2"),
        ("agent.sv", "agent.sv.j2"),
        ("trans.sv", "trans.sv.j2"),
        ("agt_cfg.sv", "cfg.sv.j2"),
        ("drv.sv", "drv.sv.j2"),
        ("mon.sv", "mon.sv.j2"),
        ("sqr.sv", "sqr.sv.j2"),
        ("base_seq.sv", "base_seq.sv.j2"),
        ("if.sv", "if.sv.j2"),
    ]

    def generate_agent(self, agent_cfg: AgentConfig, output_dir: str) -> None:
        name = agent_cfg.name
        agent_dir = os.path.join(output_dir, f"{name}_agent")
        src_dir = os.path.join(agent_dir, "src")
        os.makedirs(src_dir, exist_ok=True)

        ctx = {
            "name": name,
            "name_upper": name.upper(),
            "block_name": self.cfg.block_name,
        }

        # Generate src files
        for suffix, template_name in self.AGENT_SRC_TEMPLATES:
            filename = f"{name}_{suffix}"
            template_path = self.get_template_path("agent", template_name)
            content = self.render_template(template_path, file_name=filename, **ctx)
            self.write_file(os.path.join(src_dir, filename), content)

        # Generate filelist
        template_path = self.get_template_path("agent", "agent_f.j2")
        f_content = self.render_template(template_path, file_name=f"{name}_agent.f", **ctx)
        self.write_file(os.path.join(agent_dir, f"{name}_agent.f"), f_content)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_agent_generator.py -v`
Expected: All 8 tests PASS

- [ ] **Step 7: Commit**

```bash
git add uvm_gen/generators/agent.py uvm_gen/templates/self_contained/agent/ uvm_gen/templates/standard/agent/ tests/test_agent_generator.py
git commit -m "feat: add agent generator with self-contained and standard templates"
```

---

### Task 5: Env Templates & Generator

**Files:**
- Create: `uvm_gen/uvm_gen/generators/env.py`
- Create: `uvm_gen/uvm_gen/templates/self_contained/env/*.j2` (5 files)
- Create: `uvm_gen/uvm_gen/templates/standard/env/*.j2` (5 files)
- Create: `uvm_gen/tests/test_env_generator.py`

- [ ] **Step 1: Write failing test**

```python
# uvm_gen/tests/test_env_generator.py
import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.env import EnvGenerator


@pytest.fixture
def sc_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[
            AgentConfig(name="axi", mode=AgentMode.MASTER),
            AgentConfig(name="apb", mode=AgentMode.SLAVE),
        ],
    )


@pytest.fixture
def std_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[
            AgentConfig(name="axi", mode=AgentMode.MASTER),
            AgentConfig(name="apb", mode=AgentMode.SLAVE),
        ],
    )


def test_sc_env_generates_all_files(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)

        expected = [
            "top_env.sv",
            "top_env_cfg.sv",
            "top_rm.sv",
            "top_checker.sv",
            "top_vsqr.sv",
        ]
        for f in expected:
            assert os.path.exists(os.path.join(tmpdir, f)), f"Missing: {f}"


def test_sc_env_no_fifo(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "uvm_tlm_analysis_fifo" not in content
        assert "m_axi_agt" in content
        assert "m_apb_agt" in content


def test_std_env_has_fifo(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(std_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env.sv")) as f:
            content = f.read()
        assert "uvm_tlm_analysis_fifo" in content


def test_env_cfg_has_agent_cfgs(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_env_cfg.sv")) as f:
            content = f.read()
        assert "axi_agt_cfg" in content
        assert "apb_agt_cfg" in content


def test_vsqr_has_agent_sqrs(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = EnvGenerator(sc_cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "top_vsqr.sv")) as f:
            content = f.read()
        assert "axi_sqr" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_env_generator.py -v`
Expected: FAIL

- [ ] **Step 3: Create self_contained env templates**

Create 5 templates under `uvm_gen/uvm_gen/templates/self_contained/env/`:

**env.sv.j2** — env class with agent instances, rm, checker, vsqr. No FIFO declarations. `connect_phase` directly connects `agent.m_mon_ap` to rm/checker exports. Uses `{% for agent in agents %}` loop. Port from spec section 9.4.

**env_cfg.sv.j2** — env config class containing each agent's `{{ agent.name }}_agt_cfg` handle. Port from `gen_uvm_env_cfg` (line 256).

**rm.sv.j2** — reference model skeleton with `uvm_analysis_imp` input. Port from `gen_uvm_rm` (line 303).

**checker.sv.j2** — checker skeleton with analysis imp. Port from `gen_uvm_checker` (line 378).

**vsqr.sv.j2** — virtual sequencer with handles to each agent's sqr. Port from `gen_uvm_vsqr` (line 492).

- [ ] **Step 4: Create standard env templates**

Create 5 templates under `uvm_gen/uvm_gen/templates/standard/env/` with key differences:
- **env.sv.j2** — declares `uvm_tlm_analysis_fifo` per agent, connect_phase creates FIFO connections. Port from spec section 9.3.
- **rm.sv.j2** — uses `blocking_get_port` instead of analysis_imp
- **checker.sv.j2** — uses `blocking_get_port` for expect/actual
- **env_cfg.sv.j2** and **vsqr.sv.j2** — identical to self_contained versions

- [ ] **Step 5: Implement EnvGenerator**

```python
# uvm_gen/uvm_gen/generators/env.py
from __future__ import annotations

import os

from uvm_gen.config import ProjectConfig
from uvm_gen.generators.base import BaseGenerator


class EnvGenerator(BaseGenerator):
    ENV_TEMPLATES = [
        ("env.sv", "env.sv.j2"),
        ("env_cfg.sv", "env_cfg.sv.j2"),
        ("rm.sv", "rm.sv.j2"),
        ("checker.sv", "checker.sv.j2"),
        ("vsqr.sv", "vsqr.sv.j2"),
    ]

    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        block = self.cfg.block_name

        ctx = {
            "agents": self.cfg.agents,
        }

        for suffix, template_name in self.ENV_TEMPLATES:
            filename = f"{block}_{suffix}"
            template_path = self.get_template_path("env", template_name)
            content = self.render_template(template_path, file_name=filename, **ctx)
            self.write_file(os.path.join(output_dir, filename), content)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_env_generator.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add uvm_gen/generators/env.py uvm_gen/templates/self_contained/env/ uvm_gen/templates/standard/env/ tests/test_env_generator.py
git commit -m "feat: add env generator with self-contained and standard templates"
```

---

### Task 6: Harness, Testcase, Cfg, Sim Generators

**Files:**
- Create: `uvm_gen/uvm_gen/generators/harness.py`
- Create: `uvm_gen/uvm_gen/generators/testcase.py`
- Create: `uvm_gen/uvm_gen/templates/harness/harness.sv.j2`
- Create: `uvm_gen/uvm_gen/templates/tc/base_test.sv.j2`
- Create: `uvm_gen/uvm_gen/templates/tc/tc_f.j2`
- Create: `uvm_gen/uvm_gen/templates/cfg/dut_f.j2`
- Create: `uvm_gen/uvm_gen/templates/cfg/env_f.j2`
- Create: `uvm_gen/uvm_gen/templates/cfg/tb_f.j2`
- Create: `uvm_gen/uvm_gen/templates/sim/Makefile.j2`
- Create: `uvm_gen/tests/test_supporting_generators.py`

- [ ] **Step 1: Write failing test**

```python
# uvm_gen/tests/test_supporting_generators.py
import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.harness import HarnessGenerator
from uvm_gen.generators.testcase import TestcaseGenerator


@pytest.fixture
def cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[
            AgentConfig(name="axi", mode=AgentMode.MASTER),
            AgentConfig(name="apb", mode=AgentMode.SLAVE),
        ],
    )


def test_harness_generates(cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = HarnessGenerator(cfg)
        gen.generate(tmpdir)
        path = os.path.join(tmpdir, "harness.sv")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "axi_if" in content
        assert "apb_if" in content


def test_testcase_generates(cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestcaseGenerator(cfg)
        gen.generate(tmpdir)
        assert os.path.exists(os.path.join(tmpdir, "base_test.sv"))
        assert os.path.exists(os.path.join(tmpdir, "tc.f"))
        with open(os.path.join(tmpdir, "base_test.sv")) as f:
            content = f.read()
        assert "top_env" in content


def test_testcase_tc_f_includes(cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = TestcaseGenerator(cfg)
        gen.generate(tmpdir)
        with open(os.path.join(tmpdir, "tc.f")) as f:
            content = f.read()
        assert "base_test.sv" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_supporting_generators.py -v`
Expected: FAIL

- [ ] **Step 3: Create templates**

Port from existing functions:
- `templates/harness/harness.sv.j2` — from `gen_uvm_harness` (line 519). Interface instantiation per agent, `initial begin` for `uvm_config_db` set.
- `templates/tc/base_test.sv.j2` — from `gen_uvm_tc_file` (line 566). Base test class with env instantiation.
- `templates/tc/tc_f.j2` — filelist with base_test and tc_sanity includes.
- `templates/cfg/dut_f.j2` — placeholder DUT filelist.
- `templates/cfg/env_f.j2` — from `gen_uvm_cfg_file` (line 25). References to common, agents, env files.
- `templates/cfg/tb_f.j2` — combines dut.f + env.f.
- `templates/sim/Makefile.j2` — from `gen_uvm_makefile` (line 740). VCS compile/run/clean/verdi targets.

- [ ] **Step 4: Implement HarnessGenerator and TestcaseGenerator**

```python
# uvm_gen/uvm_gen/generators/harness.py
from __future__ import annotations

import os

from uvm_gen.generators.base import BaseGenerator


class HarnessGenerator(BaseGenerator):
    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        template_path = self.get_template_path("harness", "harness.sv.j2")
        content = self.render_template(
            template_path,
            file_name="harness.sv",
            agents=self.cfg.agents,
        )
        self.write_file(os.path.join(output_dir, "harness.sv"), content)
```

```python
# uvm_gen/uvm_gen/generators/testcase.py
from __future__ import annotations

import os

from uvm_gen.generators.base import BaseGenerator


class TestcaseGenerator(BaseGenerator):
    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        # base_test.sv
        template_path = self.get_template_path("tc", "base_test.sv.j2")
        content = self.render_template(
            template_path,
            file_name="base_test.sv",
            agents=self.cfg.agents,
        )
        self.write_file(os.path.join(output_dir, "base_test.sv"), content)

        # tc.f
        template_path = self.get_template_path("tc", "tc_f.j2")
        content = self.render_template(template_path, file_name="tc.f")
        self.write_file(os.path.join(output_dir, "tc.f"), content)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_supporting_generators.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add uvm_gen/generators/harness.py uvm_gen/generators/testcase.py uvm_gen/templates/harness/ uvm_gen/templates/tc/ uvm_gen/templates/cfg/ uvm_gen/templates/sim/ tests/test_supporting_generators.py
git commit -m "feat: add harness, testcase, cfg, and sim generators with templates"
```

---

### Task 7: Platform Generator (Full Orchestration)

**Files:**
- Create: `uvm_gen/uvm_gen/generators/platform.py`
- Create: `uvm_gen/tests/test_platform_generator.py`

- [ ] **Step 1: Write failing test**

```python
# uvm_gen/tests/test_platform_generator.py
import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.platform import PlatformGenerator


@pytest.fixture
def sc_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[
            AgentConfig(name="axi", mode=AgentMode.MASTER),
            AgentConfig(name="apb", mode=AgentMode.SLAVE),
        ],
    )


@pytest.fixture
def std_cfg():
    return ProjectConfig(
        project_name="bootis",
        author="ryan.yu",
        block_name="top",
        platform_type=PlatformType.STANDARD,
        agents=[
            AgentConfig(name="axi", mode=AgentMode.MASTER),
        ],
    )


def test_sc_platform_full_structure(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        sc_cfg.output_dir = tmpdir
        gen = PlatformGenerator(sc_cfg)
        gen.generate()

        project_dir = os.path.join(tmpdir, "bootis_top")

        # Top-level dirs
        for d in ["agents", "env", "common", "harness", "tc", "cfg", "sim", "ral", "doc"]:
            assert os.path.isdir(os.path.join(project_dir, d)), f"Missing dir: {d}"

        # Agent dirs
        assert os.path.isdir(os.path.join(project_dir, "agents", "axi_agent", "src"))
        assert os.path.isdir(os.path.join(project_dir, "agents", "apb_agent", "src"))

        # Key files
        assert os.path.exists(os.path.join(project_dir, "env", "top_env.sv"))
        assert os.path.exists(os.path.join(project_dir, "common", "common_lib_pkg.sv"))
        assert os.path.exists(os.path.join(project_dir, "harness", "harness.sv"))
        assert os.path.exists(os.path.join(project_dir, "tc", "base_test.sv"))
        assert os.path.exists(os.path.join(project_dir, "cfg", "tb.f"))
        assert os.path.exists(os.path.join(project_dir, "sim", "Makefile"))


def test_std_platform_full_structure(std_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        std_cfg.output_dir = tmpdir
        gen = PlatformGenerator(std_cfg)
        gen.generate()

        project_dir = os.path.join(tmpdir, "bootis_top")
        env_file = os.path.join(project_dir, "env", "top_env.sv")
        assert os.path.exists(env_file)
        with open(env_file) as f:
            content = f.read()
        assert "uvm_tlm_analysis_fifo" in content


def test_platform_sim_dirs(sc_cfg):
    with tempfile.TemporaryDirectory() as tmpdir:
        sc_cfg.output_dir = tmpdir
        gen = PlatformGenerator(sc_cfg)
        gen.generate()

        project_dir = os.path.join(tmpdir, "bootis_top")
        assert os.path.isdir(os.path.join(project_dir, "sim", "log"))
        assert os.path.isdir(os.path.join(project_dir, "sim", "wave"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_platform_generator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement PlatformGenerator**

```python
# uvm_gen/uvm_gen/generators/platform.py
from __future__ import annotations

import os

from uvm_gen.config import ProjectConfig
from uvm_gen.generators.agent import AgentGenerator
from uvm_gen.generators.common import CommonGenerator
from uvm_gen.generators.env import EnvGenerator
from uvm_gen.generators.harness import HarnessGenerator
from uvm_gen.generators.testcase import TestcaseGenerator
from uvm_gen.generators.base import BaseGenerator


class PlatformGenerator(BaseGenerator):
    def generate(self) -> str:
        output_dir = self.cfg.output_dir or "."
        project_dir = os.path.join(
            output_dir, f"{self.cfg.project_name}_{self.cfg.block_name}"
        )

        if os.path.exists(project_dir):
            raise FileExistsError(f"{project_dir} already exists")

        os.makedirs(project_dir)

        # agents/
        agents_dir = os.path.join(project_dir, "agents")
        agent_gen = AgentGenerator(self.cfg)
        for agent_cfg in self.cfg.agents:
            agent_gen.generate_agent(agent_cfg, agents_dir)

        # env/
        env_gen = EnvGenerator(self.cfg)
        env_gen.generate(os.path.join(project_dir, "env"))

        # common/
        common_gen = CommonGenerator(self.cfg)
        common_gen.generate(os.path.join(project_dir, "common"))

        # harness/
        harness_gen = HarnessGenerator(self.cfg)
        harness_gen.generate(os.path.join(project_dir, "harness"))

        # tc/
        tc_gen = TestcaseGenerator(self.cfg)
        tc_gen.generate(os.path.join(project_dir, "tc"))

        # cfg/ (filelists)
        cfg_dir = os.path.join(project_dir, "cfg")
        os.makedirs(cfg_dir, exist_ok=True)
        for tpl_name, out_name in [
            ("dut_f.j2", "dut.f"),
            ("env_f.j2", "env.f"),
            ("tb_f.j2", "tb.f"),
        ]:
            content = self.render_template(
                f"cfg/{tpl_name}",
                file_name=out_name,
                agents=self.cfg.agents,
            )
            self.write_file(os.path.join(cfg_dir, out_name), content)

        # sim/
        sim_dir = os.path.join(project_dir, "sim")
        os.makedirs(sim_dir, exist_ok=True)
        makefile = self.render_template("sim/Makefile.j2", file_name="Makefile")
        self.write_file(os.path.join(sim_dir, "Makefile"), makefile)
        os.makedirs(os.path.join(sim_dir, "log"), exist_ok=True)
        os.makedirs(os.path.join(sim_dir, "wave"), exist_ok=True)

        # ral/ and doc/ (empty dirs)
        os.makedirs(os.path.join(project_dir, "ral"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "doc"), exist_ok=True)

        return project_dir
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_platform_generator.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add uvm_gen/generators/platform.py tests/test_platform_generator.py
git commit -m "feat: add platform generator orchestrating all sub-generators"
```

---

### Task 8: CLI (argparse + interactive + YAML)

**Files:**
- Create: `uvm_gen/uvm_gen/cli.py`
- Create: `uvm_gen/tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# uvm_gen/tests/test_cli.py
import os
import tempfile

import pytest
from uvm_gen.cli import build_parser, run_from_args


@pytest.fixture
def parser():
    return build_parser()


def test_parser_platform_subcommand(parser):
    args = parser.parse_args([
        "platform",
        "--type", "self-contained",
        "--block", "top",
        "--agents", "axi:master,apb:slave",
        "--author", "ryan",
        "--project", "bootis",
    ])
    assert args.command == "platform"
    assert args.type == "self-contained"
    assert args.block == "top"
    assert args.agents == "axi:master,apb:slave"


def test_parser_agent_subcommand(parser):
    args = parser.parse_args([
        "agent",
        "--type", "standard",
        "--name", "axi",
        "--mode", "master",
        "--author", "ryan",
        "--project", "bootis",
    ])
    assert args.command == "agent"
    assert args.name == "axi"
    assert args.mode == "master"


def test_parser_yaml_mode(parser):
    args = parser.parse_args(["-f", "config.yaml"])
    assert args.config_file == "config.yaml"


def test_run_platform_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        args_list = [
            "platform",
            "--type", "self-contained",
            "--block", "top",
            "--agents", "axi:master",
            "--author", "ryan",
            "--project", "testprj",
            "--output", tmpdir,
        ]
        parser = build_parser()
        args = parser.parse_args(args_list)
        run_from_args(args)

        project_dir = os.path.join(tmpdir, "testprj_top")
        assert os.path.isdir(project_dir)
        assert os.path.exists(os.path.join(project_dir, "env", "top_env.sv"))


def test_run_agent_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        args_list = [
            "agent",
            "--type", "self-contained",
            "--name", "spi",
            "--mode", "slave",
            "--author", "ryan",
            "--project", "testprj",
            "--output", tmpdir,
        ]
        parser = build_parser()
        args = parser.parse_args(args_list)
        run_from_args(args)

        agent_dir = os.path.join(tmpdir, "spi_agent")
        assert os.path.isdir(agent_dir)
        assert os.path.exists(os.path.join(agent_dir, "src", "spi_agent.sv"))


def test_run_yaml_from_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "config.yaml")
        with open(yaml_path, "w") as f:
            f.write(f"""
project: yamlprj
author: test
block: sub
type: standard
output_dir: {tmpdir}
agents:
  - name: uart
    mode: master
""")
        parser = build_parser()
        args = parser.parse_args(["-f", yaml_path])
        run_from_args(args)

        project_dir = os.path.join(tmpdir, "yamlprj_sub")
        assert os.path.isdir(project_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Implement cli.py**

```python
# uvm_gen/uvm_gen/cli.py
from __future__ import annotations

import argparse
import sys

from uvm_gen.config import (
    AgentConfig,
    AgentMode,
    PlatformType,
    ProjectConfig,
)
from uvm_gen.generators.agent import AgentGenerator
from uvm_gen.generators.platform import PlatformGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uvm_gen",
        description="UVM Testbench Generator",
    )
    parser.add_argument("-f", "--config-file", dest="config_file", help="YAML config file")

    subparsers = parser.add_subparsers(dest="command")

    # platform subcommand
    p_platform = subparsers.add_parser("platform", help="Generate full UVM platform")
    p_platform.add_argument("--type", required=True, choices=["self-contained", "standard"])
    p_platform.add_argument("--block", required=True)
    p_platform.add_argument("--agents", required=True, help='e.g. "axi:master,apb:slave"')
    p_platform.add_argument("--author", required=True)
    p_platform.add_argument("--project", required=True)
    p_platform.add_argument("--output", default=".")

    # agent subcommand
    p_agent = subparsers.add_parser("agent", help="Generate standalone agent")
    p_agent.add_argument("--type", required=True, choices=["self-contained", "standard"])
    p_agent.add_argument("--name", required=True)
    p_agent.add_argument("--mode", required=True,
                         choices=["master", "slave", "only-master", "only-slave", "only-monitor"])
    p_agent.add_argument("--author", required=True)
    p_agent.add_argument("--project", required=True)
    p_agent.add_argument("--output", default=".")

    return parser


def parse_agents_string(agents_str: str) -> list[AgentConfig]:
    agents = []
    for pair in agents_str.split(","):
        parts = pair.strip().split(":")
        name = parts[0]
        mode = AgentMode(parts[1]) if len(parts) > 1 else AgentMode.MASTER
        agents.append(AgentConfig(name=name, mode=mode))
    return agents


def run_from_args(args: argparse.Namespace) -> None:
    # YAML mode
    if hasattr(args, "config_file") and args.config_file:
        with open(args.config_file) as f:
            cfg = ProjectConfig.from_yaml(f.read())
        gen = PlatformGenerator(cfg)
        project_dir = gen.generate()
        print(f"Platform generated: {project_dir}")
        return

    if args.command == "platform":
        agents = parse_agents_string(args.agents)
        cfg = ProjectConfig(
            project_name=args.project,
            author=args.author,
            block_name=args.block,
            platform_type=PlatformType(args.type),
            agents=agents,
            output_dir=args.output,
        )
        gen = PlatformGenerator(cfg)
        project_dir = gen.generate()
        print(f"Platform generated: {project_dir}")

    elif args.command == "agent":
        agent_cfg = AgentConfig(name=args.name, mode=AgentMode(args.mode))
        cfg = ProjectConfig(
            project_name=args.project,
            author=args.author,
            block_name="",
            platform_type=PlatformType(args.type),
            agents=[agent_cfg],
        )
        gen = AgentGenerator(cfg)
        gen.generate_agent(agent_cfg, args.output)
        print(f"Agent generated: {args.output}/{args.name}_agent/")

    elif args.command is None:
        interactive_mode()

    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


def interactive_mode() -> None:
    print("=== UVM Gen Interactive Mode ===")
    print("Choose generation type:")
    print("  1) Full platform")
    print("  2) Standalone agent")
    choice = input("Enter choice [1/2]: ").strip()

    print("\nPlatform type:")
    print("  1) self-contained (FIFO internalized, task-based sequence)")
    print("  2) standard (traditional UVM, env manages FIFO)")
    ptype_choice = input("Enter choice [1/2]: ").strip()
    platform_type = PlatformType.SELF_CONTAINED if ptype_choice == "1" else PlatformType.STANDARD

    project = input("Project name: ").strip()
    author = input("Author: ").strip()

    if choice == "1":
        block = input("Block name: ").strip()
        agents_str = input('Agents (e.g. "axi:master,apb:slave"): ').strip()
        output = input("Output directory [.]: ").strip() or "."

        agents = parse_agents_string(agents_str)
        cfg = ProjectConfig(
            project_name=project,
            author=author,
            block_name=block,
            platform_type=platform_type,
            agents=agents,
            output_dir=output,
        )
        gen = PlatformGenerator(cfg)
        project_dir = gen.generate()
        print(f"\nPlatform generated: {project_dir}")

    elif choice == "2":
        name = input("Agent name: ").strip()
        print("Agent mode: master/slave/only-master/only-slave/only-monitor")
        mode = input("Mode [master]: ").strip() or "master"
        output = input("Output directory [.]: ").strip() or "."

        agent_cfg = AgentConfig(name=name, mode=AgentMode(mode))
        cfg = ProjectConfig(
            project_name=project,
            author=author,
            block_name="",
            platform_type=platform_type,
            agents=[agent_cfg],
        )
        gen = AgentGenerator(cfg)
        gen.generate_agent(agent_cfg, output)
        print(f"\nAgent generated: {output}/{name}_agent/")


def main():
    parser = build_parser()
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/test_cli.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add uvm_gen/cli.py tests/test_cli.py
git commit -m "feat: add CLI with argparse subcommands, interactive mode, and YAML support"
```

---

### Task 9: Integration Test & Final Verification

**Files:**
- Create: `uvm_gen/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# uvm_gen/tests/test_integration.py
import os
import tempfile

import pytest
from uvm_gen.config import ProjectConfig, PlatformType, AgentConfig, AgentMode
from uvm_gen.generators.platform import PlatformGenerator


@pytest.fixture
def sc_three_agents():
    return ProjectConfig(
        project_name="chip_a",
        author="engineer",
        block_name="top",
        platform_type=PlatformType.SELF_CONTAINED,
        agents=[
            AgentConfig(name="axi", mode=AgentMode.MASTER),
            AgentConfig(name="apb", mode=AgentMode.SLAVE),
            AgentConfig(name="pcie", mode=AgentMode.ONLY_MONITOR),
        ],
    )


@pytest.fixture
def std_two_agents():
    return ProjectConfig(
        project_name="chip_b",
        author="engineer",
        block_name="sub",
        platform_type=PlatformType.STANDARD,
        agents=[
            AgentConfig(name="spi", mode=AgentMode.MASTER),
            AgentConfig(name="uart", mode=AgentMode.SLAVE),
        ],
    )


def test_sc_full_generation(sc_three_agents):
    """Self-contained platform with 3 agents generates complete structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sc_three_agents.output_dir = tmpdir
        gen = PlatformGenerator(sc_three_agents)
        project_dir = gen.generate()

        # All 3 agent directories
        for name in ["axi", "apb", "pcie"]:
            agent_sv = os.path.join(project_dir, "agents", f"{name}_agent", "src", f"{name}_agent.sv")
            assert os.path.exists(agent_sv)

        # Self-contained: agent has FIFO, env does not
        with open(os.path.join(project_dir, "agents", "axi_agent", "src", "axi_agent.sv")) as f:
            assert "m_mon_fifo" in f.read()
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            assert "uvm_tlm_analysis_fifo" not in f.read()

        # base_seq has task wrappers
        with open(os.path.join(project_dir, "agents", "axi_agent", "src", "axi_base_seq.sv")) as f:
            content = f.read()
            assert "send_trans" in content
            assert "wait_trans" in content

        # Env references all agents
        with open(os.path.join(project_dir, "env", "top_env.sv")) as f:
            content = f.read()
            assert "m_axi_agt" in content
            assert "m_apb_agt" in content
            assert "m_pcie_agt" in content


def test_std_full_generation(std_two_agents):
    """Standard platform with 2 agents generates FIFO-based env."""
    with tempfile.TemporaryDirectory() as tmpdir:
        std_two_agents.output_dir = tmpdir
        gen = PlatformGenerator(std_two_agents)
        project_dir = gen.generate()

        # Standard: agent has NO FIFO, env HAS FIFO
        with open(os.path.join(project_dir, "agents", "spi_agent", "src", "spi_agent.sv")) as f:
            assert "m_mon_fifo" not in f.read()
        with open(os.path.join(project_dir, "env", "sub_env.sv")) as f:
            assert "uvm_tlm_analysis_fifo" in f.read()

        # base_seq has NO task wrappers
        with open(os.path.join(project_dir, "agents", "spi_agent", "src", "spi_base_seq.sv")) as f:
            assert "send_trans" not in f.read()


def test_duplicate_project_raises(sc_three_agents):
    """Generating into existing directory raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sc_three_agents.output_dir = tmpdir
        gen = PlatformGenerator(sc_three_agents)
        gen.generate()

        with pytest.raises(FileExistsError):
            gen2 = PlatformGenerator(sc_three_agents)
            gen2.generate()


def test_cfg_filelist_references_agents(sc_three_agents):
    """env.f filelist references all agent .f files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sc_three_agents.output_dir = tmpdir
        gen = PlatformGenerator(sc_three_agents)
        project_dir = gen.generate()

        with open(os.path.join(project_dir, "cfg", "env.f")) as f:
            content = f.read()
        assert "axi_agent" in content
        assert "apb_agent" in content
        assert "pcie_agent" in content
```

- [ ] **Step 2: Run full test suite**

Run: `cd /home/ubuntu/ryan/uvm_gen && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Run CLI end-to-end test**

```bash
cd /home/ubuntu/ryan/uvm_gen

# Self-contained platform
python -m uvm_gen.cli platform --type self-contained --block top --agents "axi:master,apb:slave,pcie:only-monitor" --author ryan --project demo_sc --output /tmp/uvm_test
ls -R /tmp/uvm_test/demo_sc_top/

# Standard platform
python -m uvm_gen.cli platform --type standard --block top --agents "axi:master,apb:slave" --author ryan --project demo_std --output /tmp/uvm_test
ls -R /tmp/uvm_test/demo_std_top/

# Standalone agent
python -m uvm_gen.cli agent --type self-contained --name spi --mode slave --author ryan --project test --output /tmp/uvm_test
ls -R /tmp/uvm_test/spi_agent/
```

Expected: Three complete directory trees generated without errors.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full platform generation"
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: complete uvm_gen rewrite - modular template-driven CLI tool"
```
