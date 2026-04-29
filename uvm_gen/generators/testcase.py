from __future__ import annotations
import os
from uvm_gen.generators.base import BaseGenerator


class TestcaseGenerator(BaseGenerator):
    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        template_path = self.get_template_path("tc", "base_test.sv.j2")
        content = self.render_template(template_path, file_name="base_test.sv", agents=self.cfg.agents)
        self.write_file(os.path.join(output_dir, "base_test.sv"), content)
        template_path = self.get_template_path("tc", "tc_f.j2")
        content = self.render_template(template_path, file_name="tc.f")
        self.write_file(os.path.join(output_dir, "tc.f"), content)
