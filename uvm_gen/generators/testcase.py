from __future__ import annotations
import os
from uvm_gen.generators.base import BaseGenerator


class TestcaseGenerator(BaseGenerator):
    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        # tc_base.sv (always generated)
        template_path = self.get_template_path("tc", "base_test.sv.j2")
        content = self.render_template(template_path, file_name="tc_base.sv", agents=self.cfg.agents)
        self.write_file(os.path.join(output_dir, "tc_base.sv"), content)

        # tc_tcl.sv (aip_core only)
        if self.cfg.aip_core:
            content = self.render_template("tc/tc_tcl.sv.j2", file_name="tc_tcl.sv", agents=self.cfg.agents)
            self.write_file(os.path.join(output_dir, "tc_tcl.sv"), content)

            # tcl/ demo script
            tcl_dir = os.path.join(output_dir, "tcl")
            os.makedirs(tcl_dir, exist_ok=True)
            content = self.render_template("tc/tc_tcl_demo.tcl.j2", file_name="tc_tcl_demo.tcl", agents=self.cfg.agents)
            self.write_file(os.path.join(tcl_dir, "tc_tcl_demo.tcl"), content)

        # tc.f
        template_path = self.get_template_path("tc", "tc_f.j2")
        content = self.render_template(template_path, file_name="tc.f")
        self.write_file(os.path.join(output_dir, "tc.f"), content)
