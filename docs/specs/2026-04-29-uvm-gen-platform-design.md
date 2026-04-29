# UVM 自动化生成平台设计文档

## 1. 概述

将现有的 2220 行单文件 UVM testbench 生成脚本重构为模块化、模板驱动的 CLI 工具，支持：
- 两种平台类型（生成时选择，两套独立模板）
  - **self-contained**：自包含模式，FIFO 内化、sqr 自动启动、task 直调
  - **standard**：传统 UVM 模式，env 管理 FIFO、标准 port 连接
- 五种 agent 模式（运行时枚举切换，一套代码）
- 三种 sequence 工作模式（仅 self-contained 类型）
- 单独生成 agent / 生成完整平台 / 增量添加 agent
- 三种 CLI 交互方式（参数、交互式、YAML 配置文件）

## 1.1 两种平台类型对比

生成时通过 `--type` 选择，生成完全不同的 agent + env 代码，互不混用：

| | self-contained（自包含） | standard（传统 UVM） |
|---|---|---|
| 定位 | IP 交付、联合仿真辅助 | 正式 block 级验证平台 |
| agent 内部 | 内置 FIFO、mon_fifo，base_seq 封装 task | 传统结构，对外暴露 analysis port |
| env 连接 | 不创建 FIFO，只接 agent 的 m_mon_ap | 创建 FIFO，手动连 agent port 到 rm/checker |
| base_seq | 封装 send_trans / wait_trans 等 task | 标准 uvm_sequence，用户自己写 body |
| sequence 调用 | 一行 task 调用搞定 | 用户自行 start_item/finish_item |
| 适合谁 | 需要快速集成的使用者 | 需要完整控制的验证工程师 |

## 2. 生成产物目录结构

### 2.1 完整平台生成

```
project/
├── agents/                     # 所有 agent（独立可复用）
│   ├── axi_agent/
│   │   ├── src/
│   │   │   ├── axi_agent_pkg.sv
│   │   │   ├── axi_agent.sv
│   │   │   ├── axi_trans.sv
│   │   │   ├── axi_agt_cfg.sv
│   │   │   ├── axi_drv.sv
│   │   │   ├── axi_mon.sv
│   │   │   ├── axi_sqr.sv
│   │   │   ├── axi_base_seq.sv
│   │   │   └── axi_if.sv
│   │   └── axi_agent.f
│   └── apb_agent/
│       └── ...
├── env/
│   ├── block_env.sv
│   ├── block_env_cfg.sv
│   ├── block_rm.sv
│   ├── block_checker.sv
│   └── block_vsqr.sv
├── common/
│   ├── common_pkg.sv
│   ├── report_server.sv
│   ├── base_scb.sv
│   └── draw_table.sv
├── harness/
│   └── harness.sv
├── tc/
│   ├── base_test.sv
│   └── tc.f
├── cfg/
│   ├── dut.f
│   ├── env.f
│   └── tb.f
├── sim/
│   ├── Makefile
│   ├── log/
│   └── wave/
├── ral/
└── doc/
```

### 2.2 单独生成 agent

只产出 `agents/xxx_agent/` 目录，包含完整的 `.f` 文件，可独立引用。

## 3. Agent 模式体系

### 3.1 五种模式枚举

生成的 agent 是一套代码，通过 cfg 中的枚举变量在运行时选择模式：

```systemverilog
typedef enum {
    AGENT_MASTER,       // drv(主动发起) + mon + sqr
    AGENT_SLAVE,        // drv(被动响应) + mon + sqr
    AGENT_ONLY_MASTER,  // drv(主动发起) + sqr，无 mon
    AGENT_ONLY_SLAVE,   // drv(被动响应) + sqr，无 mon
    AGENT_ONLY_MONITOR  // mon only，无 drv/sqr
} agent_mode_e;
```

### 3.2 组件实例化逻辑

agent build_phase 根据枚举决定实例化：

