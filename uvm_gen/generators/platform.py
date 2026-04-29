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
        project_dir = os.path.join(output_dir, f"{self.cfg.project_name}_{self.cfg.block_name}")

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

        # cfg/
        cfg_dir = os.path.join(project_dir, "cfg")
        os.makedirs(cfg_dir, exist_ok=True)
        for tpl_name, out_name in [("dut_f.j2", "dut.f"), ("env_f.j2", "env.f"), ("tb_f.j2", "tb.f")]:
            content = self.render_template(f"cfg/{tpl_name}", file_name=out_name, agents=self.cfg.agents)
            self.write_file(os.path.join(cfg_dir, out_name), content)

        # sim/
        sim_dir = os.path.join(project_dir, "sim")
        os.makedirs(sim_dir, exist_ok=True)
        makefile = self.render_template("sim/Makefile.j2", file_name="Makefile")
        self.write_file(os.path.join(sim_dir, "Makefile"), makefile)
        os.makedirs(os.path.join(sim_dir, "log"), exist_ok=True)
        os.makedirs(os.path.join(sim_dir, "wave"), exist_ok=True)

        # ral/ and doc/
        os.makedirs(os.path.join(project_dir, "ral"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "doc"), exist_ok=True)

        return project_dir
