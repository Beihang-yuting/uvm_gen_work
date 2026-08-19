# Generated-project scoreboard AIP integration smoke.
# Run from any generated cfg/ directory with tc_tcl and AIP_HOME set.

source $env(AIP_HOME)/aip_core/aip_cmd.tcl

set scb_path "uvm_test_top.m_env.m_scb.m_axi_scb"
set scb_summary_pattern {^status=SCB_PASS expected=0 actual=0 match=0 mismatch=0 drop=0 unexpected=0 pending_expected=0 pending_actual=0 overflow=0 peak_pending=0 suppressed=0$}
set scb_commands {scb_list scb_status scb_report scb_set_limit}

if {![info exists ::_aip_known_cmds]} {
    error "SCB_ADAPTER_SMOKE command registration cache is unavailable"
}
foreach scb_command $scb_commands {
    if {![dict exists $::_aip_known_cmds $scb_command]} {
        error "SCB_ADAPTER_SMOKE command is not registered: $scb_command"
    }
}
puts "SCB_ADAPTER_REGISTRATION commands=scb_list,scb_status,scb_report,scb_set_limit"

set scb_list_result [scb_list]
set scb_list_status [aip_check_status]
if {$scb_list_status != 0 || $scb_list_result ne $scb_path} {
    error "SCB_ADAPTER_SMOKE scb_list failed: status=$scb_list_status result=$scb_list_result"
}
puts "SCB_ADAPTER_SMOKE command=scb_list status=$scb_list_status result=$scb_list_result"

set scb_status_result [scb_status name=uvm_test_top.m_env.m_scb.m_axi_scb]
set scb_status_status [aip_check_status]
if {$scb_status_status != 0 || ![regexp $scb_summary_pattern $scb_status_result]} {
    error "SCB_ADAPTER_SMOKE scb_status failed: status=$scb_status_status result=$scb_status_result"
}
puts "SCB_ADAPTER_SMOKE command=scb_status status=$scb_status_status result=$scb_status_result"

set scb_report_result [scb_report name=uvm_test_top.m_env.m_scb.m_axi_scb limit=0]
set scb_report_status [aip_check_status]
if {$scb_report_status != 0 || ![regexp $scb_summary_pattern $scb_report_result]} {
    error "SCB_ADAPTER_SMOKE scb_report failed: status=$scb_report_status result=$scb_report_result"
}
puts "SCB_ADAPTER_SMOKE command=scb_report status=$scb_report_status result=$scb_report_result"

set scb_limit_result [scb_set_limit name=uvm_test_top.m_env.m_scb.m_axi_scb limit=-1]
set scb_limit_status [aip_check_status]
set scb_limit_expected "$scb_path report_limit=-1"
if {$scb_limit_status != 0 || $scb_limit_result ne $scb_limit_expected} {
    error "SCB_ADAPTER_SMOKE scb_set_limit failed: status=$scb_limit_status result=$scb_limit_result"
}
puts "SCB_ADAPTER_SMOKE command=scb_set_limit status=$scb_limit_status result=$scb_limit_result"

set scb_end_result [end_test idle=1us timeout=10us]
set scb_end_status [aip_check_status]
if {$scb_end_status != 0} {
    error "SCB_ADAPTER_SMOKE end_test failed: status=$scb_end_status result=$scb_end_result"
}
puts "SCB_ADAPTER_SMOKE command=end_test status=$scb_end_status result=$scb_end_result"
run