```systemverilog
function void xxx_agent::build_phase(uvm_phase phase);
    super.build_phase(phase);

    // cfg 获取/创建
    if(this.m_cfg == null) begin
        this.m_cfg = xxx_agt_cfg::type_id::create("m_cfg", this);
        if(!this.m_cfg.randomize())
            `uvm_fatal(get_full_name, "agent_cfg randomize failed")
    end

    `uvm_info(get_full_name, $sformatf("agent mode = %s", m_cfg.m_mode.name), UVM_NONE)

    // monitor: master / slave / only-monitor
    if(m_cfg.m_mode inside {AGENT_MASTER, AGENT_SLAVE, AGENT_ONLY_MONITOR}) begin
        m_mon = xxx_mon::type_id::create("m_mon", this);
        m_mon.m_cfg = this.m_cfg;
    end

    // driver + sqr: 除 only-monitor 外都创建
    if(m_cfg.m_mode != AGENT_ONLY_MONITOR) begin
        m_sqr = xxx_sqr::type_id::create("m_sqr", this);
        m_drv = xxx_drv::type_id::create("m_drv", this);
        m_drv.m_cfg = this.m_cfg;
    end

    // 自包含模式：内部 FIFO
    if(m_cfg.m_mode inside {AGENT_MASTER, AGENT_SLAVE}) begin
        m_req_fifo = new("m_req_fifo", this);
        m_rsp_fifo = new("m_rsp_fifo", this);
    end
    if(m_mon != null) begin
        m_mon_fifo = new("m_mon_fifo", this);
    end

    // debug scb
    if(m_cfg.m_self_debug_en && m_cfg.m_mode != AGENT_ONLY_MONITOR) begin
        m_debug_scb = common_self_debug_scb#(xxx_trans)::type_id::create("m_debug_scb", this);
    end
endfunction
```

### 3.3 Driver 模式分支

```systemverilog
task xxx_drv::run_phase(uvm_phase phase);
    super.run_phase(phase);
    case(m_cfg.m_mode)
        AGENT_MASTER, AGENT_ONLY_MASTER: master_drive();
        AGENT_SLAVE, AGENT_ONLY_SLAVE:   slave_drive();
        default: `uvm_fatal(get_full_name, "only-monitor mode should not have driver")
    endcase
endtask

// 用户需要实现的两个 task（留空骨架）
virtual task master_drive();
endtask

virtual task slave_drive();
endtask
```

## 4. Sequence 工作模式

### 4.1 三种 task 封装

在 base_seq 中提供三类 task，内部带模式检查：

```systemverilog
class xxx_base_seq extends uvm_sequence #(xxx_trans);

    // Fire & Forget: 发完不等
    virtual task send_trans(input xxx_trans tr);
        if(p_sequencer.m_cfg.m_mode == AGENT_ONLY_MONITOR)
            `uvm_fatal(get_type_name, "send_trans not available in ONLY_MONITOR mode")
        start_item(tr);
        finish_item(tr);
    endtask

    // Send & Wait Response: 发完等回应
    virtual task send_trans_with_rsp(input xxx_trans tr, output xxx_trans rsp);
        if(p_sequencer.m_cfg.m_mode == AGENT_ONLY_MONITOR)
            `uvm_fatal(get_type_name, "send_trans_with_rsp not available in ONLY_MONITOR mode")
        start_item(tr);
        finish_item(tr);
        get_response(rsp);
    endtask

    // Monitor Only: 被动抓取
    virtual task wait_trans(output xxx_trans tr);
        if(p_sequencer.m_cfg.m_mode inside {AGENT_ONLY_MASTER, AGENT_ONLY_SLAVE})
            `uvm_fatal(get_type_name, "wait_trans not available without monitor")
        p_sequencer.m_mon_fifo.get(tr);
    endtask

endclass
```

### 4.2 Slave 专用 task

```systemverilog
// 等待 master 请求
virtual task wait_request(output xxx_trans req);
    if(!(p_sequencer.m_cfg.m_mode inside {AGENT_SLAVE, AGENT_ONLY_SLAVE}))
        `uvm_fatal(get_type_name, "wait_request only available in SLAVE modes")
    p_sequencer.m_req_fifo.get(req);
endtask

// 发送响应
virtual task send_response(input xxx_trans rsp);
    if(!(p_sequencer.m_cfg.m_mode inside {AGENT_SLAVE, AGENT_ONLY_SLAVE}))
        `uvm_fatal(get_type_name, "send_response only available in SLAVE modes")
    start_item(rsp);
    finish_item(rsp);
endtask
```

### 4.3 用户调用示例

