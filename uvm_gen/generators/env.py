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

        # sys_if.sv
        filename = f"{block}_sys_if.sv"
        template_path = self.get_template_path("env", "sys_if.sv.j2")
        content = self.render_template(template_path, file_name=filename, **ctx)
        self.write_file(os.path.join(output_dir, filename), content)

        # assert.sv and cov.sv (reference templates, not in filelist)
        for tpl, suffix in [("common/assert.sv.j2", "_assert.sv"), ("common/cov.sv.j2", "_cov.sv")]:
            filename = "%s%s" % (block, suffix)
            content = self.render_template(tpl, file_name=filename, **ctx)
            self.write_file(os.path.join(output_dir, filename), content)
