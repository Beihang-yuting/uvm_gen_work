#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 AIP_HOME" >&2
}

fail() {
    printf 'standalone agent matrix: %s\n' "$*" >&2
    return 1
}

normalize_log() {
    local source_log=$1
    local normalized_log=$2
    sed -E $'s/\033\\[[0-?]*[ -\\/]*[@-~]//g; s/\r$//' \
        -- "${source_log}" >"${normalized_log}"
}

require_nonempty_log() {
    local label=$1
    local stage=$2
    local kind=$3
    local log_file=$4

    if [[ ! -s ${log_file} ]]; then
        fail "${label}: ${stage} ${kind} log missing or empty: ${log_file}"
        return 1
    fi
}

has_infrastructure_diagnostic() {
    local normalized_log=$1

    grep -Eiq \
        'no such file or directory|file not found|(cannot|unable|failed to) (open|read) (file|include)|cannot find (file|include)|internal (compiler )?(error|failure)|compiler internal error|license.*(error|fail|denied|unavailable|expired)|(error|fail|denied|unavailable|expired).*license|segmentation fault|bus error|core dumped|aborted|illegal instruction|floating point exception|killed by signal|terminated by signal|timed out|timeout infrastructure failure|fatal (error|signal)' \
        "${normalized_log}"
}

reject_stage_diagnostics() {
    local label=$1
    local stage=$2
    shift 2
    local log_file
    local normalized_log

    for log_file in "$@"; do
        normalized_log="${log_file}.normalized"
        normalize_log "${log_file}" "${normalized_log}"
        if grep -Eiq \
                '\{\{|\{%|%\}|Error-\[[^]]+\]|syntax error|undefined (macro|type|variable)|unknown (macro|type)|unresolved (type|reference)|not declared' \
                "${normalized_log}" \
                || has_infrastructure_diagnostic "${normalized_log}"; then
            fail "${label}: unexpected ${stage} diagnostic: ${log_file}"
            tail -n 100 "${normalized_log}" >&2 || true
            return 1
        fi
    done
}

require_clean_runtime() {
    local label=$1
    local primary_log=$2
    local console_log=$3
    local primary_normalized="${primary_log}.normalized"
    local console_normalized="${console_log}.normalized"
    local error_zero_count
    local fatal_zero_count
    local marker_count
    local unexpected_uvm

    normalize_log "${primary_log}" "${primary_normalized}"
    normalize_log "${console_log}" "${console_normalized}"
    if ! reject_stage_diagnostics \
            "${label}" runtime "${primary_log}" "${console_log}"; then
        return 1
    fi

    unexpected_uvm=$(grep -E '^UVM_(ERROR|FATAL)' \
        "${primary_normalized}" "${console_normalized}" \
        | grep -Ev \
            'UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$|UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        || true)
    if [[ -n ${unexpected_uvm} ]]; then
        fail "${label}: unexpected runtime UVM diagnostic"
        printf '%s\n' "${unexpected_uvm}" >&2
        return 1
    fi

    error_zero_count=$(grep -Ec \
        '^UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${primary_normalized}" || true)
    fatal_zero_count=$(grep -Ec \
        '^UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${primary_normalized}" || true)
    marker_count=$(grep -Fxc STANDALONE_AGENT_TEST_PASS \
        "${primary_normalized}" || true)
    if [[ ${error_zero_count} -ne 1 || ${fatal_zero_count} -ne 1 ]]; then
        fail "${label}: runtime requires exactly one clean UVM_ERROR/UVM_FATAL summary"
        return 1
    fi
    if [[ ${marker_count} -ne 1 ]]; then
        fail "${label}: runtime PASS marker missing or duplicated"
        return 1
    fi
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
    local run_log="run_${label}.log"
    local run_console_log="run_${label}_console.log"
    local compile_status
    local run_status
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
        rm -f -- "${compile_log}" "${console_log}" "${run_log}" \
            "${run_console_log}" "simv_${label}"
        set +e
        timeout --kill-after=30s 600s \
            vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
            "${aip_options[@]}" -F test_env/cfg/tb.f \
            -top axi_test_harness -o "simv_${label}" -l "${compile_log}" \
            >"${console_log}" 2>&1
        compile_status=$?
        set -e
        if [[ ${compile_status} -ne 0 ]]; then
            case ${compile_status} in
                124|125|126|127|137)
                    fail "${label}: compile timeout/infrastructure failure (exit ${compile_status})"
                    ;;
                *)
                    fail "${label}: compile failed/infrastructure failure (exit ${compile_status})"
                    ;;
            esac
            tail -n 100 "${console_log}" >&2 || true
            exit "${compile_status}"
        fi
        require_nonempty_log \
            "${label}" compile primary "${compile_log}" || exit 1
        require_nonempty_log \
            "${label}" compile console "${console_log}" || exit 1
        reject_stage_diagnostics \
            "${label}" compile "${compile_log}" "${console_log}" || exit 1
        if [[ ! -x simv_${label} ]]; then
            fail "${label}: VCS did not create the simulator executable"
            exit 1
        fi

        set +e
        timeout --kill-after=10s 90s \
            "./simv_${label}" +UVM_TESTNAME=axi_base_test \
            -l "${run_log}" >"${run_console_log}" 2>&1
        run_status=$?
        set -e
        if [[ ${run_status} -ne 0 ]]; then
            case ${run_status} in
                124|125|126|127|137)
                    fail "${label}: runtime timeout/infrastructure failure (exit ${run_status})"
                    ;;
                *)
                    fail "${label}: runtime failed/infrastructure failure (exit ${run_status})"
                    ;;
            esac
            tail -n 100 "${run_console_log}" >&2 || true
            exit "${run_status}"
        fi
        require_nonempty_log \
            "${label}" runtime primary "${run_log}" || exit 1
        require_nonempty_log \
            "${label}" runtime console "${run_console_log}" || exit 1
        require_clean_runtime \
            "${label}" "${run_log}" "${run_console_log}" || exit 1
    )

    printf 'STANDALONE_AGENT_MATRIX_PASS %s\n' "${label}"
}

generate_and_compile advance_off advance false
generate_and_compile advance_on advance true
generate_and_compile port_off port false
generate_and_compile port_on port true

echo 'STANDALONE_AGENT_MATRIX_PASS total=4'
