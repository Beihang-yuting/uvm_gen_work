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
        ctx = {"agents": self.cfg.agents}
        for suffix, template_name in self.ENV_TEMPLATES:
            filename = f"{block}_{suffix}"
            template_path = self.get_template_path("env", template_name)
            content = self.render_template(template_path, file_name=filename, **ctx)
            self.write_file(os.path.join(output_dir, filename), content)
