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
    local destination
    local failure_dir
    local log_file
    local relative_path

    if [[ ${status} -ne 0 ]]; then
        failure_dir=$(mktemp -d \
            "${TMPDIR:-/tmp}/template-refinement-failure.XXXXXX")
        while IFS= read -r -d '' log_file; do
            relative_path=${log_file#"${run_dir}/"}
            destination="${failure_dir}/${relative_path}"
            mkdir -p -- "$(dirname "${destination}")"
            cp -- "${log_file}" "${destination}"
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

has_infrastructure_diagnostic() {
    local normalized_log=$1

    grep -Eiq \
        '\{\{|\{%|%\}|syntax error|undefined (macro|type)|invalid command name|no such file or directory|file not found|(cannot|unable|failed to) (open|read) (file|include)|cannot find (file|include)|internal (compiler )?(error|failure)|compiler internal error|FLEXlm.*(error|failure)|license.*(error|fail|denied|unavailable|expired)|(error|fail|denied|unavailable|expired).*license|^[[:space:]]*(segmentation fault|bus error|aborted|illegal instruction|floating point exception)([[:space:]]*(\(core dumped\)|core dumped))?[[:space:]]*$|^[[:space:]]*core dumped[[:space:]]*$|^.*:[[:space:]]+line[[:space:]]+[0-9]+:([[:space:]]+[0-9]+)?[[:space:]]*(segmentation fault|bus error|aborted|illegal instruction|floating point exception|killed|terminated)([[:space:]]*(\(core dumped\)|core dumped))?([[:space:]].*)?$|^[[:space:]]*(killed|terminated) by signal([[:space:]]+[[:alnum:]_+-]+)?[[:space:]]*$|^[[:space:]]*(vcs|vcs1|simv|compiler)(:|[[:space:]-]).*(crash(ed)?|fatal (error|signal)|caught signal|received signal|terminated by signal)' \
        "${normalized_log}"
}

validate_width_mismatch_logs() {
    local primary_log=$1
    local console_log=$2
    local expected_error='Error-[CFCILFBI] Cannot find cell in liblist'
    local log
    local normalized
    local primary_normalized
    local unexpected

    if [[ ! -s ${primary_log} || ! -s ${console_log} ]]; then
        fail 'width mismatch compile did not produce both diagnostic logs'
        return 1
    fi
    primary_normalized=$(mktemp "${run_dir}/width-primary.XXXXXX.log")
    normalize_log "${primary_log}" "${primary_normalized}"
    if [[ $(grep -Fxc "${expected_error}" "${primary_normalized}" || true) \
            -ne 1 \
            || $(grep -Ec \
                "^[[:space:]]*Cell 'UVG_STATIC_ASSERTION_FAILED' cannot be found in liblist for binding[[:space:]]*$" \
                "${primary_normalized}" || true) -ne 1 \
            || $(grep -Ec \
                "^[[:space:]]*instance '.*u_uvg_if_width_mismatch'\\.[[:space:]]*$" \
                "${primary_normalized}" || true) -ne 1 ]]; then
        fail 'width mismatch failed without the exact intentional CFCILFBI diagnostic'
        return 1
    fi

    for log in "${primary_log}" "${console_log}"; do
        normalized=$(mktemp "${run_dir}/width-diagnostic.XXXXXX.log")
        normalize_log "${log}" "${normalized}"
        unexpected=$(grep -E 'Error-\[[^]]+\]' "${normalized}" \
            | grep -Ev \
                '^Error-\[CFCILFBI\] Cannot find cell in liblist[[:space:]]*$' \
            || true)
        if [[ -n ${unexpected} ]] \
                || has_infrastructure_diagnostic "${normalized}"; then
            fail "unexpected width mismatch diagnostic: ${log}"
            grep -E \
                'Error-\[[^]]+\]|syntax error|undefined (macro|type)|invalid command name|no such file|file not found|internal|license|segmentation fault|core dumped|bus error|aborted|illegal instruction|floating point exception|(killed|terminated) by signal' \
                "${normalized}" >&2 || true
            return 1
        fi
    done
}

validate_missing_vif_logs() {
    local primary_log=$1
    local console_log=$2
    local expected_fatal_re='^UVM_FATAL .* \[UVG_VIF_GET\] .*field=m_vif[[:space:]]*$'
    local allowed_uvm_re
    local log
    local normalized
    local primary_normalized
    local unexpected

    allowed_uvm_re="${expected_fatal_re}|^UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$|^UVM_FATAL[[:space:]]*:[[:space:]]*1[[:space:]]*$"
    if [[ ! -s ${primary_log} || ! -s ${console_log} ]]; then
        fail 'missing VIF leg did not produce both diagnostic logs'
        return 1
    fi
    primary_normalized=$(mktemp "${run_dir}/missing-vif-primary.XXXXXX.log")
    normalize_log "${primary_log}" "${primary_normalized}"
    if [[ $(grep -Ec "${expected_fatal_re}" "${primary_normalized}" || true) \
            -ne 1 \
            || $(grep -Ec \
                '^UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
                "${primary_normalized}" || true) -ne 1 \
            || $(grep -Ec \
                '^UVM_FATAL[[:space:]]*:[[:space:]]*1[[:space:]]*$' \
                "${primary_normalized}" || true) -ne 1 ]]; then
        fail 'missing VIF leg did not contain the exact expected fatal/summary'
        return 1
    fi

    for log in "${primary_log}" "${console_log}"; do
        normalized=$(mktemp "${run_dir}/missing-vif-diagnostic.XXXXXX.log")
        normalize_log "${log}" "${normalized}"
        unexpected=$(grep -E '^UVM_(FATAL|ERROR)' "${normalized}" \
            | grep -Ev "${allowed_uvm_re}" || true)
        if [[ -n ${unexpected} ]] \
                || grep -Eq 'Error-\[[^]]+\]' "${normalized}" \
                || has_infrastructure_diagnostic "${normalized}"; then
            fail "unexpected missing VIF diagnostic: ${log}"
            grep -E \
                '^UVM_(FATAL|ERROR)|Error-\[[^]]+\]|syntax error|undefined (macro|type)|invalid command name|no such file|file not found|internal|license|segmentation fault|core dumped|bus error|aborted|illegal instruction|floating point exception|(killed|terminated) by signal' \
                "${normalized}" >&2 || true
            return 1
        fi
    done
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

root_bind_env_file="${run_dir}/cfg/env.f"
if [[ $(grep -Fxc '# ../th/bind/bind_example.sv' \
        "${root_bind_env_file}" || true) -ne 1 ]]; then
    fail 'optional bind source is not disabled exactly once in cfg/env.f'
    exit 1
fi
sed -i \
    's|^# ../th/bind/bind_example.sv$|../th/bind/bind_example.sv|' \
    "${root_bind_env_file}"

cd "${run_dir}"
run_vcs_compile root_bind \
    -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    -F cfg/tb.f -top harness -o simv_root_bind

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
    -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    +define+UVG_WIDTH_MISMATCH \
    -F ../common/common_lib_pkg.f \
    -F ../env/agents/axi_agent/axi_agent.f \
    template_refinement_tb.sv -top template_refinement_tb \
    -o simv_bad_width -l compile_bad_width.log \
    >compile_bad_width_console.log 2>&1
bad_width_status=$?
set -e
case ${bad_width_status} in
    124|125|126|127|137)
        fail "width mismatch compile timeout infrastructure failure (exit ${bad_width_status})"
        exit 1
        ;;
esac
if [[ ${bad_width_status} -eq 0 ]]; then
    fail 'width mismatch unexpectedly elaborated'
    exit 1
fi
if ! validate_width_mismatch_logs \
        compile_bad_width.log compile_bad_width_console.log; then
    exit 1
fi

set +e
timeout --kill-after=10s 90s \
    ./simv_template +UVM_TESTNAME=template_refinement_test \
    +UVG_SKIP_VIF_SET -l run_missing_vif.log \
    >run_missing_vif_console.log 2>&1
missing_vif_status=$?
set -e
case ${missing_vif_status} in
    124|125|126|127|137)
        fail "missing VIF leg timeout infrastructure failure (exit ${missing_vif_status})"
        exit 1
        ;;
