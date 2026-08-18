#!/usr/bin/env bash
set -euo pipefail

validate_uvm_log() {
    local log=$1
    local normalized
    local error_zero_count
    local fatal_zero_count
    local unexpected

    if [[ ! -f ${log} ]]; then
        echo "UVM log not found: ${log}" >&2
        return 2
    fi

    normalized=$(mktemp "${TMPDIR:-/tmp}/common-scb-v2-log.XXXXXX")
    sed -E $'s/\033\\[[0-?]*[ -\\/]*[@-~]//g; s/\r$//' \
        -- "${log}" >"${normalized}"

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

    if [[ ${error_zero_count} -ne 1 || ${fatal_zero_count} -ne 1 ]]; then
        echo "expected exactly one zero UVM_ERROR and UVM_FATAL summary" >&2
        grep -E '^UVM_(ERROR|FATAL)' "${normalized}" >&2 || true
        rm -f -- "${normalized}"
        return 1
    fi
    if [[ -n ${unexpected} ]]; then
        echo "unexpected UVM error/fatal diagnostic or nonzero summary" >&2
        printf '%s\n' "${unexpected}" >&2
        rm -f -- "${normalized}"
        return 1
    fi

    rm -f -- "${normalized}"
}

if [[ $# -eq 2 && $1 == "--validate-log" ]]; then
    validate_uvm_log "$(realpath -- "$2")"
    exit $?
fi

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 GENERATED_COMMON_DIR COMMON_SCB_UNIT_TB" >&2
    echo "       $0 --validate-log UVM_LOG" >&2
    exit 2
fi

common_dir=$(realpath -- "$1")
unit_tb=$(realpath -- "$2")

if [[ ! -f ${common_dir}/common_lib_pkg.f ]]; then
    echo "generated common filelist not found: ${common_dir}" >&2
    exit 2
fi
if [[ ! -f ${unit_tb} ]]; then
    echo "scoreboard v2 unit harness not found: ${unit_tb}" >&2
    exit 2
fi

run_dir=$(mktemp -d "${TMPDIR:-/tmp}/common-scb-v2.XXXXXX")
cleanup() {
    rm -rf -- "${run_dir}"
}
trap cleanup EXIT

mkdir -p "${run_dir}/common"
cp -R "${common_dir}/." "${run_dir}/common/"
cp -- "${unit_tb}" "${run_dir}/common/common_scb_unit_tb.sv"

compile_log="${run_dir}/compile.log"
compile_console="${run_dir}/compile_console.log"
if ! (
    cd "${run_dir}/common"
    timeout --kill-after=30s 600s \
        vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps \
        -F common_lib_pkg.f common_scb_unit_tb.sv \
        -top common_scb_unit_tb -o "${run_dir}/simv" \
        -l "${compile_log}"
) >"${compile_console}" 2>&1; then
    echo "common scoreboard v2 compile failed" >&2
    tail -n 100 "${compile_console}" >&2 || true
    tail -n 100 "${compile_log}" >&2 || true
    exit 1
fi

run_mode() {
    local label=$1
    local expected_limit=$2
    local expected_shown=$3
    local expected_omitted=$4
    local expect_cfg_warn=$5
    local expected_cfg_text=$6
    shift 6

    local run_log="${run_dir}/run_${label}.log"
    local run_console="${run_dir}/run_${label}_console.log"
    if ! timeout --kill-after=10s 90s \
        "${run_dir}/simv" \
        +UVM_TESTNAME=common_scb_unit_test \
        "+SCB_EXPECT_REPORT_LIMIT=${expected_limit}" \
        "+SCB_EXPECT_CFG_WARN=${expect_cfg_warn}" \
        +SCB_EXPECT_CONFIG_WARN=1 \
        "+SCB_EXPECT_CFG_TEXT=${expected_cfg_text}" \
        "$@" -l "${run_log}" >"${run_console}" 2>&1; then
        echo "common scoreboard v2 run failed: ${label}" >&2
        tail -n 120 "${run_console}" >&2 || true
        tail -n 120 "${run_log}" >&2 || true
        exit 1
    fi

    if grep -Fq 'SCB_UNIT_FAIL' "${run_log}"; then
        echo "common scoreboard v2 self-check failure: ${label}" >&2
        grep -F 'SCB_UNIT_FAIL' "${run_log}" >&2 || true
        exit 1
    fi
    if [[ $(grep -Fxc 'SCB_UNIT_PASS' "${run_log}" || true) -ne 1 ]]; then
        echo "common scoreboard v2 exact PASS marker missing/duplicated: ${label}" >&2
        tail -n 120 "${run_log}" >&2 || true
        exit 1
    fi
    if [[ $(grep -Fxc 'SCB_CLONE_DISABLED_OWNERSHIP_PASS' \
            "${run_log}" || true) -ne 1 ]]; then
        echo "common scoreboard v2 clone-disabled ownership marker missing/duplicated: ${label}" >&2
        tail -n 120 "${run_log}" >&2 || true
        exit 1
    fi
    if ! validate_uvm_log "${run_log}"; then
        echo "common scoreboard v2 UVM log validation failed: ${label}" >&2
        tail -n 80 "${run_log}" >&2 || true
        exit 1
    fi

    local totals="Problem streams: total=15 shown=${expected_shown} omitted=${expected_omitted}"
    if [[ $(grep -Fc "${totals}" "${run_log}" || true) -ne 1 ]]; then
        echo "common scoreboard v2 report totals mismatch: ${label}" >&2
        grep -F 'Problem streams:' "${run_log}" >&2 || true
        exit 1
    fi
    if [[ $(grep -Fc '15 runtime detail messages suppressed (limit=0)' \
            "${run_log}" || true) -ne 1 ]]; then
        echo "common scoreboard v2 suppressed-detail summary mismatch: ${label}" >&2
        grep -F 'runtime detail messages suppressed' "${run_log}" >&2 || true
        exit 1
    fi

    echo "SCB_UNIT_MODE_PASS ${label} total=15 shown=${expected_shown} omitted=${expected_omitted}"
}

run_mode default 10 10 5 0 __NONE__
run_mode summary 0 0 15 0 __NONE__ +SCB_REPORT_LIMIT=0
run_mode unlimited -1 15 0 0 __NONE__ +SCB_REPORT_LIMIT=-1
run_mode finite_gt 20 15 0 0 __NONE__ +SCB_REPORT_LIMIT=20
run_mode valid_plus17 17 15 0 0 __NONE__ "+SCB_REPORT_LIMIT=+17"
run_mode valid_int32_max 2147483647 15 0 0 __NONE__ \
    +SCB_REPORT_LIMIT=2147483647
run_mode invalid_neg2 10 10 5 1 -2 +SCB_REPORT_LIMIT=-2
run_mode malformed 10 10 5 1 malformed +SCB_REPORT_LIMIT=malformed
run_mode int32_overflow 10 10 5 1 2147483648 \
    +SCB_REPORT_LIMIT=2147483648
run_mode numeric_suffix 10 10 5 1 1junk +SCB_REPORT_LIMIT=1junk
run_mode empty_value 10 10 5 1 __EMPTY__ "+SCB_REPORT_LIMIT="
run_mode sign_only_plus 10 10 5 1 + "+SCB_REPORT_LIMIT=+"
run_mode sign_only_minus 10 10 5 1 - +SCB_REPORT_LIMIT=-
run_mode very_long_decimal 10 10 5 1 \
    9999999999999999999999999999999999999999 \
    +SCB_REPORT_LIMIT=9999999999999999999999999999999999999999

echo "common scoreboard v2 semantic/report matrix passed"
