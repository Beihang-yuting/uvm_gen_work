import uvm_pkg::*;
import aip_core_pkg::*;
import common_lib_pkg::*;

class common_scb_adapter_mock_proxy extends common_scb_control_proxy;
    string m_path;
    string m_summary;
    int report_calls;
    int last_report_limit;
    int set_limit_calls;
    int last_set_limit;
    int report_limit;

    function new(string path, string summary);
        super.new({path, "_proxy"});
        m_path = path;
        m_summary = summary;
        report_calls = 0;
        last_report_limit = 32'h1357_2468;
        set_limit_calls = 0;
        last_set_limit = 32'h2468_1357;
        report_limit = 10;
    endfunction

    virtual function string scoreboard_name();
        return m_path;
    endfunction

    virtual function scb_status_e status();
        return SCB_PASS;
    endfunction

    virtual function string summary();
        return m_summary;
    endfunction

    virtual function void report(int limit=-2);
        report_calls++;
        last_report_limit = limit;
    endfunction

    virtual function bit set_report_limit(int limit, output string error);
        set_limit_calls++;
        last_set_limit = limit;
        if (limit < -1) begin
            error = $sformatf("report limit must be -1 or non-negative, got %0d",
                              limit);
            return 0;
        end
        report_limit = limit;
        error = "";
        return 1;
    endfunction
endclass

class common_scb_adapter_parse_probe extends common_scb_aip_adapter;
    static function bit parse(string text, output int value);
        return parse_int_exact(text, value);
    endfunction
endclass