esac
if ! validate_missing_vif_logs \
        run_missing_vif.log run_missing_vif_console.log; then
    exit 1
fi
if grep -Fq TEMPLATE_REFINEMENT_VCS_PASS \
        run_missing_vif.log run_missing_vif_console.log; then
    fail 'missing VIF leg reached the positive PASS marker'
    exit 1
fi

fsdb_native=false
fsdb_compile_options=()
fsdb_roots=()
if [[ -n ${VERDI_HOME:-} ]]; then
    fsdb_roots+=("${VERDI_HOME}")
fi
if [[ -n ${NOVAS_HOME:-} ]]; then
    fsdb_roots+=("${NOVAS_HOME}")
fi
if verdi_bin=$(command -v verdi 2>/dev/null); then
    verdi_bin=$(realpath -- "${verdi_bin}")
    fsdb_roots+=("$(cd "$(dirname "${verdi_bin}")/.." && pwd)")
fi
for fsdb_root in "${fsdb_roots[@]}"; do
    fsdb_pli_dir="${fsdb_root}/share/PLI/VCS/LINUX64"
    if [[ -r ${fsdb_pli_dir}/novas.tab && -r ${fsdb_pli_dir}/pli.a ]]; then
        fsdb_compile_options=(
            -P "${fsdb_pli_dir}/novas.tab" "${fsdb_pli_dir}/pli.a"
        )
        fsdb_native=true
        break
    fi
