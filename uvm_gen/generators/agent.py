import os

from ..config import AgentConfig, ProjectConfig
from .base import BaseGenerator


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
        }

        for suffix, template_name in self.AGENT_SRC_TEMPLATES:
            filename = f"{name}_{suffix}"
            template_path = self.get_template_path("agent", template_name)
            content = self.render_template(template_path, file_name=filename, **ctx)
            self.write_file(os.path.join(src_dir, filename), content)

        template_path = self.get_template_path("agent", "agent_f.j2")
        f_content = self.render_template(template_path, file_name=f"{name}_agent.f", **ctx)
        self.write_file(os.path.join(agent_dir, f"{name}_agent.f"), f_content)

        self.generate_test_env(agent_cfg, agent_dir)

    def generate_test_env(self, agent_cfg: AgentConfig, agent_dir: str) -> None:
        name = agent_cfg.name
        test_env_dir = os.path.join(agent_dir, "test_env")
        os.makedirs(test_env_dir, exist_ok=True)

        ctx = {
            "name": name,
            "name_upper": name.upper(),
            "agents": [agent_cfg],
        }

        templates = [
            ("test_env.sv.j2", f"{name}_test_env.sv"),
            ("test_env_cfg.sv.j2", f"{name}_test_env_cfg.sv"),
            ("test_harness.sv.j2", f"{name}_test_harness.sv"),
            ("base_test.sv.j2", f"{name}_base_test.sv"),
        ]
        for tpl_name, out_name in templates:
            template_path = self.get_template_path("test_env", tpl_name)
            content = self.render_template(template_path, file_name=out_name, **ctx)
            self.write_file(os.path.join(test_env_dir, out_name), content)

        cfg_dir = os.path.join(test_env_dir, "cfg")
        os.makedirs(cfg_dir, exist_ok=True)
        for tpl_name, out_name in [("tb_f.j2", "tb.f"), ("env_f.j2", "env.f")]:
            template_path = self.get_template_path("test_env", tpl_name)
            content = self.render_template(template_path, file_name=out_name, **ctx)
            self.write_file(os.path.join(cfg_dir, out_name), content)
