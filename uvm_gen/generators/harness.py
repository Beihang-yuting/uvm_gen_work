import os
from .base import BaseGenerator


class HarnessGenerator(BaseGenerator):
    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        template_path = self.get_template_path("harness", "harness.sv.j2")
        content = self.render_template(template_path, file_name="harness.sv", agents=self.cfg.agents)
        self.write_file(os.path.join(output_dir, "harness.sv"), content)
