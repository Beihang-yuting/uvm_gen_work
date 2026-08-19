#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 AIP_HOME" >&2
}

fail() {
    printf 'standalone agent matrix: %s\n' "$*" >&2
    return 1
}

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
if [[ ! -d $1 ]] || ! aip_home=$(realpath -- "$1" 2>/dev/null); then
    fail "AIP_HOME not found: $1"
    exit 2
fi
if [[ ! -f ${aip_home}/aip_core/aip_core_pkg.sv ]]; then
    fail "aip_core_pkg.sv missing below AIP_HOME: ${aip_home}"
    exit 2
fi

run_dir=$(mktemp -d "${TMPDIR:-/tmp}/standalone-agent-matrix.XXXXXX")
cleanup() {
    local status=$?
    if [[ ${status} -ne 0 ]]; then
        printf 'standalone agent matrix: failure artifacts preserved at %s\n' \
            "${run_dir}" >&2
        return "${status}"
    fi
    rm -rf -- "${run_dir}"
}
trap cleanup EXIT

generate_and_compile() {
    local label=$1
    local platform_type=$2
    local aip_enabled=$3
    local output_dir="${run_dir}/${label}"
    local project_dir="${output_dir}/axi_agent"
    local compile_log="compile_${label}.log"
    local console_log="compile_${label}_console.log"
    local -a aip_options=()

    mkdir -p -- "${output_dir}"
    if [[ ${aip_enabled} == true ]]; then
        (
            cd "${repo_root}"
            python3 -m uvm_gen.cli -a axi -t "${platform_type}" \
                -o "${output_dir}" --aip-core
        )
        aip_options=(-debug_access+all -lca)
    elif [[ ${aip_enabled} == false ]]; then
        (
            cd "${repo_root}"
            python3 -m uvm_gen.cli -a axi -t "${platform_type}" \
                -o "${output_dir}"
        )
    else
        fail "${label}: invalid AIP mode ${aip_enabled}"
        return 2
    fi

    if [[ ! -f ${project_dir}/common/common_lib_pkg.f \
            || ! -f ${project_dir}/test_env/cfg/tb.f ]]; then
        fail "${label}: standalone common package or root filelist missing"
        return 1
    fi
    if grep -R -n -E '\{\{|\{%|%\}|AIP_CORE_HOME|aip_activity_subscriber' \
            -- "${project_dir}" >/dev/null; then
        fail "${label}: generated tree contains unresolved or obsolete tokens"
        return 1
    fi

    (
        cd "${project_dir}"
        if [[ ${aip_enabled} == true ]]; then
            export AIP_HOME="${aip_home}"
        else
            unset AIP_HOME
        fi
        timeout --kill-after=30s 600s \
            vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
            "${aip_options[@]}" -F test_env/cfg/tb.f \
            -top axi_test_harness -o "simv_${label}" -l "${compile_log}" \
            >"${console_log}" 2>&1
        if [[ ! -x simv_${label} ]]; then
            fail "${label}: VCS did not create the simulator executable"
            exit 1
        fi
        if grep -Eiq \
                '\{\{|\{%|%\}|Error-\[[^]]+\]|syntax error|undefined (macro|type)|file not found|cannot open' \
                "${compile_log}" "${console_log}"; then
            fail "${label}: compile log contains an unexpected diagnostic"
            tail -n 100 "${compile_log}" >&2 || true
            exit 1
        fi
    )

    printf 'STANDALONE_AGENT_VCS_MATRIX_PASS label=%s\n' "${label}"
}

generate_and_compile advance_off advance false
generate_and_compile advance_on advance true
generate_and_compile port_off port false
generate_and_compile port_on port true

echo STANDALONE_AGENT_VCS_MATRIX_PASS
