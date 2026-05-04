# gen_tb - UVM Testbench Generator

自动生成完整的 UVM 验证平台代码，支持两种平台类型、五种 agent 运行时模式。

## 安装

### 依赖

- Python 3.8+
- Jinja2 >= 2.11
- PyYAML >= 5.0
- MarkupSafe >= 1.1, < 2.2（Jinja2 依赖，Python 3.8 需限制版本）

### 在线安装

```bash
# 默认源
pip install -e .

# 国内源（推荐）
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 离线安装

如果目标机器无法联网，先在能上网的机器下载依赖包：

```bash
# 1. 下载依赖到 packages/ 目录
pip download Jinja2 PyYAML -d ./packages -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 将整个项目（含 packages/）拷贝到目标机器

# 3. 在目标机器上离线安装
pip install --no-index --find-links=./packages -e .
```

### 免安装使用

不想安装也可以直接运行（需手动确保 Jinja2 和 PyYAML 已安装）：

```bash
# 手动安装依赖
pip install Jinja2 PyYAML

# 直接运行
python -m uvm_gen.cli -b top -a "axi,apb"
```

### 全局命令配置

`pip install` 后如果 `gen_tb` 命令找不到，有以下方案：

**方案 1：添加 pip scripts 目录到 PATH**
```bash
# 查看 pip 安装脚本的位置
pip show -f uvm_gen | grep gen_tb

# 通常在 ~/.local/bin，加到 PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**方案 2：使用项目自带的 bin/gen_tb 脚本**
```bash
# 将项目 bin 目录加到 PATH
echo 'export PATH="/path/to/uvm_gen/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**方案 3：创建别名**
```bash
echo 'alias gen_tb="python3 -m uvm_gen.cli"' >> ~/.bashrc
source ~/.bashrc
```

## 快速开始

```bash
# 生成完整平台（默认 advance 模式）
gen_tb -b top -a "axi,apb"

# 生成单独 agent（含测试环境）
gen_tb -a axi
```

## CLI 用法

```
gen_tb -b <block> [-a <agents>] [-t advance|port] [-o <dir>]  生成完整平台
gen_tb -a <agent_name> [-t advance|port] [-o <dir>]           生成单独 agent
gen_tb -f <config.yaml>                                        从 YAML 配置生成
gen_tb                                                         交互模式
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-b, --block` | Block 名称（省略则为单独 agent 模式） | 无 |
| `-a, --agent` | Agent 名称列表，逗号分隔（平台模式可省略） | 无 |
| `-t, --type` | 平台类型：`advance` 或 `port` | `advance` |
| `-f, --config` | YAML 配置文件路径 | 无 |
| `-o, --output` | 输出目录 | `.`（当前目录） |

### 示例

```bash
# advance 模式，3 个 agent
gen_tb -b top -a "axi,apb,pcie"

# port 模式
gen_tb -b top -a "axi,apb" -t port

# 输出到指定目录
gen_tb -b top -a "axi" -o /path/to/output

# 从 YAML 配置生成
gen_tb -f config.yaml

# 交互式（不带参数）
gen_tb
```

## YAML 配置

```yaml
block: top
type: advance          # advance 或 port
agents:
  - name: axi
  - name: apb
  - name: pcie
