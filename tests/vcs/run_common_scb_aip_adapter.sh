#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 GENERATED_PROJECT AIP_CORE_DIR ADAPTER_TB_SV" >&2
    exit 2
fi

project_dir=$(realpath -- "$1")
aip_core_dir=$(realpath -- "$2")
adapter_tb=$(realpath -- "$3")

if [[ ! -f ${project_dir}/common/common_lib_pkg.f ]]; then
    echo "generated common filelist not found: ${project_dir}" >&2
    exit 2
fi
if [[ ! -f ${project_dir}/common/common_scb_aip_adapter.sv ]]; then
    echo "generated AIP adapter not found: ${project_dir}" >&2
    exit 2
fi
if [[ ! -f ${aip_core_dir}/aip_core_pkg.sv ]]; then
    echo "aip_core_pkg.sv not found: ${aip_core_dir}" >&2
    exit 2
fi
if [[ ! -f ${adapter_tb} ]]; then
    echo "adapter behavioral harness not found: ${adapter_tb}" >&2
    exit 2
fi

run_dir=$(mktemp -d "${TMPDIR:-/tmp}/common-scb-aip-adapter.XXXXXX")
cleanup() {
    rm -rf -- "${run_dir}"
}
trap cleanup EXIT

mkdir -p "${run_dir}/common"
cp -R "${project_dir}/common/." "${run_dir}/common/"
cp -- "${adapter_tb}" "${run_dir}/common/common_scb_aip_adapter_tb.sv"

export AIP_CORE_HOME="${aip_core_dir}"
compile_log="${run_dir}/compile.log"
compile_console="${run_dir}/compile_console.log"
run_log="${run_dir}/run.log"
run_console="${run_dir}/run_console.log"

if ! (
    cd "${run_dir}/common"
    timeout --kill-after=30s 600s \
        vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
        -debug_access+all -lca \
        "+incdir+${AIP_CORE_HOME}" "${AIP_CORE_HOME}/aip_core_pkg.sv" \
        -F common_lib_pkg.f common_scb_aip_adapter_tb.sv \
        -top common_scb_aip_adapter_tb -o "${run_dir}/simv" \
        -l "${compile_log}"
) >"${compile_console}" 2>&1; then
    echo "common scoreboard AIP adapter compile failed" >&2
    tail -n 80 "${compile_console}" >&2 || true
    exit 1
fi

if ! timeout --kill-after=10s 60s \
    "${run_dir}/simv" -l "${run_log}" >"${run_console}" 2>&1; then
    echo "common scoreboard AIP adapter run failed" >&2
    tail -n 80 "${run_console}" >&2 || true
    exit 1
fi

if ! grep -Fxq "SCB_AIP_ADAPTER_TB_PASS" "${run_log}"; then
    echo "common scoreboard AIP adapter pass marker missing" >&2
    tail -n 80 "${run_log}" >&2 || true
    exit 1
fi
if grep -Eq '^UVM_(ERROR|FATAL)[[:space:]]' "${run_log}"; then
    echo "common scoreboard AIP adapter emitted UVM error/fatal" >&2
    tail -n 80 "${run_log}" >&2 || true
    exit 1
fi
if grep -Eq '\[ERROR\]' \
    "${compile_console}" "${compile_log}" "${run_console}" "${run_log}"; then
    echo "common scoreboard AIP adapter emitted AIP error" >&2
    tail -n 80 "${run_console}" >&2 || true
    exit 1
fi
if grep -Fq "SCB_AIP_ADAPTER_TB_FAIL" "${run_log}"; then
    echo "common scoreboard AIP adapter self-check failed" >&2
    tail -n 80 "${run_log}" >&2 || true
    exit 1
fi

echo "common scoreboard AIP adapter behavioral test passed"
