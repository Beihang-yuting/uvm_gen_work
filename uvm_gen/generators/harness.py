import os
from .base import BaseGenerator


class HarnessGenerator(BaseGenerator):
    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        template_path = self.get_template_path("harness", "harness.sv.j2")
        content = self.render_template(template_path, file_name="harness.sv", agents=self.cfg.agents)
        self.write_file(os.path.join(output_dir, "harness.sv"), content)

        bind_dir = os.path.join(output_dir, "bind")
        os.makedirs(bind_dir, exist_ok=True)
        for template_name, file_name in (
            ("common_sva.svh.j2", "common_sva.svh"),
            ("bind_example.sv.j2", "bind_example.sv"),
        ):
            content = self.render_template(
                f"harness/{template_name}",
                file_name=file_name,
                agents=self.cfg.agents,
            )
            self.write_file(os.path.join(bind_dir, file_name), content)
