# UVM Gen 项目结构优化设计文档

## 1. 目录结构变更

### 1.1 完整平台生成（`gen_tb -b top -a "axi,apb"`）

```
top/
├── env/
│   ├── agents/
│   │   ├── axi_agent/
│   │   │   ├── src/
│   │   │   │   ├── axi_agent_pkg.sv
│   │   │   │   ├── axi_agent.sv
│   │   │   │   ├── axi_trans.sv
│   │   │   │   ├── axi_agt_cfg.sv
│   │   │   │   ├── axi_drv.sv
│   │   │   │   ├── axi_mon.sv
│   │   │   │   ├── axi_sqr.sv
│   │   │   │   ├── axi_base_seq.sv
│   │   │   │   └── axi_if.sv
│   │   │   └── axi_agent.f
│   │   └── apb_agent/
│   │       └── ...
│   ├── ral/
│   ├── top_sys_if.sv
│   ├── top_env.sv
│   ├── top_env_cfg.sv
│   ├── top_rm.sv
│   ├── top_checker.sv
│   └── top_vsqr.sv
├── common/
│   ├── common_lib_pkg.f
│   ├── common_lib_pkg.sv
│   ├── common_dec.sv
│   ├── common_report_server.sv
│   ├── common_self_debug_scb.sv
│   ├── common_uvm_scb.sv
│   └── common_draw_table.sv
├── th/
│   └── harness.sv
├── tc/
│   ├── base_test.sv
│   └── tc.f
├── cfg/
│   ├── dut.f
│   ├── env.f
│   ├── tb.f
│   ├── initreg.cfg
│   ├── xprop.cfg
│   └── wave.tcl
└── doc/
```

### 1.2 单独 Agent 生成（`gen_tb -a axi`）

```
axi_agent/
├── src/
│   ├── axi_agent_pkg.sv
│   ├── axi_agent.sv
│   ├── axi_trans.sv
│   ├── axi_agt_cfg.sv
│   ├── axi_drv.sv
│   ├── axi_mon.sv
│   ├── axi_sqr.sv
│   ├── axi_base_seq.sv
│   └── axi_if.sv
├── axi_agent.f
└── test_env/
    ├── axi_test_env.sv
    ├── axi_test_env_cfg.sv
    ├── axi_test_harness.sv
    ├── axi_base_test.sv
    └── cfg/
        ├── tb.f
        └── env.f
```

### 1.3 变更汇总

| 变更 | 说明 |
|------|------|
| `agents/` -> `env/agents/` | agent 归属 env 管理 |
| `ral/` -> `env/ral/` | ral 归属 env 管理 |
| 删除 `sim/` | 不再生成 sim 目录 |
| `harness/` -> `th/` | 目录改名，内部 harness.sv 不变 |
| 新增 `cfg/initreg.cfg` | VCS initreg 配置，含默认配置和详细注释 |
| 新增 `cfg/xprop.cfg` | VCS xprop 配置，含默认配置和详细注释 |
| 新增 `cfg/wave.tcl` | Verdi fsdb dump 脚本，含全功能示例 |
| 新增 `env/top_sys_if.sv` | 顶层系统 interface，例化各 agent interface |
| 根目录名 `{project}_{block}` -> `{block}` | 仅使用 block_name |
| 单独 agent 增加 `test_env/` | 可独立仿真的测试环境 |

## 2. CLI 变更

### 2.1 命令名

`uvm_gen` -> `gen_tb`

### 2.2 参数简化

```bash
# 完整平台（默认 advance 类型）
gen_tb -b top -a "axi,apb"

# 指定 port 类型
gen_tb -b top -a "axi,apb" -t port

# 单独生成 agent（无 -b 参数时自动推断）
gen_tb -a axi

# 交互式
gen_tb

# YAML 配置
gen_tb -f config.yaml
```

### 2.3 参数表

| 短参数 | 长参数 | 说明 | 默认值 |
|--------|--------|------|--------|
| `-b` | `--block` | block 名称 | 无（无则为单独 agent 模式） |
| `-a` | `--agent` | agent 列表，逗号分隔 | 必填 |
| `-t` | `--type` | 平台类型：`advance` / `port` | `advance` |
| `-f` | `--config-file` | YAML 配置文件 | 无 |
| `-o` | `--output` | 输出目录 | `.` |

### 2.4 移除的参数

| 参数 | 原因 |
|------|------|
| `--author` | 默认取 `os.getlogin()` |
| `--project` | 不再使用，目录名直接用 block_name |
| 子命令 `platform` / `agent` | 通过有无 `-b` 自动推断 |

### 2.5 平台类型重命名

| 旧名 | 新名 | 说明 |
|------|------|------|
| `self-contained` | `advance` | 自包含模式 |
| `standard` | `port` | 传统 UVM port 连接模式 |

## 3. 新增模板内容

### 3.1 initreg.cfg

VCS 寄存器初始化配置文件，包含：
- 全局初始化策略（random/0/1/x）
- 按模块层次指定初始化值
- 按信号名 pattern 匹配
- memory 初始化
- 排除规则

### 3.2 xprop.cfg

VCS X 传播配置文件，包含：
- xprop 模式选择（tmerge/xmerge/vmerge）
- 按模块层次指定 xprop 模式
- 排除模块/信号
- xprop 与 gate-level 仿真配合

### 3.3 wave.tcl

