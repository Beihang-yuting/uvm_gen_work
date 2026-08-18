#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 GENERATED_PORT_PROJECT PORT_RESET_LIFECYCLE_SV" >&2
    exit 2
fi

project_dir=$1
lifecycle_test=$2

if [[ ! -f ${lifecycle_test} ]]; then
    echo "lifecycle test source not found: ${lifecycle_test}" >&2
    exit 2
fi
lifecycle_test=$(realpath -- "${lifecycle_test}")

(
    cd "${project_dir}/cfg"
    rm -f -- simv compile_port_reset_lifecycle.log run_port_reset_lifecycle.log
    timeout --kill-after=30s 600s \
        vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
        -f tb.f "${lifecycle_test}" -top harness -o simv \
        -l compile_port_reset_lifecycle.log
    timeout --kill-after=10s 60s \
        ./simv +UVM_TESTNAME=tc_port_reset_lifecycle \
        -l run_port_reset_lifecycle.log
    grep -Eq '^UVM_INFO.*PORT_LIFECYCLE.*STAGE_0_MATCHED' run_port_reset_lifecycle.log
    grep -Eq '^UVM_INFO.*PORT_LIFECYCLE.*STAGE_1_MATCHED' run_port_reset_lifecycle.log
    grep -Eq '^UVM_INFO.*PORT_LIFECYCLE.*STAGE_2_MATCHED' run_port_reset_lifecycle.log
    grep -Eq '^TC PASSED\.\(warning:[0-9]+,error:0,fatal:0\)$' run_port_reset_lifecycle.log
)

echo 'PORT reset lifecycle runtime passed'
