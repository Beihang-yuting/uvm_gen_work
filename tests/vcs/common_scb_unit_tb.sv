`timescale 1ns/1ps

module common_scb_unit_tb;
    import uvm_pkg::*;
    import common_lib_pkg::*;
    `include "uvm_macros.svh"

    class scb_item extends uvm_sequence_item;
        int value;

        `uvm_object_utils_begin(scb_item)
            `uvm_field_int(value, UVM_ALL_ON)
        `uvm_object_utils_end

        function new(string name="scb_item");
            super.new(name);
        endfunction

        function bit self_define_do_compare(scb_item actual,
                                            output string diff,
                                            input int kind=-1);
            if ((actual != null) && (value == actual.value)) begin
                diff = "";
                return 1;
            end
            diff = $sformatf("expected=%0d actual=%0d kind=%0d",
                             value, (actual == null) ? 'x : actual.value,
                             kind);
            return 0;
        endfunction
    endclass

    class wrong_clone_item extends scb_item;
        function new(string name="wrong_clone_item");
            super.new(name);
        endfunction

        virtual function uvm_object clone();
            uvm_sequence_item wrong_type;
            wrong_type = new("wrong_clone_type");
            return wrong_type;
        endfunction
    endclass

    typedef common_scb_result#(scb_item) scb_result_t;

    class result_sink extends uvm_subscriber#(scb_result_t);
        `uvm_component_utils(result_sink)
        scb_result_t results[$];

        function new(string name="result_sink", uvm_component parent=null);
            super.new(name, parent);
        endfunction

        virtual function void write(scb_result_t t);
            results.push_back(t);
        endfunction

        function int id_count(longint unsigned stream_id);
            int count;
            count = 0;
            foreach (results[i])
                if (results[i].stream_id == stream_id) count++;
            return count;
        endfunction
    endclass

    class scb_probe extends common_uvm_scb#(scb_item);
        `uvm_component_utils(scb_probe)

        function new(string name="scb_probe", uvm_component parent=null);
            super.new(name, parent);
        endfunction

        function int stream_count();
            return m_streams.num();
        endfunction

        function int problem_row_count();
            int count;
            common_scb_problem_row row;
            count = 0;
            foreach (m_streams[id]) begin
                row = make_row(m_streams[id]);
                if (row.issue_count != 0) count++;
            end
            return count;
        endfunction

        function void collect_sorted_rows(
            output common_scb_problem_row rows[$]
        );
            common_scb_problem_row row;
            int insert_at;
            rows.delete();
            foreach (m_streams[id]) begin
                row = make_row(m_streams[id]);
                if (row.issue_count != 0) begin
                    insert_at = rows.size();
                    foreach (rows[i]) begin
                        if (row_before(row, rows[i])) begin
                            insert_at = i;
                            break;
                        end
                    end
                    rows.insert(insert_at, row);
                end
            end
        endfunction

        function longint unsigned expected_inputs();
            return m_expected_inputs;
        endfunction

        function longint unsigned actual_inputs();
            return m_actual_inputs;
        endfunction

        function longint unsigned match_count();
            return m_matches;
        endfunction

        function longint unsigned mismatch_count();
            return m_mismatches;
        endfunction

        function longint unsigned drop_count();
            return m_allowed_drops;
        endfunction

        function longint unsigned unexpected_count();
            return m_unexpected_actuals;
        endfunction

        function longint unsigned overflow_count();
            return m_overflows;
        endfunction

        function longint unsigned diagnostic_count();
            return m_diagnostic_warnings;
        endfunction

        function longint unsigned current_pending();
            return m_current_pending;
        endfunction

        function longint unsigned peak_pending();
            return m_peak_pending;
        endfunction

        function longint unsigned detail_emitted();
            return m_detail_emitted;
        endfunction

        function longint unsigned suppressed_details();
            return m_suppressed_details;
        endfunction

        function void probe_finalize_pending();
            finalize_pending();
        endfunction
    endclass

    class scb_report_event;
        string client;
        string id;
        string message;
        uvm_severity original_severity;
    endclass

    class scb_report_expectation;
        string client;
        string id;
        string required_message;
        uvm_severity original_severity;
        int remaining;

        function new(string client,
                     string id,
                     uvm_severity original_severity,
                     int remaining,
                     string required_message="");
            this.client = client;
            this.id = id;
            this.original_severity = original_severity;
            this.remaining = remaining;
            this.required_message = required_message;
        endfunction
    endclass

    class scb_report_catcher extends uvm_report_catcher;
        `uvm_object_utils(scb_report_catcher)
        scb_report_event events[$];
        scb_report_expectation expectations[$];
        int unexpected_guarded_events;

        function new(string name="scb_report_catcher");
            super.new(name);
            unexpected_guarded_events = 0;
        endfunction

        function void expect_report(string client,
                                    string id,
                                    uvm_severity original_severity,
                                    int count=1,
                                    string required_message="");
            scb_report_expectation expectation;
            expectation = new(client, id, original_severity, count,
                              required_message);
            expectations.push_back(expectation);
        endfunction

        function bit contains(string text, string needle);
            int last;
            if (needle.len() == 0) return 1;
            last = text.len() - needle.len();
            for (int i=0; i<=last; i++)
                if (text.substr(i, i+needle.len()-1) == needle) return 1;
            return 0;
        endfunction

        function bit is_guarded_id(string id);
            return (id == "SCB_MISMATCH")
                || (id == "SCB_UNEXPECTED_ACTUAL")
                || (id == "SCB_PENDING_OVERFLOW")
                || (id == "SCB_NULL_INPUT")
                || (id == "SCB_CLONE_FAILED")
                || (id == "SCB_FINAL")
                || (id == "SCB_SUPPRESSED")
                || (id == "SCB_CFG")
                || (id == "SCB_ACTUAL_FIRST")
                || (id == "SCB_REPORT_LIMIT");
        endfunction

        function bit all_expectations_consumed();
            foreach (expectations[i])
                if (expectations[i].remaining != 0) return 0;
            return 1;
        endfunction

        function string unconsumed_expectations();
            string result;
            result = "";
            foreach (expectations[i]) begin
                if (expectations[i].remaining != 0)
                    result = {result, $sformatf(
                        "%s%s/%s severity=%s remaining=%0d",
                        (result == "") ? "" : "; ",
                        expectations[i].client, expectations[i].id,
                        expectations[i].original_severity.name(),
                        expectations[i].remaining)};
            end
            return result;
        endfunction

        virtual function action_e catch();
            scb_report_event report_event;
            uvm_report_object client_object;
            uvm_severity original_severity;
            string client;
            string report_id;
            string message;
            int matched_expectation;
            report_event = new();
            client_object = get_client();
            client = (client_object == null)
                   ? "" : client_object.get_full_name();
            report_id = get_id();
            message = get_message();
            original_severity = get_severity();
            report_event.client = client;
            report_event.id = report_id;
            report_event.message = message;
            report_event.original_severity = original_severity;
            events.push_back(report_event);

            if (is_guarded_id(report_id)) begin
                matched_expectation = -1;
                foreach (expectations[i]) begin
                    if ((expectations[i].remaining > 0)
                        && (expectations[i].client == client)
                        && (expectations[i].id == report_id)
                        && (expectations[i].original_severity
                            == original_severity)
                        && contains(message,
                                    expectations[i].required_message)) begin
                        matched_expectation = i;
                        break;
                    end
                end
                if (matched_expectation < 0)
                    unexpected_guarded_events++;
                else begin
                    expectations[matched_expectation].remaining--;
                    if (original_severity == UVM_ERROR)
                        set_severity(UVM_INFO);
                end
            end
            return THROW;
        endfunction

        function int count(string client, string id);
            int result;
            result = 0;
            foreach (events[i])
                if ((events[i].client == client) && (events[i].id == id))
                    result++;
            return result;
        endfunction

        function int count_id(string id);
            int result;
            result = 0;
            foreach (events[i])
                if (events[i].id == id) result++;
            return result;
        endfunction

        function string message_at(string client, string id, int ordinal);
            int found;
            found = 0;
            foreach (events[i]) begin
                if ((events[i].client == client) && (events[i].id == id)) begin
                    if (found == ordinal) return events[i].message;
                    found++;
                end
            end
            return "";
        endfunction
    endclass

    class common_scb_unit_test extends uvm_test;
        `uvm_component_utils(common_scb_unit_test)

        scb_probe m_exact_pass;
        scb_probe m_exact_fail;
        scb_probe m_lossy;
        scb_probe m_unordered;
        scb_probe m_overflow;
        scb_probe m_many;
        scb_probe m_topn;
        scb_probe m_reset;
        scb_probe m_reset_counters;
        scb_probe m_clone_error;
        scb_probe m_suppression;
        scb_probe m_suppression_zero;
        scb_probe m_report_disabled;
        scb_probe m_check_once;
        scb_probe m_cfg_seven;
        scb_probe m_cfg_invalid;

        result_sink m_exact_results;
        result_sink m_topn_results;
        result_sink m_check_results;
        scb_report_catcher m_catcher;
        int m_failures;

        function new(string name="common_scb_unit_test",
                     uvm_component parent=null);
            super.new(name, parent);
        endfunction

        function scb_item item(int value);
            scb_item result;
            result = new($sformatf("item_%0d", value));
            result.value = value;
            return result;
        endfunction

        function void unit_check(bit condition, string message);
            if (!condition) begin
                m_failures++;
                $display("SCB_UNIT_FAIL: %s", message);
            end
        endfunction

        function int find_text(string text, string needle, int start=0);
            int last;
            if (needle.len() == 0) return start;
            if (start < 0) start = 0;
            last = text.len() - needle.len();
            for (int i=start; i<=last; i++)
                if (text.substr(i, i+needle.len()-1) == needle) return i;
            return -1;
        endfunction

        function int count_text(string text, string needle);
            int count;
            int position;
            count = 0;
            position = find_text(text, needle, 0);
            while (position >= 0) begin
                count++;
                position = find_text(text, needle, position + needle.len());
            end
            return count;
        endfunction

        function void check_contains(string text, string needle,
                                     string message);
            unit_check(find_text(text, needle) >= 0, message);
        endfunction

        function void check_stream_order(string table, string tokens[$],
                                         string message);
            int cursor;
            int position;
            cursor = 0;
            foreach (tokens[i]) begin
                position = find_text(table, tokens[i], cursor);
                unit_check(position >= cursor,
                           $sformatf("%s token[%0d]=%s",
                                     message, i, tokens[i]));
                if (position >= cursor) cursor = position + tokens[i].len();
            end
        endfunction

        function void expect_final(string client,
                                   uvm_severity severity,
                                   string status,
                                   int count=1);
            m_catcher.expect_report(client, "SCB_FINAL", severity, count,
                                    {"status=", status});
        endfunction

        function void expect_cfg_warning(string client,
                                         int expected_cfg_warn,
                                         string expected_cfg_text);
            if (expected_cfg_warn != 0)
                m_catcher.expect_report(
                    client, "SCB_CFG", UVM_WARNING, 1,
                    $sformatf(
                        "invalid SCB_REPORT_LIMIT='%s'; ignoring override",
                        expected_cfg_text));
        endfunction

        function void register_report_expectations(int expected_cfg_warn,
                                                    string expected_cfg_text);
            string actual_first;
            actual_first = "actual input arrived before expected";

            m_catcher.expect_report("uvm_test_top.m_exact_fail",
                "SCB_MISMATCH", UVM_ERROR, 1, "expected=1 actual=2");
            m_catcher.expect_report("uvm_test_top.m_overflow",
                "SCB_PENDING_OVERFLOW", UVM_ERROR, 1,
                "expected pending depth=1 limit=1");
            m_catcher.expect_report("uvm_test_top.m_overflow",
                "SCB_MISMATCH", UVM_ERROR, 1,
                "expected transaction has no actual match");
            m_catcher.expect_report("uvm_test_top.m_clone_error",
                "SCB_NULL_INPUT", UVM_ERROR, 1, "expected input is null");
            m_catcher.expect_report("uvm_test_top.m_clone_error",
                "SCB_CLONE_FAILED", UVM_ERROR, 1,
                "expected input clone failed typed cast");
            m_catcher.expect_report("uvm_test_top.m_suppression",
                "SCB_MISMATCH", UVM_ERROR, 2, "expected=");
            m_catcher.expect_report("uvm_test_top.m_report_disabled",
                "SCB_MISMATCH", UVM_ERROR, 1, "expected=1 actual=2");
            m_catcher.expect_report("uvm_test_top.m_reset_counters",
                "SCB_MISMATCH", UVM_ERROR, 1, "expected=2 actual=3");

            m_catcher.expect_report("uvm_test_top.m_topn",
                "SCB_ACTUAL_FIRST", UVM_WARNING, 1, actual_first);
            m_catcher.expect_report("uvm_test_top.m_reset",
                "SCB_ACTUAL_FIRST", UVM_WARNING, 1, actual_first);
            m_catcher.expect_report("uvm_test_top.m_reset_counters",
                "SCB_ACTUAL_FIRST", UVM_WARNING, 1, actual_first);
            m_catcher.expect_report("uvm_test_top.m_topn",
                "SCB_REPORT_LIMIT", UVM_WARNING, 1,
                "invalid report limit=-3; using configured limit=2");

            m_catcher.expect_report("uvm_test_top.m_many",
                "SCB_SUPPRESSED", UVM_WARNING, 1,
                "15 runtime detail messages suppressed (limit=0)");
            m_catcher.expect_report("uvm_test_top.m_topn",
                "SCB_SUPPRESSED", UVM_WARNING, 1,
                "9 runtime detail messages suppressed (limit=0)");
            m_catcher.expect_report("uvm_test_top.m_suppression",
                "SCB_SUPPRESSED", UVM_WARNING, 1,
                "3 runtime detail messages suppressed (limit=2)");
            m_catcher.expect_report("uvm_test_top.m_suppression_zero",
                "SCB_SUPPRESSED", UVM_WARNING, 1,
                "4 runtime detail messages suppressed (limit=0)");
            m_catcher.expect_report("uvm_test_top.m_check_once",
                "SCB_SUPPRESSED", UVM_WARNING, 1,
                "1 runtime detail messages suppressed (limit=0)");
            m_catcher.expect_report("uvm_test_top.m_cfg_seven",
                "SCB_SUPPRESSED", UVM_WARNING, 1,
                "12 runtime detail messages suppressed (limit=0)");
            m_catcher.expect_report("uvm_test_top.m_cfg_invalid",
                "SCB_SUPPRESSED", UVM_WARNING, 1,
                "12 runtime detail messages suppressed (limit=0)");

            expect_final("uvm_test_top.m_exact_pass", UVM_INFO, "SCB_PASS");
            expect_final("uvm_test_top.m_exact_fail", UVM_ERROR, "SCB_FAIL");
            expect_final("uvm_test_top.m_lossy", UVM_WARNING, "SCB_WARN");
            expect_final("uvm_test_top.m_unordered", UVM_INFO, "SCB_PASS");
            expect_final("uvm_test_top.m_overflow", UVM_ERROR, "SCB_FAIL");
            expect_final("uvm_test_top.m_many", UVM_ERROR, "SCB_FAIL");
            expect_final("uvm_test_top.m_topn", UVM_ERROR, "SCB_FAIL");
            expect_final("uvm_test_top.m_reset", UVM_INFO, "SCB_PASS");
            expect_final("uvm_test_top.m_reset_counters", UVM_INFO,
                         "SCB_PASS");
            expect_final("uvm_test_top.m_clone_error", UVM_ERROR,
                         "SCB_FAIL");
            expect_final("uvm_test_top.m_suppression", UVM_ERROR,
                         "SCB_FAIL");
            expect_final("uvm_test_top.m_suppression_zero", UVM_ERROR,
                         "SCB_FAIL");
            expect_final("uvm_test_top.m_report_disabled", UVM_ERROR,
                         "SCB_FAIL");
            expect_final("uvm_test_top.m_check_once", UVM_ERROR,
                         "SCB_FAIL", 2);
            expect_final("uvm_test_top.m_cfg_seven", UVM_ERROR, "SCB_FAIL");
            expect_final("uvm_test_top.m_cfg_invalid", UVM_ERROR,
                         "SCB_FAIL");

            expect_cfg_warning("uvm_test_top.m_exact_pass", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_exact_fail", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_lossy", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_unordered", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_overflow", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_many", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_topn", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_reset", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_reset_counters",
                               expected_cfg_warn, expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_clone_error", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_suppression", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_suppression_zero",
                               expected_cfg_warn, expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_report_disabled",
                               expected_cfg_warn, expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_check_once", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_cfg_seven", expected_cfg_warn,
                               expected_cfg_text);
            expect_cfg_warning("uvm_test_top.m_cfg_invalid", expected_cfg_warn,
                               expected_cfg_text);
        endfunction

        function void build_phase(uvm_phase phase);
            common_uvm_scb_cfg cfg_seven;
            common_uvm_scb_cfg cfg_invalid;
            int expected_cfg_warn;
            string expected_cfg_text;
            super.build_phase(phase);
            m_failures = 0;
            m_catcher = new();
            uvm_report_cb::add(null, m_catcher);

            if (!$value$plusargs("SCB_EXPECT_CFG_WARN=%d", expected_cfg_warn))
                expected_cfg_warn = 0;
            expected_cfg_text = "";
            if (expected_cfg_warn != 0) begin
                unit_check($value$plusargs(
                          "SCB_EXPECT_CFG_TEXT=%s", expected_cfg_text),
                      "runner did not provide SCB_EXPECT_CFG_TEXT");
                if (expected_cfg_text == "__EMPTY__")
                    expected_cfg_text = "";
            end

            cfg_seven = new();
            cfg_seven.m_cmp_mode = SCB_UNORDERED;
            cfg_seven.m_err_limit = 0;
            cfg_seven.m_report_limit = 7;
            uvm_config_db#(common_uvm_scb_cfg)::set(
                this, "m_cfg_seven", "cfg", cfg_seven);

            cfg_invalid = new();
            cfg_invalid.m_cmp_mode = SCB_UNORDERED;
            cfg_invalid.m_err_limit = 0;
            cfg_invalid.m_report_limit = -2;
            uvm_config_db#(common_uvm_scb_cfg)::set(
                this, "m_cfg_invalid", "cfg", cfg_invalid);

            m_exact_pass = scb_probe::type_id::create("m_exact_pass", this);
            m_exact_fail = scb_probe::type_id::create("m_exact_fail", this);
            m_lossy = scb_probe::type_id::create("m_lossy", this);
            m_unordered = scb_probe::type_id::create("m_unordered", this);
            m_overflow = scb_probe::type_id::create("m_overflow", this);
            m_many = scb_probe::type_id::create("m_many", this);
            m_topn = scb_probe::type_id::create("m_topn", this);
            m_reset = scb_probe::type_id::create("m_reset", this);
            m_reset_counters = scb_probe::type_id::create(
                "m_reset_counters", this);
            m_clone_error = scb_probe::type_id::create("m_clone_error", this);
            m_suppression = scb_probe::type_id::create("m_suppression", this);
            m_suppression_zero = scb_probe::type_id::create(
                "m_suppression_zero", this);
            m_report_disabled = scb_probe::type_id::create(
                "m_report_disabled", this);
            m_check_once = scb_probe::type_id::create("m_check_once", this);
            m_cfg_seven = scb_probe::type_id::create("m_cfg_seven", this);
            m_cfg_invalid = scb_probe::type_id::create("m_cfg_invalid", this);

            m_exact_results = result_sink::type_id::create(
                "m_exact_results", this);
            m_topn_results = result_sink::type_id::create(
                "m_topn_results", this);
            m_check_results = result_sink::type_id::create(
                "m_check_results", this);

            m_exact_pass.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_exact_fail.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_lossy.m_cfg.m_cmp_mode = SCB_ORDERED_LOSSY;
            m_unordered.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_overflow.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_overflow.m_cfg.m_pending_limit = 1;
            m_many.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_many.m_cfg.m_err_limit = 0;
            m_topn.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_topn.m_cfg.m_strict_arrival = 1;
            m_topn.m_cfg.m_err_limit = 0;
            m_reset.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_reset.m_cfg.m_strict_arrival = 1;
            m_reset.m_cfg.m_err_limit = 0;
            m_reset_counters.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_reset_counters.m_cfg.m_strict_arrival = 1;
            m_reset_counters.m_cfg.m_err_limit = 1;
            m_clone_error.m_cfg.m_err_limit = 10;
            m_suppression.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_suppression.m_cfg.m_err_limit = 2;
            m_suppression_zero.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_suppression_zero.m_cfg.m_err_limit = 0;
            m_report_disabled.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_report_disabled.m_cfg.m_report_en = 0;
            m_check_once.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_check_once.m_cfg.m_err_limit = 0;

            m_exact_pass.m_cfg.m_report_en = 0;
            m_exact_fail.m_cfg.m_report_en = 0;
            m_lossy.m_cfg.m_report_en = 0;
            m_unordered.m_cfg.m_report_en = 0;
            m_overflow.m_cfg.m_report_en = 0;
            m_topn.m_cfg.m_report_en = 0;
            m_reset.m_cfg.m_report_en = 0;
            m_reset_counters.m_cfg.m_report_en = 0;
            m_clone_error.m_cfg.m_report_en = 0;
            m_suppression.m_cfg.m_report_en = 0;
            m_suppression_zero.m_cfg.m_report_en = 0;
            m_check_once.m_cfg.m_report_en = 0;

            register_report_expectations(expected_cfg_warn,
                                         expected_cfg_text);
        endfunction

        function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
            m_exact_pass.m_result_ap.connect(m_exact_results.analysis_export);
            m_topn.m_result_ap.connect(m_topn_results.analysis_export);
            m_check_once.m_result_ap.connect(m_check_results.analysis_export);
        endfunction

        function void test_reporter();
            common_scb_reporter reporter;
            string headers[$];
            bit numeric[$];
            string cells[$];
            string rendered;
            string expected;
            reporter = new();

            headers = '{"Name", "Count"};
            numeric = '{0, 1};
            reporter.set_columns(headers, numeric);
            cells = '{"x", "7"};
            reporter.add_row(cells);
            cells = '{"long", "123"};
            reporter.add_row(cells);
            rendered = reporter.render();
            expected = {"+------+-------+\n",
                        "| Name | Count |\n",
                        "+------+-------+\n",
                        "| x    |     7 |\n",
                        "| long |   123 |\n",
                        "+------+-------+"};
            unit_check(rendered == expected,
                  {"reporter alignment mismatch:\n", rendered});

            headers = '{"L", "N"};
            numeric = '{0, 1};
            reporter.set_columns(headers, numeric);
            cells = '{"z", "2"};
            reporter.add_row(cells);
            rendered = reporter.render();
            expected = {"+---+---+\n",
                        "| L | N |\n",
                        "+---+---+\n",
                        "| z | 2 |\n",
                        "+---+---+"};
            unit_check(rendered == expected,
                  {"reporter retained stale row or width:\n", rendered});

            headers = '{"A", "B"};
            numeric = '{0, 1};
            reporter.set_columns(headers, numeric);
            rendered = reporter.render();
            expected = {"+---+---+\n",
                        "| A | B |\n",
                        "+---+---+"};
            unit_check(rendered == expected,
                  {"zero-row reporter boundaries/stale state mismatch:\n",
                   rendered});
        endfunction

        function void test_item_copy_clone();
            scb_item source;
            scb_item copied;
            scb_item cloned;
            uvm_object clone_object;
            string diff;
            source = item(123);
            copied = item(0);
            copied.copy(source);
            unit_check(copied.value == 123, "scb_item do_copy did not copy value");
            clone_object = source.clone();
            unit_check($cast(cloned, clone_object),
                  "scb_item clone did not preserve the typed object");
            if (cloned != null) begin
                unit_check(cloned.value == 123, "scb_item clone did not copy value");
                unit_check(source.self_define_do_compare(cloned, diff, 77),
                      "scb_item self_define_do_compare rejected equal clone");
                cloned.value = 124;
                unit_check(!source.self_define_do_compare(cloned, diff, 77),
                      "scb_item self_define_do_compare accepted mismatch");
                check_contains(diff, "kind=77",
                               "scb_item mismatch diff lost compare kind");
            end
        endfunction

        function void test_topn_reporting();
            common_scb_problem_row rows[$];
            string client;
            string message;
            string table_k2;
            string table_full;
            string table_all;
            string tokens[$];
            int report_before;
            string expected_k2;
            client = "uvm_test_top.m_topn";

            m_topn.m_cfg.m_report_limit = 2;

            m_topn.push_expected(item(0), 64'h0);
            m_topn.push_actual(item(0), 64'h0);

            m_topn.push_actual(item(1), 64'h1);
            m_topn.push_expected(item(1), 64'h1);

            m_topn.push_actual(item(2), 64'h2);
            repeat (3) m_topn.push_actual(item(3), 64'h3);
            m_topn.push_actual(item(4), 64'h4);
            repeat (2)
                m_topn.push_actual(item(8), 64'h8000_0000_0000_0002);
            repeat (2)
                m_topn.push_actual(item(15), 64'hf000_0000_0000_0001);

            m_topn.check_phase(null);
            m_topn.collect_sorted_rows(rows);
            unit_check(rows.size() == 6,
                  $sformatf("top-N problem row count=%0d expected=6", rows.size()));
            if (rows.size() == 6) begin
                unit_check((rows[0].stream_id == 64'h3)
                      && (rows[0].status == SCB_FAIL)
                      && (rows[0].issue_count == 6),
                      "top-N first row metadata/order mismatch");
                unit_check((rows[1].stream_id == 64'h8000_0000_0000_0002)
                      && (rows[1].status == SCB_FAIL)
                      && (rows[1].issue_count == 4),
                      "top-N high-ID retained row metadata mismatch");
                unit_check((rows[2].stream_id == 64'hf000_0000_0000_0001)
                      && (rows[2].status == SCB_FAIL)
                      && (rows[2].issue_count == 4),
                      "top-N unsigned tie ordering/truncation mismatch");
                unit_check((rows[3].stream_id == 64'h2)
                      && (rows[3].issue_count == 2),
                      "top-N low-ID tie row mismatch");
                unit_check((rows[4].stream_id == 64'h4)
                      && (rows[4].issue_count == 2),
                      "top-N deterministic ascending-ID tie mismatch");
                unit_check((rows[5].stream_id == 64'h1)
                      && (rows[5].status == SCB_WARN)
                      && (rows[5].issue_count == 1),
                      "top-N WARN severity row mismatch");
            end

            report_before = m_catcher.count(client, "SCB_REPORT");
            m_topn.print_report(0);
            unit_check(m_catcher.count(client, "SCB_REPORT") == report_before + 2,
                  "K=0 emitted a detail table");
            message = m_catcher.message_at(client, "SCB_REPORT",
                                           report_before + 1);
            unit_check(message == "Problem streams: total=6 shown=0 omitted=6",
                  {"K=0 totals mismatch: ", message});

            report_before = m_catcher.count(client, "SCB_REPORT");
            m_topn.print_report(2);
            unit_check(m_catcher.count(client, "SCB_REPORT") == report_before + 3,
                  "K=2 report message count mismatch");
            message = m_catcher.message_at(client, "SCB_REPORT",
                                           report_before + 1);
            unit_check(message == "Problem streams: total=6 shown=2 omitted=4",
                  {"K=2 totals mismatch: ", message});
            table_k2 = m_catcher.message_at(client, "SCB_REPORT",
                                            report_before + 2);
            expected_k2 = {"\n",
                "+----------+--------------------+-------+----------+------+------------+---------+---------+----------+------+\n",
                "| Status   | Stream             | Match | Mismatch | Drop | Unexpected | PendExp | PendAct | Overflow | Peak |\n",
                "+----------+--------------------+-------+----------+------+------------+---------+---------+----------+------+\n",
                "| SCB_FAIL | 0x3                |     0 |        0 |    0 |          3 |       0 |       0 |        0 |    3 |\n",
                "| SCB_FAIL | 0x8000000000000002 |     0 |        0 |    0 |          2 |       0 |       0 |        0 |    2 |\n",
                "+----------+--------------------+-------+----------+------+------------+---------+---------+----------+------+"};
            unit_check(table_k2 == expected_k2,
                  {"K=2 exact ASCII/order mismatch:\n", table_k2});

            report_before = m_catcher.count(client, "SCB_REPORT");
            m_topn.print_report(-2);
            unit_check(m_catcher.count(client, "SCB_REPORT") == report_before + 3,
                  "API -2 configured sentinel did not use K=2");
            unit_check(m_catcher.message_at(client, "SCB_REPORT",
                                       report_before + 2)
                      == table_k2,
                  "API -2 configured sentinel changed K=2 selection");

            report_before = m_catcher.count(client, "SCB_REPORT_LIMIT");
            m_topn.print_report(-3);
            unit_check(m_catcher.count(client, "SCB_REPORT_LIMIT")
                      == report_before + 1,
                  "invalid API report limit did not warn exactly once");
            unit_check(m_catcher.message_at(client, "SCB_REPORT",
                                       m_catcher.count(client, "SCB_REPORT")-1)
                      == table_k2,
                  "invalid API report limit did not fall back to configured K=2");

            report_before = m_catcher.count(client, "SCB_REPORT");
            m_topn.print_report(9);
            message = m_catcher.message_at(client, "SCB_REPORT",
                                           report_before + 1);
            unit_check(message == "Problem streams: total=6 shown=6 omitted=0",
                  {"K>=S totals mismatch: ", message});
            table_full = m_catcher.message_at(client, "SCB_REPORT",
                                              report_before + 2);
            unit_check(count_text(table_full, "| SCB_FAIL") == 5,
                  "K>=S did not show all five FAIL rows");
            unit_check(count_text(table_full, "| SCB_WARN") == 1,
                  "K>=S did not show the WARN row");
            tokens = '{"0x3", "0x8000000000000002",
                       "0xf000000000000001", "0x2", "0x4", "0x1"};
            check_stream_order(table_full, tokens,
                               "K>=S composite ordering mismatch");

            report_before = m_catcher.count(client, "SCB_REPORT");
            m_topn.print_report(-1);
            message = m_catcher.message_at(client, "SCB_REPORT",
                                           report_before + 1);
            unit_check(message == "Problem streams: total=6 shown=6 omitted=0",
                  {"unlimited totals mismatch: ", message});
            table_all = m_catcher.message_at(client, "SCB_REPORT",
                                             report_before + 2);
            unit_check(table_all == table_full,
                  "unlimited ordering differs from finite full-set ordering");
            check_contains(table_all, "0x8000000000000002",
                           "unlimited report truncated high stream ID");
            check_contains(table_all, "0xf000000000000001",
                           "unlimited report sign-corrupted high stream ID");
            unit_check(find_text(table_all, "0x0") < 0,
                  "normal/PASS stream appeared in problem detail");
        endfunction

        function void test_reset_semantics();
            common_scb_problem_row rows[$];
            string client;
            string message;
            int report_before;
            client = "uvm_test_top.m_reset";

            m_reset.push_actual(item(9), 64'h9);
            m_reset.push_expected(item(9), 64'h9);
            m_reset.push_expected(item(10), 64'ha);
            unit_check(m_reset.get_status() == SCB_WARN,
                  "strict-arrival diagnostic did not produce WARN");
            unit_check(m_reset.stream_count() == 2,
                  "reset precondition stream count mismatch");
            unit_check(m_reset.current_pending() == 1,
                  "reset precondition pending count mismatch");

            m_reset.reset_state(0);
            unit_check(m_reset.stream_count() == 0,
                  "reset_state(0) retained stream state");
            unit_check(m_reset.current_pending() == 0,
                  "reset_state(0) retained pending state");
            unit_check(m_reset.problem_row_count() == 0,
                  "reset_state(0) retained problem detail rows");
            unit_check(m_reset.get_status() == SCB_WARN,
                  "reset_state(0) erased cumulative diagnostic WARN");
            unit_check(!m_reset.is_clean(),
                  "reset_state(0) WARN history incorrectly reported clean");
            unit_check((m_reset.expected_inputs() == 2)
                  && (m_reset.actual_inputs() == 1)
                  && (m_reset.match_count() == 1)
                  && (m_reset.diagnostic_count() == 1),
                  "reset_state(0) changed cumulative counters");
            m_reset.collect_sorted_rows(rows);
            unit_check(rows.size() == 0,
                  "reset_state(0) produced rows without stream state");

            report_before = m_catcher.count(client, "SCB_REPORT");
            m_reset.print_report(0);
            message = m_catcher.message_at(client, "SCB_REPORT",
                                           report_before);
            check_contains(message, "status=SCB_WARN",
                           "zero-row post-reset summary lost WARN");
            message = m_catcher.message_at(client, "SCB_REPORT",
                                           report_before + 1);
            unit_check(message == "Problem streams: total=0 shown=0 omitted=0",
                  {"zero-row post-reset problem totals mismatch: ", message});

            m_reset.reset_state(1);
            unit_check(m_reset.get_status() == SCB_PASS,
                  "reset_state(1) did not clear WARN history");
            unit_check(m_reset.is_clean(),
                  "reset_state(1) did not return clean state");
            unit_check((m_reset.expected_inputs() == 0)
                  && (m_reset.actual_inputs() == 0)
                  && (m_reset.match_count() == 0)
                  && (m_reset.diagnostic_count() == 0)
                  && (m_reset.peak_pending() == 0)
                  && (m_reset.suppressed_details() == 0),
                  "reset_state(1) did not clear all cumulative counters");
        endfunction

        function void check_reset_counter_snapshot(string stage,
                                                   int expected_streams,
                                                   int expected_rows,
                                                   int expected_pending,
                                                   int expected_inputs,
                                                   int actual_inputs,
                                                   int match_total,
                                                   int mismatches,
                                                   int drops,
                                                   int unexpected,
                                                   int overflows,
                                                   int diagnostics,
                                                   int peak,
                                                   int emitted,
                                                   int suppressed);
            unit_check(m_reset_counters.stream_count() == expected_streams,
                  $sformatf("%s stream_count=%0d expected=%0d", stage,
                            m_reset_counters.stream_count(), expected_streams));
            unit_check(m_reset_counters.problem_row_count() == expected_rows,
                  $sformatf("%s problem_row_count=%0d expected=%0d", stage,
                            m_reset_counters.problem_row_count(), expected_rows));
            unit_check(m_reset_counters.current_pending() == expected_pending,
                  $sformatf("%s current_pending=%0d expected=%0d", stage,
                            m_reset_counters.current_pending(), expected_pending));
            unit_check(m_reset_counters.expected_inputs() == expected_inputs,
                  $sformatf("%s expected_inputs changed", stage));
            unit_check(m_reset_counters.actual_inputs() == actual_inputs,
                  $sformatf("%s actual_inputs changed", stage));
            unit_check(m_reset_counters.match_count() == match_total,
                  $sformatf("%s matches changed", stage));
            unit_check(m_reset_counters.mismatch_count() == mismatches,
                  $sformatf("%s mismatches changed", stage));
            unit_check(m_reset_counters.drop_count() == drops,
                  $sformatf("%s drops changed", stage));
            unit_check(m_reset_counters.unexpected_count() == unexpected,
                  $sformatf("%s unexpected count changed", stage));
            unit_check(m_reset_counters.overflow_count() == overflows,
                  $sformatf("%s overflows changed", stage));
            unit_check(m_reset_counters.diagnostic_count() == diagnostics,
                  $sformatf("%s diagnostics changed", stage));
            unit_check(m_reset_counters.peak_pending() == peak,
                  $sformatf("%s peak_pending changed", stage));
            unit_check(m_reset_counters.detail_emitted() == emitted,
                  $sformatf("%s detail_emitted changed", stage));
            unit_check(m_reset_counters.suppressed_details() == suppressed,
                  $sformatf("%s suppressed_details changed", stage));
        endfunction

        function void test_reset_counter_preservation();
            m_reset_counters.push_actual(item(1), 64'h101);
            m_reset_counters.push_expected(item(1), 64'h101);
            m_reset_counters.m_cfg.m_strict_arrival = 0;

            m_reset_counters.m_cfg.m_cmp_mode = SCB_ORDERED_EXACT;
            m_reset_counters.push_expected(item(2), 64'h102);
            m_reset_counters.push_actual(item(3), 64'h102);

            m_reset_counters.m_cfg.m_cmp_mode = SCB_ORDERED_LOSSY;
            m_reset_counters.push_expected(item(10), 64'h103);
            m_reset_counters.push_expected(item(20), 64'h103);
            m_reset_counters.push_actual(item(20), 64'h103);

            m_reset_counters.m_cfg.m_cmp_mode = SCB_UNORDERED;
            m_reset_counters.push_actual(item(30), 64'h104);
            m_reset_counters.probe_finalize_pending();

            m_reset_counters.m_cfg.m_pending_limit = 1;
            m_reset_counters.push_expected(item(40), 64'h105);
            m_reset_counters.push_expected(item(41), 64'h105);

            check_reset_counter_snapshot(
                "pre-reset", 5, 5, 1,
                6, 4, 2, 1, 1, 1, 1, 1, 3, 1, 2);

            m_reset_counters.reset_state(0);
            check_reset_counter_snapshot(
                "reset_state(0)", 0, 0, 0,
                6, 4, 2, 1, 1, 1, 1, 1, 3, 1, 2);
            unit_check(m_reset_counters.get_status() == SCB_FAIL,
                  "reset_state(0) erased cumulative failure status");
            unit_check(!m_reset_counters.is_clean(),
                  "reset_state(0) cumulative failures reported clean");

            m_reset_counters.reset_state(1);
            check_reset_counter_snapshot(
                "reset_state(1)", 0, 0, 0,
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
            unit_check(m_reset_counters.get_status() == SCB_PASS,
                  "reset_state(1) did not clear cumulative failure status");
            unit_check(m_reset_counters.is_clean(),
                  "reset_state(1) did not restore clean state");
        endfunction

        function void test_repeated_check_phase();
            string client;
            client = "uvm_test_top.m_check_once";
            m_check_once.push_actual(item(70), 64'h70);
            m_check_once.check_phase(null);
            m_check_once.check_phase(null);
            unit_check(m_check_results.results.size() == 1,
                  "repeated check_phase finalized first epoch more than once");
            unit_check(m_catcher.count(client, "SCB_FINAL") == 1,
                  "repeated check_phase emitted duplicate first-epoch SCB_FINAL");

            m_check_once.reset_state(1);
            m_check_once.push_expected(item(80), 64'h80);
            m_check_once.check_phase(null);
            m_check_once.check_phase(null);
            unit_check(m_check_results.results.size() == 2,
                  "post-reset epoch did not finalize exactly once");
            unit_check(m_catcher.count(client, "SCB_FINAL") == 2,
                  "post-reset epoch SCB_FINAL count is not exactly two total");
        endfunction

        task run_phase(uvm_phase phase);
            scb_item mutable;
            wrong_clone_item bad_clone;
            phase.raise_objection(this);

            test_reporter();
            test_item_copy_clone();

            mutable = item(7);
            m_exact_pass.push_actual(mutable, 64'h7000, 7);
            mutable.value = 99;
            m_exact_pass.push_expected(item(7), 64'h7000, 7);
            m_exact_pass.push_expected(item(8), 64'h8000, 8);
            m_exact_pass.push_actual(item(8), 64'h8000, 8);
            unit_check(m_exact_pass.is_clean(),
                  "ordered exact pass is not clean before check phase");
            unit_check((m_exact_results.results.size() == 2)
                  && (m_exact_results.results[0].actual.value == 7),
                  "retained clone changed with producer-owned handle");

            m_exact_fail.push_expected(item(1), 64'h11);
            m_exact_fail.push_actual(item(2), 64'h11);

            m_lossy.push_expected(item(10), 64'h20);
            m_lossy.push_expected(item(20), 64'h20);
            m_lossy.push_actual(item(20), 64'h20);
            m_lossy.push_expected(item(30), 64'h20);

            m_unordered.push_expected(item(1), 64'h30);
            m_unordered.push_expected(item(2), 64'h30);
            m_unordered.push_actual(item(2), 64'h30);
            m_unordered.push_actual(item(1), 64'h30);

            m_overflow.push_expected(item(30), 64'h40);
            m_overflow.push_expected(item(31), 64'h40);

            for (int i=0; i<15; i++)
                m_many.push_actual(item(i), i);

            m_clone_error.push_expected(null, 64'h50);
            bad_clone = new();
            bad_clone.value = 51;
            m_clone_error.push_expected(bad_clone, 64'h51);

            for (int i=0; i<5; i++) begin
                m_suppression.push_expected(item(i), i);
                m_suppression.push_actual(item(100+i), i);
            end
            for (int i=0; i<4; i++) begin
                m_suppression_zero.push_expected(item(i), i);
                m_suppression_zero.push_actual(item(200+i), i);
            end

            m_report_disabled.push_expected(item(1), 64'h60);
            m_report_disabled.push_actual(item(2), 64'h60);

            for (int i=0; i<12; i++) begin
                m_cfg_seven.push_actual(item(300+i), 64'h300+i);
                m_cfg_invalid.push_actual(item(400+i), 64'h400+i);
            end

            test_topn_reporting();
            test_reset_semantics();
            test_reset_counter_preservation();
            test_repeated_check_phase();

            phase.drop_objection(this);
        endtask

        function void check_many_report_mode();
            string client;
            string message;
            string table;
            string tokens[$];
            int expected_limit;
            int expected_cfg_warn;
            int expected_shown;
            int expected_omitted;
            int report_count;
            client = "uvm_test_top.m_many";

            unit_check($value$plusargs("SCB_EXPECT_REPORT_LIMIT=%d", expected_limit),
                  "runner did not provide SCB_EXPECT_REPORT_LIMIT");
            unit_check($value$plusargs("SCB_EXPECT_CFG_WARN=%d", expected_cfg_warn),
                  "runner did not provide SCB_EXPECT_CFG_WARN");
            unit_check(m_many.m_cfg.m_report_limit == expected_limit,
                  $sformatf("report limit=%0d expected=%0d",
                            m_many.m_cfg.m_report_limit, expected_limit));
            if (expected_cfg_warn != 0)
                unit_check(m_catcher.count_id("SCB_CFG") == 16,
                      "invalid report limit SCB_CFG warning count is not 16");
            else
                unit_check(m_catcher.count_id("SCB_CFG") == 0,
                      "valid report limit emitted unexpected SCB_CFG warning");

            expected_shown = (expected_limit == -1) ? 15 : expected_limit;
            if (expected_shown > 15) expected_shown = 15;
            expected_omitted = 15 - expected_shown;
            report_count = m_catcher.count(client, "SCB_REPORT");
            unit_check(report_count == ((expected_shown == 0) ? 2 : 3),
                  $sformatf("m_many report message count=%0d", report_count));
            message = m_catcher.message_at(client, "SCB_REPORT", 1);
            unit_check(message == $sformatf(
                      "Problem streams: total=15 shown=%0d omitted=%0d",
                      expected_shown, expected_omitted),
                  {"m_many report totals mismatch: ", message});
            if (expected_shown != 0) begin
                table = m_catcher.message_at(client, "SCB_REPORT", 2);
                unit_check(count_text(table, "| SCB_FAIL") == expected_shown,
                      "m_many displayed row count mismatch");
                tokens.delete();
                for (int i=0; i<expected_shown; i++)
                    tokens.push_back($sformatf("0x%0h", i));
                check_stream_order(table, tokens,
                                   "m_many deterministic stream ordering mismatch");
            end
        endfunction

        function void check_config_report(scb_probe scoreboard,
                                          string client,
                                          int expected_limit);
            string message;
            string table;
            int expected_shown;
            int expected_omitted;
            int report_count;
            expected_shown = (expected_limit == -1) ? 12 : expected_limit;
            if (expected_shown > 12) expected_shown = 12;
            expected_omitted = 12 - expected_shown;

            unit_check(scoreboard.m_cfg.m_report_limit == expected_limit,
                  $sformatf("%s configured report limit=%0d expected=%0d",
                            client, scoreboard.m_cfg.m_report_limit,
                            expected_limit));
            report_count = m_catcher.count(client, "SCB_REPORT");
            unit_check(report_count == ((expected_shown == 0) ? 2 : 3),
                  $sformatf("%s report message count=%0d",
                            client, report_count));
            message = m_catcher.message_at(client, "SCB_REPORT", 1);
            unit_check(message == $sformatf(
                      "Problem streams: total=12 shown=%0d omitted=%0d",
                      expected_shown, expected_omitted),
                  {client, " report totals mismatch: ", message});
            if (expected_shown != 0) begin
                table = m_catcher.message_at(client, "SCB_REPORT", 2);
                unit_check(count_text(table, "| SCB_FAIL") == expected_shown,
                      {client, " displayed row count mismatch"});
            end
        endfunction

        function void check_config_report_modes();
            int expected_many_limit;
            int expected_cfg_warn;
            int expected_seven_limit;
            int expected_invalid_limit;
            bit raw_override_present;

            unit_check($value$plusargs(
                      "SCB_EXPECT_REPORT_LIMIT=%d", expected_many_limit),
                  "runner did not provide SCB_EXPECT_REPORT_LIMIT");
            unit_check($value$plusargs(
                      "SCB_EXPECT_CFG_WARN=%d", expected_cfg_warn),
                  "runner did not provide SCB_EXPECT_CFG_WARN");
            raw_override_present = $test$plusargs("SCB_REPORT_LIMIT=");
            if (raw_override_present && (expected_cfg_warn == 0)) begin
                expected_seven_limit = expected_many_limit;
                expected_invalid_limit = expected_many_limit;
            end else begin
                expected_seven_limit = 7;
                expected_invalid_limit = 10;
            end

            check_config_report(m_cfg_seven, "uvm_test_top.m_cfg_seven",
                                expected_seven_limit);
            check_config_report(m_cfg_invalid, "uvm_test_top.m_cfg_invalid",
                                expected_invalid_limit);
        endfunction

        function void final_phase(uvm_phase phase);
            string summary;
            super.final_phase(phase);

            unit_check(m_exact_pass.get_status() == SCB_PASS,
                  "ordered exact expected/actual order or clone isolation failed");
            unit_check((m_exact_pass.match_count() == 2)
                  && (m_exact_pass.mismatch_count() == 0)
                  && m_exact_pass.is_clean(),
                  "ordered exact pass counters/clean status mismatch");
            unit_check(m_exact_fail.get_status() == SCB_FAIL,
                  "ordered exact mismatch did not fail");
            unit_check(m_exact_fail.mismatch_count() == 1,
                  "ordered exact mismatch count is not one");
            unit_check(m_lossy.get_status() == SCB_WARN,
                  "lossy expected drop did not warn");
            unit_check(m_lossy.drop_count() == 2,
                  "lossy middle/tail drop count mismatch");
            unit_check(m_unordered.get_status() == SCB_PASS,
                  "unordered out-of-order matching failed");
            unit_check((m_unordered.match_count() == 2) && m_unordered.is_clean(),
                  "unordered pass counters/clean status mismatch");
            unit_check(m_overflow.get_status() == SCB_FAIL,
                  "pending overflow did not fail");
            unit_check((m_overflow.overflow_count() == 1)
                  && (m_overflow.mismatch_count() == 1)
                  && (m_overflow.current_pending() == 0),
                  "pending overflow reject/final accounting mismatch");
            unit_check(m_many.get_status() == SCB_FAIL,
                  "many residual actual streams did not fail");
            unit_check((m_many.unexpected_count() == 15)
                  && (m_many.suppressed_details() == 15)
                  && (m_many.detail_emitted() == 0),
                  "many stream suppression/counter accounting mismatch");
            unit_check(m_clone_error.get_status() == SCB_FAIL,
                  "null/failed typed clone inputs did not fail");
            unit_check((m_clone_error.expected_inputs() == 2)
                  && (m_clone_error.overflow_count() == 2)
                  && (m_clone_error.current_pending() == 0),
                  "null/failed typed clone accounting mismatch");
            unit_check((m_suppression.mismatch_count() == 5)
                  && (m_suppression.detail_emitted() == 2)
                  && (m_suppression.suppressed_details() == 3),
                  "m_err_limit=2 boundary/counter accounting mismatch");
            unit_check((m_suppression_zero.mismatch_count() == 4)
                  && (m_suppression_zero.detail_emitted() == 0)
                  && (m_suppression_zero.suppressed_details() == 4),
                  "m_err_limit=0 boundary/counter accounting mismatch");
            unit_check((m_report_disabled.get_status() == SCB_FAIL)
                  && (m_report_disabled.mismatch_count() == 1),
                  "m_report_en=0 changed comparison status/counters");
            unit_check(m_catcher.count("uvm_test_top.m_report_disabled",
                                  "SCB_REPORT") == 0,
                  "m_report_en=0 did not suppress report output");

            unit_check(m_catcher.count("uvm_test_top.m_exact_fail",
                                  "SCB_MISMATCH") == 1,
                  "ordered mismatch detail count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_overflow",
                                  "SCB_PENDING_OVERFLOW") == 1,
                  "pending overflow detail count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_clone_error",
                                  "SCB_NULL_INPUT") == 1,
                  "null input detail count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_clone_error",
                                  "SCB_CLONE_FAILED") == 1,
                  "typed clone failure detail count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_suppression",
                                  "SCB_MISMATCH") == 2,
                  "m_err_limit=2 emitted detail count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_suppression_zero",
                                  "SCB_MISMATCH") == 0,
                  "m_err_limit=0 emitted runtime detail");
            unit_check(m_catcher.count("uvm_test_top.m_suppression",
                                  "SCB_SUPPRESSED") == 1,
                  "suppression final summary was not emitted exactly once");
            check_contains(m_catcher.message_at(
                               "uvm_test_top.m_suppression",
                               "SCB_SUPPRESSED", 0),
                           "3 runtime detail messages suppressed (limit=2)",
                           "suppression final summary count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_suppression_zero",
                                  "SCB_SUPPRESSED") == 1,
                  "m_err_limit=0 suppression summary count mismatch");
            check_contains(m_catcher.message_at(
                               "uvm_test_top.m_suppression_zero",
                               "SCB_SUPPRESSED", 0),
                           "4 runtime detail messages suppressed (limit=0)",
                           "m_err_limit=0 suppression summary value mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_many",
                                  "SCB_SUPPRESSED") == 1,
                  "many-stream suppression summary count mismatch");
            check_contains(m_catcher.message_at("uvm_test_top.m_many",
                                                "SCB_SUPPRESSED", 0),
                           "15 runtime detail messages suppressed (limit=0)",
                           "many-stream suppression summary value mismatch");

            unit_check(m_catcher.count("uvm_test_top.m_topn",
                                  "SCB_ACTUAL_FIRST") == 1,
                  "strict arrival diagnostic was not globally bounded");
            unit_check(m_catcher.count("uvm_test_top.m_reset",
                                  "SCB_ACTUAL_FIRST") == 1,
                  "reset strict arrival diagnostic count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_reset_counters",
                                  "SCB_ACTUAL_FIRST") == 1,
                  "reset counter strict arrival diagnostic count mismatch");
            unit_check(m_catcher.count("uvm_test_top.m_topn",
                                  "SCB_FINAL") == 1,
                  "automatic check_phase duplicated manually finalized SCB_FINAL");
            unit_check(m_catcher.count("uvm_test_top.m_check_once",
                                  "SCB_FINAL") == 2,
                  "check_phase did not emit exactly once per reset epoch");
            unit_check(m_check_results.results.size() == 2,
                  "automatic check_phase duplicated per-epoch result finalization");

            unit_check(m_topn_results.id_count(64'h8000_0000_0000_0002) == 2,
                  "result API truncated high-bit 64-bit stream ID");
            unit_check(m_topn_results.id_count(64'hf000_0000_0000_0001) == 2,
                  "result API sign-corrupted 64-bit stream ID");

            summary = m_report_disabled.get_summary();
            check_contains(summary, "status=SCB_FAIL",
                           "m_report_en=0 summary lost failure status");
            check_contains(summary, "mismatch=1",
                           "m_report_en=0 summary lost mismatch counter");

            check_many_report_mode();
            check_config_report_modes();

            unit_check(m_catcher.unexpected_guarded_events == 0,
                  $sformatf("unexpected guarded report events=%0d",
                            m_catcher.unexpected_guarded_events));
            unit_check(m_catcher.all_expectations_consumed(),
                  {"unconsumed report expectations: ",
                   m_catcher.unconsumed_expectations()});

            if (m_failures != 0)
                `uvm_fatal("SCB_UNIT",
                           $sformatf("scoreboard v2 semantic failures=%0d",
                                     m_failures))
            $display("SCB_UNIT_PASS");
        endfunction
    endclass

    initial run_test("common_scb_unit_test");
endmodule
