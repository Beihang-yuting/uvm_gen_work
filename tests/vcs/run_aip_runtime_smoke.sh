#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat >&2 <<EOF
Usage: $0 ADVANCE_OFF ADVANCE_ON PORT_OFF PORT_ON AIP_CORE_DIR
       $0 --validate-log {base|tcl} LABEL LOG
       $0 --validate-compile LABEL COMPILE_LOG CONSOLE_LOG
EOF
}

run_labeled() {
    local stage=$1
    local label=$2
    local status
    shift 2

    if "$@"; then
        return 0
    else
        status=$?
        printf 'AIP runtime %s failed for %s (exit %d)\n' \
            "${stage}" "${label}" "${status}" >&2
        return "${status}"
    fi
}

verify_success_log() (
    local stage=$1
    local label=$2
    local log_file=$3
    local normalized
    local pass_count
    local pass_marker_count
    local error_zero_count
    local fatal_zero_count
    local unexpected_uvm
    local progress_pattern='@[[:space:]]*([1-9][0-9]*(\.[0-9]+)?|0\.[0-9]*[1-9][0-9]*)ns'

    case ${stage} in
        base|tcl) ;;
        *)
            printf 'AIP runtime validation stage must be base or tcl (got %s)\n' \
                "${stage}" >&2
            return 2
            ;;
    esac
    if [[ ! -f ${log_file} ]]; then
        printf 'AIP runtime %s for %s: log not found: %s\n' \
            "${stage}" "${label}" "${log_file}" >&2
        return 2
    fi

    normalized=$(mktemp "${TMPDIR:-/tmp}/aip-runtime-log.XXXXXX")
    cleanup_normalized_log() {
        rm -f -- "${normalized}"
    }
    trap cleanup_normalized_log EXIT
    sed -E $'s/\033\\[[0-?]*[ -\\/]*[@-~]//g; s/\r$//' \
        -- "${log_file}" >"${normalized}"

    pass_count=$(grep -Ec \
        '^TC PASSED\.\(warning:[0-9]+,error:0,fatal:0\)[[:space:]]*$' \
        "${normalized}" || true)
    pass_marker_count=$(grep -Ec '^TC PASSED\.' "${normalized}" || true)
    if [[ ${pass_count} -ne 1 || ${pass_marker_count} -ne 1 ]]; then
        printf 'AIP runtime %s for %s: expected exactly one TC PASSED marker and it must be clean (clean=%s total=%s)\n' \
            "${stage}" "${label}" "${pass_count}" "${pass_marker_count}" >&2
        return 1
    fi
    if grep -Fq 'TC FAILED' "${normalized}"; then
        printf 'AIP runtime %s for %s: TC FAILED marker present\n' \
            "${stage}" "${label}" >&2
        return 1
    fi

    error_zero_count=$(grep -Ec \
        '^[[:space:]]*UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${normalized}" || true)
    fatal_zero_count=$(grep -Ec \
        '^[[:space:]]*UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${normalized}" || true)
    unexpected_uvm=$(grep -E \
        '^[[:space:]]*UVM_(ERROR|FATAL)([[:space:]:@]|$)' \
        "${normalized}" \
        | grep -Ev \
            '^[[:space:]]*UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$|^[[:space:]]*UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        || true)
    if [[ ${error_zero_count} -ne 1 || ${fatal_zero_count} -ne 1 ]]; then
        printf 'AIP runtime %s for %s: expected exactly one zero UVM_ERROR and UVM_FATAL summary\n' \
            "${stage}" "${label}" >&2
        return 1
    fi
    if [[ -n ${unexpected_uvm} ]]; then
        printf 'AIP runtime %s for %s: UVM error/fatal diagnostic or nonzero summary present\n' \
            "${stage}" "${label}" >&2
        printf '%s\n' "${unexpected_uvm}" >&2
        return 1
    fi
    if grep -Eiq \
        '(^|[[:space:]])(ERROR|FATAL):|Error-\[[^]]+\]|\[(ERROR|FATAL)\]|AIP[^[:cntrl:]]*(ERROR|FATAL|FAIL(ED|URE)?)' \
        "${normalized}"; then
        printf 'AIP runtime %s for %s: AIP/general error or failure diagnostic present\n' \
            "${stage}" "${label}" >&2
        return 1
    fi
    if grep -Eiq \
        '\[AIP_TCL_BRIDGE\][[:space:]]+WARN:.*(no[[:space:]-]*ack|stale|陈旧)' \
        "${normalized}"; then
        printf 'AIP runtime %s for %s: AIP bridge acknowledgement timeout/stale-result warning present\n' \
            "${stage}" "${label}" >&2
        return 1
    fi
    if grep -Eq '\{\{|\}\}|\{%|%\}|\{#|#\}' "${normalized}"; then
        printf 'AIP runtime %s for %s: unresolved Jinja token present\n' \
            "${stage}" "${label}" >&2
        return 1
    fi
    if ! grep -Eq "${progress_pattern}" "${normalized}"; then
        printf 'AIP runtime %s for %s: nonzero timestamp missing from %s\n' \
            "${stage}" "${label}" "${log_file}" >&2
        return 1
    fi
)

verify_compile_logs() (
    local label=$1
    local compile_log=$2
    local console_log=$3
    local normalized_compile=""
    local normalized_console=""

    if [[ ! -s ${compile_log} || ! -s ${console_log} ]]; then
        printf 'AIP runtime compile for %s: fresh compile log/console missing or empty\n' \
            "${label}" >&2
        return 1
    fi

    cleanup_normalized_compile_logs() {
        if [[ -n ${normalized_compile} ]]; then
            rm -f -- "${normalized_compile}"
        fi
        if [[ -n ${normalized_console} ]]; then
            rm -f -- "${normalized_console}"
        fi
    }
    trap cleanup_normalized_compile_logs EXIT
    normalized_compile=$(mktemp "${TMPDIR:-/tmp}/aip-compile-log.XXXXXX")
    normalized_console=$(mktemp "${TMPDIR:-/tmp}/aip-compile-log.XXXXXX")
    sed -E $'s/\033\\[[0-?]*[ -\\/]*[@-~]//g; s/\r$//' \
        -- "${compile_log}" >"${normalized_compile}"
    sed -E $'s/\033\\[[0-?]*[ -\\/]*[@-~]//g; s/\r$//' \
        -- "${console_log}" >"${normalized_console}"

    if grep -Eq '\{\{|\}\}|\{%|%\}|\{#|#\}' \
            "${normalized_compile}" "${normalized_console}"; then
        printf 'AIP runtime compile for %s: unresolved Jinja token present\n' \
            "${label}" >&2
        return 1
    fi
    if grep -Eiq \
            '^[[:space:]]*(ERROR|FATAL):|^[[:space:]]*UVM_(ERROR|FATAL)([[:space:]:@]|$)' \
            "${normalized_compile}" "${normalized_console}"; then
        printf 'AIP runtime compile for %s: generic error/fatal or UVM diagnostic present\n' \
            "${label}" >&2
        return 1
    fi
    if grep -Eq '\[(ERROR|FATAL)\]' \
            "${normalized_compile}" "${normalized_console}"; then
        printf 'AIP runtime compile for %s: AIP [ERROR]/[FATAL] diagnostic present\n' \
            "${label}" >&2
        return 1
    fi
    if grep -Eiq \
        'Error-\[[^]]+\]|syntax[[:space:]]+error|undefined[[:space:]]+(macro|type|variable|identifier|symbol|package|class)|unknown[[:space:]]+(macro|type|package|class)|unresolved[[:space:]]+(type|reference|name|symbol|package|hierarchical)|cross-module[[:space:]]+reference[[:space:]]+resolution[[:space:]]+error|identifier[^[:cntrl:]]*not[[:space:]]+declared|not[[:space:]]+declared' \
        "${normalized_compile}" "${normalized_console}"; then
        printf 'AIP runtime compile for %s: VCS syntax/type/unresolved diagnostic present\n' \
            "${label}" >&2
        return 1
    fi
)

if (($# > 0)); then
    case $1 in
        --validate-log)
            if [[ $# -ne 4 ]]; then
                usage
                exit 2
            fi
            verify_success_log "$2" "$3" "$4"
            exit $?
            ;;
        --validate-compile)
            if [[ $# -ne 4 ]]; then
                usage
                exit 2
            fi
            verify_compile_logs "$2" "$3" "$4"
            exit $?
            ;;
        -*)
            usage
            exit 2
            ;;
    esac
fi

if [[ $# -ne 5 ]]; then
    usage
    exit 2
fi

advance_off=$1
advance_on=$2
port_off=$3
port_on=$4
aip_core_dir=$5

if [[ ${aip_core_dir} =~ [[:space:]] ]]; then
    echo 'AIP_CORE_DIR must not contain whitespace' >&2
    exit 2
fi

export AIP_CORE_HOME="${aip_core_dir}"

compile_and_run_base() {
    local project_dir=$1
    local label=$2
    local aip_core_enabled=$3
    local compile_log="compile_${label}.log"
    local compile_console="compile_${label}_console.log"
    local run_log="run_${label}_base.log"
    local status
    local -a aip_compile_options=()

    case ${aip_core_enabled} in
        true)
            aip_compile_options=(-debug_access+all -lca)
            ;;
        false) ;;
        *)
            printf 'AIP runtime %s: AIP_ENABLED must be true or false (got %s)\n' \
                "${label}" "${aip_core_enabled}" >&2
            return 2
            ;;
    esac

    (
        cd "${project_dir}/cfg"
        rm -f -- simv "${compile_log}" "${compile_console}"
        if run_labeled compile "${label}" \
                timeout --kill-after=30s 600s \
                vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
                "${aip_compile_options[@]}" \
                -f tb.f -top harness -o simv -l "${compile_log}" \
                >"${compile_console}" 2>&1; then
            :
        else
            status=$?
            tail -n 100 "${compile_console}" >&2 || true
            tail -n 100 "${compile_log}" >&2 || true
            return "${status}"
        fi
        if [[ ! -x simv ]]; then
            printf 'AIP runtime compile for %s: fresh executable missing or not executable\n' \
                "${label}" >&2
            return 1
        fi
        verify_compile_logs "${label}" "${compile_log}" "${compile_console}"

        rm -f -- "${run_log}"
        run_labeled base "${label}" \
            timeout --kill-after=10s 60s \
            ./simv +UVM_TESTNAME=tc_base -l "${run_log}"
        verify_success_log base "${label}" "${run_log}"
    )
}

run_tcl() {
    local project_dir=$1
    local label=$2
    local run_log="run_${label}_tcl.log"

    (
        cd "${project_dir}/cfg"
        rm -f -- "${run_log}"
        run_labeled tcl "${label}" \
            timeout --kill-after=10s 60s \
            ./simv -ucli -i ../tc/tcl/tc_tcl_demo.tcl \
            +UVM_TESTNAME=tc_tcl -l "${run_log}"
        verify_success_log tcl "${label}" "${run_log}"
    )
}

compile_and_run_base "${advance_off}" advance_off false
compile_and_run_base "${advance_on}" advance_on true
run_tcl "${advance_on}" advance_on
compile_and_run_base "${port_off}" port_off false
compile_and_run_base "${port_on}" port_on true
run_tcl "${port_on}" port_on

echo 'AIP runtime matrix passed'
