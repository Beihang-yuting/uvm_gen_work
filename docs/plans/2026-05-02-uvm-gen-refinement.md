# UVM Gen Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure directory layout, simplify CLI to `gen_tb`, add VCS config templates, fix common_uvm_scb bugs, add agent test_env generation, and verify on remote VCS server.

**Architecture:** Rename template dirs (self_contained->advance, standard->port), flatten CLI (no subcommands, auto-infer mode from -b presence), add new Jinja2 templates for initreg/xprop/wave/sys_if/test_env, fix all scb bugs in template.

**Tech Stack:** Python 3.10+, Jinja2, PyYAML, pytest

---

### Task 1: Rename template directories and update PlatformType + config

Rename self_contained->advance, standard->port. Remove project_name from config. Default author to os user.

### Task 2: Rewrite CLI as gen_tb

Remove subcommands, add -b/-a/-t/-f/-o flags, auto-infer mode, add help and error messages.

### Task 3: Restructure platform generator

Output to block_name/, agents under env/agents/, ral under env/ral/, harness to th/, remove sim/, add cfg templates.

### Task 4: Add new templates (initreg.cfg, xprop.cfg, wave.tcl, sys_if.sv)

VCS config files with detailed examples, sys_if for top-level interface.

### Task 5: Add agent test_env generation

Standalone agent gets a test_env/ directory with minimal testbench for independent simulation.

### Task 6: Fix common_uvm_scb bugs

Fix naming (DISSORDER->DISORDER, threadhold->threshold), logic bugs, reporting improvements.

### Task 7: Update all test files and fixtures

Adapt all tests to new config API and directory structure.

### Task 8: Update .f templates for new directory structure

Fix paths in env_f.j2 and tb_f.j2 for relocated agents and harness dirs.

### Task 9: Test on remote VCS server

Generate platform, copy to 10.11.10.61:2222, compile with VCS, fix any issues.
