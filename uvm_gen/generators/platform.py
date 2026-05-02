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
        project_dir = os.path.join(output_dir, self.cfg.block_name)

        if os.path.exists(project_dir):
            raise FileExistsError(f"directory '{project_dir}' already exists. Remove it or use -o to specify a different path.")

        os.makedirs(project_dir)

        # env/agents/
        agents_dir = os.path.join(project_dir, "env", "agents")
        agent_gen = AgentGenerator(self.cfg)
        for agent_cfg in self.cfg.agents:
            agent_gen.generate_agent(agent_cfg, agents_dir)

        # env/ (env.sv, env_cfg.sv, rm.sv, checker.sv, vsqr.sv, sys_if.sv)
        env_gen = EnvGenerator(self.cfg)
        env_gen.generate(os.path.join(project_dir, "env"))

        # env/ral/
        os.makedirs(os.path.join(project_dir, "env", "ral"), exist_ok=True)

        # common/
        common_gen = CommonGenerator(self.cfg)
        common_gen.generate(os.path.join(project_dir, "common"))

        # th/
        harness_gen = HarnessGenerator(self.cfg)
        harness_gen.generate(os.path.join(project_dir, "th"))

        # tc/
        tc_gen = TestcaseGenerator(self.cfg)
        tc_gen.generate(os.path.join(project_dir, "tc"))

        # cfg/
        cfg_dir = os.path.join(project_dir, "cfg")
        os.makedirs(cfg_dir, exist_ok=True)
        for tpl_name, out_name in [
            ("dut_f.j2", "dut.f"),
            ("env_f.j2", "env.f"),
            ("tb_f.j2", "tb.f"),
            ("initreg_cfg.j2", "initreg.cfg"),
            ("xprop_cfg.j2", "xprop.cfg"),
            ("wave_tcl.j2", "wave.tcl"),
        ]:
            content = self.render_template(f"cfg/{tpl_name}", file_name=out_name, agents=self.cfg.agents)
            self.write_file(os.path.join(cfg_dir, out_name), content)

        # doc/
        os.makedirs(os.path.join(project_dir, "doc"), exist_ok=True)

        return project_dir