module common_scb_aip_adapter_tb;
    int failures;
    common_scb_adapter_mock_proxy alpha;
    common_scb_adapter_mock_proxy zeta;

    task automatic check(input bit condition, input string message);
        if (!condition) begin
            failures++;
            $display("SCB_AIP_ADAPTER_TB_FAIL: %s", message);
        end
    endtask

    task automatic preload_stale_result();
        aip_cmd::__aip_cmd_last_status = 32'h5a5a_5a5a;
        aip_cmd::__aip_cmd_last_result = "STALE_RESULT";
    endtask

    task automatic check_error_overwrites_stale(input string label);
        check(aip_cmd::__aip_cmd_last_status == -1,
              {label, ": expected failure status"});
        check(aip_cmd::__aip_cmd_last_result != "STALE_RESULT",
              {label, ": stale result leaked"});
        check(aip_cmd::__aip_cmd_last_result != "",
              {label, ": error result is empty"});
    endtask

    task automatic check_parse(input string text,
                               input bit expected_valid,
                               input int expected_value);
        int value;
        bit valid;
        value = 32'h6b6b_6b6b;
        valid = common_scb_adapter_parse_probe::parse(text, value);
        check(valid == expected_valid,
              $sformatf("parse '%s' validity got %0d expected %0d",
                        text, valid, expected_valid));
        if (expected_valid)
            check(value == expected_value,
                  $sformatf("parse '%s' value got %0d expected %0d",
                            text, value, expected_value));
    endtask

    task automatic check_report_rejected(input string limit_text);
        int calls_before;
        calls_before = alpha.report_calls;
        preload_stale_result();
        common_scb_aip_adapter::report("alpha", limit_text);
        check_error_overwrites_stale({"report '", limit_text, "'"});
        check(alpha.report_calls == calls_before,
              {"report '", limit_text, "' reached proxy.report"});
    endtask

    task automatic check_set_limit_rejected_before_proxy(input string limit_text);
        int calls_before;
        int value_before;
        calls_before = alpha.set_limit_calls;
        value_before = alpha.report_limit;
        preload_stale_result();
        common_scb_aip_adapter::set_limit("alpha", limit_text);
        check_error_overwrites_stale({"set_limit '", limit_text, "'"});
        check(alpha.set_limit_calls == calls_before,
              {"set_limit '", limit_text, "' reached proxy"});
        check(alpha.report_limit == value_before,
              {"set_limit '", limit_text, "' changed report limit"});
    endtask

    task automatic check_report_success(input string limit_text,
                                        input int expected_limit);
        int calls_before;
        calls_before = alpha.report_calls;
        preload_stale_result();
        common_scb_aip_adapter::report("alpha", limit_text);
        check(aip_cmd::__aip_cmd_last_status == 0,
              {"report '", limit_text, "' status"});
        check(aip_cmd::__aip_cmd_last_result == "alpha summary",
              {"report '", limit_text, "' summary"});
        check(alpha.report_calls == calls_before + 1,
              {"report '", limit_text, "' call count"});
        check(alpha.last_report_limit == expected_limit,
              {"report '", limit_text, "' parsed limit"});
    endtask

    task automatic check_set_limit_success(input string limit_text,
                                           input int expected_limit);
        int calls_before;
        calls_before = alpha.set_limit_calls;
        preload_stale_result();
        common_scb_aip_adapter::set_limit("alpha", limit_text);
        check(aip_cmd::__aip_cmd_last_status == 0,
              {"set_limit '", limit_text, "' status"});
        check(aip_cmd::__aip_cmd_last_result ==
                  $sformatf("alpha report_limit=%0d", expected_limit),
              {"set_limit '", limit_text, "' result"});
        check(alpha.set_limit_calls == calls_before + 1,
              {"set_limit '", limit_text, "' call count"});
        check(alpha.last_set_limit == expected_limit,
              {"set_limit '", limit_text, "' parsed limit"});
        check(alpha.report_limit == expected_limit,
              {"set_limit '", limit_text, "' stored limit"});
    endtask

    initial begin
        string error;
        int calls_before;
        int value_before;
        aip_cmd list_command;
        aip_cmd report_command;
        aip_cmd set_limit_command;
        aip_cmd status_command;

        failures = 0;

        preload_stale_result();
        common_scb_aip_adapter::list("");
        check(aip_cmd::__aip_cmd_last_status == 0, "empty list status");
        check(aip_cmd::__aip_cmd_last_result == "", "empty list result");

        zeta = new("zeta", "zeta summary");
        alpha = new("alpha", "alpha summary");
        check(common_scb_registry::register_proxy(zeta, error),
              {"zeta registration: ", error});
        check(common_scb_registry::register_proxy(alpha, error),
              {"alpha registration: ", error});

        preload_stale_result();
        common_scb_aip_adapter::list("");
        check(aip_cmd::__aip_cmd_last_status == 0, "populated list status");
        check(aip_cmd::__aip_cmd_last_result == "alpha\nzeta",
              "populated list deterministic result");

        list_command = aip_cmd::get_handle("scb_list");
        check(list_command != null, "scb_list macro registration");
        if (list_command != null) begin
            preload_stale_result();
            list_command.args_in = "";
            list_command.cmd_exec();
            check(list_command.status == 0, "scb_list macro status");
            check(list_command.result_out == "alpha\nzeta",
                  "scb_list macro result");
            check(aip_cmd::__aip_cmd_last_status == 0,
                  "scb_list global status");
            check(aip_cmd::__aip_cmd_last_result == "alpha\nzeta",
                  "scb_list global result");
        end

        preload_stale_result();
        common_scb_aip_adapter::status("alpha");
        check(aip_cmd::__aip_cmd_last_status == 0, "known status code");
        check(aip_cmd::__aip_cmd_last_result == "alpha summary",
              "known status summary");

        status_command = aip_cmd::get_handle("scb_status");
        check(status_command != null, "scb_status macro registration");
        if (status_command != null) begin
            preload_stale_result();
            status_command.args_in = "name=alpha";
            status_command.cmd_exec();
            check(status_command.status == 0, "scb_status macro status");
            check(status_command.result_out == "alpha summary",
                  "scb_status macro result");
            check(aip_cmd::__aip_cmd_last_status == 0,
                  "scb_status global status");
            check(aip_cmd::__aip_cmd_last_result == "alpha summary",
                  "scb_status global result");
        end

        preload_stale_result();
        common_scb_aip_adapter::status("missing");
        check_error_overwrites_stale("unknown status");
        check(aip_cmd::__aip_cmd_last_result ==
                  "unknown scoreboard 'missing'",
              "unknown status diagnostic");

        preload_stale_result();
        common_scb_aip_adapter::report("missing", "0");
        check_error_overwrites_stale("unknown report");
        check(aip_cmd::__aip_cmd_last_result ==
                  "unknown scoreboard 'missing'",
              "unknown report diagnostic");

        preload_stale_result();
        common_scb_aip_adapter::set_limit("missing", "0");
        check_error_overwrites_stale("unknown set_limit");
        check(aip_cmd::__aip_cmd_last_result ==
                  "unknown scoreboard 'missing'",
              "unknown set_limit diagnostic");

        check_parse("-2147483648", 1, -2147483647 - 1);
        check_parse("2147483647", 1, 2147483647);
        check_parse("-17", 1, -17);
        check_parse("+17", 1, 17);
        check_parse("12345", 1, 12345);
        check_parse("00012", 1, 12);
        check_parse("-0", 1, 0);
        check_parse("-2147483649", 0, 0);
        check_parse("2147483648", 0, 0);
        check_parse("", 0, 0);
        check_parse("+", 0, 0);
        check_parse("-", 0, 0);
        check_parse(" 1", 0, 0);
        check_parse("1 ", 0, 0);
        check_parse("1.0", 0, 0);
        check_parse("1junk", 0, 0);
        check_parse("9999999999999999999999999999999999999999", 0, 0);

        check_report_success("-2", -2);
        check_report_success("-1", -1);
        check_report_success("0", 0);
        check_report_success("2147483647", 2147483647);

        report_command = aip_cmd::get_handle("scb_report");
        check(report_command != null, "scb_report macro registration");
        if (report_command != null) begin
            calls_before = alpha.report_calls;
            preload_stale_result();
            report_command.args_in = "name=alpha";
            report_command.cmd_exec();
            check(report_command.status == 0, "scb_report default macro status");
            check(report_command.result_out == "alpha summary",
                  "scb_report default macro result");
            check(aip_cmd::__aip_cmd_last_status == 0,
                  "scb_report default global status");
            check(aip_cmd::__aip_cmd_last_result == "alpha summary",
                  "scb_report default global result");
            check(alpha.report_calls == calls_before + 1,
                  "scb_report default call count");
            check(alpha.last_report_limit == -2,
                  "scb_report default -2 sentinel");
        end

        check_report_rejected("-3");
        check_report_rejected("-2147483648");
        check_report_rejected("-2147483649");
        check_report_rejected("2147483648");
        check_report_rejected("");
        check_report_rejected("+");
        check_report_rejected("-");
        check_report_rejected(" 1");
        check_report_rejected("1 ");
        check_report_rejected("1.0");
        check_report_rejected("1junk");
        check_report_rejected("9999999999999999999999999999999999999999");

        check_set_limit_success("-1", -1);
        check_set_limit_success("0", 0);
        check_set_limit_success("2147483647", 2147483647);

        set_limit_command = aip_cmd::get_handle("scb_set_limit");
        check(set_limit_command != null, "scb_set_limit macro registration");
        if (set_limit_command != null) begin
            calls_before = alpha.set_limit_calls;
            preload_stale_result();
            set_limit_command.args_in = "name=alpha limit=7";
            set_limit_command.cmd_exec();
            check(set_limit_command.status == 0,
                  "scb_set_limit macro status");
            check(set_limit_command.result_out == "alpha report_limit=7",
                  "scb_set_limit macro result");
            check(aip_cmd::__aip_cmd_last_status == 0,
                  "scb_set_limit global status");
            check(aip_cmd::__aip_cmd_last_result == "alpha report_limit=7",
                  "scb_set_limit global result");
            check(alpha.set_limit_calls == calls_before + 1,
                  "scb_set_limit macro call count");
            check(alpha.last_set_limit == 7,
                  "scb_set_limit macro argument");
            check(alpha.report_limit == 7,
                  "scb_set_limit macro stored limit");
        end

        calls_before = alpha.set_limit_calls;
        value_before = alpha.report_limit;
        preload_stale_result();
        common_scb_aip_adapter::set_limit("alpha", "-2");
        check_error_overwrites_stale("set_limit -2 proxy rejection");
        check(alpha.set_limit_calls == calls_before + 1,
              "set_limit -2 must reach authoritative proxy");
        check(alpha.last_set_limit == -2, "set_limit -2 proxy argument");
        check(alpha.report_limit == value_before,
              "set_limit -2 changed report limit");

        check_set_limit_rejected_before_proxy("-2147483649");
        check_set_limit_rejected_before_proxy("2147483648");
        check_set_limit_rejected_before_proxy("");
        check_set_limit_rejected_before_proxy("+");
        check_set_limit_rejected_before_proxy("-");
        check_set_limit_rejected_before_proxy(" 1");
        check_set_limit_rejected_before_proxy("1 ");
        check_set_limit_rejected_before_proxy("1.0");
        check_set_limit_rejected_before_proxy("1junk");
        check_set_limit_rejected_before_proxy(
            "9999999999999999999999999999999999999999");

        if (failures != 0)
            $fatal(1, "SCB AIP adapter behavioral failures: %0d", failures);

        $display("SCB_AIP_ADAPTER_TB_PASS");
        $finish;
    end
endmodule