```systemverilog
// Master: 写操作（fire & forget）
class axi_wr_seq extends axi_base_seq;
    task body();
        axi_trans tr = axi_trans::type_id::create("tr");
        tr.randomize() with { m_cmd == WRITE; };
        send_trans(tr);
    endtask
endclass

// Master: 读操作（需要返回数据）
class axi_rd_seq extends axi_base_seq;
    task body();
        axi_trans tr = axi_trans::type_id::create("tr");
        axi_trans rsp;
        tr.randomize() with { m_cmd == READ; };
        send_trans_with_rsp(tr, rsp);
        `uvm_info(get_type_name, $sformatf("read data = 0x%0h", rsp.m_data), UVM_NONE)
    endtask
endclass

// Slave: 被动响应
class axi_slave_seq extends axi_base_seq;
    task body();
        forever begin
            axi_trans req, rsp;
            wait_request(req);
            rsp = axi_trans::type_id::create("rsp");
            rsp.m_data = mem[req.m_addr];
            send_response(rsp);
        end
    endtask
endclass

// Monitor: 纯监测
class axi_mon_seq extends axi_base_seq;
    task body();
        axi_trans tr;
        wait_trans(tr);
        `uvm_info(get_type_name, $sformatf("captured: %s", tr.sprint()), UVM_NONE)
    endtask
endclass
```

## 5. 自包含 Agent 机制

### 5.1 内部 FIFO

```systemverilog
class xxx_agent extends uvm_agent;
    // 内部 FIFO（自包含模式）
    uvm_tlm_analysis_fifo #(xxx_trans)  m_mon_fifo;     // mon 输出
    uvm_tlm_analysis_fifo #(xxx_trans)  m_req_fifo;     // slave: 请求缓存
    uvm_tlm_analysis_fifo #(xxx_trans)  m_rsp_fifo;     // slave: 响应缓存

    // 对外暴露的 analysis port（供 env 级 checker/rm 使用）
    uvm_analysis_port #(xxx_trans)      m_mon_ap;
endclass
```

### 5.2 Connect Phase

```systemverilog
function void xxx_agent::connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // drv <-> sqr
    if(m_cfg.m_mode != AGENT_ONLY_MONITOR) begin
        m_drv.seq_item_port.connect(m_sqr.seq_item_export);
    end

    // mon -> 内部 FIFO + 对外 AP
    if(m_mon != null) begin
        m_mon.m_ap.connect(m_mon_fifo.analysis_export);
        m_mon.m_ap.connect(m_mon_ap);
    end

    // debug scb
    if(m_cfg.m_self_debug_en && m_drv != null) begin
        m_drv.m_debug_scb = m_debug_scb;
        if(m_mon != null)
            m_mon.m_debug_scb = m_debug_scb;
    end
endfunction
```

### 5.3 Agent Cfg

```systemverilog
class xxx_agt_cfg extends uvm_object;
    agent_mode_e            m_mode = AGENT_MASTER;
    bit                     m_auto_start_seq = 0;
    bit                     m_self_debug_en  = 0;
    uvm_active_passive_enum m_is_active = UVM_ACTIVE;  // 保持兼容
endclass
```

## 6. 模式合法性校验矩阵

| agent mode | send_trans | send_trans_with_rsp | wait_trans | wait_request | send_response |
|------------|-----------|-------------------|-----------|-------------|--------------|
| MASTER | OK | OK | OK | FATAL | FATAL |
| SLAVE | FATAL | FATAL | OK | OK | OK |
| ONLY_MASTER | OK | OK | FATAL | FATAL | FATAL |
| ONLY_SLAVE | FATAL | FATAL | FATAL | OK | OK |
| ONLY_MONITOR | FATAL | FATAL | OK | FATAL | FATAL |

## 7. Python 工具架构

### 7.1 代码结构

