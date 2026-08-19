import os

from ..config import ProjectConfig
from .base import BaseGenerator


class CommonGenerator(BaseGenerator):
    CORE_TEMPLATES = [
        ("common_lib_pkg.sv", "common/common_pkg.sv.j2"),
        ("common_dec.sv", "common/common_dec.sv.j2"),
        ("common_scb_types.sv", "common/common_scb_types.sv.j2"),
        ("common_scb_reporter.sv", "common/common_scb_reporter.sv.j2"),
        ("common_uvm_scb.sv", "common/base_scb.sv.j2"),
    ]
    AIP_TEMPLATES = [
        ("common_scb_registry.sv", "common/common_scb_registry.sv.j2"),
    ]

    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        filelist = "+incdir+./\n./common_lib_pkg.sv\n"
        if self.cfg.aip_core:
            filelist += "./common_scb_aip_adapter.sv\n"
        self.write_file(os.path.join(output_dir, "common_lib_pkg.f"), filelist)

        templates = list(self.CORE_TEMPLATES)
        if self.cfg.aip_core:
            templates[-1:-1] = self.AIP_TEMPLATES
        for filename, template in templates:
            content = self.render_template(template, file_name=filename)
            self.write_file(os.path.join(output_dir, filename), content)

        if self.cfg.aip_core:
            content = self.render_template(
                "common/common_scb_aip_adapter.sv.j2",
                file_name="common_scb_aip_adapter.sv",
            )
            self.write_file(
                os.path.join(output_dir, "common_scb_aip_adapter.sv"), content
            )
