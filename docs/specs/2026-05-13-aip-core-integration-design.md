# uvm_gen × aip_core 深度集成设计

**日期：** 2026-05-13
**作者：** ryan
**状态：** 已确认

## 概述

在 uvm_gen 现有 ADVANCE/PORT 模式基础上，叠加 `aip_core: true` 开关，让生成的 UVM 环境原生集成 aip_core 的 TCL 命令框架、参数传递、彩色日志、时钟生成和活动检测能力。用户拿到就能 TCL 驱动测试。

不开启时，生成结果与现有完全一致。

## 配置方式

### YAML

```yaml
block: top
type: port           # advance 或 port
aip_core: true       # 开启 aip_core 集成
agents:
  - name: axi
  - name: apb
```

### CLI

```bash
gen_tb -b top -a "axi,apb" -t port --aip-core
```

### 前置条件

用户需设置环境变量 `AIP_CORE_HOME` 指向 aip_core 目录。生成的 filelist 通过 `$AIP_CORE_HOME` 引用，不拷贝 aip_core 文件。

## 生成的目录结构变化

```
{block}/
├── env/
│   ├── agents/{name}_agent/src/     # agent 不变
│   ├── {block}_vsqr.sv              # vsqr 加 static 成员
│   ├── {block}_env.sv               # env 加 activity_subscriber 连接
│   └── ...
├── common/
│   ├── aip_activity_subscriber.sv   # 新增：通用 activity subscriber
│   └── ...                          # 原有 common 文件不变
├── tc/
│   ├── tc_tcl.sv                    # 新增：TCL bridge 模式 test
│   ├── tc_base.sv                   # 传统 UVM 模式 test（原 base_test 改名）
│   ├── tc.f
│   └── tcl/
│       └── tc_tcl_demo.tcl          # TCL 示例脚本
├── th/
│   └── harness.sv                   # harness 加 aip_clk 100MHz demo
├── cfg/
│   ├── tb.f                         # 加 +incdir+$AIP_CORE_HOME、aip_core_pkg.sv
│   └── ...
└── ...
```

## 各组件改动

### 1. vsqr — static 成员供 aip_cmd_seq 注册

```systemverilog
class {block}_vsqr extends uvm_sequencer;
    // 实例成员（env connect_phase 赋值）
    {name}_sqr m_{name}_sqr;
    // static 成员（aip_cmd_seq 宏直接引用）
    static {name}_sqr s_{name}_sqr;   // aip_core 模式
endclass
```

env connect_phase 同时赋值两者：
```systemverilog
m_vsqr.m_{name}_sqr = m_{name}_agt.m_sqr;
{block}_vsqr::s_{name}_sqr = m_{name}_agt.m_sqr;  // aip_core
```

### 2. trans — set_path() 骨架 + 注释示例

不自动注册 cmdline 字段（trans 是空骨架，用户还没定义协议字段）。生成 `set_path(string path)` 方法框架和注释示例，用户实现。

### 3. base_seq — aip_cmd_seq 注册示例

seq 文件末尾生成注释状态的注册宏示例：
```systemverilog
// `aip_cmd_seq({name}_write, {name}_wr_seq, {block}_vsqr::s_{name}_sqr)
```

### 4. env — aip_activity_subscriber 自动连接

每个 agent 的 `m_mon_ap` 自动连接一个 `aip_activity_subscriber`：
- build_phase 创建 subscriber 实例
- connect_phase 连接 agent.m_mon_ap → subscriber.analysis_export
- 注释提示用户后续 rm/scb 实现后可自行添加更多 subscriber

### 5. common — 新增 aip_activity_subscriber.sv

通用 UVM subscriber，write() 时自动调 aip_activity::tick()。参数化类型，可挂任何 AP。

### 6. harness — aip_clk 100MHz demo

aip_core 模式用 `aip_clk_create(clk0, 100e6)` 替代传统 `CLK_GEN` 宏。

### 7. tc_tcl.sv — TCL bridge test

- raise_objection → 等 reset → aip_tcl_bridge::run_loop() → drop_objection
- 用户通过 TCL 脚本控制所有 seq 调用

### 8. tc_base.sv — 传统 UVM test

- 原 base_test 改名为 tc_base
- 保留传统 UVM 测试能力，用户在 run_phase 中写测试逻辑

### 9. tc/tcl/tc_tcl_demo.tcl — TCL 示例

- source $AIP_CORE_HOME/aip_cmd.tcl
- set_param / seq 调用 / fork join / end_test 示例（注释状态）

### 10. tb.f — filelist

aip_core 模式追加：
```
+incdir+$AIP_CORE_HOME
$AIP_CORE_HOME/aip_core_pkg.sv
```

### 11. aip_log 替换 UVM 原生日志

所有模板中的 `uvm_info/error/fatal` 在 aip_core 模式下替换为 `aip_uinfo/uerror/ufatal` 双括号宏。

## Python 侧改动

- `config.py`：ProjectConfig 加 `aip_core: bool = False`
- `cli.py`：加 `--aip-core` 参数
- `generators/base.py`：模板上下文加 `aip_core` 变量
- 各 generator 无需改动（模板层面条件控制）
- tc_tcl_demo.tcl 新增模板

## 不改的部分

- agent 内部（drv/mon/sqr）结构不变
- ADVANCE/PORT 的 FIFO 策略不变
- common 现有工具（report_server、draw_table 等）不变
- 不开 aip_core 时，生成结果和现在完全一致
- aip_cmd.tcl 不拷贝，用户从 $AIP_CORE_HOME source
