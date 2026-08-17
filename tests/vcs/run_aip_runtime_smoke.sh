#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
    echo "Usage: $0 ADVANCE_OFF ADVANCE_ON PORT_OFF PORT_ON AIP_CORE_DIR" >&2
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

verify_success_log() {
    local stage=$1
    local label=$2
    local log_file=$3
    local pass_pattern='^TC PASSED\.\(warning:[0-9]+,error:0,fatal:0\)$'
    local progress_pattern='@[[:space:]]*([1-9][0-9]*(\.[0-9]+)?|0\.[0-9]*[1-9][0-9]*)ns'

    if ! grep -Eq "${pass_pattern}" "${log_file}"; then
        printf 'AIP runtime %s for %s: pass marker missing from %s\n' \
            "${stage}" "${label}" "${log_file}" >&2
        return 1
    fi

    if ! grep -Eq "${progress_pattern}" "${log_file}"; then
        printf 'AIP runtime %s for %s: nonzero timestamp missing from %s\n' \
            "${stage}" "${label}" "${log_file}" >&2
        return 1
    fi
}

compile_and_run_base() {
    local project_dir=$1
    local label=$2
    local compile_log="compile_${label}.log"
    local run_log="run_${label}_base.log"

    (
        cd "${project_dir}/cfg"
        rm -f -- simv "${compile_log}"
        run_labeled compile "${label}" \
            timeout --kill-after=30s 600s \
            vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
            -f tb.f -top harness -o simv -l "${compile_log}"

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

compile_and_run_base "${advance_off}" advance_off
compile_and_run_base "${advance_on}" advance_on
run_tcl "${advance_on}" advance_on
compile_and_run_base "${port_off}" port_off
compile_and_run_base "${port_on}" port_on
run_tcl "${port_on}" port_on

echo 'AIP runtime matrix passed'
