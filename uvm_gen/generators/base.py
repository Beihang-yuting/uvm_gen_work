import os
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..config import ProjectConfig, PlatformType

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class BaseGenerator:
    def __init__(self, cfg: ProjectConfig):
        self.cfg = cfg
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_string(self, template_str: str, **kwargs) -> str:
        tmpl = self.jinja_env.from_string(template_str)
        return tmpl.render(**kwargs)

    def render_header(self, file_name: str) -> str:
        tmpl = self.jinja_env.get_template("_header.sv.j2")
        return tmpl.render(
            project_name=self.cfg.block_name,
            author=self.cfg.author,
            date=time.strftime("%Y-%m-%d %X"),
            file_name=file_name,
        )

    def render_template(self, template_path: str, **kwargs) -> str:
        tmpl = self.jinja_env.get_template(template_path)
        return tmpl.render(
            author=self.cfg.author,
            block_name=self.cfg.block_name,
            date=time.strftime("%Y-%m-%d %X"),
            header=self.render_header,
            aip_core=self.cfg.aip_core,
            **kwargs,
        )

    def get_template_path(self, category: str, template_name: str) -> str:
        if category in ("common", "harness", "tc", "cfg"):
            return f"{category}/{template_name}"
        type_dir = (
            "advance"
            if self.cfg.platform_type == PlatformType.ADVANCE
            else "port"
        )
        return f"{type_dir}/{category}/{template_name}"

    def write_file(self, file_path: str, content: str) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
