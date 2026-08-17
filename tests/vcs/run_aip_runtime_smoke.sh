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
export AIP_CORE_HOME="${aip_core_dir}"

compile_and_run_base() {
    local project_dir=$1
    local label=$2

    (
        cd "${project_dir}/cfg"
        vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
            -f tb.f -top harness -o simv -l "compile_${label}.log"
        timeout 60s ./simv +UVM_TESTNAME=tc_base -l "run_${label}_base.log"
        grep -Fq 'TC PASSED.' "run_${label}_base.log"
    )
}

run_tcl() {
    local project_dir=$1
    local label=$2

    (
        cd "${project_dir}/cfg"
        timeout 60s ./simv -ucli -i ../tc/tcl/tc_tcl_demo.tcl \
            +UVM_TESTNAME=tc_tcl -l "run_${label}_tcl.log"
        grep -Fq 'TC PASSED.' "run_${label}_tcl.log"
    )
}

compile_and_run_base "${advance_off}" advance_off
compile_and_run_base "${advance_on}" advance_on
run_tcl "${advance_on}" advance_on
compile_and_run_base "${port_off}" port_off
compile_and_run_base "${port_on}" port_on
run_tcl "${port_on}" port_on

echo 'AIP runtime matrix passed'