Verdi fsdb dump 脚本，包含：
- 基础 dump（fsdbDumpfile/fsdbDumpvars）
- 按层次选择性 dump
- dump 控制（on/off/limit）
- 信号过滤（include/exclude）
- dump memory/array
- dump SV interface/struct
- dump power 信息
- 重新 dump 前一段时间（fsdbDumpRewind）
- dump 状态查询
- 条件触发 dump

### 3.4 top_sys_if.sv

顶层系统 interface：
- 例化各 agent 的 interface（基于 agents 列表动态生成）
- clock/reset 信号
- 用于 uvm_config_db 统一传递

## 4. common_uvm_scb 修复

### 4.1 Bug 修复

| # | 问题 | 修复 |
|---|------|------|
| 1 | `ORDER_CMP_WITHOUT_LOSS` 分支 error 消息写成 `ORDER_CMP_WITH_LOSS` | 修正消息文案 |
| 2 | `cmp_order_with_loss_dut_trans` 中 `drop_cnt - 1` 逻辑反了 | 改为 `not_match_pair_cnt++`，不修改 drop_cnt |
| 3 | `ORDER_CMP_WITHOUT_LOSS` + `dut_faster_en=1` 比较失败时 rm/dut 包都丢失 | 失败时存入 `dut_find_not_match_q`，increment not_match_pair_cnt |
| 4 | `ORDER_CMP_WITHOUT_LOSS` + `dut_faster_en=0` dut_q 非空时缺少计数 | 增加 `not_match_pair_cnt++` 和存入 `dut_find_not_match_q` |

### 4.2 命名修复

| 旧名 | 新名 |
|------|------|
| `DISSORDER_CMP` | `DISORDER_CMP` |
| `m_err_print_threadhold` | `m_err_print_threshold` |

### 4.3 功能完善

| # | 改进 |
|---|------|
| 1 | `gen_report_info(report_in_env)` 区分两种格式 |
| 2 | report 表格增加列：`not_match_cnt`、`unmatched_dut_cnt`、`drop_cnt` |
| 3 | `queue_status_chk` 对 WITH_LOSS 模式：rm_q 残留改为 warning |
| 4 | `cmp_not_pass_action` 超过 threshold 后在 report_phase 输出 suppressed 计数 |
| 5 | `stream_trans_manager::report_info` 改用 `uvm_info` 替代 `$display` |

## 5. CLI 帮助与错误提示

### 5.1 Help 输出

`gen_tb -h` 输出完整使用说明：
```
UVM Testbench Generator

Usage:
  gen_tb -b <block> -a <agents> [-t advance|port] [-o <dir>]   Generate full platform
  gen_tb -a <agent_name> [-t advance|port] [-o <dir>]          Generate standalone agent
  gen_tb -f <config.yaml>                                       Generate from YAML config
  gen_tb                                                        Interactive mode

Options:
  -b, --block   Block name (omit for standalone agent mode)
  -a, --agent   Agent name(s), comma-separated (e.g. "axi,apb,pcie")
  -t, --type    Platform type: advance (default) or port
  -f, --config  YAML configuration file
  -o, --output  Output directory (default: current directory)
  -h, --help    Show this help message

Examples:
  gen_tb -b top -a "axi,apb"              # Full platform, advance mode
  gen_tb -b top -a "axi,apb" -t port      # Full platform, port mode
  gen_tb -a axi                            # Standalone agent with test env
  gen_tb -f my_project.yaml                # From YAML config
```

### 5.2 错误提示

| 场景 | 提示信息 |
|------|----------|
| 缺少 `-a` | `Error: -a/--agent is required. Use -h for help.` |
| agent 名称含非法字符 | `Error: agent name 'xx-yy' is invalid. Use only [a-z0-9_].` |
| 输出目录已存在 | `Error: directory 'top/' already exists. Remove it or use -o to specify a different path.` |
| `-t` 值非法 | `Error: invalid type 'xxx'. Choose from: advance, port` |
| YAML 文件不存在 | `Error: config file 'xxx.yaml' not found.` |
| YAML 格式错误 | `Error: failed to parse 'xxx.yaml': <yaml error detail>` |
| YAML 缺少必填字段 | `Error: missing required field 'block' in config file.` |

## 6. Python 代码变更

### 5.1 config.py

- 删除 `project_name` 字段
- `PlatformType` 枚举值改为 `ADVANCE = "advance"` / `PORT = "port"`
- `author` 默认值改为 `os.getlogin()`

### 5.2 cli.py

- 入口命令改为 `gen_tb`
- 移除子命令，通过有无 `-b` 推断模式
- 参数简化：`-b/-a/-t/-f/-o`

### 5.3 generators/platform.py

- 输出目录改为 `{block_name}/`
- agents 和 ral 生成到 `env/` 下
- 删除 sim 目录生成
- harness 输出到 `th/`
- 新增 initreg.cfg / xprop.cfg / wave.tcl 生成
- 新增 sys_if.sv 生成

### 5.4 generators/agent.py

- 新增 `generate_test_env()` 方法，生成 test_env/ 目录

### 5.5 模板文件变更

- 新增 `templates/cfg/initreg_cfg.j2`
- 新增 `templates/cfg/xprop_cfg.j2`
- 新增 `templates/cfg/wave_tcl.j2`
- 新增 `templates/{advance,port}/env/sys_if.sv.j2`
- 新增 `templates/{advance,port}/test_env/*.j2`（agent 测试环境）
- 重命名 `templates/self_contained/` -> `templates/advance/`
- 重命名 `templates/standard/` -> `templates/port/`