```
uvm_gen/
├── uvm_gen/
│   ├── __init__.py
│   ├── cli.py                  # CLI 入口
│   ├── config.py               # 配置 dataclass
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── base.py             # 生成器基类（Jinja2 渲染）
│   │   ├── agent.py            # agent 生成
│   │   ├── env.py              # env 生成
│   │   ├── common.py           # common 组件生成
│   │   ├── harness.py          # harness 生成
│   │   ├── testcase.py         # tc 生成
│   │   └── platform.py         # 完整平台编排
│   └── templates/
│       ├── self_contained/         # 自包含模式模板
│       │   ├── agent/              # agent .sv.j2（内置 FIFO、task 封装）
│       │   └── env/                # env .sv.j2（轻量连接）
│       ├── standard/               # 传统 UVM 模式模板
│       │   ├── agent/              # agent .sv.j2（暴露 port）
│       │   └── env/                # env .sv.j2（创建 FIFO、port 连接）
│       ├── common/                 # 公共模板（两种类型共享）
│       ├── harness/
│       ├── tc/
│       ├── cfg/
│       └── sim/
├── setup.py
└── README.md
```

### 7.2 配置模型

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class PlatformType(Enum):
    SELF_CONTAINED = "self-contained"   # 自包含模式
    STANDARD = "standard"               # 传统 UVM 模式

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
```

### 7.3 CLI 子命令

```bash
# 生成完整平台（自包含模式）
uvm_gen platform --type self-contained --block top --agents "axi:master,apb:slave" --author ryan --project bootis

# 生成完整平台（传统 UVM 模式）
uvm_gen platform --type standard --block top --agents "axi:master,apb:slave" --author ryan --project bootis

# 单独生成 agent（自包含）
uvm_gen agent --type self-contained --name axi --mode master --author ryan --project bootis

# 单独生成 agent（传统）
uvm_gen agent --type standard --name axi --mode master --author ryan --project bootis

# 增量添加 agent 到已有项目（自动检测项目类型）
uvm_gen add-agent --name spi --mode master --project ./my_project

# 交互式（无参数时自动进入）
uvm_gen

# 配置文件驱动
uvm_gen -f config.yaml
```

### 7.4 YAML 配置示例

```yaml
project: bootis
author: ryan.yu
block: top
type: self-contained        # 或 standard
agents:
  - name: axi
    mode: master
  - name: apb
    mode: slave
  - name: pcie
    mode: only-monitor
```

## 8. 与现有脚本的迁移对照

| 现有函数 | 新架构 |
|---------|--------|
| gen_uvm_agent* (12个函数) | generators/agent.py + templates/agent/*.j2 |
| gen_uvm_env* (5个函数) | generators/env.py + templates/env/*.j2 |
| gen_uvm_common* (6个函数) | generators/common.py + templates/common/*.j2 |
| gen_uvm_harness | generators/harness.py + templates/harness/*.j2 |
| gen_uvm_tc* | generators/testcase.py + templates/tc/*.j2 |
| gen_uvm_cfg_file | generators/platform.py + templates/cfg/*.j2 |
| gen_uvm_makefile | generators/platform.py + templates/sim/*.j2 |
| gen_description | templates 中的通用 header block |
| main 逻辑 | cli.py + generators/platform.py |

## 9. Standard 类型（传统 UVM 模式）详细设计

### 9.1 Standard Agent

传统 agent 不含内部 FIFO，对外暴露 analysis port，由 env 负责连接：

```systemverilog
class xxx_agent extends uvm_agent;
    xxx_agt_cfg         m_cfg;
    xxx_sqr             m_sqr;
    xxx_drv             m_drv;
    xxx_mon             m_mon;
    common_self_debug_scb#(xxx_trans)  m_debug_scb;

    // 对外暴露的 port（env 来连）
    uvm_analysis_port #(xxx_trans)  m_mon_ap;

    // 无内部 FIFO，无 base_seq task 封装
endclass

