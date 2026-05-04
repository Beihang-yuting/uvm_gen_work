# Agent 复位机制设计文档

## 概述

为 agent 模板添加复位机制，使 driver/monitor 能在任意时刻响应复位，自动清理状态并重新进入工作循环。

## 设计

### 1. cfg 新增字段

`{name}_agt_cfg` 中新增：
```systemverilog
bit  m_rst_flush_fifo = 1;    // 复位时是否清空 FIFO（默认清空）
```

### 2. driver 复位机制

run_phase 使用 `fork...join_any` 监听 rst_n 下降沿：
- 工作线程：执行 master_drive() 或 slave_drive()
- 复位线程：等待 negedge rst_n
- 复位触发时 disable fork，调用 `reset_signals()` + `reset_callback()`
- 然后 wait(rst_n===1) 重新进入循环

虚方法：
- `reset_signals()` — 用户 override，将输出信号拉到初始状态
- `reset_callback()` — 用户自定义复位回调（默认空）

driver 需要在 build_phase 中获取 vif（当前只有 monitor 有 vif）。

### 3. monitor 复位机制

与 driver 相同的 fork...join_any 结构：
- 工作线程：mon_transaction()
- 复位线程：等待 negedge rst_n
- 复位触发时 disable fork，调用 `reset_callback()`

### 4. agent 层 FIFO 清理

agent 新增 run_phase，监听 rst_n 下降沿：
- 根据 `m_cfg.m_rst_flush_fifo` 决定是否清空 m_mon_fifo/m_req_fifo/m_rsp_fifo
- agent 需要持有 m_vif 引用（build_phase 中从 config_db 获取）

### 5. 涉及文件

advance 模式：
- `templates/advance/agent/cfg.sv.j2` — 新增 m_rst_flush_fifo
- `templates/advance/agent/drv.sv.j2` — fork 复位监听 + reset_signals/reset_callback
- `templates/advance/agent/mon.sv.j2` — fork 复位监听 + reset_callback
- `templates/advance/agent/agent.sv.j2` — run_phase FIFO 清理 + build_phase 获取 vif

port 模式：
- `templates/port/agent/cfg.sv.j2` — 同上
- `templates/port/agent/drv.sv.j2` — 同上
- `templates/port/agent/mon.sv.j2` — 同上
- `templates/port/agent/agent.sv.j2` — 同上（无 FIFO 清理，只有 reset 日志）
