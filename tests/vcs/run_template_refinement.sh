#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 GENERATED_OFF_PROJECT AIP_HOME" >&2
}

fail() {
    printf 'template refinement gate: %s\n' "$*" >&2
    return 1
}

if [[ $# -ne 2 ]]; then
    usage
    exit 2
fi

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
if [[ ! -d $1 ]] || ! project_dir=$(realpath -- "$1" 2>/dev/null); then
    printf 'template refinement gate: generated project not found: %s\n' \
        "$1" >&2
    exit 2
fi
if [[ ! -d $2 ]] || ! aip_home=$(realpath -- "$2" 2>/dev/null); then
    printf 'template refinement gate: AIP_HOME not found: %s\n' "$2" >&2
    exit 2
fi
if [[ ! -f ${aip_home}/aip_core/aip_core_pkg.sv \
        || ! -f ${aip_home}/aip_core/aip_cmd.tcl ]]; then
    printf 'template refinement gate: AIP package/Tcl missing below AIP_HOME: %s\n' \
        "${aip_home}" >&2
    exit 2
fi
if [[ ! -f ${project_dir}/cfg/tb.f ]]; then
    printf 'template refinement gate: generated cfg/tb.f missing: %s\n' \
        "${project_dir}" >&2
    exit 2
fi

run_dir=$(mktemp -d "${TMPDIR:-/tmp}/template-refinement.XXXXXX")
cleanup() {
    local status=$?
    local failure_dir
    local log_file

    if [[ ${status} -ne 0 ]]; then
        failure_dir="${TMPDIR:-/tmp}/template-refinement-failure.$$.logs"
        mkdir -p -- "${failure_dir}"
        while IFS= read -r -d '' log_file; do
            cp -- "${log_file}" \
                "${failure_dir}/$(basename "${log_file}")"
        done < <(find "${run_dir}" -type f \
            \( -name '*.log' -o -name '*.tcl' \) -print0)
        printf 'template refinement gate: failure logs preserved at %s\n' \
            "${failure_dir}" >&2
    fi
    rm -rf -- "${run_dir}"
    return "${status}"
}
trap cleanup EXIT

cp -R "${project_dir}/." "${run_dir}/"
cp -- "${repo_root}/tests/vcs/template_refinement_tb.sv" \
    "${run_dir}/cfg/"

normalize_log() {
    local source_log=$1
    local normalized_log=$2
    sed -E $'s/\033\\[[0-?]*[ -\\/]*[@-~]//g; s/\r$//' \
        -- "${source_log}" >"${normalized_log}"
}

reject_bad_log() {
    local log=$1
    local normalized

    if [[ ! -s ${log} ]]; then
        fail "missing or empty log: ${log}"
        return 1
    fi
    normalized=$(mktemp "${run_dir}/normalized.XXXXXX.log")
    normalize_log "${log}" "${normalized}"
    if grep -Eiq \
            '\{\{|\{%|%\}|Error-\[[^]]+\]|syntax error|undefined (macro|type)|invalid command name' \
            "${normalized}"; then
        printf 'template refinement gate: unexpected diagnostic: %s\n' \
            "${log}" >&2
        tail -n 100 "${normalized}" >&2 || true
        return 1
    fi
}

require_clean_uvm_summary() {
    local log=$1
    local normalized
    local error_zero_count
    local fatal_zero_count
    local unexpected

    normalized=$(mktemp "${run_dir}/uvm-summary.XXXXXX.log")
    normalize_log "${log}" "${normalized}"
    error_zero_count=$(grep -Ec \
        '^UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${normalized}" || true)
    fatal_zero_count=$(grep -Ec \
        '^UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${normalized}" || true)
    unexpected=$(grep -E '^UVM_(ERROR|FATAL)' "${normalized}" \
        | grep -Ev \
            '^UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$|^UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        || true)
    if [[ ${error_zero_count} -ne 1 || ${fatal_zero_count} -ne 1 \
            || -n ${unexpected} ]]; then
        fail "expected exactly one clean UVM_ERROR/UVM_FATAL summary: ${log}"
        grep -E '^UVM_(ERROR|FATAL)' "${normalized}" >&2 || true
        return 1
    fi
}

require_clean_tc_pass() {
    local log=$1
    local normalized
    local pass_count

    normalized=$(mktemp "${run_dir}/tc-summary.XXXXXX.log")
    normalize_log "${log}" "${normalized}"
    pass_count=$(grep -Ec \
        '^TC PASSED\.\(warning:[0-9]+,error:0,fatal:0\)[[:space:]]*$' \
        "${normalized}" || true)
    if [[ ${pass_count} -ne 1 ]] || grep -Fq 'TC FAILED.' "${normalized}"; then
        fail "expected exactly one clean TC PASSED marker: ${log}"
        grep -E '^TC (PASSED|FAILED)' "${normalized}" >&2 || true
        return 1
    fi
    require_clean_uvm_summary "${log}"
}

run_vcs_compile() {
    local label=$1
    shift
    local compile_log="compile_${label}.log"
    local console_log="compile_${label}_console.log"
    local status

    rm -f -- "${compile_log}" "${console_log}"
    if timeout --kill-after=30s 600s vcs "$@" -l "${compile_log}" \
            >"${console_log}" 2>&1; then
        :
    else
        status=$?
        printf 'template refinement gate: %s compile failed/timeout (exit %d)\n' \
            "${label}" "${status}" >&2
        tail -n 100 "${console_log}" >&2 || true
        tail -n 100 "${compile_log}" >&2 || true
        return "${status}"
    fi
    reject_bad_log "${compile_log}"
    reject_bad_log "${console_log}"
}

cd "${run_dir}/cfg"

run_vcs_compile template \
    -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    -F ../common/common_lib_pkg.f \
    -F ../env/agents/axi_agent/axi_agent.f \
    template_refinement_tb.sv -top template_refinement_tb \
    -o simv_template

timeout --kill-after=10s 90s \
    ./simv_template +UVM_TESTNAME=template_refinement_test \
    -l run_template.log >run_template_console.log 2>&1
reject_bad_log run_template.log
reject_bad_log run_template_console.log
if [[ $(grep -Fxc TEMPLATE_REFINEMENT_VCS_PASS run_template.log || true) \
        -ne 1 ]]; then
    fail 'positive semantic run PASS marker missing or duplicated'
    exit 1
fi
require_clean_uvm_summary run_template.log

set +e
timeout --kill-after=30s 600s vcs \
    -full64 -sverilog -ntb_opts uvm-1.2 \
    +define+UVG_WIDTH_MISMATCH \
    -F ../common/common_lib_pkg.f \
    -F ../env/agents/axi_agent/axi_agent.f \
    template_refinement_tb.sv -top template_refinement_tb \
    -o simv_bad_width -l compile_bad_width.log \
    >compile_bad_width_console.log 2>&1
bad_width_status=$?
set -e
if [[ ${bad_width_status} -eq 0 ]]; then
    fail 'width mismatch unexpectedly elaborated'
    exit 1
fi
if ! grep -Eq \
        'UVG_STATIC_ASSERTION_FAILED|u_uvg_if_width_mismatch' \
        compile_bad_width.log compile_bad_width_console.log; then
    fail 'width mismatch failed without the intentional assertion module'
    exit 1
fi
if grep -Eiq '\{\{|\{%|%\}|syntax error|undefined (macro|type)' \
        compile_bad_width.log compile_bad_width_console.log; then
    fail 'width mismatch compile exposed an unrelated diagnostic'
    exit 1
fi

./simv_template +UVM_TESTNAME=template_refinement_test \
    +UVG_SKIP_VIF_SET -l run_missing_vif.log \
    >run_missing_vif_console.log 2>&1 || true
if ! grep -Eq 'UVG_VIF_GET.*field=m_vif' \
        run_missing_vif.log run_missing_vif_console.log; then
    fail 'missing VIF leg did not identify UVG_VIF_GET field=m_vif'
    exit 1
fi
if grep -Fq TEMPLATE_REFINEMENT_VCS_PASS \
        run_missing_vif.log run_missing_vif_console.log; then
    fail 'missing VIF leg reached the positive PASS marker'
    exit 1
fi

run_vcs_compile xprop \
    -full64 -sverilog -ntb_opts uvm-1.2 -debug_access+all -lca \
    -f tb.f -xprop=xprop.cfg -top harness -o simv_xprop
run_vcs_compile initreg \
    -full64 -sverilog -ntb_opts uvm-1.2 \
    -f initreg.cfg -f tb.f -top harness -o simv_initreg
run_vcs_compile coverage \
    -full64 -sverilog -ntb_opts uvm-1.2 \
    -f tb.f -cm line+cond+fsm+tgl+branch -cm_hier coverage.cfg \
    -top harness -o simv_cov

# Execute the generated wave.tcl entry point.  Native FSDB commands are used
# when available.  A host without Verdi/FSDB support takes an explicit,
# observable compatibility path which validates both calls without claiming
# that an FSDB database was produced.
mv -- wave.tcl wave.generated.tcl
cat >wave.tcl <<'TCL'
if {[llength [info commands fsdbDumpfile]] == 0 ||
    [llength [info commands fsdbDumpvars]] == 0} {
    puts "TEMPLATE_REFINEMENT_FSDB_UNAVAILABLE backend=portable"
    proc fsdbDumpfile {file_name} {
        if {$file_name ne "wave.fsdb"} {
            error "unexpected FSDB output: $file_name"
        }
        puts "TEMPLATE_REFINEMENT_WAVE_CALL fsdbDumpfile wave.fsdb"
    }
    proc fsdbDumpvars {depth scope} {
        if {$depth != 0 || $scope ne "harness"} {
            error "unexpected FSDB scope: depth=$depth scope=$scope"
        }
        puts "TEMPLATE_REFINEMENT_WAVE_CALL fsdbDumpvars 0 harness"
    }
}
source wave.generated.tcl
TCL

timeout --kill-after=10s 90s \
    ./simv_xprop +UVM_TESTNAME=tc_base -ucli -i wave.tcl \
    -l run_wave.log >run_wave_console.log 2>&1
reject_bad_log run_wave.log
reject_bad_log run_wave_console.log
require_clean_tc_pass run_wave.log
if grep -Fq 'TEMPLATE_REFINEMENT_FSDB_UNAVAILABLE backend=portable' \
        run_wave.log run_wave_console.log; then
    if [[ $(grep -Fxc \
            'TEMPLATE_REFINEMENT_WAVE_CALL fsdbDumpfile wave.fsdb' \
            run_wave.log || true) \
            -ne 1 \
            || $(grep -Fxc \
            'TEMPLATE_REFINEMENT_WAVE_CALL fsdbDumpvars 0 harness' \
            run_wave.log || true) \
            -ne 1 ]]; then
        fail 'portable wave leg did not execute both generated FSDB calls once'
        exit 1
    fi
elif [[ ! -s wave.fsdb ]]; then
    fail 'native FSDB commands were present but no wave.fsdb was produced'
    exit 1
fi

echo TEMPLATE_REFINEMENT_VCS_GATE_PASS
