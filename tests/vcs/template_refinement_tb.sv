`timescale 1ns/1ps

import uvm_pkg::*;
import common_lib_pkg::*;
import axi_agent_pkg::*;

interface uvg_probe_if;
    logic marker;
endinterface

class uvg_vif_consumer extends uvm_component;
    `uvm_component_utils(uvg_vif_consumer)
    virtual uvg_probe_if m_vif;

    function new(string name="uvg_vif_consumer", uvm_component parent=null);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        `UVG_VIF_GET(uvg_probe_if, m_vif)
    endfunction
endclass

class template_refinement_test extends uvm_test;
    `uvm_component_utils(template_refinement_test)
    uvg_vif_consumer m_consumer;

    function new(string name="template_refinement_test",
                 uvm_component parent=null);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        m_consumer = uvg_vif_consumer::type_id::create("m_consumer", this);
    endfunction

    task run_phase(uvm_phase phase);
        axi_trans tr;
        axi_trans copied;
        uvm_object cloned;

        phase.raise_objection(this);
        wait (template_refinement_tb.connection_checks_done);
        wait (template_refinement_tb.probe_rst_n === 1'b1);
        if (template_refinement_tb.probe_clk !== 1'b0)
            `uvm_fatal("UVG_RSTN",
                       "reset did not deassert on a falling edge")
        tr = new("tr");
        cloned = tr.clone();
        if ((cloned == null) || !$cast(copied, cloned))
            `uvm_fatal("TRANS_CLONE",
                       "generated transaction clone/cast failed")
        if (tr.compare(copied))
            `uvm_fatal("TRANS_COMPARE",
                       "empty comparison hook passed unexpectedly")
        tr.print();
        $display("TEMPLATE_REFINEMENT_VCS_PASS");
        phase.drop_objection(this);
    endtask
endclass

module template_refinement_tb;
    logic probe_clk;
    logic probe_rst_n;
    bit connection_checks_done;
    uvg_probe_if probe_if();

    logic master_m2s_vif;
    wire  master_m2s_rtl;
    logic master_s2m_rtl;
    wire  master_s2m_vif;
    logic slave_m2s_rtl;
    wire  slave_m2s_vif;
    logic slave_s2m_vif;
    wire  slave_s2m_rtl;
    logic monitor_m2s_rtl;
    wire  monitor_m2s_vif;
    logic monitor_s2m_rtl;
    wire  monitor_s2m_vif;

    `UVG_CLK(probe_clk, 10ns, 1ns)
    `UVG_RSTN(probe_rst_n, probe_clk, 2)
    `UVG_STATIC_ASSERT(uvg_positive_assert,
                       $bits(master_m2s_rtl) == $bits(master_m2s_vif),
                       "equal widths required")

    `UVG_IF_CONNECT(MASTER,  M2S, master_m2s_rtl,  master_m2s_vif);
    `UVG_IF_CONNECT(MASTER,  S2M, master_s2m_rtl,  master_s2m_vif);
    `UVG_IF_CONNECT(SLAVE,   M2S, slave_m2s_rtl,   slave_m2s_vif);
    `UVG_IF_CONNECT(SLAVE,   S2M, slave_s2m_rtl,   slave_s2m_vif);
    `UVG_IF_CONNECT(MONITOR, M2S, monitor_m2s_rtl, monitor_m2s_vif);
    `UVG_IF_CONNECT(MONITOR, S2M, monitor_s2m_rtl, monitor_s2m_vif);

`ifdef UVG_WIDTH_MISMATCH
    logic [1:0] bad_rtl;
    wire        bad_vif;
    `UVG_IF_CONNECT(MONITOR, M2S, bad_rtl, bad_vif);
`endif

    initial begin
        connection_checks_done = 0;
        master_m2s_vif = 1;
        master_s2m_rtl = 1;
        slave_m2s_rtl = 1;
        slave_s2m_vif = 1;
        monitor_m2s_rtl = 1;
        monitor_s2m_rtl = 1;
        #1ns;
        if ({master_m2s_rtl, master_s2m_vif,
             slave_m2s_vif, slave_s2m_rtl,
             monitor_m2s_vif, monitor_s2m_vif} !== 6'b111111)
            $fatal(1, "UVG_IF_CONNECT direction check failed");
        connection_checks_done = 1;
    end

    initial begin
        if (!$test$plusargs("UVG_SKIP_VIF_SET"))
            `UVG_VIF_SET(uvg_probe_if,
                         "uvm_test_top.m_consumer",
                         probe_if);
        run_test("template_refinement_test");
    end
endmodule
