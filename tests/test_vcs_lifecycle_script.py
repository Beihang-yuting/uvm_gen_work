import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_RUNNER = REPO_ROOT / "tests" / "vcs" / "run_port_reset_lifecycle.sh"
LIFECYCLE_SOURCE = REPO_ROOT / "tests" / "vcs" / "port_reset_lifecycle.sv"


def write_executable(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_port_reset_lifecycle_supplies_an_implemented_comparison_hook() -> None:
    source = LIFECYCLE_SOURCE.read_text(encoding="utf-8")

    assert "class port_lifecycle_axi_trans extends axi_trans;" in source
    assert "`uvm_object_utils(port_lifecycle_axi_trans)" in source
    assert "function bit self_define_do_compare(" in source
    assert "return 1;" in source
    assert "port_lifecycle_axi_trans::type_id::create" in source


@pytest.mark.parametrize("source_is_absolute", [False, True], ids=["relative", "absolute"])
def test_port_reset_lifecycle_runner_resolves_source_before_cd(
    tmp_path: Path, source_is_absolute: bool
) -> None:
    caller_dir = tmp_path / "caller"
    caller_dir.mkdir()
    lifecycle_source = caller_dir / "port_reset_lifecycle.sv"
    lifecycle_source.write_text("module harness; endmodule\n", encoding="utf-8")

    project_cfg = tmp_path / "generated_project" / "cfg"
    project_cfg.mkdir(parents=True)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    write_executable(
        fake_bin / "vcs",
        """#!/usr/bin/env bash
set -euo pipefail

for argument in "$@"; do
    case "${argument}" in
        *.sv)
            if [[ ! -f "${argument}" ]]; then
                echo "source unavailable from ${PWD}: ${argument}" >&2
                exit 92
            fi
            ;;
    esac
done

printf '%s\\n' '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'while [[ $# -gt 0 ]]; do' \
    '    case "$1" in' \
    '        -l) log=$2; shift 2 ;;' \
    '        *) shift ;;' \
    '    esac' \
    'done' \
    'printf "%s\\n" \\' \
    '    "UVM_INFO [PORT_LIFECYCLE] STAGE_0_MATCHED" \\' \
    '    "UVM_INFO [PORT_LIFECYCLE] STAGE_1_MATCHED" \\' \
    '    "UVM_INFO [PORT_LIFECYCLE] STAGE_2_MATCHED" \\' \
    '    "TC PASSED.(warning:0,error:0,fatal:0)" > "$log"' > simv
chmod +x simv
""",
    )

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    source_argument = (
        str(lifecycle_source) if source_is_absolute else lifecycle_source.name
    )
    result = subprocess.run(
        [str(LIFECYCLE_RUNNER), str(project_cfg.parent), source_argument],
        cwd=caller_dir,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "PORT reset lifecycle runtime passed" in result.stdout