function void xxx_agent::build_phase(uvm_phase phase);
    super.build_phase(phase);

    if(this.m_cfg == null) begin
        this.m_cfg = xxx_agt_cfg::type_id::create("m_cfg", this);
        if(!this.m_cfg.randomize())
            `uvm_fatal(get_full_name, "agent_cfg randomize failed")
    end

    // 同样根据五种枚举模式决定组件实例化
    if(m_cfg.m_mode inside {AGENT_MASTER, AGENT_SLAVE, AGENT_ONLY_MONITOR}) begin
        m_mon = xxx_mon::type_id::create("m_mon", this);
        m_mon.m_cfg = this.m_cfg;
        m_mon_ap = new("m_mon_ap", this);
    end

    if(m_cfg.m_mode != AGENT_ONLY_MONITOR) begin
        m_sqr = xxx_sqr::type_id::create("m_sqr", this);
        m_drv = xxx_drv::type_id::create("m_drv", this);
        m_drv.m_cfg = this.m_cfg;
    end

    if(m_cfg.m_self_debug_en && m_cfg.m_mode != AGENT_ONLY_MONITOR) begin
        m_debug_scb = common_self_debug_scb#(xxx_trans)::type_id::create("m_debug_scb", this);
    end
endfunction

function void xxx_agent::connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    if(m_cfg.m_mode != AGENT_ONLY_MONITOR)
        m_drv.seq_item_port.connect(m_sqr.seq_item_export);

    // mon -> 对外 AP（env 负责接）
    if(m_mon != null)
        m_mon.m_ap.connect(m_mon_ap);

    if(m_cfg.m_self_debug_en && m_drv != null) begin
        m_drv.m_debug_scb = m_debug_scb;
        if(m_mon != null)
            m_mon.m_debug_scb = m_debug_scb;
    end
endfunction
```

### 9.2 Standard Base Seq

传统模式的 base_seq 不封装 task，用户自己写 body：

```systemverilog
class xxx_base_seq extends uvm_sequence #(xxx_trans);
    `uvm_object_utils(xxx_base_seq)
    `uvm_declare_p_sequencer(xxx_sqr)

    function new(string name = "xxx_base_seq");
        super.new(name);
    endfunction

    // 用户继承后自己写 body，使用 start_item/finish_item
endclass
```

### 9.3 Standard Env

env 创建 FIFO，负责 agent port 到 rm/checker 的连接：

```systemverilog
class block_env extends uvm_env;
    block_env_cfg       m_cfg;

    // agents
    xxx_agent           m_xxx_agt;
    yyy_agent           m_yyy_agt;

    // rm & checker
    block_rm            m_rm;
    block_checker       m_scb;
    block_vsqr          m_vsqr;

    // env 层 FIFO（标准模式核心区别）
    // active agent mon -> rm
    uvm_tlm_analysis_fifo #(uvm_sequence_item)  m_xxx_agt_mon_to_rm_fifo;
    // rm output -> checker
    uvm_tlm_analysis_fifo #(uvm_sequence_item)  m_rm_yyy_trans_to_scb_fifo;
    // passive agent mon -> checker
    uvm_tlm_analysis_fifo #(uvm_sequence_item)  m_agt_yyy_trans_to_scb_fifo;
endclass

function void block_env::build_phase(uvm_phase phase);
    super.build_phase(phase);

    // 创建 agents
    m_xxx_agt = xxx_agent::type_id::create("m_xxx_agt", this);
    m_yyy_agt = yyy_agent::type_id::create("m_yyy_agt", this);

    // 传递 cfg
    m_xxx_agt.m_cfg = m_cfg.m_xxx_agt_cfg;
    m_yyy_agt.m_cfg = m_cfg.m_yyy_agt_cfg;

    // 创建 rm, checker
    m_rm  = block_rm::type_id::create("m_rm", this);
    m_scb = block_checker::type_id::create("m_scb", this);

    // 创建 FIFO
    m_xxx_agt_mon_to_rm_fifo    = new("m_xxx_agt_mon_to_rm_fifo", this);
    m_rm_yyy_trans_to_scb_fifo  = new("m_rm_yyy_trans_to_scb_fifo", this);
    m_agt_yyy_trans_to_scb_fifo = new("m_agt_yyy_trans_to_scb_fifo", this);

    // vsqr
    m_vsqr = block_vsqr::type_id::create("m_vsqr", this);
endfunction

function void block_env::connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // active agent mon -> FIFO -> rm
    m_xxx_agt.m_mon_ap.connect(m_xxx_agt_mon_to_rm_fifo.analysis_export);

    // rm -> FIFO -> checker (expect)
    // passive agent mon -> FIFO -> checker (actual)
    m_yyy_agt.m_mon_ap.connect(m_agt_yyy_trans_to_scb_fifo.analysis_export);

    // rm & checker 从 FIFO 取数据
    m_rm.m_input_port.connect(m_xxx_agt_mon_to_rm_fifo.blocking_get_export);
    m_scb.m_expect_port.connect(m_rm_yyy_trans_to_scb_fifo.blocking_get_export);
    m_scb.m_actual_port.connect(m_agt_yyy_trans_to_scb_fifo.blocking_get_export);

    // vsqr
    m_vsqr.m_xxx_sqr = m_xxx_agt.m_sqr;
endfunction
```

