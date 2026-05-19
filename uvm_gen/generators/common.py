import os

from ..config import ProjectConfig
from .base import BaseGenerator


class CommonGenerator(BaseGenerator):
    TEMPLATES = [
        ("common_lib_pkg.sv", "common/common_pkg.sv.j2"),
        ("common_dec.sv", "common/common_dec.sv.j2"),
        ("common_report_server.sv", "common/report_server.sv.j2"),
        ("common_self_debug_scb.sv", "common/self_debug_scb.sv.j2"),
        ("common_uvm_scb.sv", "common/base_scb.sv.j2"),
        ("common_draw_table.sv", "common/draw_table.sv.j2"),
    ]

    def generate(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        # Generate filelist
        f_content = "+incdir+./\n./common_lib_pkg.sv\n"
        if self.cfg.aip_core:
            f_content += "./aip_activity_subscriber.sv\n"
        self.write_file(os.path.join(output_dir, "common_lib_pkg.f"), f_content)

        # Generate SV files
        for filename, template in self.TEMPLATES:
            content = self.render_template(template, file_name=filename)
            self.write_file(os.path.join(output_dir, filename), content)

        # aip_core: generate activity subscriber
        if self.cfg.aip_core:
            content = self.render_template(
                "common/aip_activity_subscriber.sv.j2",
                file_name="aip_activity_subscriber.sv",
            )
            self.write_file(os.path.join(output_dir, "aip_activity_subscriber.sv"), content)