done

run_vcs_compile xprop \
    -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
    -debug_access+all -lca "${fsdb_compile_options[@]}" \
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
if [[ ${fsdb_native} == false ]]; then
    mv -- wave.tcl wave.generated.tcl
    cat >wave.tcl <<'TCL'
puts "TEMPLATE_REFINEMENT_FSDB_UNAVAILABLE backend=portable"
if {[llength [info commands fsdbDumpfile]] != 0} {
    rename fsdbDumpfile {}
}
if {[llength [info commands fsdbDumpvars]] != 0} {
    rename fsdbDumpvars {}
}
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
source wave.generated.tcl
TCL
fi

rm -f -- wave.fsdb
timeout --kill-after=10s 90s \
    ./simv_xprop +UVM_TESTNAME=tc_base -ucli -i wave.tcl \
    -l run_wave.log >run_wave_console.log 2>&1
reject_bad_log run_wave.log
reject_bad_log run_wave_console.log
require_clean_tc_pass run_wave.log
if [[ ${fsdb_native} == false ]]; then
    if [[ $(grep -Fxc \
            'TEMPLATE_REFINEMENT_FSDB_UNAVAILABLE backend=portable' \
            run_wave.log || true) -ne 1 ]]; then
        fail 'portable wave leg did not report unavailable native FSDB support'
        exit 1
    fi
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
    if [[ -e wave.fsdb ]]; then
        fail 'portable wave leg unexpectedly claimed a native FSDB database'
        exit 1
    fi
else
    if grep -Fq 'TEMPLATE_REFINEMENT_FSDB_UNAVAILABLE backend=portable' \
            run_wave.log run_wave_console.log; then
        fail 'native FSDB leg unexpectedly used the portable path'
        exit 1
    fi
    if [[ ! -s wave.fsdb ]]; then
        fail 'native FSDB PLI was loaded but no wave.fsdb was produced'
        exit 1
    fi
fi

echo TEMPLATE_REFINEMENT_VCS_GATE_PASS