### 9.4 Self-Contained Env

自包含模式的 env 更简洁，不创建 FIFO：

```systemverilog
class block_env extends uvm_env;
    block_env_cfg       m_cfg;

    xxx_agent           m_xxx_agt;
    yyy_agent           m_yyy_agt;

    block_rm            m_rm;
    block_checker       m_scb;
    block_vsqr          m_vsqr;

    // 无 FIFO 声明 — agent 内部已自包含
endclass

function void block_env::build_phase(uvm_phase phase);
    super.build_phase(phase);

    m_xxx_agt = xxx_agent::type_id::create("m_xxx_agt", this);
    m_yyy_agt = yyy_agent::type_id::create("m_yyy_agt", this);

    m_xxx_agt.m_cfg = m_cfg.m_xxx_agt_cfg;
    m_yyy_agt.m_cfg = m_cfg.m_yyy_agt_cfg;

    m_rm  = block_rm::type_id::create("m_rm", this);
    m_scb = block_checker::type_id::create("m_scb", this);
    m_vsqr = block_vsqr::type_id::create("m_vsqr", this);
endfunction

function void block_env::connect_phase(uvm_phase phase);
    super.connect_phase(phase);

    // 只接 agent 对外暴露的 AP 到 rm/checker
    m_xxx_agt.m_mon_ap.connect(m_rm.m_input_export);
    m_yyy_agt.m_mon_ap.connect(m_scb.m_actual_export);

    // vsqr
    m_vsqr.m_xxx_sqr = m_xxx_agt.m_sqr;
endfunction
```

### 9.5 两种类型的模板文件组织

```
templates/
├── self_contained/
│   ├── agent/
│   │   ├── agent.sv.j2          # 内置 FIFO、mon_fifo
│   │   ├── base_seq.sv.j2       # 封装 send_trans/wait_trans 等 task
│   │   ├── drv.sv.j2            # master_drive/slave_drive 分支
│   │   ├── mon.sv.j2
│   │   ├── sqr.sv.j2            # 持有 mon_fifo/req_fifo 引用
│   │   ├── trans.sv.j2
│   │   ├── cfg.sv.j2
│   │   ├── if.sv.j2
│   │   ├── pkg.sv.j2
│   │   └── agent.f.j2
│   └── env/
│       ├── env.sv.j2            # 无 FIFO，轻量 connect
│       ├── env_cfg.sv.j2
│       ├── rm.sv.j2             # 用 analysis export 接数据
│       ├── checker.sv.j2        # 用 analysis export 接数据
│       └── vsqr.sv.j2
├── standard/
│   ├── agent/
│   │   ├── agent.sv.j2          # 无内部 FIFO，暴露 AP
│   │   ├── base_seq.sv.j2       # 空 body，用户自己写
│   │   ├── drv.sv.j2            # master_drive/slave_drive 分支
│   │   ├── mon.sv.j2
│   │   ├── sqr.sv.j2            # 标准 sqr
│   │   ├── trans.sv.j2
│   │   ├── cfg.sv.j2
│   │   ├── if.sv.j2
│   │   ├── pkg.sv.j2
│   │   └── agent.f.j2
│   └── env/
│       ├── env.sv.j2            # 创建 FIFO，port 连接
│       ├── env_cfg.sv.j2
│       ├── rm.sv.j2             # 从 FIFO blocking_get 取数据
│       ├── checker.sv.j2        # 从 FIFO blocking_get 取数据
│       └── vsqr.sv.j2
├── common/                      # 两种类型共享
│   ├── common_pkg.sv.j2
│   ├── report_server.sv.j2
│   ├── base_scb.sv.j2
│   └── draw_table.sv.j2
├── harness/
│   └── harness.sv.j2
├── tc/
│   ├── base_test.sv.j2
│   └── tc.f.j2
├── cfg/
│   ├── dut.f.j2
│   ├── env.f.j2
│   └── tb.f.j2
└── sim/
    └── Makefile.j2
```

## 10. 依赖

- Python 3.10+
- Jinja2（模板引擎）
- PyYAML（配置文件解析）
- 无其他外部依赖
