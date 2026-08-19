#!/usr/bin/env bash
set -euo pipefail

readonly scoreboard_path='uvm_test_top.m_env.m_scb.m_axi_scb'

usage() {
    cat >&2 <<EOF
Usage: $0 ADVANCE_OFF ADVANCE_ON PORT_OFF PORT_ON AIP_HOME TCL_SCRIPT
       $0 --validate-log {base|tcl} LABEL LOG
EOF
}

fail() {
    printf 'generated scoreboard matrix: %s\n' "$*" >&2
    return 1
}

normalize_log() {
    local source_log=$1
    local normalized_log=$2
    sed -E $'s/\033\\[[0-?]*[ -\\/]*[@-~]//g; s/\r$//' \
        -- "${source_log}" >"${normalized_log}"
}

validate_runtime_log() (
    local stage=$1
    local label=$2
    local log_file=$3
    local normalized
    local pass_count
    local error_zero_count
    local fatal_zero_count
    local unexpected_uvm
    local marker_count
    local clean_summary
    local native_trace_count
    local native_command_count
    local native_command
    local expected_command
    local -a native_commands=()
    local -a expected_native_commands=()

    case ${stage} in
        base|tcl) ;;
        *) fail "${label}: validation stage must be base or tcl (got ${stage})"; return 2 ;;
    esac
    if [[ ! -f ${log_file} ]]; then
        fail "${label} ${stage}: log not found: ${log_file}"
        return 2
    fi
    log_file=$(realpath -- "${log_file}")
    normalized=$(mktemp "${TMPDIR:-/tmp}/generated-scb-log.XXXXXX")
    cleanup_normalized_log() {
        rm -f -- "${normalized}"
    }
    trap cleanup_normalized_log EXIT
    normalize_log "${log_file}" "${normalized}"

    pass_count=$(grep -Ec \
        '^TC PASSED\.\(warning:[0-9]+,error:0,fatal:0\)[[:space:]]*$' \
        "${normalized}" || true)
    if [[ ${pass_count} -ne 1 ]]; then
        fail "${label} ${stage}: expected exactly one clean TC PASSED marker (got ${pass_count})"
        rm -f -- "${normalized}"
        return 1
    fi
    if grep -Fq 'TC FAILED.' "${normalized}"; then
        fail "${label} ${stage}: TC FAILED marker present"
        rm -f -- "${normalized}"
        return 1
    fi

    error_zero_count=$(grep -Ec \
        '^UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${normalized}" || true)
    fatal_zero_count=$(grep -Ec \
        '^UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        "${normalized}" || true)
    unexpected_uvm=$(grep -E '^UVM_(ERROR|FATAL)' "${normalized}" \
        | grep -Ev \
            '^UVM_ERROR[[:space:]]*:[[:space:]]*0[[:space:]]*$|^UVM_FATAL[[:space:]]*:[[:space:]]*0[[:space:]]*$' \
        || true)
    if [[ ${error_zero_count} -ne 1 || ${fatal_zero_count} -ne 1 ]]; then
        fail "${label} ${stage}: expected one zero UVM_ERROR and UVM_FATAL summary"
        rm -f -- "${normalized}"
        return 1
    fi
    if [[ -n ${unexpected_uvm} ]]; then
        fail "${label} ${stage}: UVM error/fatal diagnostic or nonzero summary present"
        printf '%s\n' "${unexpected_uvm}" >&2
        rm -f -- "${normalized}"
        return 1
    fi
    if grep -Eiq \
        '(^|[[:space:]])ERROR:|\[(ERROR|FATAL)\]|AIP[^[:cntrl:]]*(ERROR|FAIL)' \
        "${normalized}"; then
        fail "${label} ${stage}: AIP error/failure diagnostic present"
        rm -f -- "${normalized}"
        return 1
    fi
    if grep -Eiq \
        '\[AIP_TCL_BRIDGE\][[:space:]]+WARN:.*(no[[:space:]]+ack|stale|陈旧)' \
        "${normalized}"; then
        fail "${label} ${stage}: AIP bridge acknowledgement timeout/stale-result warning present"
        rm -f -- "${normalized}"
        return 1
    fi
    if grep -Eiq \
        'invalid command name|unknown command|unknown scoreboard|invalid report limit|stale (status|result)' \
        "${normalized}"; then
        fail "${label} ${stage}: invalid/unknown AIP command result present"
        rm -f -- "${normalized}"
        return 1
    fi
    if grep -Eq '\{\{|\{%|%\}' "${normalized}"; then
        fail "${label} ${stage}: unresolved Jinja token present"
        rm -f -- "${normalized}"
        return 1
    fi
    if ! grep -Eq \
            "\\[PH/TRC/STRT\\].*Phase 'uvm\\.uvm_sched\\.reset'.*Starting phase" \
            "${normalized}" \
            || ! grep -Eq \
            "\\[PH/TRC/DONE\\].*Phase 'uvm\\.uvm_sched\\.reset'.*Completed phase" \
            "${normalized}"; then
        fail "${label} ${stage}: reset-phase start/completion trace evidence missing"
        rm -f -- "${normalized}"
        return 1
    fi

    if [[ ${stage} == tcl ]]; then
        if ! grep -Fxq \
            'SCB_ADAPTER_REGISTRATION commands=scb_list,scb_status,scb_report,scb_set_limit' \
            "${normalized}"; then
            fail "${label} tcl: four-command registration evidence missing"
            rm -f -- "${normalized}"
            return 1
        fi
        marker_count=$(grep -Ec '^SCB_ADAPTER_SMOKE[[:space:]]' \
            "${normalized}" || true)
        if [[ ${marker_count} -ne 5 ]]; then
            fail "${label} tcl: expected exactly five command ledger markers (got ${marker_count})"
            rm -f -- "${normalized}"
            return 1
        fi
        expected_native_commands=(
            'scb_list' \
            "scb_status name=${scoreboard_path}" \
            "scb_report name=${scoreboard_path} limit=0" \
            "scb_set_limit name=${scoreboard_path} limit=-1" \
            'end_test idle=1us timeout=10us'
        )
        native_trace_count=$(grep -Ec \
            '^[[:space:]]*\[tcl_cmd\][[:space:]]' \
            "${normalized}" || true)
        mapfile -t native_commands < <(
            awk '
                /^[[:space:]]*\[tcl_cmd\][[:space:]]/ {
                    trace = $0
                    sub(/^[[:space:]]*\[tcl_cmd\][[:space:]]*/, "", trace)
                    if (!match(trace, /[[:space:]]@[[:space:]][^:]+:[[:space:]]/)) {
                        print "__INVALID_TCL_TRACE__"
                        next
                    }
                    print substr(trace, RSTART + RLENGTH)
                }
            ' "${normalized}"
        )
        # source is Tcl-native and must not create an AIP bridge trace.  Thus the
        # closed native set is exactly four scoreboard commands plus end_test.
        if [[ ${native_trace_count} -ne 5 \
                || ${#native_commands[@]} -ne ${native_trace_count} ]]; then
            fail "${label} tcl: expected exactly five parseable native command traces (got ${native_trace_count})"
            rm -f -- "${normalized}"
            return 1
        fi
        for expected_command in "${expected_native_commands[@]}"; do
            native_command_count=0
            for native_command in "${native_commands[@]}"; do
                if [[ ${native_command} == "${expected_command}" ]]; then
                    native_command_count=$((native_command_count + 1))
                fi
            done
            if [[ ${native_command_count} -ne 1 ]]; then
                fail "${label} tcl: exact native invocation missing/duplicated: ${expected_command}"
                rm -f -- "${normalized}"
                return 1
            fi
        done
        if [[ $(grep -Fxc \
            "SCB_ADAPTER_SMOKE command=scb_list status=0 result=${scoreboard_path}" \
            "${normalized}" || true) -ne 1 ]]; then
            fail "${label} tcl: exact scoreboard path/list result missing"
            rm -f -- "${normalized}"
            return 1
        fi
        clean_summary='status=SCB_PASS expected=0 actual=0 match=0 mismatch=0 drop=0 unexpected=0 pending_expected=0 pending_actual=0 overflow=0 peak_pending=0 suppressed=0'
        if [[ $(grep -Fxc \
                "SCB_ADAPTER_SMOKE command=scb_status status=0 result=${clean_summary}" \
                "${normalized}" || true) -ne 1 ]]; then
            fail "${label} tcl: exact clean status result missing/duplicated"
            rm -f -- "${normalized}"
            return 1
        fi
        if [[ $(grep -Fxc \
                "SCB_ADAPTER_SMOKE command=scb_report status=0 result=${clean_summary}" \
                "${normalized}" || true) -ne 1 ]]; then
            fail "${label} tcl: exact clean report result missing/duplicated"
            rm -f -- "${normalized}"
            return 1
        fi
        if [[ $(grep -Ec \
                "${scoreboard_path//./\\.}.*\\[SCB_REPORT\\].*Problem streams: total=0 shown=0 omitted=0" \
                "${normalized}" || true) -lt 1 ]]; then
            fail "${label} tcl: limit=0 report evidence missing"
            rm -f -- "${normalized}"
            return 1
        fi
        if [[ $(grep -Fxc \
            "SCB_ADAPTER_SMOKE command=scb_set_limit status=0 result=${scoreboard_path} report_limit=-1" \
            "${normalized}" || true) -ne 1 ]]; then
            fail "${label} tcl: set-limit success evidence missing"
            rm -f -- "${normalized}"
            return 1
        fi
        if [[ $(grep -Ec \
                '^SCB_ADAPTER_SMOKE command=end_test status=0 result=OK(:.*)?$' \
                "${normalized}" || true) -ne 1 ]]; then
            fail "${label} tcl: end_test success evidence missing"
            rm -f -- "${normalized}"
            return 1
        fi
    fi

    rm -f -- "${normalized}"
)

validate_compile_logs() {
    local label=$1
    local compile_log=$2
    local console_log=$3

    if [[ ! -s ${compile_log} || ! -s ${console_log} ]]; then
        fail "${label}: fresh compile log/console missing or empty"
        return 1
    fi
    if grep -Eq '\{\{|\{%|%\}' "${compile_log}" "${console_log}"; then
        fail "${label}: compile output contains unresolved Jinja tokens"
        return 1
    fi
    if grep -Fq '[ERROR]' "${compile_log}" "${console_log}" \
            || grep -Fq '[FATAL]' "${compile_log}" "${console_log}"; then
        fail "${label}: compile output contains AIP [ERROR]/[FATAL]"
        return 1
    fi
    if grep -Eiq \
        'Error-\[[^]]+\]|syntax error|undefined (macro|type|variable)|unknown (macro|type)|unresolved (type|reference)|not declared' \
        "${compile_log}" "${console_log}"; then
        fail "${label}: compile output contains unresolved type/macro/syntax diagnostic"
        return 1
    fi
}

validate_aip_off_tree() {
    local label=$1
    local project_dir=$2
    local generated_file
    local relative_file

    while IFS= read -r -d '' generated_file; do
        relative_file=${generated_file#"${project_dir}/"}
        if [[ ${relative_file,,} == *aip_* ]] \
                || grep -Eiq 'aip_' "${generated_file}"; then
            fail "${label}: AIP-off generated text contains AIP integration: ${relative_file}"
            return 1
        fi
    done < <(
        find "${project_dir}" -type f \
            \( -name '*.sv' -o -name '*.svh' -o -name '*.v' \
               -o -name '*.vh' -o -name '*.f' -o -name '*.tcl' \
               -o -name '*.cfg' -o -name '*.mk' -o -name 'Makefile' \
               -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' \) \
            -print0
    )
}

validate_project() {
    local label=$1
    local project_dir=$2
    local aip_enabled=$3
    local tb_file="${project_dir}/cfg/tb.f"
    local env_file="${project_dir}/cfg/env.f"
    local common_file="${project_dir}/common/common_lib_pkg.f"
    local aip_line
    local aip_incdir_line
    local env_line
    local package_line
    local adapter_line
    local aip_count
    local aip_incdir_count
    local aip_reference_count
    local env_count
    local common_include_count
    local package_count
    local adapter_count

    if [[ ! -f ${tb_file} || ! -f ${env_file} || ! -f ${common_file} ]]; then
        fail "${label}: generated tb/env/common filelist missing"
        return 2
    fi
    if grep -R -n -E '\{\{|\{%|%\}' -- "${project_dir}" >/dev/null; then
        fail "${label}: generated project contains unresolved Jinja tokens"
        return 1
    fi

    case ${aip_enabled} in
        false)
            validate_aip_off_tree "${label}" "${project_dir}"
            if [[ -e ${project_dir}/common/common_scb_aip_adapter.sv \
                    || -e ${project_dir}/tc/tc_tcl.sv ]]; then
                fail "${label}: AIP-off project contains AIP runtime assets"
                return 1
            fi
            if grep -Fq '$AIP_HOME' "${tb_file}" \
                    || grep -Fq 'common_scb_aip_adapter.sv' "${common_file}"; then
                fail "${label}: AIP-off filelist contains AIP tokens"
                return 1
            fi
            ;;
        true)
            if [[ ! -f ${project_dir}/common/common_scb_aip_adapter.sv \
                    || ! -f ${project_dir}/tc/tc_tcl.sv ]]; then
                fail "${label}: AIP-on project is missing adapter/Tcl test"
                return 1
            fi
            aip_incdir_count=$(grep -Fxc "${aip_filelist_sources[0]}" \
                "${tb_file}" || true)
            aip_count=$(grep -Fxc "${aip_filelist_sources[1]}" \
                "${tb_file}" || true)
            aip_reference_count=$(awk '
                /^[[:space:]]*($|#|\/\/)/ { next }
                {
                    line = tolower($0)
                    if (line ~ /aip_core/ || line ~ /\$aip_[[:alnum:]_]+/) {
                        count++
                    }
                }
                END { print count + 0 }
            ' "${tb_file}")
            env_count=$(grep -Ec \
                '^[[:space:]]*-F[[:space:]]+\./env\.f[[:space:]]*$' \
                "${tb_file}" || true)
            common_include_count=$(grep -Ec \
                '^[[:space:]]*-F[[:space:]]+\.\./common/common_lib_pkg\.f[[:space:]]*$' \
                "${env_file}" || true)
            package_count=$(grep -Fxc './common_lib_pkg.sv' \
                "${common_file}" || true)
            adapter_count=$(grep -Fxc './common_scb_aip_adapter.sv' \
                "${common_file}" || true)
            if [[ ${aip_incdir_count} -ne 1 || ${aip_count} -ne 1 \
                    || ${aip_reference_count} -ne 2 || ${env_count} -ne 1 \
                    || ${common_include_count} -ne 1 || ${package_count} -ne 1 \
                    || ${adapter_count} -ne 1 ]]; then
                fail "${label}: AIP-on filelist entries must appear exactly once (aip_incdir=${aip_incdir_count} aip_pkg=${aip_count} aip_refs=${aip_reference_count} env=${env_count} common_include=${common_include_count} common_pkg=${package_count} adapter=${adapter_count})"
                return 1
            fi
            aip_incdir_line=$(grep -nFx "${aip_filelist_sources[0]}" "${tb_file}" \
                | cut -d: -f1)
            aip_line=$(grep -nFx "${aip_filelist_sources[1]}" "${tb_file}" \
                | cut -d: -f1)
            env_line=$(grep -nE \
                '^[[:space:]]*-F[[:space:]]+\./env\.f[[:space:]]*$' \
                "${tb_file}" | cut -d: -f1)
            package_line=$(grep -nFx './common_lib_pkg.sv' "${common_file}" \
                | cut -d: -f1)
            adapter_line=$(grep -nFx './common_scb_aip_adapter.sv' "${common_file}" \
                | cut -d: -f1)
            if [[ ${aip_incdir_line} -ge ${aip_line} \
                    || ${aip_line} -ge ${env_line} \
                    || ${package_line} -ge ${adapter_line} ]]; then
                fail "${label}: AIP package/adapter compile order is invalid"
                return 1
            fi
            ;;
        *) fail "${label}: invalid AIP mode ${aip_enabled}"; return 2 ;;
    esac
}

compile_and_run_base() {
    local project_dir=$1
    local label=$2
    local aip_enabled=$3
    local cfg_dir="${project_dir}/cfg"
    local simv="simv_${label}"
    local compile_log="compile_${label}.log"
    local compile_console="compile_${label}_console.log"
    local run_log="run_${label}_base.log"
    local run_console="run_${label}_base_console.log"
    local status
    local -a aip_options=()

    if [[ ${aip_enabled} == true ]]; then
        aip_options=(-debug_access+all -lca)
    elif [[ ${aip_enabled} != false ]]; then
        fail "${label}: invalid AIP mode ${aip_enabled}"
        return 2
    fi

    (
        cd "${cfg_dir}"
        if [[ ${aip_enabled} == true ]]; then
            export AIP_HOME="${aip_home}"
        else
            unset AIP_HOME
        fi
        rm -f -- "${simv}" "${compile_log}" "${compile_console}" \
            "${run_log}" "${run_console}"
        if timeout --kill-after=30s 600s \
                vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
                "${aip_options[@]}" -f tb.f -top harness -o "${simv}" \
                -l "${compile_log}" >"${compile_console}" 2>&1; then
            :
        else
            status=$?
            printf 'generated scoreboard matrix: %s compile failed/timeout (exit %d)\n' \
                "${label}" "${status}" >&2
            tail -n 100 "${compile_console}" >&2 || true
            tail -n 100 "${compile_log}" >&2 || true
            exit "${status}"
        fi
        if [[ ! -x ${simv} ]]; then
            fail "${label}: fresh simulator executable missing"
            exit 1
        fi
        validate_compile_logs "${label}" "${compile_log}" "${compile_console}"
        printf 'GENERATED_SCB_MATRIX_PASS label=%s stage=compile\n' "${label}"

        if timeout --kill-after=10s 90s \
                "./${simv}" +UVM_TESTNAME=tc_base +UVM_PHASE_TRACE \
                -l "${run_log}" >"${run_console}" 2>&1; then
            :
        else
            status=$?
            printf 'generated scoreboard matrix: %s base failed/timeout (exit %d)\n' \
                "${label}" "${status}" >&2
            tail -n 120 "${run_console}" >&2 || true
            tail -n 120 "${run_log}" >&2 || true
            exit "${status}"
        fi
        if [[ ! -s ${run_log} || ! -s ${run_console} ]]; then
            fail "${label} base: fresh run log/console missing or empty"
            exit 1
        fi
        validate_runtime_log base "${label}" "${run_log}"
        printf 'GENERATED_SCB_MATRIX_PASS label=%s stage=base\n' "${label}"
    )
}

run_adapter_smoke() {
    local project_dir=$1
    local label=$2
    local tcl_script=$3
    local cfg_dir="${project_dir}/cfg"
    local simv="simv_${label}"
    local run_log="run_${label}_tcl.log"
    local run_console="run_${label}_tcl_console.log"
    local status

    (
        cd "${cfg_dir}"
        export AIP_HOME="${aip_home}"
        rm -f -- "${run_log}" "${run_console}"
        if timeout --kill-after=10s 90s \
                "./${simv}" +UVM_TESTNAME=tc_tcl +UVM_PHASE_TRACE \
                -ucli -i "${tcl_script}" -l "${run_log}" \
                >"${run_console}" 2>&1; then
            :
        else
            status=$?
            printf 'generated scoreboard matrix: %s Tcl failed/timeout (exit %d)\n' \
                "${label}" "${status}" >&2
            tail -n 140 "${run_console}" >&2 || true
            tail -n 140 "${run_log}" >&2 || true
            exit "${status}"
        fi
        if [[ ! -s ${run_log} || ! -s ${run_console} ]]; then
            fail "${label} tcl: fresh run log/console missing or empty"
            exit 1
        fi
        validate_runtime_log tcl "${label}" "${run_log}"
        printf 'GENERATED_SCB_MATRIX_PASS label=%s stage=tcl\n' "${label}"
    )
}

if [[ $# -eq 4 && $1 == --validate-log ]]; then
    validate_runtime_log "$2" "$3" "$4"
    exit $?
fi

if [[ $# -ne 6 ]]; then
    usage
    exit 2
fi

advance_off=$(realpath -- "$1")
advance_on=$(realpath -- "$2")
port_off=$(realpath -- "$3")
port_on=$(realpath -- "$4")
requested_aip_home=$5
if [[ ! -d ${requested_aip_home} ]] \
        || ! aip_home=$(realpath -- "${requested_aip_home}" 2>/dev/null); then
    printf 'generated scoreboard matrix: AIP_HOME does not contain a reviewed aip_core checkout: %s\n' \
        "${requested_aip_home}" >&2
    exit 2
fi
aip_core_dir="${aip_home}/aip_core"

export AIP_HOME="${aip_home}"
aip_compile_sources=(
    "+incdir+${AIP_HOME}/aip_core"
    "${AIP_HOME}/aip_core/aip_core_pkg.sv"
)
aip_filelist_sources=(
    '+incdir+$AIP_HOME/aip_core'
    '$AIP_HOME/aip_core/aip_core_pkg.sv'
)
if [[ ! -d ${aip_compile_sources[0]#+incdir+} \
        || ! -f ${aip_compile_sources[1]} \
        || ! -f "${aip_core_dir}/aip_cmd.tcl" ]]; then
    printf 'generated scoreboard matrix: AIP_HOME does not contain a reviewed aip_core checkout: %s\n' \
        "${aip_home}" >&2
    exit 2
fi
tcl_script=$(realpath -- "$6")
if [[ ! -f ${tcl_script} ]]; then
    printf 'generated scoreboard matrix: Tcl smoke script not found: %s\n' \
        "${tcl_script}" >&2
    exit 2
fi

validate_project advance_off "${advance_off}" false
validate_project advance_on "${advance_on}" true
validate_project port_off "${port_off}" false
validate_project port_on "${port_on}" true

compile_and_run_base "${advance_off}" advance_off false
compile_and_run_base "${advance_on}" advance_on true
run_adapter_smoke "${advance_on}" advance_on "${tcl_script}"
compile_and_run_base "${port_off}" port_off false
compile_and_run_base "${port_on}" port_on true
run_adapter_smoke "${port_on}" port_on "${tcl_script}"

echo 'Generated scoreboard VCS matrix passed: 4 compile, 4 base, 2 Tcl smoke legs'