```

## 两种平台类型

### advance（默认）

自包含模式，适合 IP 交付和快速集成：

- Agent 内置 FIFO（m_mon_fifo, m_req_fifo, m_rsp_fifo）
- base_seq 封装 `send_trans` / `wait_trans` / `wait_request` 等 task
- Env 不创建 FIFO，只接 agent 对外暴露的 m_mon_ap
- 用户通过 task 一行调用完成收发

### port

传统 UVM 模式，适合正式 block 级验证：

- Agent 对外暴露 analysis port，无内部 FIFO
- base_seq 为空骨架，用户自行 start_item/finish_item
- Env 创建 FIFO，手动连接 agent port 到 rm/checker

## 五种 Agent 运行时模式

生成的 agent 代码通过 cfg 中的枚举在运行时切换模式（不需要重新生成）：

| 模式 | 组件 | 说明 |
|------|------|------|
| `AGENT_MASTER` | drv + mon + sqr | 主动发起事务 |
| `AGENT_SLAVE` | drv + mon + sqr | 被动响应事务 |
| `AGENT_ONLY_MASTER` | drv + sqr | 只发不收 |
| `AGENT_ONLY_SLAVE` | drv + sqr | 只响应，无监控 |
| `AGENT_ONLY_MONITOR` | mon | 纯监测 |

## 生成的目录结构

### 完整平台（`gen_tb -b top -a "axi,apb"`）

```
top/
├── env/
│   ├── agents/
│   │   ├── axi_agent/
│   │   │   ├── src/                    # agent 源文件
│   │   │   │   ├── axi_agent_pkg.sv
│   │   │   │   ├── axi_agent.sv
│   │   │   │   ├── axi_trans.sv
│   │   │   │   ├── axi_agt_cfg.sv
│   │   │   │   ├── axi_drv.sv
│   │   │   │   ├── axi_mon.sv
│   │   │   │   ├── axi_sqr.sv
│   │   │   │   ├── axi_base_seq.sv
│   │   │   │   └── axi_if.sv
│   │   │   ├── axi_agent.f             # agent filelist
│   │   │   └── test_env/               # agent 独立测试环境
│   │   └── apb_agent/
│   │       └── ...
│   ├── ral/                             # 寄存器模型（预留）
│   ├── top_sys_if.sv                    # 顶层系统 interface
│   ├── top_env.sv
│   ├── top_env_cfg.sv
│   ├── top_rm.sv                        # Reference Model
│   ├── top_checker.sv                   # Checker/Scoreboard
│   └── top_vsqr.sv                      # Virtual Sequencer
├── common/
│   ├── common_lib_pkg.f
│   ├── common_lib_pkg.sv
│   ├── common_dec.sv                    # CLK_GEN / RST_GEN 宏
│   ├── common_report_server.sv          # 自定义 report 格式
│   ├── common_self_debug_scb.sv         # agent 内部自检 scb
│   ├── common_uvm_scb.sv               # 通用 scoreboard（3 种比较模式）
│   └── common_draw_table.sv             # 表格打印工具
├── th/
│   └── harness.sv                       # 顶层 harness（例化 DUT + interface）
├── tc/
│   ├── base_test.sv                     # 基础 test class
│   └── tc.f
├── cfg/
│   ├── dut.f                            # DUT filelist
│   ├── env.f                            # 环境 filelist
│   ├── tb.f                             # 顶层 filelist
│   ├── initreg.cfg                      # VCS 寄存器初始化配置
│   ├── xprop.cfg                        # VCS X 传播配置
│   └── wave.tcl                         # Verdi fsdb dump 脚本
└── doc/
```

### 单独 Agent（`gen_tb -a axi`）

```
axi_agent/
├── src/                                 # agent 源文件（同上）
├── axi_agent.f
└── test_env/                            # 可独立仿真的测试环境
    ├── axi_test_env.sv
    ├── axi_test_env_cfg.sv
    ├── axi_test_harness.sv
    ├── axi_base_test.sv
    └── cfg/
        ├── tb.f
        └── env.f
```

## VCS 编译

### 基础编译

```bash
cd top/
vcs -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    -f cfg/tb.f \
    -top harness
```

### 带 FSDB 波形 dump

```bash
vcs -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    +define+FSDB \
    -P $VERDI_HOME/share/PLI/VCS/LINUX64/novas.tab \
       $VERDI_HOME/share/PLI/VCS/LINUX64/pli.a \
    -f cfg/tb.f \
    -top harness

# 仿真时启用波形
./simv +UVM_TESTNAME=tc_base +wave_en=1
```

### 带 InitReg（寄存器随机初始化）

```bash
vcs -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    -initreg+cfg/initreg.cfg \
    -f cfg/tb.f \
    -top harness
```

### 带 Xprop（X 传播检测）

```bash
vcs -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    -xprop=tmerge,cfg/xprop.cfg \
    -f cfg/tb.f \
    -top harness
```

### 组合使用

```bash
vcs -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    +define+FSDB \
    -P $VERDI_HOME/share/PLI/VCS/LINUX64/novas.tab \
       $VERDI_HOME/share/PLI/VCS/LINUX64/pli.a \
    -initreg+cfg/initreg.cfg \
    -xprop=tmerge,cfg/xprop.cfg \
    -f cfg/tb.f \
    -top harness
```

## common_uvm_scb 使用说明

通用 scoreboard 支持三种比较模式：

| 模式 | 说明 |
|------|------|
| `ORDER_CMP_WITHOUT_LOSS` | 严格有序比较，不允许丢包 |
| `ORDER_CMP_WITH_LOSS` | 有序比较，允许丢包 |
| `DISORDER_CMP` | 乱序比较（默认） |

### 基本用法

```systemverilog
// 在 env 或 checker 中实例化
common_uvm_scb #(my_trans) m_scb;

// 配置比较模式
m_scb.m_cfg.m_cmp_mode = ORDER_CMP_WITHOUT_LOSS;
m_scb.m_cfg.m_allow_dut_faster_en = 0;
m_scb.m_cfg.m_err_print_threshold = 5;

// 发送 RM 预期
m_scb.send_rm_trans_to_cmp(rm_tr, stream_id);

// 发送 DUT 实际
m_scb.send_dut_trans_to_cmp(dut_tr, stream_id);
```

### Transaction 要求

Transaction 类需要实现 `self_define_do_compare` 方法：

```systemverilog
class my_trans extends uvm_object;
    // ...
    function bit self_define_do_compare(my_trans cmp_trans, output string diff, input int kind = -1);
        bit pass = 1;
        diff = "";
        if(this.addr != cmp_trans.addr) begin
            pass = 0;
            diff = {diff, $sformatf("addr: 0x%0h vs 0x%0h\n", this.addr, cmp_trans.addr)};
        end
        return pass;
    endfunction
endclass
```

## 开发与测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python -m pytest tests/ -v

# 当前测试覆盖：69 tests
```
