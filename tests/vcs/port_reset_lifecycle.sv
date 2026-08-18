`ifndef PORT_RESET_LIFECYCLE__SV
`define PORT_RESET_LIFECYCLE__SV

// This directed test exercises the generated PORT environment across phase
// cleanup.  Each main_phase invocation happens only after reset_phase has
// ended, so traffic must be consumed by workers owned by run_phase rather than
// by a reset_phase descendant.
class tc_port_reset_lifecycle extends tc_base;
    `uvm_component_utils(tc_port_reset_lifecycle)

    int m_stage;

    function new(string name="tc_port_reset_lifecycle",
                 uvm_component parent=null);
        super.new(name, parent);
        m_stage = 0;
    endfunction

    extern virtual task main_phase(uvm_phase phase);
    extern virtual task send_and_match(int stage);
endclass

task tc_port_reset_lifecycle::main_phase(uvm_phase phase);
    phase.raise_objection(this);
    case (m_stage)
        0: begin
            send_and_match(0);
            m_stage = 1;
            phase.jump(uvm_reset_phase::get());
        end
        1: begin
            send_and_match(1);
            m_stage = 2;
            phase.jump(uvm_reset_phase::get());
        end
        2: begin
            send_and_match(2);
            m_stage = 3;
        end
        default: begin
            `uvm_fatal("PORT_LIFECYCLE",
                       $sformatf("unexpected main-phase stage %0d", m_stage))
        end
    endcase
    phase.drop_objection(this);
endtask

task tc_port_reset_lifecycle::send_and_match(int stage);
    axi_trans tr;
    int expected_rm_count;
    int expected_agt_count;

    tr = axi_trans::type_id::create($sformatf("stage_%0d_tr", stage));
    expected_rm_count = m_env.m_scb.m_from_rm_axi_trans_cnt + 1;
    expected_agt_count = m_env.m_scb.m_from_dut_axi_trans_cnt + 1;

    // Drive the monitor fanout legs directly so this test isolates RM/checker
    // worker ownership from the generated placeholder protocol driver.
    m_env.m_axi_agt_mon_to_rm_fifo.write(tr);
    m_env.m_agt_axi_trans_to_scb_fifo.write(tr);

    fork : wait_for_stage_match
        begin
            wait (m_env.m_scb.m_from_rm_axi_trans_cnt >= expected_rm_count
                  && m_env.m_scb.m_from_dut_axi_trans_cnt >= expected_agt_count);
            #1ns;
            if (!m_env.m_scb.m_axi_scb.is_clean()) begin
                `uvm_fatal("PORT_LIFECYCLE",
                           $sformatf("stage %0d did not produce a clean AXI match", stage))
            end
        end
        begin
            #1000ns;
            `uvm_fatal("PORT_LIFECYCLE",
                       $sformatf("stage %0d timed out waiting for PORT workers", stage))
        end
    join_any
    disable wait_for_stage_match;

    `uvm_info("PORT_LIFECYCLE", $sformatf("STAGE_%0d_MATCHED", stage), UVM_NONE)
endtask

`endif
