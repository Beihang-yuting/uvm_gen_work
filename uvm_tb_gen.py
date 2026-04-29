# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
import re
import time


def gen_description(prj_name,author_name,file_name):
    line_arry = ''
    line_arry += '//===============================================================\n'
    line_arry += '//       Copyright(c) -xxx_company, All rights reserved.         \n'
    line_arry += '//===============================================================\n'
    line_arry += '//\n'
    line_arry += '//        project     :       ' + prj_name +'\n'
    line_arry += '//        author      :       ' + author_name + '\n'
    line_arry += '//        Date        :       ' + time.strftime("%Y-%m-%d %X") + '\n'
    line_arry += '//        Filename    :       ' + file_name + '\n'
    line_arry += '//        Description :       \n'
    line_arry += '//\n'
    line_arry += '//===============================================================\n'
    return line_arry

def gen_uvm_cfg_file(file_path,block_name,agent_arry):

    dut_path = os.path.join(file_path, 'dut.f')
    dut_file = open(dut_path, 'w', encoding='utf-8')
    dut_file.write('//add your dut filelist!\n')
    dut_file.close()

    env_path = os.path.join(file_path, 'env.f')
    env_file = open(env_path, 'w', encoding='utf-8')
    env_file.write('-F  ../common_utils/common_lib_pkg.f\n')
    for key, value in agent_arry.items():
        env_file.write('-F  ../self_utils/'+key+'_agent/'+key+'_agent.f\n')
    env_file.write('../env/' + block_name + '_vsqr.sv\n')
    env_file.write('../env/' + block_name + '_rm.sv\n')
    env_file.write('../env/' + block_name + '_checker.sv\n')
    env_file.write('../env/' + block_name + '_env_cfg.sv\n')
    env_file.write('../env/' + block_name + '_env.sv\n')
    env_file.write('../harness/harness.sv\n')
    env_file.write('-f ../tc/tc.f\n')

    env_file.close()

    tb_path = os.path.join(file_path, 'tb.f')
    tb_file = open(tb_path, 'w', encoding='utf-8')
    tb_file.write('-F   ./dut.f\n')
    tb_file.write('-F   ./env.f\n')
    tb_file.close()


def gen_uvm_env(prj_name,author_name,file_path,block_name,agent_arry):

    init_path = os.path.join(file_path, block_name + '_env.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    tmp_agent_name = list(agent_arry.keys())[0]

    line_arry = ''
    file_name = block_name + '_env.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + block_name.upper() + '_ENV__SV\n'
    line_arry += '`define  ' + block_name.upper() + '_ENV__SV' + '\n'*3
    line_arry += 'class '+block_name+'_env extends uvm_env;\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_begin(' + block_name + '_env)\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_end\n\n'
    line_arry += ' ' * 4 + '//START_DEC_ENV_MEMBER\n'
    line_arry += ' ' * 4 + block_name + '_env_cfg' + '\t' * 5 + 'm_cfg;\n'  #add agent to do
    for key,value in agent_arry.items() :
        line_arry += ' ' * 4 + key+'_agent                  m_'+ key + '_agt;\n'
    line_arry += ' ' * 4 + block_name + '_rm' + '\t' * 6 + 'm_rm;\n'
    line_arry += ' ' * 4 + block_name + '_checker' + ' ' * 17 + 'm_scb;\n'
    line_arry += ' ' * 4 + 'bit' + '\t' * 7 + 'm_env_cfg_done;\n'
    line_arry += ' ' * 4 + 'bit' + '\t' * 7 + 'm_env_main_phase_done;\n\n'
    line_arry += ' ' * 4 + '//dec connect to rm fifo\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += ' ' * 4 + 'uvm_tlm_analysis_fifo#('+'uvm_sequence_item)   m_'+key+'_agt_mon_to_rm_fifo;\n'
    line_arry += ' ' * 4 + '//dec connect to scb fifo\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_PASSIVE':
            line_arry += ' ' * 4 + 'uvm_tlm_analysis_fifo#('+'uvm_sequence_item)   m_rm_'+key+'_trans_to_scb_fifo;\n'
            line_arry += ' ' * 4 + 'uvm_tlm_analysis_fifo#('+'uvm_sequence_item)   m_agt_' + key + '_trans_to_scb_fifo;\n'
    line_arry += ' ' * 4 + block_name + '_vsqr' +'\t'*5 + 'm_vsqr;\n'
    line_arry += ' ' * 4 + '//xxx_blk_ral' + '\t'*4 + 'm_ral;\n'
    line_arry += ' ' * 4 + '//xxx_adapter' + '\t' * 4 + 'm_adapter;\n'
    line_arry += ' ' * 4 + '//END_DEC_ENV_MEMBER\n\n'
    line_arry += ' ' * 4 + 'extern function new (string name=\"' + block_name +'_env\",uvm_component parent = null);\n'
    line_arry += ' ' * 4 + 'extern virtual function void build_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'extern virtual function void connect_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'extern virtual function void end_of_elaboration_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void start_of_simulation_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task run_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_reset_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_reset_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_configure_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task configure_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_configure_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_main_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'extern virtual task main_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_main_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_shutdown_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task shutdown_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_shutdown_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void extract_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void check_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'extern virtual function void report_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void final_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void pre_abort();\n'
    line_arry += ' ' * 4 + 'extern virtual function int  get_env_quit_control_cnt();\n'
    line_arry += ' ' * 4 + 'extern virtual function void end_of_simulation_chk();\n'
    line_arry += '\nendclass\n\n'

    #new create
    line_arry += 'function '+block_name+'_env::new(string name = \"'+block_name+'_env\", uvm_component parent);\n'
    line_arry += ' ' * 4 + 'super.new(name,parent);\n'
    line_arry += 'endfunction\n\n'

    #build_phase create
    line_arry += 'function void ' + block_name + '_env::build_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'super.build_phase(phase);\n'
    line_arry += ' ' * 4 + '`uvm_info(get_full_name(),\"function phase build_phase start\",UVM_NONE);\n'
    line_arry += ' ' * 4 + 'if( this.m_cfg == null) begin\n'
    line_arry += ' ' * 8 + '`uvm_info(get_full_name(),\"tc use default env_cfg,just create it by env itself\",UVM_NONE);\n'
    line_arry += ' ' * 8 + 'this.m_cfg = '+ block_name +'_env_cfg::type_id::create(\"m_cfg\",this);\n'
    line_arry += ' ' * 8 + 'if( !this.m_cfg.randomize() ) begin\n'
    line_arry += ' ' * 12 + 'this.m_cfg.print();\n'
    line_arry += ' ' * 12 + '`uvm_fatal(get_full_name(),\"env_cfg set is error!!!\");\n'
    line_arry += ' ' * 8 + 'end\n'
    line_arry += ' ' * 4 + 'end\n\n'
    line_arry += ' ' * 4 + '//create agents\n'
    for key,value in agent_arry.items() :
        line_arry += ' ' * 4 + 'm_'+key+'_agt = '+ key + '_agent::type_id::create(\"m_'+key+'_agt\",this);\n'
    line_arry += ' ' * 4 + '//agt cfg connect to env_cfg,to decide agt work mode\n'
    for key,value in agent_arry.items() :
        line_arry += ' ' * 4 + 'm_'+key+'_agt.m_cfg = m_cfg.m_'+ key + '_agt_cfg;\n'
    line_arry += ' ' * 4 + '//create rm and scb\n'
    line_arry += ' ' * 4 + 'm_rm    = ' + block_name + '_rm::type_id::create(\"m_rm\",this);\n'
    line_arry += ' ' * 4 + 'm_scb   = ' + block_name + '_checker::type_id::create(\"m_scb\",this);\n\n'
    line_arry += ' ' * 4 + 'm_vsqr  = ' + block_name + '_vsqr::type_id::create(\"m_vsqr\",this);\n\n'
    line_arry += ' ' * 4 + 'm_env_cfg_done = 0;\n'
    line_arry += ' ' * 4 + 'm_env_main_phase_done = 0;\n\n'
    line_arry += ' ' * 4 + '//new connect to rm fifo;\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += ' ' * 4 + 'm_'+key+'_agt_mon_to_rm_fifo = new($sformatf(\"m_'+key+'_agt_mon_to_rm_fifo\"),this);\n'
    line_arry += ' ' * 4 + '//new connect to scb fifo;\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_PASSIVE':
            line_arry += ' ' * 4 + 'm_rm_'+key+'_trans_to_scb_fifo= new($sformatf(\"m_rm_'+key+'_trans_to_scb_fifo\"),this);\n'
            line_arry += ' ' * 4 + 'm_agt_' + key + '_trans_to_scb_fifo= new($sformatf(\"m_agt_' + key + '_trans_to_scb_fifo\"),this);\n'
    line_arry += ' ' * 4 + '//ral create\n'
    line_arry += ' ' * 4 + '//if( m_ral == null ) begin;\n'
    line_arry += ' ' * 8 + '//`uvm_info(get_full_name(),\"ral is not create,just create it by env itself\",UVM_NONE);\n'
    line_arry += ' ' * 8 + '//m_ral = xxx_blk_ral::type_id::create(\"m_ral\",this);\n'
    line_arry += ' ' * 8 + '//m_ral.configure(null,\"\");\n'
    line_arry += ' ' * 8 + '//m_ral.build();\n'
    line_arry += ' ' * 8 + '//m_ral.lock_model();\n'
    line_arry += ' ' * 8 + '//m_ral.reset();\n'
    line_arry += ' ' * 8 + '//m_ral.set_hdl_path_root(\"harness._xxx_.xxx_cfg\");\n'
    line_arry += ' ' * 8 + '//m_adapter = new(\"m_adapter\");\n'
    line_arry += ' ' * 4 + '//end\n\n'
    line_arry += 'endfunction\n\n'

    #end_of_elaboration_phase create
    line_arry += 'function void ' + block_name + '_env::end_of_elaboration_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'super.end_of_elaboration_phase(phase);\n'
    line_arry += ' ' * 4 + '`uvm_info(get_full_name(),\"function phase end_of_elaboration_phase start\",UVM_NONE);\n'
    line_arry += ' ' * 4 + 'uvm_top.print_topology();\n'
    line_arry += 'endfunction\n\n'

    #connect_phase create
    line_arry += 'function void ' + block_name + '_env::connect_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'super.connect_phase(phase);\n'
    line_arry += ' ' * 4 + '`uvm_info(get_full_name(),\"function phase connect_phase start\",UVM_NONE);\n'
    line_arry += ' ' * 4 + '//connect to rm fifo;\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += ' ' * 4 + 'm_'+key+'_agt.m_mon.m_ap.connect(m_'+key+'_agt_mon_to_rm_fifo.analysis_export);\n'
            line_arry += ' ' * 4 + 'm_rm.m_from_'+key+'_agt_mon_port.connect(m_'+key+'_agt_mon_to_rm_fifo.blocking_get_export);\n\n'  # to do

    line_arry += ' ' * 4 + '//connect to scb fifo;\n\n' #to do
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_PASSIVE':
            line_arry += ' ' * 4 + 'm_rm.m_rm_'+key+'_trans_to_scb_port.connect(m_rm_'+key+'_trans_to_scb_fifo.analysis_export);//rm\n'  # to do
            line_arry += ' ' * 4 + 'm_scb.m_from_rm_' + key + '_trans_port.connect(m_rm_' + key + '_trans_to_scb_fifo.blocking_get_export);//rm\n'  # to do
            line_arry += ' ' * 4 + 'm_' + key + '_agt.m_mon.m_ap.connect(m_agt_' + key + '_trans_to_scb_fifo.analysis_export);//dut\n'  # to do
            line_arry += ' ' * 4 + 'm_scb.m_from_agt_' + key + '_trans_port.connect(m_agt_' + key + '_trans_to_scb_fifo.blocking_get_export);//dut\n'  # to do
    line_arry += ' ' * 4 + '//connect vsqr;\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += ' ' * 4 + 'm_vsqr.m_'+key+'_sqr = this.m_'+key+'_agt.m_sqr;\n' #to do
    line_arry += ' ' * 4 + '//if( this.m_cfg.m_is_reuse_by_top == 0) begin;\n'
    line_arry += ' ' * 8 + '//m_ral.default_map.set_sequencer(xxx.m_sqr,m_adapter);\n'
    line_arry += ' ' * 8 + '//m_ral.default_map.set_auto_predict(1);\n'
    line_arry += ' ' * 4 + '//end\n'
    line_arry += 'endfunction\n\n'

    # main_phase create
    line_arry += 'task ' + block_name + '_env::main_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'int i,j,k;\n'
    line_arry += ' ' * 4 + 'int wait_times;\n'
    line_arry += ' ' * 4 + 'int pre_get_cnt,get_cnt;\n'
    line_arry += ' ' * 4 + 'wait_times = 0;\n'
    line_arry += ' ' * 4 + 'pre_get_cnt = 0;\n'
    line_arry += ' ' * 4 + 'get_cnt = 0;\n'
    line_arry += ' ' * 4 + 'phase.raise_objection(this);\n'
    line_arry += ' ' * 4 + 'super.main_phase(phase);\n'
    line_arry += ' ' * 4 + '`uvm_info(get_full_name(),\"task phase main_phase start\",UVM_NONE);\n'
    line_arry += ' ' * 4 + 'while( m_cfg.m_is_reuse_by_top == 0) begin\n'
    line_arry += ' ' * 8 + 'repeat( m_cfg.m_quit_cnt_interval) @(m_'+tmp_agent_name+'_agt.m_mon.m_vif.mon_cb);\n' #to do
    line_arry += ' ' * 8 + 'wait_times++;\n'
    line_arry += ' ' * 8 + 'get_cnt = this.get_env_quit_control_cnt();\n'
    line_arry += ' ' * 8 + 'if( pre_get_cnt != get_cnt ) begin\n'
    line_arry += ' ' * 12 + 'pre_get_cnt = get_cnt;\n'
    line_arry += ' ' * 12 + 'wait_times = 0;\n'
    line_arry += ' ' * 8 + 'end\n'
    line_arry += ' ' * 8 + 'if( wait_times > 2) begin\n'
    line_arry += ' ' * 12 + '`uvm_info(get_full_name(),\"no trans cnt change,env main phase done\",UVM_NONE);\n'
    line_arry += ' ' * 12 + 'break;\n'
    line_arry += ' ' * 8 + 'end\n'
    line_arry += ' ' * 4 + 'end\n'
    line_arry += ' ' * 4 + 'm_env_main_phase_done = 1;\n'
    line_arry += ' ' * 4 + 'phase.drop_objection(this);\n'
    line_arry +=  'endtask\n\n'

    # report_phase create
    line_arry += 'function void ' + block_name + '_env::report_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'super.report_phase(phase);\n'
    # to do
    line_arry += 'endfunction\n\n'

    # quit_control create
    line_arry += 'function int ' + block_name + '_env::get_env_quit_control_cnt();\n'
    line_arry += ' ' * 4 + 'int ret_cnt;\n'
    line_arry += ' ' * 4 + 'ret_cnt = 0;\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += ' ' * 4 + 'ret_cnt = ret_cnt + m_'+key+'_agt.get_drv_mon_trans_cnt();\n' #to do
    line_arry += ' ' * 4 + 'ret_cnt = ret_cnt + m_scb.m_scb_rec_rm_trans_total_cnt;\n'
    line_arry += ' ' * 4 + 'ret_cnt = ret_cnt + m_scb.m_scb_rec_dut_trans_total_cnt;\n'
    line_arry += ' ' * 4 + 'return ret_cnt;\n'
    line_arry += 'endfunction\n\n'

    # end_of_simulation create
    line_arry += 'function void ' + block_name + '_env::end_of_simulation_chk();\n'
    #to do
    line_arry += 'endfunction\n\n'

    #end of env
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_env_cfg(prj_name,author_name,file_path,block_name,agent_arry):

    init_path = os.path.join(file_path, block_name + '_env_cfg.sv')
    env_file = open(init_path,'w',encoding='utf-8')

    line_arry = ''
    file_name = block_name + '_env_cfg.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + block_name.upper() + '_ENV_CFG__SV\n'
    line_arry += '`define  ' + block_name.upper() + '_ENV_CFG__SV' + '\n'*3
    line_arry += 'class '+block_name+'_env_cfg extends uvm_object;\n'
    line_arry += ' ' * 4 + '     bit                     m_quit_cnt_interval;\n'
    line_arry += ' ' * 4 + 'rand bit                     m_is_reuse_by_top;\n'
    for key,value in agent_arry.items() :
        line_arry += ' ' * 4 + 'rand '+key+'_agt_cfg            m_'+key+'_agt_cfg;\n'
    line_arry += ' ' * 4 + '`uvm_object_utils_begin(' + block_name + '_env_cfg)\n'
    line_arry += ' ' * 8 + '`uvm_field_int(m_is_reuse_by_top,  UVM_ALL_ON);\n'
    for key, value in agent_arry.items():
        line_arry += ' ' * 8 + '`uvm_field_object(m_'+key+'_agt_cfg,   UVM_ALL_ON);\n'
    line_arry += ' ' * 4 + '`uvm_object_utils_end\n\n'
    line_arry += '    constraint is_reuse_by_top_cons{\n' \
                 '        soft m_is_reuse_by_top == 0;\n' \
                 '    }\n\n'
    line_arry += '    constraint agt_cfg_cons {\n' \
                 '        if(m_is_reuse_by_top == 0) {\n'
    for key,value in agent_arry.items() :
        line_arry += '            m_'+key+'_agt_cfg.m_is_active == '+value.upper()+';\n'
    line_arry += '        }\n' \
                 '        else {\n'
    for key,value in agent_arry.items() :
        line_arry += '            m_'+key+'_agt_cfg.m_is_active == UVM_PASSIVE;\n'
    line_arry += '         }\n' \
                 '    }\n'
    line_arry += '    function new(string name = \"'+block_name+'_env_cfg\");\n' \
                 '        super.new(name);\n' \
                 '        this.m_quit_cnt_interval = 300;\n'
    for key, value in agent_arry.items():
        line_arry += '        m_'+key+'_agt_cfg = new(\"m_'+key+'_agt_cfg\");\n'
    line_arry += '    endfunction\n\n'
    line_arry += 'endclass\n'

    # end of env_cfg
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()


def gen_uvm_rm(prj_name,author_name,file_path,block_name,agent_arry):

    init_path = os.path.join(file_path, block_name + '_rm.sv')
    env_file = open(init_path,'w',encoding='utf-8')

    line_arry = ''
    file_name = block_name + '_rm.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + block_name.upper() + '_RM__SV\n'
    line_arry += '`define  ' + block_name.upper() + '_RM__SV' + '\n'*3
    line_arry += 'class '+block_name+'_rm extends uvm_component;\n\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_begin(' + block_name + '_rm)\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_end\n\n'
    line_arry += '    //dec common rm member\n\n'
    line_arry += '    //dec in_port\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += ' ' * 4 + 'uvm_blocking_get_port#('+'uvm_sequence_item)   m_from_'+key+'_agt_mon_port;\n\n'  # to do

    line_arry += '    //dec out_port\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_PASSIVE':
            line_arry += ' ' * 4 + 'uvm_analysis_port#('+'uvm_sequence_item)       m_rm_'+key+'_trans_to_scb_port;\n\n'  # to do
    line_arry += '    extern function new(string name,uvm_component parent);\n' \
                 '    extern virtual function void build_phase(uvm_phase phase);\n' \
                 '    extern virtual task run_phase(uvm_phase phase);\n\n'
    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += '    extern virtual task process_trans_from_'+key+'_agt();\n'

    line_arry += '    extern virtual task fork_rec_trans_task();\n\n' \
                 'endclass\n\n' \
                 'function ' + block_name+'_rm::new(string name,uvm_component parent);\n' \
                 '    super.new(name,parent);\n' \
                 'endfunction\n\n'
    line_arry += 'function void ' + block_name+'_rm::build_phase(uvm_phase phase);\n'
    line_arry += '    super.build_phase(phase);\n'

    for key,value in agent_arry.items() :
        if value.upper() == 'UVM_ACTIVE':
            line_arry += ' ' * 4 + 'm_from_'+key+'_agt_mon_port = new(\"m_from_' + key + '_agt_mon_port\",this);\n'
        elif value.upper() == 'UVM_PASSIVE':
            line_arry += ' ' * 4 + 'm_rm_'+key+'_trans_to_scb_port = new(\"m_rm_'+key+'_trans_to_scb_port\",this);\n'
    line_arry += 'endfunction\n\n'
    line_arry += 'task ' + block_name + '_rm::run_phase(uvm_phase phase);\n'
    line_arry += '    fork\n' \
                 '        this.fork_rec_trans_task();\n' \
                 '    join\n' \
                 'endtask\n\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_ACTIVE':
            line_arry += 'task ' + block_name + '_rm::process_trans_from_'+key+'_agt();\n'
            line_arry += '    uvm_sequence_item     get_tr;\n' \
                         '    '+key+'_trans    tr;\n' \
                         '    `uvm_info(get_full_name(),\"process_trans_from_'+key+'_agt start\",UVM_NONE);\n' \
                         '    while(1) begin\n' \
                         '        this.m_from_'+key+'_agt_mon_port.get(get_tr);\n' \
                         '        if( !$cast(tr,get_tr) ) begin\n' \
                         '            `uvm_fatal(get_full_name(),$sformatf(\"trans type should be '+key+'_tr\"));\n' \
                         '        end\n' \
                         '    end\n' \
                         'endtask\n\n'
    line_arry += 'task ' + block_name + '_rm::fork_rec_trans_task();\n'
    line_arry += '    fork\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_ACTIVE':
            line_arry += '        this.process_trans_from_'+key+'_agt();\n'
    line_arry += '    join_none\n'
    line_arry +='endtask\n\n'
    # end of rm
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()


def gen_uvm_checker(prj_name,author_name,file_path,block_name,agent_arry):

    init_path = os.path.join(file_path, block_name + '_checker.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = block_name + '_checker.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + block_name.upper() + '_CHECKER__SV\n'
    line_arry += '`define  ' + block_name.upper() + '_CHECKER__SV' + '\n'*3
    line_arry += 'class '+block_name+'_checker extends uvm_scoreboard;\n\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_begin(' + block_name + '_checker)\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_end\n\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            line_arry += '    int                   m_from_rm_'+key+'_trans_cnt;\n' \
                         '    int                   m_from_dut_'+key+'_trans_cnt;\n'
    line_arry += '    int                   m_scb_rec_rm_trans_total_cnt;\n' \
                 '    int                   m_scb_rec_dut_trans_total_cnt;\n'
    line_arry += '    //dec rm get port\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            line_arry += '    uvm_blocking_get_port#('+'uvm_sequence_item)    m_from_rm_'+key+'_trans_port;//get from rm\n'

    line_arry += '    //dec dut get port\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            line_arry += '    uvm_blocking_get_port#('+'uvm_sequence_item)    m_from_agt_'+key+'_trans_port;//get from dut\n'

    line_arry += '    //dec agt common scb\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            line_arry += '    common_uvm_scb#('+key+'_trans)           m_'+key+'_trans_scb;\n'

    line_arry += '    extern function new(string name,uvm_component parent = null);\n' \
                 '    extern task fork_checker_rec_trans_task();\n' \
                 '    extern virtual task run_phase(uvm_phase phase);\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            line_arry += '    extern task process_'+key+'_trans_from_rm();\n'
            line_arry += '    extern task process_'+key+'_trans_from_agt();\n'

    line_arry += 'endclass\n\n' \
                 'function ' + block_name+'_checker::new(string name,uvm_component parent = null);\n' \
                 '    super.new(name,parent);\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            line_arry += '    m_from_rm_'+key+'_trans_cnt = 0;\n' \
                         '    m_from_dut_'+key+'_trans_cnt = 0;\n'
    line_arry += '    m_scb_rec_rm_trans_total_cnt  = 0;\n' \
                 '    m_scb_rec_dut_trans_total_cnt = 0;\n' \
                 'endfunction\n\n'
    line_arry += 'task ' + block_name + '_checker::run_phase(uvm_phase phase);\n' \
                 '    super.run_phase(phase);\n' \
                 '    `uvm_info(get_full_name,\"scb run phase start\",UVM_NONE);\n' \
                 '    fork\n' \
                 '        this.fork_checker_rec_trans_task();\n' \
                 '    join_none\n' \
                 'endtask\n\n'
    i = 0
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            if i == 0 :
                line_arry += 'task ' + block_name+'_checker::process_'+key+'_trans_from_rm();\n'
            line_arry += '    '+key+'_trans tr;\n' 
            line_arry += '    '+'uvm_sequence_item get_'+key+'_tr;\n' 
            if i == 0:
                line_arry += '    `uvm_info(get_full_name,$sformatf(\"process_'+key+'_trans_from_rm start\"),UVM_NONE);\n'
            line_arry += '    while(1) begin\n' \
                         '        this.m_from_rm_'+key+'_trans_port.get(get_'+key+'_tr);\n' \
                         '        if(!$cast(tr,get_'+key+'_tr)) begin\n' \
                         '            `uvm_fatal(get_full_name,\"trans_type from rm should be '+key+'_trans\");\n' \
                         '        end\n' \
                         '        this.m_from_rm_'+key+'_trans_cnt++;\n' \
                         '        this.m_scb_rec_rm_trans_total_cnt++;\n' \
                         '        m_'+key+'_trans_scb.send_rm_trans_to_cmp(tr);\n' \
                         '    end\n'
            i = i+ 1
    if(i>0):
        line_arry += 'endtask\n\n'
    i = 0
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            if i == 0:
                line_arry += 'task ' + block_name + '_checker::process_'+key+'_trans_from_agt();\n'
            line_arry += '    ' + key + '_trans tr;\n'
            line_arry += '    '+'uvm_sequence_item get_'+key+'_tr;\n' 
            if i == 0:
                line_arry += '    `uvm_info(get_full_name,$sformatf(\"process_'+key+'_trans_from_agt start\"),UVM_NONE);\n'
            line_arry += '    while(1) begin\n' \
                         '        this.m_from_agt_' + key + '_trans_port.get(get_'+key+'_tr);\n' \
                         '        if(!$cast(tr,get_'+key+'_tr)) begin\n' \
                         '            `uvm_fatal(get_full_name,\"trans_type from agt should be '+key+'_trans\");\n' \
                         '        end\n' \
                         '        this.m_from_dut_' + key + '_trans_cnt++;\n' \
                         '        this.m_scb_rec_dut_trans_total_cnt++;\n' \
                         '        m_' + key + '_trans_scb.send_dut_trans_to_cmp(tr);\n' \
                         '    end\n'
            i = i+1
    if(i>0):
        line_arry += 'endtask\n\n'
    line_arry += 'task ' + block_name+'_checker::fork_checker_rec_trans_task();\n' \
                 '    fork\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_PASSIVE':
            line_arry += '        this.process_'+key+'_trans_from_rm();\n'
            line_arry += '        this.process_'+key+'_trans_from_agt();\n'
    line_arry += '    join_none\n' \
                 'endtask\n\n'

    # end of checker
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_vsqr(prj_name,author_name,file_path,block_name,agent_arry):

    init_path = os.path.join(file_path, block_name + '_vsqr.sv')
    env_file = open(init_path,'w',encoding='utf-8')

    line_arry = ''
    file_name = block_name + '_vsqr.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + block_name.upper() + '_VSQR__SV\n'
    line_arry += '`define  ' + block_name.upper() + '_VSQR__SV' + '\n'*3
    line_arry += 'class '+block_name+'_vsqr extends uvm_sequencer;\n\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_begin(' + block_name + '_vsqr)\n'
    line_arry += ' ' * 4 + '`uvm_component_utils_end\n\n'
    line_arry += '    //dec agt_sqr\n\n'
    for key, value in agent_arry.items():
        if value.upper() == 'UVM_ACTIVE':
            line_arry += '    '+key+'_sqr               m_'+key+'_sqr;\n'
    line_arry += '    extern function new(string name,uvm_component parent = null);\n' \
                 'endclass\n\n' \
                 'function ' + block_name+'_vsqr::new(string name,uvm_component parent = null);\n' \
                 '    super.new(name,parent);\n' \
                 'endfunction\n\n'
    # end of vsqr
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_harness(prj_name,author_name,file_path,block_name,agent_arry):

    init_path = os.path.join(file_path , 'harness.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = 'harness.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + 'HARNESS__SV\n'
    line_arry += '`define  ' + 'HARNESS__SV' + '\n'*3
    line_arry += 'module    harness;\n\n' \
                 '//reg clk;\n' \
                 'reg rst_n;\n' \
                 '`CLK_GEN(clk,5,1);\n\n' \
                 '//init dut here\n' \
                 '//xxx_module_top UDT(\n' \
                 '//        .clk(clk),\n' \
                 '//        .rst_n(rst_n)\n' \
                 '//                  };\n\n' \
                 '//dec agt interface here\n' 
    for key, value in agent_arry.items():
        line_arry += '    '+key+'_if               m_'+key+'_if(clk,rst_n);\n'
    line_arry +='initial begin\n' 
    for key, value in agent_arry.items():
        line_arry += '    uvm_config_db#(virtual '+key+'_if)::set(null,\"uvm_test_top.m_env.m_'+key+'_agt*\",\"m_vif\",m_'+key+'_if);\n' 

    line_arry += 'end\n\n' \
                 'initial begin\n' \
                 '    run_test();\n' \
                 'end\n\n' \
                 'initial begin\n' \
                 '    bit wave_enable;\n' \
                 '    string tc_name;\n' \
                 '    if($value$plusargs(\"wave_en=%0b\",wave_enable)) begin\n' \
                 '        if(wave_enable == 1) begin\n' \
                 '            $value$plusargs(\"UVM_TESTNAME=%s\",tc_name);\n' \
                 '            $display(\"start to dump %s wave at time=%0t\",tc_name,$time);\n' \
                 '            $fsdbDumpfile($sformatf(\"./wave/%s.fsdb\",tc_name));\n' \
                 '            $fsdbDumpvars();\n' \
                 '        end\n' \
                 '    end\n' \
                 'end\n\n' \
                 'endmodule\n' \
    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_tc_file(prj_name,author_name,file_path,block_name):
    #add tc.f
    tc_path = os.path.join(file_path, 'tc.f')
    tc_file = open(tc_path, 'w', encoding='utf-8')
    tc_file.write('//add your testcase name here!\n')
    tc_file.write('../tc/tc_base.sv\n')
    tc_file.write('../tc/tc_sanity.sv\n')
    tc_file.close()
    #add tc_base.sv
    init_path = os.path.join(file_path, 'tc_base.sv')
    env_file = open(init_path, 'w', encoding='utf-8')
    line_arry = ''
    file_name = 'tc_base.sv'
    line_arry += gen_description(prj_name, author_name, file_name)
    line_arry += '`ifndef  ' + 'TC_BASE__SV\n'
    line_arry += '`define  ' + 'TC_BASE__SV' + '\n' * 3
    line_arry += 'class tc_base extends uvm_test;\n\n' \
                 '    `uvm_component_utils(tc_base)\n' \
                 '    '+ block_name+'_env           m_env;\n\n'\
                 '    function new(string name=\"tc_base\",uvm_component parent=null);\n' \
                 '        common_report_server my_server;\n' \
                 '        super.new(name,parent);\n' \
                 '        $timeformat(-9,2,\"ns\",12);\n' \
                 '        my_server = new();\n' \
                 '        uvm_report_server::set_server(my_server);\n' \
                 '    endfunction\n\n'
    line_arry += ' ' * 4 + 'extern virtual function void build_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void connect_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void end_of_elaboration_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void start_of_simulation_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task run_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_reset_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'extern virtual task reset_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_reset_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_configure_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task configure_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_configure_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_main_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task main_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_main_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task pre_shutdown_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task shutdown_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual task post_shutdown_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void extract_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void check_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'extern virtual function void report_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + '//extern virtual function void final_phase(uvm_phase phase);\n'
    line_arry += ' ' * 4 + 'extern virtual function void pre_abort();\n\n'
    line_arry += 'endclass\n\n'

    line_arry += 'function void tc_base::build_phase(uvm_phase phase);\n' \
                 '    super.build_phase(phase);\n' \
                 '    m_env = ' + block_name +'_env::type_id::create(\"m_env\",this);\n' \
                 'endfunction\n\n'
    line_arry += 'task tc_base::reset_phase(uvm_phase phase);\n' \
                 '    int i,j,k;\n' \
                 '    phase.raise_objection(this);\n' \
                 '    super.reset_phase(phase);\n' \
                 '    i = $urandom_range(3,10);\n' \
                 '    if(($urandom()%2) == 1) begin\n' \
                 '        harness.rst_n = 1\'b1;\n' \
                 '    end\n' \
                 '    else begin\n' \
                 '        harness.rst_n = 1\'b0;\n' \
                 '    end\n' \
                 '    repeat(i) @(posedge harness.clk);\n' \
                 '    harness.rst_n = 1\'b0;\n' \
                 '    i = $urandom_range(10,20);\n' \
                 '    repeat(i) @(posedge harness.clk);\n' \
                 '    harness.rst_n = 1\'b0;\n' \
                 '    repeat(10) @(posedge harness.clk);\n' \
                 '    phase.drop_objection(this);\n' \
                 'endtask\n\n'
    line_arry += 'function void tc_base::report_phase(uvm_phase phase);\n' \
                '    uvm_report_server  server;\n' \
                '    int  err_num,war_num,fatal_num;\n' \
                '    super.report_phase(phase);\n\n' \
                '    server     = get_report_server();\n' \
                '    server.enable_report_id_count_summary = 0; //set fianl info print message 0;\n\n' \
                '    err_num    = server.get_severity_count(UVM_ERROR);\n' \
                '    war_num    = server.get_severity_count(UVM_WARNING);\n' \
                '    fatal_num  = server.get_severity_count(UVM_FATAL);\n\n' \
                '    if((err_num!=0)||(fatal_num!=0)) begin\n' \
                '         $display(\"TC FAILED.(warning:%0d,error:%0d,fatal:%0d)\",war_num,err_num,fatal_num);\n' \
                '    end\n' \
                '    else begin\n' \
                '         $display(\"TC PASSED.(warning:%0d,error:%0d,fatal:%0d)\",war_num,err_num,fatal_num);\n' \
                '    end\n' \
                'endfunction\n\n'
    line_arry += 'function void tc_base::pre_abort();\n' \
                 '    this.extract_phase(null);\n' \
                 '    this.report_phase(null);\n' \
                 'endfunction\n\n'
    # end of tc_base
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

    #add tc_sanity.sv
    init_path1 = os.path.join(file_path, 'tc_sanity.sv')
    env_file1 = open(init_path1, 'w', encoding='utf-8')
    line_arry = ''
    file_name = 'tc_sanity.sv'
    line_arry += gen_description(prj_name, author_name, file_name)
    line_arry += '`ifndef  ' + 'TC_SANITY__SV\n'
    line_arry += '`define  ' + 'TC_SANITY__SV' + '\n' * 3

    # end of tc_base
    line_arry += '`endif\n'
    env_file1.write(line_arry)
    env_file1.close()

def gen_uvm_common_lib_pkg(prj_name,author_name,file_path,block_name):
    # add agent.f
    path = os.path.join(file_path,'common_lib_pkg.f')
    path = open(path, 'w', encoding='utf-8')
    path.write('+incdir+./\n')
    path.write('./common_lib_pkg.sv\n')

    path.close()

    init_path = os.path.join(file_path , 'common_lib_pkg.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    line_arry += '`ifndef  ' + 'COMMON_LIB_PKG__SV\n'
    line_arry += '`define  ' + 'COMMON_LIB_PKG__SV' + '\n' * 3
    line_arry += 'package       ' + 'common_lib_pkg;\n\n' \
                 '    timeunit      1ns;\n' \
                 '    timeprecision 1ps;\n' \
                 '    import uvm_pkg::*;\n\n' \
                 '    `include \"' + 'common_dec.sv\"\n' \
                 '    `include \"' + 'common_draw_table.sv\"\n' \
                 '    `include \"' + 'common_report_server.sv\"\n' \
                 '    `include \"' + 'common_self_debug_scb.sv\"\n' \
                 '    `include \"' + 'common_uvm_scb.sv\"\n\n' \
                 'endpackage\n\n' \
                 'import uvm_pkg::*;\n\n' \
                 'import common_lib_pkg::*;\n\n' \

    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()


def gen_uvm_common_dec(prj_name,author_name,file_path,block_name):

    init_path = os.path.join(file_path , 'common_dec.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = 'common_dec.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + 'COMMON_DEC__SV\n'
    line_arry += '`define  ' + 'COMMON_DEC__SV' + '\n'*3
    line_arry += '`define CLK_GEN(CLK,HALF_PERIED,OFFSET) \\\n' \
                 'reg CLK; \\\n' \
                 'initial begin: ``CLK``_gen \\\n' \
                 '    CLK <= 0;\\\n' \
                 '    #OFFSET;\\\n' \
                 '    forever # HALF_PERIED CLK = ~CLK; \\\n' \
                 'end\n\n' \
                 '`define RST_GEN(RST_N,EN_DLY) \\\n' \
                 'reg RST_N; \\\n' \
                 'initial begin: ``RST_N``_gen\\\n' \
                 '    RST_N <= \'0; \\\n' \
                 '    #EN_DLY; \\\n' \
                 '    RST_N <= \'1; \\\n' \
                 'end\n\n'

    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_makefile(prj_name,author_name,file_path,block_name):

    init_path = os.path.join(file_path , 'Makefile')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = 'Makefile'
   # line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += 'all: clean cmp run\n' 
    line_arry += 'cmp_run: cmp run\n\n\n' \
                 'tc=tc_sanity\n' \
                 'wave_en=0\n' \
                 'wave=tc_sanity\n' \
                 'info_leverl=UVM_HIGH\n\n' \
                 'cmp:\n' \
                 '\tvcs -full64 -sverilog +incdir+. +define+UVM_NODEPRECATED -timescale=1ns/1ps' \
                 ' -lca -kdb -debug_access+all \\\n' \
                 '\t-cpp g++ -cc gcc -LDFLAGS -Wl,--no-as-needed \\\n' \
                 '\t-P $(VERDI_HOME)/share/PLI/VCS/LINUX64/novas.tab $(VERDI_HOME)/share/PLI/VCS/LINUX64/pli.a \\\n' \
                 '\t-ntb_opts uvm-1.1 -F ../cfg/tb.f -l ./log/comp.log\n\n' \
                 'run:\n' \
                 '\t./simv +UVM_NO_RELNOTES -l ./log/$(tc).log +UVM_TESTNAME=$(tc) +UVM_VERBOSITY=$(info_level) +wave_en=$(wave_en)\n\n' \
                 'clean:\n' \
                 '\trm -rf comp.log csrc/ *.log novas.conf novas_dump.log novas.fsdb novas.rc simv* simv.daidir/ ucli.key vc_hdr.h verdilog/\n\n' \
                 'clean_all:\n' \
                 '\trm -rf comp.log csrc/ *.log novas.conf novas_dump.log novas.fsdb novas.rc simv* simv.daidir/ ucli.key vc_hdr.h verdilog/ ./log/*.log ./wave/*.fsdb\n\n' \
                 'verdi:\n' \
                 '\tverdi -ssf ./wave/$(wave).fsdb -nologo &\n\n'


    # end of harness
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_common_report_server(prj_name,author_name,file_path,block_name):

    init_path = os.path.join(file_path , 'common_report_server.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = 'common_report_server.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + 'COMMON_REPORT_SERVER__SV\n'
    line_arry += '`define  ' + 'COMMON_REPORT_SERVER__SV' + '\n'*3
    line_arry += 'class common_report_server extends uvm_report_server;\n' \
                 '    virtual function string compose_message(uvm_severity severity,\n' \
                 '                                            string   name,\n' \
                 '                                            string   id,\n' \
                 '                                            string   message,\n' \
                 '                                            string   filename,\n' \
                 '                                            int      line);\n' \
                 '        uvm_severity_type severity_type = uvm_severity_type\'(severity);\n' \
                 '        if(severity_type == UVM_INFO) begin\n' \
                 '            if(name == id) begin\n' \
                 '                return $sformatf( \"%-8s @%t %s: %s\",severity_type.name(),$time,name,message);\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                return $sformatf( \"%-8s @%t %s [%s] : %s\",severity_type.name(),$time,name,id,message);\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else if((severity_type == UVM_WARNING) ||(severity_type == UVM_ERROR) ||(severity_type == UVM_FATAL))begin\n' \
                 '            if(name == id) begin\n' \
                 '                return $sformatf( \"%-8s %s(%0d) @%t %s: %s\",severity_type.name(),filename,line,$time,name,message);\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                return $sformatf( \"%-8s %s(%0d) @%t %s [%s]: %s\",severity_type.name(),filename,line,$time,name,id,message);\n' \
                 '            end\n' \
                 '        end\n' \
                 '    endfunction\n' \
                 'endclass\n\n' \

    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_common_self_debug_scb(prj_name,author_name,file_path,block_name):

    init_path = os.path.join(file_path , 'common_self_debug_scb.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = 'common_self_debug_scb.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + 'COMMON_SELF_DEBUG_SCB__SV\n'
    line_arry += '`define  ' + 'COMMON_SELF_DEBUG_SCB__SV' + '\n'*3
    line_arry += 'class self_debug_scb_demo_trans extends uvm_object;\n' \
                 '    int m_value;\n' \
                 '    function new(string name = \"self_debug_scb_demo_trans\");\n' \
                 '        super.new(name);\n' \
                 '    endfunction\n' \
                 '    function bit self_define_do_compare(self_debug_scb_demo_trans cmp_trans, output string diff, input int kind = -1);\n' \
                 '        return 1;\n' \
                 '    endfunction\n' \
                 'endclass\n' \
                 '\n\n' \
                 'class common_self_debug_scb #(type TRANS_TYPE = self_debug_scb_demo_trans ) extends uvm_component;\n' \
                 '    `uvm_component_param_utils_begin(common_self_debug_scb#(TRANS_TYPE))\n' \
                 '    `uvm_component_utils_end\n' \
                 '    int   m_from_mon_cnt;\n' \
                 '    int   m_from_drv_cnt;\n' \
                 '    int   m_cmp_pass_cnt;\n' \
                 '    string    diff;\n' \
                 '    TRANS_TYPE m_rm_pkt_q[bit[31:0]][$];\n' \
                 '    function new(string name=\"common_self_debug_scb\",uvm_component parent);\n' \
                 '        super.new(name,parent);\n' \
                 '        this.m_from_mon_cnt = 0;\n' \
                 '        this.m_from_drv_cnt = 0;\n' \
                 '        this.m_cmp_pass_cnt = 0;\n' \
                 '    endfunction\n\n' \
                 '    extern virtual function void report_phase(uvm_phase phase);\n\n' \
                 '    task send_rm_trans_to_cmp(TRANS_TYPE rm_tr,input bit[31:0] stream_id=-1,int kind=-1);\n' \
                 '        this.m_from_drv_cnt++;\n' \
                 '        this.m_rm_pkt_q[stream_id].push_back(rm_tr);\n' \
                 '    endtask\n\n' \
                 '    task send_dut_trans_to_cmp(TRANS_TYPE dut_tr,input bit[31:0] stream_id=-1,int kind=-1);\n' \
                 '        TRANS_TYPE rm_tr;\n' \
                 '        this.m_from_mon_cnt++;\n' \
                 '        diff = \"rm    vs    dut   \\n\";\n' \
                 '        if(m_rm_pkt_q[stream_id].size() == 0) begin\n' \
                 '            `uvm_fatal(get_full_name,$sformatf(\"stream_id=0x%0d drv send trans queue has been empty\",stream_id))\n' \
                 '        end\n' \
                 '        rm_tr = m_rm_pkt_q[stream_id].pop_front();\n' \
                 '        if(!rm_tr.self_define_do_compare(dut_tr,diff,kind)) begin\n' \
                 '            `uvm_error(get_full_name,$sformatf({\"\\n\",diff}));\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            this.m_cmp_pass_cnt++;\n' \
                 '        end\n' \
                 '    endtask\n' \
                 'endclass\n\n' \
                 'function void common_self_debug_scb::report_phase(uvm_phase phase);\n' \
                 '    string tmp_str;\n' \
                 '    super.report_phase(phase);\n' \
                 '    tmp_str = \"\\n\\ncommon debug scb report\\n\";\n' \
                 '    tmp_str = {tmp_str,$sformatf(\"m_from_drv_cnt=%0d\\n\",m_from_drv_cnt)};\n' \
                 '    tmp_str = {tmp_str,$sformatf(\"m_from_mon_cnt=%0d\\n\",m_from_mon_cnt)};\n' \
                 '    tmp_str = {tmp_str,$sformatf(\"m_cmp_pass_cnt=%0d\\n\",m_cmp_pass_cnt)};\n' \
                 '    `uvm_info(get_full_name,tmp_str,UVM_NONE);\n' \
                 '    foreach( this.m_rm_pkt_q[i] ) begin\n' \
                 '        if(this.m_rm_pkt_q[i].size()>0) begin\n' \
                 '            `uvm_error(get_full_name,$sformatf(\"stream_id=0x%0d still hase %0d pkt from drv to compare\",i,m_rm_pkt_q[i].size()));\n' \
                 '        end\n' \
                 '    end\n' \
                 'endfunction\n\n' \


    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()


def gen_uvm_common_scb(prj_name,author_name,file_path,block_name):

    init_path = os.path.join(file_path , 'common_uvm_scb.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = 'common_uvm_scb.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + 'COMMON_UVM_SCB__SV\n'
    line_arry += '`define  ' + 'COMMON_UVM_SCB__SV' + '\n'*3
    line_arry += 'class new_scb_demo_trans extends uvm_object;\n' \
                 '    `uvm_object_utils(new_scb_demo_trans)\n' \
                 '    int m_value;\n' \
                 '    function new(string name = \"new_scb_demo_trans\");\n' \
                 '        super.new(name);\n' \
                 '    endfunction\n' \
                 '    function bit self_define_do_compare(new_scb_demo_trans cmp_trans, output string diff, input int kind = -1);\n' \
                 '        return 1;\n' \
                 '    endfunction\n' \
                 'endclass\n' \
                 '\n\n' \
                 'typedef enum {ORDER_CMP_WITHOUT_LOSS,ORDER_CMP_WITH_LOSS,DISSORDER_CMP} scb_cmp_mode;\n\n' \
                 'class common_uvm_scb_cfg extends uvm_object;\n' \
                 '    scb_cmp_mode          m_cmp_mode;\n' \
                 '    bit                   m_allow_dut_faster_en;\n' \
                 '    int                   m_err_print_threadhold;\n' \
                 '    int                   m_cmp_pass_print_interval;\n' \
                 '    bit                   m_report_info_en;\n' \
                 '    bit                   m_report_stream_en;\n\n' \
                 '    `uvm_object_utils_begin(common_uvm_scb_cfg)\n' \
                 '        `uvm_field_enum(scb_cmp_mode,m_cmp_mode,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_allow_dut_faster_en,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_err_print_threadhold,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_cmp_pass_print_interval,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_report_info_en,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_report_stream_en,UVM_ALL_ON)\n' \
                 '    `uvm_object_utils_end\n\n' \
                 '    function new (string name = \"common_uvm_scb_cfg\");\n' \
                 '        super.new(name);\n' \
                 '        this.m_cmp_mode                = DISSORDER_CMP;\n' \
                 '        this.m_allow_dut_faster_en     = 0;\n' \
                 '        this.m_err_print_threadhold    = 3;\n' \
                 '        this.m_cmp_pass_print_interval = 100;\n' \
                 '        this.m_report_info_en          = 1;\n' \
                 '        this.m_report_stream_en        = 1;\n' \
                 '    endfunction:new\n\n' \
                 'endclass\n\n' \
                 'class stream_trans_manager#(parameter type TRANS_TYPE = new_scb_demo_trans,parameter stream_id_len=32) extends uvm_object;\n' \
                 '    `uvm_object_param_utils(stream_trans_manager#(TRANS_TYPE,stream_id_len))\n' \
                 '    bit[stream_id_len-1:0]        m_stream_id;\n' \
                 '    TRANS_TYPE                    m_rm_trans_q[$];\n' \
                 '    TRANS_TYPE                    m_dut_trans_q[$];\n' \
                 '    TRANS_TYPE                    m_dut_find_not_match_q[$];\n' \
                 '    int                           m_get_rm_trans_cnt;\n' \
                 '    int                           m_get_dut_trans_cnt;\n' \
                 '    int                           m_with_loss_dut_drop_cnt;\n' \
                 '    int                           m_not_match_pair_cnt;\n' \
                 '    int                           m_match_pair_cnt;\n' \
                 '    int                           m_print_err_cnt;\n\n' \
                 '    function new (string name = \"stream_trans_manager\");\n' \
                 '        super.new(name);\n' \
                 '        this.m_get_rm_trans_cnt       = 0;\n' \
                 '        this.m_get_dut_trans_cnt      = 0;\n' \
                 '        this.m_with_loss_dut_drop_cnt = 0;\n' \
                 '        this.m_not_match_pair_cnt     = 0;\n' \
                 '        this.m_match_pair_cnt         = 0;\n' \
                 '        this.m_print_err_cnt          = 0;\n' \
                 '    endfunction:new\n\n' \
                 '    function void report_info();\n' \
                 '        $display(\"================stream_id=0x%0h=================\",this.m_stream_id);\n' \
                 '        $display(\"m_get_rm_trans_cnt       = %0d\",this.m_get_rm_trans_cnt);\n' \
                 '        $display(\"m_get_dut_trans_cnt      = %0d\",this.m_get_dut_trans_cnt);\n' \
                 '        $display(\"m_match_pair_cnt         = %0d\",this.m_match_pair_cnt);\n' \
                 '        $display(\"m_with_loss_dut_drop_cnt = %0d\",this.m_with_loss_dut_drop_cnt);\n' \
                 '        $display(\"m_not_match_pair_cnt     = %0d\",this.m_not_match_pair_cnt);\n' \
                 '        $display(\"m_print_err_cnt          = %0d\",this.m_print_err_cnt);\n' \
                 '        $display(\"m_rm_trans_q.size        = %0d\",this.m_rm_trans_q.size());\n' \
                 '        $display(\"m_dut_trans_q.size       = %0d\",this.m_dut_trans_q.size());\n' \
                 '        $display(\"m_dut_find_not_match_q.size = %0d\",this.m_dut_find_not_match_q.size());\n' \
                 '        $display(\"================================================\");\n' \
                 '    endfunction:report_info\n\n' \
                 '    function string gen_report_info();\n' \
                 '        string ret_str;\n' \
                 '        ret_str = $sformatf(\"0x%0h %0d %0d %0d %0d %0d\",m_stream_id,m_match_pair_cnt,m_get_rm_trans_cnt' \
                 ',m_get_dut_trans_cnt,m_rm_trans_q.size(),m_dut_trans_q.size());\n' \
                 '        return ret_str;\n' \
                 '    endfunction\n\n' \
                 'endclass\n\n' \
                 'class common_uvm_scb#(parameter type TRANS_TYPE = new_scb_demo_trans,parameter stream_id_len=32) extends uvm_component;\n' \
                 '    common_uvm_scb_cfg    m_cfg;\n' \
                 '    int                   m_total_match_pair_cnt;\n' \
                 '    int                   m_get_rm_trans_cnt;\n' \
                 '    int                   m_get_dut_trans_cnt;\n' \
                 '    stream_trans_manager#(TRANS_TYPE,stream_id_len)   m_trans_array[bit[stream_id_len-1:0]];\n\n' \
                 '    `uvm_component_param_utils_begin(common_uvm_scb#(TRANS_TYPE,stream_id_len))\n' \
                 '        `uvm_field_object(m_cfg,UVM_ALL_ON)\n' \
                 '        `uvm_field_int   (m_total_match_pair_cnt,UVM_ALL_ON)\n' \
                 '    `uvm_component_utils_end\n\n' \
                 '    extern function new(string name=\"common_uvm_scb\",uvm_component parent = null);\n' \
                 '    extern virtual task send_rm_trans_to_cmp(TRANS_TYPE rm_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    extern virtual task cmp_order_with_loss_rm_trans(TRANS_TYPE rm_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n\n' \
                 '    extern virtual task send_dut_trans_to_cmp(TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    extern virtual task cmp_order_with_loss_dut_trans(TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n\n' \
                 '    extern virtual function bit quick_compare(TRANS_TYPE rm_tr,TRANS_TYPE dut_tr,int kind=-1);\n\n' \
                 '    extern virtual task cmp_pass_action(TRANS_TYPE rm_tr,TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    extern virtual task action_when_cmp_pass(TRANS_TYPE rm_tr,TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    extern virtual task cmp_not_pass_action(bit[stream_id_len-1:0] stream_id,string diff);\n' \
                 '    extern virtual function void report_info();\n' \
                 '    extern virtual function void queue_status_chk();\n' \
                 '    extern virtual function void report_phase(uvm_phase phase);\n' \
                 '    extern virtual function void clear_all_q();\n' \
                 '    extern virtual function void clear_all_cnt();\n' \
                 '    extern virtual function void clear_all();\n\n' \
                 '    extern virtual task action_when_get_rm_trans(TRANS_TYPE rm_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    extern virtual task action_when_get_dut_trans(TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1,int kind=-1);\n' \
                 '    extern virtual function string gen_report_info(bit report_in_env=0);\n\n' \
                 'endclass\n\n' \
                 'function common_uvm_scb::new(string name=\"common_uvm_scb\",uvm_component parent=null);\n' \
                 '    super.new(name,parent);\n' \
                 '    this.m_cfg = new();\n' \
                 '    this.m_total_match_pair_cnt = 0;\n' \
                 '    this.m_get_rm_trans_cnt = 0;\n' \
                 '    this.m_get_dut_trans_cnt = 0;\n' \
                 'endfunction:new\n\n' \
                 'task common_uvm_scb::send_rm_trans_to_cmp(TRANS_TYPE rm_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    int i,j,k;\n' \
                 '    TRANS_TYPE dut_tr;\n' \
                 '    TRANS_TYPE tmp_tr;\n' \
                 '    int       q_size;\n' \
                 '    int       match_index;\n' \
                 '    bit       find_match_flag;\n' \
                 '    int       not_match_dut_cnt;\n' \
                 '    string    diff;\n\n' \
                 '    action_when_get_rm_trans(rm_tr,stream_id,kind);\n' \
                 '    this.m_get_rm_trans_cnt++;\n' \
                 '    if(m_trans_array.exists(stream_id)==0) begin\n' \
                 '        m_trans_array[stream_id] = new();\n' \
                 '        m_trans_array[stream_id].m_stream_id = stream_id;\n' \
                 '    end\n' \
                 '    m_trans_array[stream_id].m_get_rm_trans_cnt++;\n\n' \
                 '    if(m_cfg.m_cmp_mode == ORDER_CMP_WITHOUT_LOSS) begin\n' \
                 '        if(m_cfg.m_allow_dut_faster_en == 0) begin\n' \
                 '            if(m_trans_array[stream_id].m_dut_trans_q.size()>0) begin\n' \
                 '                `uvm_error(get_full_name,\"ORDER_CMP_WITH_LOSS,dut_faster_en=1 when rm pkt comes,dut_q size should be empty, ' \
                 'maybe dut send pkt faster than rm or rm ont send the pkt to scb\");\n' \
                 '            end\n' \
                 '            m_trans_array[stream_id].m_rm_trans_q.push_back(rm_tr);\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            if(m_trans_array[stream_id].m_dut_trans_q.size()>0) begin\n' \
                 '                dut_tr = m_trans_array[stream_id].m_dut_trans_q.pop_front();\n' \
                 '                if(!rm_tr.self_define_do_compare(dut_tr,diff,kind)) begin\n' \
                 '                    this.cmp_not_pass_action(stream_id,diff);\n' \
                 '                end\n' \
                 '                else begin\n' \
                 '                    this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                end\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                m_trans_array[stream_id].m_rm_trans_q.push_back(rm_tr);\n' \
                 '            end\n' \
                 '        end\n' \
                 '    end\n' \
                 '    else if(m_cfg.m_cmp_mode == ORDER_CMP_WITH_LOSS) begin\n' \
                 '        this.cmp_order_with_loss_rm_trans(rm_tr,stream_id,kind);\n' \
                 '    end\n' \
                 '    else if(m_cfg.m_cmp_mode == DISSORDER_CMP) begin\n' \
                 '        q_size = m_trans_array[stream_id].m_dut_trans_q.size();\n' \
                 '        if(q_size>0) begin\n' \
                 '            find_match_flag = 1\'b0;\n' \
                 '            for(i = 0;i<q_size;i++) begin\n' \
                 '                dut_tr = m_trans_array[stream_id].m_dut_trans_q[i];\n' \
                 '                if(this.quick_compare(rm_tr,dut_tr,kind)) begin\n' \
                 '                    this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                    match_index=i;\n' \
                 '                    find_match_flag = 1\'b1;\n' \
                 '                    break;\n' \
                 '                end\n' \
                 '            end\n' \
                 '            if(find_match_flag == 1\'b1) begin\n' \
                 '                m_trans_array[stream_id].m_dut_trans_q.delete(match_index);\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                m_trans_array[stream_id].m_rm_trans_q.push_back(rm_tr);\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            m_trans_array[stream_id].m_rm_trans_q.push_back(rm_tr);\n' \
                 '        end\n' \
                 '    end\n' \
                 'endtask\n\n' \
                 'task common_uvm_scb::cmp_order_with_loss_rm_trans(TRANS_TYPE rm_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    int i,j,k;\n' \
                 '    TRANS_TYPE dut_tr;\n' \
                 '    TRANS_TYPE tmp_tr;\n' \
                 '    int       q_size;\n' \
                 '    int       match_index;\n' \
                 '    bit       find_match_flag;\n' \
                 '    int       not_match_dut_cnt;\n' \
                 '    if(m_cfg.m_allow_dut_faster_en == 0) begin\n' \
                 '        m_trans_array[stream_id].m_rm_trans_q.push_back(rm_tr);\n' \
                 '    end\n' \
                 '    else begin\n' \
                 '        q_size = m_trans_array[stream_id].m_dut_trans_q.size();\n' \
                 '        if(q_size>0) begin\n' \
                 '            find_match_flag = 1\'b0;\n' \
                 '            not_match_dut_cnt = 0;\n' \
                 '            for(i=0;i<q_size;i++) begin\n' \
                 '                dut_tr = m_trans_array[stream_id].m_dut_trans_q[i];\n' \
                 '                if(this.quick_compare(rm_tr,dut_tr,kind)) begin\n' \
                 '                    this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                    match_index=i;\n' \
                 '                    find_match_flag = 1\'b1;\n' \
                 '                    break;\n' \
                 '                end\n' \
                 '            end\n' \
                 '            if(find_match_flag == 1\'b1 ) begin\n' \
                 '                if(match_index == 0) begin\n' \
                 '                    m_trans_array[stream_id].m_dut_trans_q.pop_front();\n' \
                 '                end\n' \
                 '                else begin\n' \
                 '                    m_trans_array[stream_id].m_dut_trans_q.delete(match_index);\n' \
                 '                    `uvm_error(get_full_name,\"ORDER_CMP_WITH_LOSS,dut_faster_en=1 when rm pkt comes,' \
                 '                     err exists in the following dut pkt or rm pkt\");\n' \
                 '                    $display(\"dut pkt info:\");\n' \
                 '                    for(i=0;i<match_index;i++) begin\n' \
                 '                        tmp_tr = m_trans_array[stream_id].m_dut_trans_q.pop_front();\n' \
                 '                        m_trans_array[stream_id].m_dut_find_not_match_q.push_back(tmp_tr);\n' \
                 '                        not_match_dut_cnt++;\n' \
                 '                        tmp_tr.print();\n' \
                 '                    end\n' \
                 '                    if(m_trans_array[stream_id].m_rm_trans_q.size()==0) begin\n' \
                 '                        `uvm_error(get_full_name,\"ORDER_CMP_WITH_LOSS,dut_faster_en=1 when rm pkt comes, ' \
                 'when match not at head,rm_q should not be 0,because has err in the rm pkt or dut pkt,scb may be wrong \");\n' \
                 '                    end\n' \
                 '                    else begin\n' \
                 '                        j=m_trans_array[stream_id].m_rm_trans_q.size();\n' \
                 '                        $display(\"rm pkt info:\");\n' \
                 '                        for(i=0;i<j;i++) begin\n' \
                 '                            m_trans_array[stream_id].m_rm_trans_q[i].print();\n' \
                 '                        end\n' \
                 '                    end\n' \
                 '                end\n' \
                 '                m_trans_array[stream_id].m_with_loss_dut_drop_cnt = m_trans_array[stream_id].m_with_loss_dut_drop_cnt+' \
                 '                m_trans_array[stream_id].m_rm_trans_q.size()-not_match_dut_cnt;\n' \
                 '                m_trans_array[stream_id].m_rm_trans_q.delete();\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                m_trans_array[stream_id].m_rm_trans_q.push_back(rm_tr);\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            m_trans_array[stream_id].m_rm_trans_q.push_back(rm_tr);\n' \
                 '        end\n' \
                 '    end\n' \
                 'endtask\n\n' \
                 'task common_uvm_scb::send_dut_trans_to_cmp(TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    int i,j,k;\n' \
                 '    TRANS_TYPE rm_tr;\n' \
                 '    TRANS_TYPE tmp_tr;\n' \
                 '    int       q_size;\n' \
                 '    int       match_index;\n' \
                 '    bit       find_match_flag;\n' \
                 '    int       not_match_dut_cnt;\n' \
                 '    string    diff;\n\n' \
                 '    action_when_get_dut_trans(dut_tr,stream_id,kind);\n' \
                 '    this.m_get_dut_trans_cnt++;\n' \
                 '    if(m_trans_array.exists(stream_id)==0) begin\n' \
                 '        m_trans_array[stream_id] = new();\n' \
                 '        m_trans_array[stream_id].m_stream_id = stream_id;\n' \
                 '    end\n' \
                 '    m_trans_array[stream_id].m_get_dut_trans_cnt++;\n\n' \
                 '    if(m_cfg.m_cmp_mode == ORDER_CMP_WITHOUT_LOSS) begin\n' \
                 '        if(m_cfg.m_allow_dut_faster_en == 0) begin\n' \
                 '            if(m_trans_array[stream_id].m_rm_trans_q.size()>0) begin\n' \
                 '                rm_tr = m_trans_array[stream_id].m_rm_trans_q.pop_front();\n' \
                 '                if(!rm_tr.self_define_do_compare(dut_tr,diff,kind)) begin\n' \
                 '                    this.cmp_not_pass_action(stream_id,diff);\n' \
                 '                end\n' \
                 '                else begin\n' \
                 '                    this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                end\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                `uvm_error(get_full_name,\"ORDER_CMP_WITH_LOSS,dut_faster_en=0 when dut pkt comes,rm_q size should not be empty, ' \
                 'maybe dut send pkt faster than rm or rm ont send the pkt to scb\");\n' \
                 '                dut_tr.print();\n' \
                 '                this.m_trans_array[stream_id].m_dut_find_not_match_q.push_back(dut_tr);\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else begin //when dut_faster_en=1,dut_tr send in to cmp\n' \
                 '            if(m_trans_array[stream_id].m_rm_trans_q.size()>0) begin\n' \
                 '                rm_tr = m_trans_array[stream_id].m_rm_trans_q.pop_front();\n' \
                 '                if(!rm_tr.self_define_do_compare(dut_tr,diff,kind)) begin\n' \
                 '                    this.cmp_not_pass_action(stream_id,diff);\n' \
                 '                end\n' \
                 '                else begin\n' \
                 '                    this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                end\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                m_trans_array[stream_id].m_dut_trans_q.push_back(dut_tr);\n' \
                 '            end\n' \
                 '        end\n' \
                 '    end\n' \
                 '    else if(m_cfg.m_cmp_mode == ORDER_CMP_WITH_LOSS) begin\n' \
                 '        this.cmp_order_with_loss_dut_trans(dut_tr,stream_id,kind);\n' \
                 '    end\n' \
                 '    else if(m_cfg.m_cmp_mode == DISSORDER_CMP) begin\n' \
                 '        q_size = m_trans_array[stream_id].m_rm_trans_q.size();\n' \
                 '        if(q_size>0) begin\n' \
                 '            find_match_flag = 1\'b0;\n' \
                 '            for(i = 0;i<q_size;i++) begin\n' \
                 '                rm_tr = m_trans_array[stream_id].m_rm_trans_q[i];\n' \
                 '                if(this.quick_compare(rm_tr,dut_tr,kind)) begin\n' \
                 '                    this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                    match_index=i;\n' \
                 '                    find_match_flag = 1\'b1;\n' \
                 '                    break;\n' \
                 '                end\n' \
                 '            end\n' \
                 '            if(find_match_flag == 1\'b1) begin\n' \
                 '                m_trans_array[stream_id].m_rm_trans_q.delete(match_index);\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                m_trans_array[stream_id].m_dut_trans_q.push_back(dut_tr);\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            m_trans_array[stream_id].m_dut_trans_q.push_back(dut_tr);\n' \
                 '        end\n' \
                 '    end\n' \
                 'endtask\n\n' \
                 'task common_uvm_scb::cmp_order_with_loss_dut_trans(TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    int i,j,k;\n' \
                 '    TRANS_TYPE rm_tr;\n' \
                 '    TRANS_TYPE tmp_tr;\n' \
                 '    int       q_size;\n' \
                 '    int       match_index;\n' \
                 '    bit       find_match_flag;\n' \
                 '    int       not_match_dut_cnt;\n' \
                 '    if(m_cfg.m_allow_dut_faster_en == 0) begin // cmp_mode = ORDER_CMP_WITH_LOSS faster_en=0\n' \
                 '        q_size = m_trans_array[stream_id].m_rm_trans_q.size();\n' \
                 '        if(q_size == 0) begin\n' \
                 '            `uvm_error(get_full_name,\"ORDER_CMP_WITH_LOSS dut_faster_en=0;when dut_tr come,rm_tr_q size should not be 0\");\n' \
                 '            m_trans_array[stream_id].m_dut_find_not_match_q.push_back(dut_tr);\n' \
                 '            return;\n' \
                 '        end\n' \
                 '        find_match_flag = 1\'b0;\n' \
                 '        for(i=0;i<q_size;i++) begin\n' \
                 '            rm_tr = m_trans_array[stream_id].m_rm_trans_q[i];\n' \
                 '            if(this.quick_compare(rm_tr,dut_tr,kind)) begin\n' \
                 '                this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                match_index=i;\n' \
                 '                find_match_flag = 1\'b1;\n' \
                 '                break;\n' \
                 '            end\n' \
                 '        end\n' \
                 '        if(find_match_flag == 1\'b1 ) begin\n' \
                 '            for(i=0;i<(match_index+1);i++) begin\n' \
                 '                m_trans_array[stream_id].m_rm_trans_q.pop_front();\n' \
                 '            end\n' \
                 '            m_trans_array[stream_id].m_with_loss_dut_drop_cnt = m_trans_array[stream_id].m_with_loss_dut_drop_cnt + match_index;\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            `uvm_error(get_full_name,\"ORDER_CMP_WITH_LOSS,dut_faster_en=0 when dut pkt comes, ' \
                 'cannot find match in rm_q ,because has err in the rm pkt or dut pkt,scb may be wrong \");\n' \
                 '            m_trans_array[stream_id].m_dut_find_not_match_q.push_back(dut_tr);\n' \
                 '            $display(\"dut pkt info:\");\n' \
                 '            dut_tr.print();\n' \
                 '            $display(\"rm pkt info:\");\n' \
                 '            for(i=0;i<m_trans_array[stream_id].m_rm_trans_q.size;i++) begin\n' \
                 '                m_trans_array[stream_id].m_rm_trans_q[i].print();\n' \
                 '            end\n' \
                 '            m_trans_array[stream_id].m_with_loss_dut_drop_cnt = m_trans_array[stream_id].m_with_loss_dut_drop_cnt-1;\n' \
                 '            m_trans_array[stream_id].m_not_match_pair_cnt++;\n' \
                 '        end\n' \
                 '    end\n' \
                 '    else begin //faster_en=1\n' \
                 '        q_size = m_trans_array[stream_id].m_rm_trans_q.size();\n' \
                 '        if(q_size>0) begin\n' \
                 '            find_match_flag = 1\'b0;\n' \
                 '            not_match_dut_cnt = 0;\n' \
                 '            for(i=0;i<q_size;i++) begin\n' \
                 '                rm_tr = m_trans_array[stream_id].m_rm_trans_q[i];\n' \
                 '                if(this.quick_compare(rm_tr,dut_tr,kind)) begin\n' \
                 '                    this.cmp_pass_action(rm_tr,dut_tr,stream_id,kind);\n' \
                 '                    match_index=i;\n' \
                 '                    find_match_flag = 1\'b1;\n' \
                 '                    break;\n' \
                 '                end\n' \
                 '            end\n' \
                 '            if(find_match_flag == 1\'b1 ) begin\n' \
                 '                if(m_trans_array[stream_id].m_dut_trans_q.size()>0) begin\n' \
                 '                    `uvm_error(get_full_name,\"ORDER_CMP_WITH_LOSS,dut_faster_en=1 when dut pkt comes, ' \
                 'err exists in the following dut pkt or rm pkt\");\n' \
                 '                    $display(\"dut pkt info:\");\n' \
                 '                    j = m_trans_array[stream_id].m_dut_trans_q.size();\n' \
                 '                    for(i=0;i<j;i++) begin\n' \
                 '                        tmp_tr = m_trans_array[stream_id].m_dut_trans_q.pop_front();\n' \
                 '                        m_trans_array[stream_id].m_dut_find_not_match_q.push_back(tmp_tr);\n' \
                 '                        m_trans_array[stream_id].m_not_match_pair_cnt++;\n' \
                 '                        tmp_tr.print();\n' \
                 '                        not_match_dut_cnt++;\n' \
                 '                    end\n' \
                 '                    $display(\"rm pkt info:\");\n' \
                 '                    for(i=0;i<match_index;i++) begin\n' \
                 '                        tmp_tr = m_trans_array[stream_id].m_rm_trans_q[i];\n' \
                 '                        tmp_tr.print();\n' \
                 '                    end\n' \
                 '                end\n' \
                 '                for(i=0;i<(match_index+1);i++) begin\n' \
                 '                    tmp_tr = m_trans_array[stream_id].m_rm_trans_q.pop_front();\n' \
                 '                    if(i<match_index) begin\n' \
                 '                        m_trans_array[stream_id].m_with_loss_dut_drop_cnt++;\n' \
                 '                    end\n' \
                 '                end\n' \
                 '                m_trans_array[stream_id].m_with_loss_dut_drop_cnt = m_trans_array[stream_id].m_with_loss_dut_drop_cnt - not_match_dut_cnt;\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                m_trans_array[stream_id].m_dut_trans_q.push_back(dut_tr);\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            m_trans_array[stream_id].m_dut_trans_q.push_back(dut_tr);\n' \
                 '        end\n' \
                 '    end\n' \
                 'endtask\n\n' \
                 'function bit common_uvm_scb::quick_compare(TRANS_TYPE rm_tr,TRANS_TYPE dut_tr,int kind=-1);\n' \
                 '    string diff;\n' \
                 '    return rm_tr.self_define_do_compare(dut_tr,diff,kind);\n' \
                 'endfunction\n\n' \
                 'task common_uvm_scb::cmp_pass_action(TRANS_TYPE rm_tr,TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 '    this.m_trans_array[stream_id].m_match_pair_cnt++;\n' \
                 '    this.m_total_match_pair_cnt++;\n' \
                 '    if(this.m_total_match_pair_cnt%m_cfg.m_cmp_pass_print_interval==0) begin\n' \
                 '        `uvm_info(get_full_name,$sformatf(\"%s %0d trans cmp pass.\",get_name,this.m_total_match_pair_cnt),UVM_NONE);\n' \
                 '    end\n' \
                 '    this.action_when_cmp_pass(rm_tr,dut_tr,stream_id,kind);\n' \
                 'endtask\n\n' \
                 'task common_uvm_scb::action_when_cmp_pass(TRANS_TYPE rm_tr,TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 'endtask\n\n' \
                 'task common_uvm_scb::cmp_not_pass_action(bit[stream_id_len-1:0] stream_id,string diff);\n' \
                 '    if(this.m_trans_array[stream_id].m_print_err_cnt<this.m_cfg.m_err_print_threadhold) begin\n' \
                 '        this.m_trans_array[stream_id].m_print_err_cnt++;\n' \
                 '        `uvm_error(get_full_name,\"scb cmp not pass\");\n' \
                 '        $display(\"%s\",diff);\n' \
                 '    end\n' \
                 'endtask\n\n' \
                 'function void common_uvm_scb::report_info();\n' \
                 '    int i,j,k;\n' \
                 '    int total_rm_trans_q_size             ;\n' \
                 '    int total_dut_trans_q_size            ;\n' \
                 '    int total_dut_find_not_match_q_size   ;\n' \
                 '    int total_with_loss_dut_drop_cnt      ;\n' \
                 '    int total_not_match_pair_cnt          ;\n' \
                 '    int total_match_pair_cnt              ;\n' \
                 '    common_draw_table         draw_inst;\n\n' \
                 '    total_rm_trans_q_size             =0;\n' \
                 '    total_dut_trans_q_size            =0;\n' \
                 '    total_dut_find_not_match_q_size   =0;\n' \
                 '    total_with_loss_dut_drop_cnt      =0;\n' \
                 '    total_not_match_pair_cnt          =0;\n' \
                 '    total_match_pair_cnt              =0;\n\n' \
                 '    foreach(this.m_trans_array[i]) begin\n' \
                 '        total_rm_trans_q_size          = total_rm_trans_q_size          +this.m_trans_array[i].m_rm_trans_q.size;\n' \
                 '        total_dut_trans_q_size         = total_dut_trans_q_size         +this.m_trans_array[i].m_dut_trans_q.size;\n' \
                 '        total_dut_find_not_match_q_size= total_dut_find_not_match_q_size+this.m_trans_array[i].m_dut_find_not_match_q.size();\n' \
                 '        total_with_loss_dut_drop_cnt   = total_with_loss_dut_drop_cnt   +this.m_trans_array[i].m_with_loss_dut_drop_cnt;\n' \
                 '        total_not_match_pair_cnt       = total_not_match_pair_cnt       +this.m_trans_array[i].m_not_match_pair_cnt;\n' \
                 '        total_match_pair_cnt           = total_match_pair_cnt           +this.m_trans_array[i].m_match_pair_cnt;\n' \
                 '    end\n\n' \
                 '    draw_inst = new();\n' \
                 '    draw_inst.insert_line_content($sformatf(\"%s_info_summary\",get_name));\n' \
                 '    if(this.m_cfg.m_report_stream_en == 1) begin\n' \
                 '        draw_inst.insert_line_content(\"stream_id match_cnt get_rm_trans_cnt get_dut_trans_cnt remain_rm_trans_cnt remain_dut_trans_cnt\");\n' \
                 '        foreach(this.m_trans_array[i]) begin\n' \
                 '            draw_inst.insert_line_content(this.m_trans_array[i].gen_report_info());\n' \
                 '        end\n' \
                 '    end\n' \
                 '    draw_inst.insert_line_content(this.gen_report_info());\n' \
                 '    draw_inst.display_table();\n' \
                 '    draw_inst.clean_table_content();\n' \
                 'endfunction\n\n' \
                 'function void common_uvm_scb::queue_status_chk();\n' \
                 '    int i,j,k;\n' \
                 '    int dut_cnt,rm_cnt,dut_find_not_match_cnt,not_match_pair_cnt;\n' \
                 '    int total_cnt,total_except_dut_drop_cnt;\n' \
                 '    foreach(this.m_trans_array[i]) begin\n' \
                 '        dut_cnt                   = this.m_trans_array[i].m_dut_trans_q.size();\n' \
                 '        rm_cnt                    = this.m_trans_array[i].m_rm_trans_q.size();\n' \
                 '        dut_find_not_match_cnt    = this.m_trans_array[i].m_dut_find_not_match_q.size();\n' \
                 '        not_match_pair_cnt        = this.m_trans_array[i].m_not_match_pair_cnt;\n' \
                 '        total_cnt                 = dut_cnt + rm_cnt + dut_find_not_match_cnt + not_match_pair_cnt;\n' \
                 '        total_except_dut_drop_cnt = dut_cnt + dut_find_not_match_cnt + not_match_pair_cnt;\n' \
                 '        if((m_cfg.m_cmp_mode == ORDER_CMP_WITH_LOSS) || (m_cfg.m_cmp_mode == DISSORDER_CMP)) begin\n' \
                 '            if(total_cnt != 0) begin\n' \
                 '                `uvm_error(get_full_name,$sformatf(\"cmp_mode=%s stream_id=0x%0h dut_q.size=%0d rm_q.size=%0d ' \
                 'dut_find_not_match_q.size=%0d m_not_match_pair_cnt=%0d should all be 0.\",m_cfg.m_cmp_mode.name(),i,dut_cnt, ' \
                 'rm_cnt,dut_find_not_match_cnt,not_match_pair_cnt));\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            if(total_except_dut_drop_cnt != 0) begin\n' \
                 '                `uvm_error(get_full_name,$sformatf(\"cmp_mode=%s stream_id=0x%0h dut_q.size=%0d ' \
                 'dut_find_not_match_q.size=%0d m_not_match_pair_cnt=%0d should all be 0.\",m_cfg.m_cmp_mode.name(),i,dut_cnt, ' \
                 'dut_find_not_match_cnt,not_match_pair_cnt));\n' \
                 '            end\n' \
                 '        end\n' \
                 '    end\n' \
                 'endfunction\n\n' \
                 'function void common_uvm_scb::report_phase(uvm_phase phase);\n' \
                 '    super.report_phase(phase);\n' \
                 '    if(this.m_cfg.m_report_info_en == 1) begin\n' \
                 '        this.report_info();\n' \
                 '    end\n' \
                 '    else begin\n' \
                 '        `uvm_info(get_full_name,$sformatf(\"m_report_info_en=0,not report info\"),UVM_NONE);\n' \
                 '    end\n' \
                 '    this.queue_status_chk();\n' \
                 'endfunction\n\n' \
                 'function void common_uvm_scb::clear_all_q();\n' \
                 '    foreach(this.m_trans_array[i]) begin\n' \
                 '        this.m_trans_array[i].m_dut_trans_q.delete();\n' \
                 '        this.m_trans_array[i].m_rm_trans_q.delete();\n' \
                 '        this.m_trans_array[i].m_dut_find_not_match_q.delete();\n' \
                 '    end\n' \
                 'endfunction\n\n' \
                 'function void common_uvm_scb::clear_all_cnt();\n' \
                 '    foreach(this.m_trans_array[i]) begin\n' \
                 '        this.m_trans_array[i].m_get_rm_trans_cnt        =0;\n' \
                 '        this.m_trans_array[i].m_get_dut_trans_cnt       =0;\n' \
                 '        this.m_trans_array[i].m_match_pair_cnt          =0;\n' \
                 '        this.m_trans_array[i].m_with_loss_dut_drop_cnt  =0;\n' \
                 '        this.m_trans_array[i].m_not_match_pair_cnt      =0;\n' \
                 '        this.m_trans_array[i].m_print_err_cnt           =0;\n' \
                 '    end\n' \
                 '    this.m_total_match_pair_cnt =0;\n' \
                 '    this.m_get_rm_trans_cnt     =0;\n' \
                 '    this.m_get_dut_trans_cnt    =0;\n' \
                 'endfunction\n\n' \
                 'function void common_uvm_scb::clear_all();\n' \
                 '    this.clear_all_q();\n' \
                 '    this.clear_all_cnt();\n' \
                 'endfunction\n\n' \
                 'task common_uvm_scb::action_when_get_rm_trans(TRANS_TYPE rm_tr,bit[stream_id_len-1:0] stream_id=-1, int kind=-1);\n' \
                 'endtask\n\n' \
                 'task common_uvm_scb::action_when_get_dut_trans(TRANS_TYPE dut_tr,bit[stream_id_len-1:0] stream_id=-1,int kind=-1);\n' \
                 'endtask\n\n' \
                 'function string common_uvm_scb::gen_report_info(bit report_in_env=0);\n' \
                 '    int total_rm_trans_q_size             ;\n' \
                 '    int total_dut_trans_q_size            ;\n' \
                 '    int total_dut_find_not_match_q_size   ;\n' \
                 '    int total_with_loss_dut_drop_cnt      ;\n' \
                 '    int total_not_match_pair_cnt          ;\n' \
                 '    int total_match_pair_cnt              ;\n\n' \
                 '    int dut_cnt,rm_cnt,dut_find_not_match_cnt,not_match_pair_cnt;\n' \
                 '    int total_cnt,total_except_dut_drop_cnt;\n' \
                 '    string    ret_str;\n' \
                 '    total_rm_trans_q_size             =0;\n' \
                 '    total_dut_trans_q_size            =0;\n' \
                 '    total_dut_find_not_match_q_size   =0;\n' \
                 '    total_with_loss_dut_drop_cnt      =0;\n' \
                 '    total_not_match_pair_cnt          =0;\n' \
                 '    total_match_pair_cnt              =0;\n\n' \
                 '    foreach(this.m_trans_array[i]) begin\n' \
                 '        total_rm_trans_q_size          = total_rm_trans_q_size          +this.m_trans_array[i].m_rm_trans_q.size;\n' \
                 '        total_dut_trans_q_size         = total_dut_trans_q_size         +this.m_trans_array[i].m_dut_trans_q.size;\n' \
                 '        total_dut_find_not_match_q_size= total_dut_find_not_match_q_size+this.m_trans_array[i].m_dut_find_not_match_q.size();\n' \
                 '        total_with_loss_dut_drop_cnt   = total_with_loss_dut_drop_cnt   +this.m_trans_array[i].m_with_loss_dut_drop_cnt;\n' \
                 '        total_not_match_pair_cnt       = total_not_match_pair_cnt       +this.m_trans_array[i].m_not_match_pair_cnt;\n' \
                 '        total_match_pair_cnt           = total_match_pair_cnt           +this.m_trans_array[i].m_match_pair_cnt;\n' \
                 '    end\n\n' \
                 '    if(report_in_env ==0) begin\n' \
                 '        ret_str = $sformatf(\"total_streams %0d %0d %0d %0d %0d\",total_match_pair_cnt,m_get_rm_trans_cnt, ' \
                 'm_get_dut_trans_cnt,total_rm_trans_q_size,total_dut_trans_q_size);\n' \
                 '    end\n' \
                 '    else begin\n' \
                 '        ret_str = $sformatf(\"total_streams %0d %0d %0d %0d %0d\",total_match_pair_cnt,m_get_rm_trans_cnt, ' \
                 'm_get_dut_trans_cnt,total_rm_trans_q_size,total_dut_trans_q_size);\n' \
                 '    end\n' \
                 '    return ret_str;\n' \
                 'endfunction\n\n' \

        # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_common_draw_table(prj_name,author_name,file_path,block_name):

    init_path = os.path.join(file_path , 'common_draw_table.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = 'common_draw_table.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + 'COMMON_DRAW_TABLE__SV\n'
    line_arry += '`define  ' + 'COMMON_DRAW_TABLE__SV' + '\n'*3
    line_arry += 'class common_draw_table;\n' \
                 '    int m_coloum_num;\n' \
                 '    int m_coloum_width;\n' \
                 '    int m_content_num;\n' \
                 '    string m_line_content_q[int][$];\n\n' \
                 '    function new();\n' \
                 '        this.m_coloum_num   = 0;\n' \
                 '        this.m_coloum_width = 20;\n' \
                 '        this.m_content_num  = 0;\n' \
                 '    endfunction\n\n' \
                 '    function string gen_head_line();\n' \
                 '        string ret_str;\n' \
                 '        string tmp_str;\n' \
                 '        int i,j,k;\n' \
                 '        ret_str = \"-\";\n' \
                 '        for(int i=0;i<this.m_coloum_num;i++) begin\n' \
                 '            tmp_str = {this.m_coloum_width{\"_\"}};\n' \
                 '            ret_str = {ret_str,tmp_str};\n' \
                 '        end\n' \
                 '        ret_str[0] = \" \";\n' \
                 '        ret_str[ret_str.len-1]=\" \";\n' \
                 '        return ret_str;\n' \
                 '    endfunction\n\n' \
                 '    function string gen_underline_one_line();\n' \
                 '        string ret_str;\n' \
                 '        string tmp_str;\n' \
                 '        int i,j,k;\n' \
                 '        ret_str = {\"|\",{this.m_coloum_num*this.m_coloum_width-1{\"_\"}},\"|\"};\n' \
                 '        return ret_str;\n' \
                 '    endfunction\n\n' \
                 '    function string gen_empty_line();\n' \
                 '        string ret_str;\n' \
                 '        ret_str = {\"|\",{this.m_coloum_num*this.m_coloum_width-1{\" \"}},\"|\"};\n' \
                 '        return ret_str;\n' \
                 '    endfunction\n\n' \
                 '    function void insert_line_content(string in_line_str);\n' \
                 '        int i,j,k;\n' \
                 '        string insert_str[$];\n' \
                 '        string get_str;\n' \
                 '        string tmp_str;\n' \
                 '        int start_index,end_index;\n' \
                 '        for(i=0;i<in_line_str.len;i++) begin\n' \
                 '            if(in_line_str[i] != \" \") begin\n' \
                 '                start_index = i;\n' \
                 '                break;\n' \
                 '            end\n' \
                 '        end\n' \
                 '        j=0;\n' \
                 '        for(i=0;i<in_line_str.len;i++) begin\n' \
                 '            if(in_line_str[in_line_str.len-1-i] == \" \") begin\n' \
                 '                j++;\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                break;\n' \
                 '            end\n' \
                 '        end\n' \
                 '        end_index = in_line_str.len-j;\n' \
                 '        k=0;\n' \
                 '        get_str = \"\";\n' \
                 '        for(i = start_index;i<end_index;i++) begin\n' \
                 '            get_str = {get_str,in_line_str[i]};\n' \
                 '            k++;\n' \
                 '        end\n' \
                 '        k = 0;\n' \
                 '        tmp_str = \"\";\n' \
                 '        for(i=0;i<get_str.len;i++) begin\n' \
                 '            if(get_str[i] == \" \") begin\n' \
                 '                if(tmp_str.len>0) begin\n' \
                 '                    insert_str.push_back(tmp_str);\n' \
                 '                    k = 0;\n' \
                 '                    tmp_str = \"\";\n' \
                 '                end\n' \
                 '            end\n' \
                 '            else begin\n' \
                 '                tmp_str = {tmp_str,get_str[i]};\n' \
                 '                k++;\n' \
                 '            end\n' \
                 '        end\n' \
                 '        insert_str.push_back(tmp_str);\n' \
                 '        this.insert_content(insert_str);\n' \
                 '    endfunction\n\n' \
                 '    function void insert_content(string insert_str[$]);\n' \
                 '        int i,j,k;\n' \
                 '        string ret_str;\n' \
                 '        this.m_line_content_q[this.m_content_num] = insert_str;\n' \
                 '        if(insert_str.size()>this.m_coloum_num) begin\n' \
                 '            this.m_coloum_num = insert_str.size();\n' \
                 '        end\n' \
                 '        if(insert_str.size()>1) begin\n' \
                 '            j=0;\n' \
                 '            for(i=0;i<insert_str.size();i++) begin\n' \
                 '                if(insert_str[i].len()>j) begin\n' \
                 '                    j = insert_str[i].len;\n' \
                 '                end\n' \
                 '            end\n' \
                 '            if(j>=(this.m_coloum_width-1)) begin\n' \
                 '                this.m_coloum_width = j+2;\n' \
                 '            end\n' \
                 '        end\n' \
                 '        this.m_content_num++;\n' \
                 '    endfunction\n\n' \
                 '    function string gen_content(string insert_str[$]);\n' \
                 '        string ret_str;\n' \
                 '        string tmp_str;\n' \
                 '        string under_line_str;\n' \
                 '        int i,j,k;\n' \
                 '        int str_len,start_index;\n' \
                 '        int column_width,tab_width;\n' \
                 '        tab_width = this.m_coloum_num*this.m_coloum_width + 1;\n' \
                 '        under_line_str = this.gen_underline_one_line();\n' \
                 '        if( insert_str.size() == 1) begin\n' \
                 '            ret_str = {\"|\",{(tab_width-2){\" \"}},\"|\"};\n' \
                 '            str_len = insert_str[0].len();\n' \
                 '            start_index = (tab_width -str_len)/2;\n' \
                 '            for(i=0;i<str_len;i++) begin\n' \
                 '                ret_str[i+start_index] = insert_str[0][i];\n' \
                 '            end\n' \
                 '        end\n' \
                 '        else begin\n' \
                 '            column_width = tab_width / insert_str.size();\n' \
                 '            ret_str = {\"|\",{(tab_width-2){\" \"}},\"|\"};\n' \
                 '            for(i=0;i<(insert_str.size()-1);i++) begin\n' \
                 '                start_index = 1+ column_width*(i+1);\n' \
                 '                ret_str[start_index] = \"|\";\n' \
                 '                under_line_str[start_index] = \"|\";\n' \
                 '            end\n' \
                 '            for(i=0;i<insert_str.size();i++) begin\n' \
                 '                str_len = insert_str[i].len;\n' \
                 '                start_index = column_width*i+1 + ((column_width - str_len)/2);\n' \
                 '                for(j=0;j<insert_str[i].len;j++) begin\n' \
                 '                    ret_str[start_index+j] = insert_str[i][j];\n' \
                 '                end\n' \
                 '            end\n' \
                 '        end\n' \
                 '        ret_str = {ret_str,"\\n",under_line_str};\n' \
                 '        return ret_str;\n' \
                 '    endfunction\n\n' \
                 '    function void display_table();\n' \
                 '        int i,j,k;\n' \
                 '        string line_str_q[$];\n' \
                 '        $display(\"%s\",this.gen_head_line);\n' \
                 '        for(i=0;i<this.m_content_num;i++) begin\n' \
                 '            line_str_q = this.m_line_content_q[i];\n' \
                 '            $display(\"%s\",this.gen_content(line_str_q));\n' \
                 '        end\n' \
                 '        $display(\"\");\n' \
                 '    endfunction\n\n' \
                 '    function void clean_table_content();\n' \
                 '        this.m_line_content_q.delete();\n' \
                 '        this.m_content_num = 0;\n' \
                 '        this.m_coloum_width = 20;\n' \
                 '        this.m_coloum_num = 0;\n' \
                 '    endfunction\n\n' \
                 'endclass\n\n' \
                 '' \
                 '' \

    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()


def gen_uvm_agent_cfg_file(file_path,agent_name,block_name):

    env_path = os.path.join(file_path, 'tb.f')
    env_file = open(env_path, 'w', encoding='utf-8')
    env_file.write('-F  ../common_utils/common_lib_pkg/common_lib_pkg.f\n')
    env_file.write('-F  ../../'+agent_name+'_agent.f\n')
    env_file.write('../env/' + agent_name + '_env.sv\n')
    env_file.write('../env/harness.sv\n')
    env_file.write('-F ../tc/tc.f\n')

    env_file.close()

def gen_uvm_agent(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_agent.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_AGENT__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_AGENT__SV' + '\n'*3
    line_arry += 'class ' + agent_name + '_agent extends uvm_agent;\n\n' \
                 '    `uvm_component_utils_begin('+agent_name+'_agent)\n' \
                 '    `uvm_component_utils_end\n\n' \
                 '    '+agent_name+'_agt_cfg                m_cfg;\n' \
                 '    '+agent_name+'_sqr                    m_sqr;\n' \
                 '    '+agent_name+'_drv                    m_drv;\n' \
                 '    '+agent_name+'_mon                    m_mon;\n\n' \
                 '    common_self_debug_scb#('+agent_name+'_trans)     m_debug_scb;\n\n' \
                 '    extern function new(string name=\"'+agent_name+'_agent\",uvm_component parent=null);\n' \
                 '    extern virtual function void build_phase(uvm_phase phase);\n' \
                 '    extern virtual function void connect_phase(uvm_phase phase);\n' \
                 '    extern function int get_drv_mon_trans_cnt();\n' \
                 '    extern function string get_report_info();\n\n' \
                 'endclass\n\n' \
                 'function '+agent_name+'_agent::new(string name=\"'+agent_name+'_agent\",uvm_component parent=null);\n' \
                 '    super.new(name,parent);\n' \
                 'endfunction : new\n\n' \
                 'function void '+agent_name+'_agent::build_phase(uvm_phase phase);\n' \
                 '    super.build_phase(phase);\n\n' \
                 '    if(this.m_cfg == null) begin\n' \
                 '        `uvm_info(get_full_name,\"'+block_name+' does not set agent_cfg,just create it by agent itself\",UVM_NONE);\n' \
                 '        this.m_cfg = '+agent_name+'_agt_cfg::type_id::create(\"m_cfg\",this);\n' \
                 '        if(!this.m_cfg.randomize()) begin\n' \
                 '            this.m_cfg.print();\n' \
                 '            `uvm_fatal(get_full_name,\"agent_cfg set is unreasonable!\")\n' \
                 '        end\n' \
                 '    end\n' \
                 '    `uvm_info(get_full_name,$sformatf(\"agent work at mode=%s build_phase start\",this.m_cfg.m_is_active.name),UVM_NONE);\n' \
                 '    m_mon = '+agent_name+'_mon::type_id::create(\"m_mon\",this);\n' \
                 '    if(this.m_cfg.m_is_active == UVM_ACTIVE) begin\n' \
                 '        m_sqr = '+agent_name+'_sqr::type_id::create(\"m_sqr\",this);\n' \
                 '        m_drv = '+agent_name+'_drv::type_id::create(\"m_drv\",this);\n' \
                 '    end\n\n' \
                 '    m_mon.m_cfg = this.m_cfg;\n' \
                 '    if(this.m_cfg.m_is_active == UVM_ACTIVE) begin\n' \
                 '        m_drv.m_cfg = this.m_cfg;\n' \
                 '        if(this.m_cfg.m_self_debug_en == 1) begin\n' \
                 '            this.m_debug_scb = common_self_debug_scb#('+agent_name+'_trans)::type_id::create(\"m_debug_scb\",this);\n' \
                 '        end\n' \
                 '    end\n' \
                 'endfunction : build_phase\n\n' \
                 'function void '+agent_name+'_agent::connect_phase(uvm_phase phase);\n' \
                 '    super.connect_phase(phase);\n' \
                 '    if(this.m_cfg.m_is_active == UVM_ACTIVE) begin\n' \
                 '        m_drv.seq_item_port.connect(m_sqr.seq_item_export);\n' \
                 '        if(this.m_cfg.m_self_debug_en == 1) begin\n' \
                 '            this.m_drv.m_debug_scb = this.m_debug_scb;\n' \
                 '            this.m_mon.m_debug_scb = this.m_debug_scb;\n' \
                 '        end\n' \
                 '    end\n' \
                 'endfunction : connect_phase\n\n' \
                 'function int '+agent_name+'_agent::get_drv_mon_trans_cnt();\n' \
                 '    int ret_value;\n' \
                 '    ret_value = 0;\n' \
                 '    if(this.m_drv != null) begin\n' \
                 '        ret_value = ret_value + this.m_drv.m_get_trans_cnt;\n' \
                 '    end\n' \
                 '    if(this.m_mon != null) begin\n' \
                 '        ret_value = ret_value + this.m_mon.m_mon_trans_cnt;\n' \
                 '    end\n' \
                 '    return ret_value;\n' \
                 'endfunction : get_drv_mon_trans_cnt\n\n' \
                 'function string '+agent_name+'_agent::get_report_info();\n' \
                 '    string     ret_str,tmp_str,cnt_str;\n' \
                 '    tmp_str = $sformatf(\"%s %s\",get_name,this.m_cfg.m_is_active.name);\n' \
                 '    if(this.m_drv == null) begin\n' \
                 '        tmp_str = { tmp_str, \" \",\"null\"};\n' \
                 '        cnt_str = \"--\";\n' \
                 '    end\n' \
                 '    else begin\n' \
                 '        tmp_str = { tmp_str, \" \",\"created\"};\n' \
                 '        cnt_str = $sformatf(\"%0d\",this.m_drv.m_get_trans_cnt);\n' \
                 '    end\n\n' \
                 '    if(this.m_mon == null) begin\n' \
                 '        tmp_str = { tmp_str, \" \",\"null\"};\n' \
                 '        cnt_str = { cnt_str, \" \",\"--\"};\n' \
                 '    end\n' \
                 '    else begin\n' \
                 '        tmp_str = { tmp_str, \" \",\"created\"};\n' \
                 '        cnt_str = { cnt_str,\" \",$sformatf(\"%0d\",this.m_mon.m_mon_trans_cnt)};\n' \
                 '    end\n' \
                 '    ret_str = {tmp_str,\" \",cnt_str};\n' \
                 '    return ret_str;\n' \
                 'endfunction : get_report_info\n\n'

    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_agent_cfg(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_agt_cfg.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_cfg.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_AGT_CFG__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_AGT_CFG__SV' + '\n'*3
    line_arry += 'class ' + agent_name + '_agt_cfg extends uvm_object;\n\n' \
                 '    rand uvm_active_passive_enum      m_is_active;\n' \
                 '    rand bit                          m_self_debug_en;\n' \
                 '    rand bit                          m_drv_get_trans_en;\n' \
                 '    rand bit                          m_mon_send_en;\n' \
                 '    rand bit                          m_mon_stop_mon_en;\n' \
                 '    //rand common_lib_pkg::drv_idle_e   m_drv_idle_mode;\n' \
                 '    `uvm_object_utils_begin('+agent_name+'_agt_cfg)\n' \
                 '        `uvm_field_enum(uvm_active_passive_enum,m_is_active,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_self_debug_en,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_drv_get_trans_en,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_mon_send_en,UVM_ALL_ON)\n' \
                 '        `uvm_field_int(m_mon_stop_mon_en,UVM_ALL_ON)\n' \
                 '       // `uvm_field_enum(common_lib_pkg::drv_idle_e,m_drv_idle_mode,UVM_ALL_ON)\n' \
                 '    `uvm_object_utils_end\n\n' \
                 '    constraint agt_cfg_cons {\n' \
                 '        soft m_is_active         == UVM_ACTIVE;\n' \
                 '        soft m_self_debug_en     == 0;\n' \
                 '        soft m_drv_get_trans_en  == 1;\n' \
                 '        soft m_mon_send_en       == 1;\n' \
                 '        soft m_mon_stop_mon_en   == 0;\n' \
                 '       // soft m_drv_idle_mode     == common_lib_pkg::LOW;\n' \
                 '    }\n\n' \
                 '    function new(string name=\"'+agent_name+'_agt_cfg\");\n' \
                 '        super.new(name);\n' \
                 '        this.m_is_active          = UVM_ACTIVE;\n' \
                 '        this.m_self_debug_en      = 0;\n' \
                 '        this.m_drv_get_trans_en   = 1;\n' \
                 '        this.m_mon_send_en        = 1;\n' \
                 '        this.m_mon_stop_mon_en    = 0;\n' \
                 '       // this.m_drv_idle_mode      = common_lib_pkg::LOW;\n' \
                 '    endfunction : new\n\n' \
                 'endclass\n\n' \


    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_agent_dec(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_dec.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    line_arry += '`ifndef  ' + agent_name.upper() +'_DEC__SV\n'
    line_arry += '`define  ' + agent_name.upper() +'_DEC__SV' + '\n' * 3

    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()


def gen_uvm_agent_file(prj_name,author_name,file_path,agent_name,block_name):
    #add agent.f
    path = os.path.join(file_path, agent_name+'_agent.f')
    path = open(path, 'w', encoding='utf-8')
    path.write('+incdir+./src\n')
    path.write('./src/' + agent_name + '_if.sv\n' )
    path.write('./src/' + agent_name + '_agent_pkg.sv\n')
    path.close()


def gen_uvm_agent_pkg(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_agent_pkg.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_pkg.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_AGENT_PKG__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_AGENT_PKG__SV' + '\n'*3
    line_arry += 'package       '+agent_name+'_agent_pkg;\n\n' \
                 '    timeunit      1ns;\n' \
                 '    timeprecision 1ps;\n' \
                 '    import uvm_pkg::*;\n\n' \
                 '    import common_lib_pkg::*;\n' \
                 '    `include \"'+agent_name+'_dec.sv\"\n' \
                 '    `include \"'+agent_name+'_trans.sv\"\n' \
                 '    `include \"'+agent_name+'_agt_cfg.sv\"\n' \
                 '    `include \"'+agent_name+'_drv.sv\"\n' \
                 '    `include \"'+agent_name+'_mon.sv\"\n' \
                 '    `include \"'+agent_name+'_sqr.sv\"\n' \
                 '    `include \"'+agent_name+'_agent.sv\"\n' \
                 '    `include \"'+agent_name+'_base_seq.sv\"\n' \
                 'endpackage\n\n' \
                 'import ' + agent_name + '_agent_pkg::*;\n\n'


    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_agent_if(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_if.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_if.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_IF__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_IF__SV' + '\n'*3
    line_arry += 'interface '+agent_name+'_if(input logic clk, input logic rst_n);\n\n' \
                 '    //wire        in_vld;\n\n' \
                 '    clocking drv_cb @(posedge clk);\n' \
                 '        //default input #1step output #0.1ns;\n' \
                 '        //output  in_vld;\n' \
                 '    endclocking:drv_cb\n' \
                 '    clocking mon_cb @(posedge clk);\n' \
                 '        //default input #1step ;\n' \
                 '        //output  in_vld;\n' \
                 '    endclocking:mon_cb\n' \
                 '    modport drv_mp (\n' \
                 '        clocking drv_cb\n' \
                 '    );\n' \
                 '    modport mon_mp (\n' \
                 '        clocking mon_cb\n' \
                 '    );\n' \
                 'endinterface\n\n' \
        # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()


def gen_uvm_agent_base_seq(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_base_seq.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_base_seq.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_BASE_SEQ__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_BASE_SEQ__SV' + '\n'*3
    line_arry += 'class ' + agent_name + '_base_seq extends uvm_sequence;\n\n' \
                 '    int      m_send_num;\n' \
                 '    `uvm_object_utils_begin('+agent_name+'_base_seq)\n' \
                 '        `uvm_field_int(m_send_num,UVM_ALL_ON)\n' \
                 '    `uvm_object_utils_end\n\n' \
                 '    `uvm_declare_p_sequencer('+agent_name+'_sqr)\n\n' \
                 '    function new(string name=\"'+agent_name+'_base_seq\");\n' \
                 '        super.new(name);\n' \
                 '        m_send_num = 1;\n' \
                 '    endfunction : new\n\n' \
                 '    virtual task body();\n' \
                 '        '+agent_name+'_trans tr;\n' \
                 '        repeat(m_send_num) begin\n' \
                 '            tr = new();\n' \
                 '            tr.randomize();\n' \
                 '            `uvm_send(tr);\n' \
                 '        end\n' \
                 '    endtask\n\n' \
                 'endclass\n\n' \


    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_agent_trans(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_trans.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_trans.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_TRANS__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_TRANS__SV' + '\n'*3
    line_arry += 'class ' + agent_name + '_trans extends uvm_sequence_item;\n\n' \
                 '    `uvm_object_utils_begin('+agent_name+'_trans)\n' \
                 '    `uvm_object_utils_end\n\n' \
                 '    extern constraint trans_cons;\n\n' \
                 '    function new(string name=\"'+agent_name+'_trans\");\n' \
                 '        super.new(name);\n' \
                 '    endfunction \n\n' \
                 '    function bit self_define_do_compare('+agent_name+'_trans cmp_trans, output string diff, input int kind = -1);\n' \
                 '        return 1;\n' \
                 '    endfunction\n\n' \
                 'endclass\n\n' \
                 'constraint '+agent_name+'_trans::trans_cons{\n' \
                 '    //soft m_pkg_len dist {[0:2] :/ 1, 3 :/ 1};\n' \
                 '}\n' \

    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_agent_sqr(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_sqr.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_sqr.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_SQR__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_SQR__SV' + '\n'*3
    line_arry += 'class ' + agent_name + '_sqr extends uvm_sequencer;\n\n' \
                 '    `uvm_component_utils_begin('+agent_name+'_sqr)\n' \
                 '    `uvm_component_utils_end\n\n' \
                 '    function new(string name=\"'+agent_name+'_sqr\",uvm_component parent);\n' \
                 '        super.new(name);\n' \
                 '    endfunction \n\n' \
                 'endclass\n\n' \


    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_agent_drv(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_drv.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_drv.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_DRV__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_DRV__SV' + '\n'*3
    line_arry += 'class ' + agent_name + '_drv extends uvm_driver;\n\n' \
                 '    `uvm_component_utils_begin('+agent_name+'_drv)\n' \
                 '    `uvm_component_utils_end\n\n' \
                 '    '+agent_name+'_agt_cfg                        m_cfg;\n' \
                 '    virtual '+agent_name+'_if                     m_vif;\n' \
                 '    common_self_debug_scb#('+agent_name+'_trans)  m_debug_scb;\n' \
                 '    int                                           m_get_trans_cnt;\n' \
                 '    extern function new(string name=\"'+agent_name+'_drv\",uvm_component parent = null);\n' \
                 '    extern virtual function void build_phase(uvm_phase phase);\n' \
                 '    extern virtual task run_phase(uvm_phase phase);\n' \
                 '    extern virtual task init_interface();\n' \
                 '    extern virtual task send_transaction();\n' \
                 '    extern virtual task drv_idle();\n\n' \
                 'endclass\n\n' \
                 'function '+agent_name+'_drv::new(string name=\"'+agent_name+'_drv\",uvm_component parent=null);\n' \
                 '    super.new(name,parent);\n' \
                 '    this.m_get_trans_cnt = 0;\n' \
                 'endfunction : new\n\n' \
                 'function void '+agent_name+'_drv::build_phase(uvm_phase phase);\n' \
                 '    super.build_phase(phase);\n\n' \
                 '    if(!uvm_config_db#(virtual '+agent_name+'_if)::get(this,\"\",\"m_vif\",m_vif)) begin\n' \
                 '        `uvm_fatal(get_full_name,\"virtual interface must be set for agent_driver!!!\")\n' \
                 '    end\n' \
                 'endfunction\n' \
                 'task '+agent_name+'_drv::run_phase(uvm_phase phase);\n' \
                 '    super.run_phase(phase);\n' \
                 '    `uvm_info(get_full_name,\"task phase run_phase start\",UVM_NONE);\n' \
                 '    this.init_interface();\n' \
                 '    fork\n' \
                 '        send_transaction();\n' \
                 '    join_none\n' \
                 'endtask\n\n' \
                 'task '+agent_name+'_drv::init_interface();\n' \
                 '    `uvm_info(get_full_name,\"add init_interface code here \",UVM_NONE);\n' \
                 'endtask\n\n' \
                 'task '+agent_name+'_drv::send_transaction();\n' \
                 '    '+agent_name+'_trans drv_tr;\n' \
                 '    bit get_pkt;\n' \
                 '    while(1) begin\n' \
                 '        @(m_vif.drv_cb);\n' \
                 '        if(this.m_cfg.m_drv_get_trans_en == 0 ) begin\n' \
                 '            continue;\n' \
                 '        end\n\n' \
                 '        if(seq_item_port.has_do_available()) begin\n' \
                 '            seq_item_port.get_next_item(req);\n' \
                 '            if(!$cast(drv_tr,req)) begin\n' \
                 '                `uvm_fatal(get_full_name,\"type of trans from driver not match!!!\")\n' \
                 '            end\n' \
                 '            this.m_get_trans_cnt++;\n' \
                 '            //if self_debug,please uncommnent the following code\n' \
                 '            //if(this.m_cfg.m_self_debug_en == 1) begin\n' \
                 '            //    `uvm_info(get_full_name,$sformatf(\"get %0d trans\",m_get_trans_cnt),UVM_NONE);\n' \
                 '            //    this.m_debug_scb.send_rm_trans_to_cmp(drv_tr);\n' \
                 '            //end\n' \
                 '            seq_item_port.item_done();\n' \
                 '        end\n' \
                 '    end\n' \
                 'endtask\n\n' \
                 'task '+agent_name+'_drv::drv_idle();\n' \
                 '    `uvm_info(get_full_name,\"add drv_idle code here\",UVM_NONE);\n' \
                 'endtask\n\n'  \


    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

def gen_uvm_agent_mon(prj_name,author_name,file_path,agent_name,block_name):

    init_path = os.path.join(file_path , agent_name + '_mon.sv')
    env_file = open(init_path,'w',encoding='utf-8')
    line_arry = ''
    file_name = agent_name + '_mon.sv'
    line_arry += gen_description(prj_name,author_name,file_name)
    line_arry += '`ifndef  ' + agent_name.upper() + '_MON__SV\n'
    line_arry += '`define  ' + agent_name.upper() + '_MON__SV' + '\n'*3
    line_arry += 'class ' + agent_name + '_mon extends uvm_monitor;\n\n' \
                 '    `uvm_component_utils_begin('+agent_name+'_mon)\n' \
                 '    `uvm_component_utils_end\n\n' \
                 '    '+agent_name+'_agt_cfg                        m_cfg;\n' \
                 '    virtual '+agent_name+'_if                     m_vif;\n' \
                 '    uvm_analysis_port#(uvm_sequence_item)         m_ap;\n' \
                 '    common_self_debug_scb#('+agent_name+'_trans)  m_debug_scb;\n' \
                 '    int                                           m_mon_trans_cnt;\n' \
                 '    extern function new(string name=\"'+agent_name+'_mon\",uvm_component parent = null);\n' \
                 '    extern virtual function void build_phase(uvm_phase phase);\n' \
                 '    extern virtual task run_phase(uvm_phase phase);\n' \
                 '    extern virtual task mon_transaction();\n\n' \
                 'endclass\n\n' \
                 'function '+agent_name+'_mon::new(string name=\"'+agent_name+'_mon\",uvm_component parent=null);\n' \
                 '    super.new(name,parent);\n' \
                 '    this.m_mon_trans_cnt = 0;\n' \
                 'endfunction : new\n\n' \
                 'function void '+agent_name+'_mon::build_phase(uvm_phase phase);\n' \
                 '    super.build_phase(phase);\n\n' \
                 '    if(!uvm_config_db#(virtual '+agent_name+'_if)::get(this,\"\",\"m_vif\",m_vif)) begin\n' \
                 '        `uvm_fatal(get_full_name,\"virtual interface must be set for agent_monitor!!!\")\n' \
                 '    end\n' \
                 '    m_ap = new(\"m_ap\", this);\n' \
                 'endfunction\n' \
                 'task '+agent_name+'_mon::run_phase(uvm_phase phase);\n' \
                 '    super.run_phase(phase);\n' \
                 '    `uvm_info(get_full_name,\"task phase run_phase start\",UVM_NONE);\n' \
                 '    fork\n' \
                 '        mon_transaction();\n' \
                 '    join_none\n' \
                 'endtask\n\n' \
                 'task '+agent_name+'_mon::mon_transaction();\n' \
                 '    '+agent_name+'_trans mon_tr;\n' \
                 '    `uvm_info(get_full_name,\"add mon_transaction code here\",UVM_NONE);\n' \
                 '    //while(1) begin\n' \
                 '    //    @(m_vif.mon_cb);\n' \
                 '    //    if( this.m_cfg.m_mon_stop_mon_en ) begin\n' \
                 '    //        continue;\n' \
                 '    //    end\n' \
                 '    //    if( a pkt has finish ) begin\n' \
                 '    //        this.m_mon_trans_cnt ++;\n' \
                 '    //        if( this.m_cfg.m_mon_send_en == 1) begin\n' \
                 '    //            this.m_ap.write(mon_tr);\n' \
                 '    //        end\n' \
                 '    //        if( this.m_cfg.m_self_debug_en == 1) begin\n' \
                 '    //            this.m_debug_scb.send_dut_trans_to_cmp(mon_tr);\n' \
                 '    //        end\n' \
                 '    //    end\n' \
                 '    //end\n' \
                 'endtask\n\n'  \


    # end of harness
    line_arry += '`endif\n'
    env_file.write(line_arry)
    env_file.close()

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    uvm_file_name = r'E:\uvm_test_top'
    author_name   = 'ryan.yu'
    agent_arry = {'axis':'UVM_ACTIVE'}
    prj_name = 'bootis'
    block_name = 'top'
    if (os.path.exists(uvm_file_name)):
        raise Exception(r'{uvm_file_name}已经存在不可创建,继续使用该目录')
        #os.remove(uvm_file_name)
    else:
        os.mkdir(uvm_file_name)
        # creat cfg in uvm_file_name
        cfg_file = os.path.join(uvm_file_name, 'cfg')
        os.mkdir(cfg_file)
        gen_uvm_cfg_file(cfg_file,block_name,agent_arry)

        # creat common_utils in uvm_file_name
        common_utils_file = os.path.join(uvm_file_name, 'common_utils')
        os.mkdir(common_utils_file)
        gen_uvm_common_dec(prj_name,author_name,common_utils_file,block_name)
        gen_uvm_common_draw_table(prj_name, author_name, common_utils_file, block_name)
        gen_uvm_common_report_server(prj_name, author_name, common_utils_file, block_name)
        gen_uvm_common_self_debug_scb(prj_name, author_name, common_utils_file, block_name)
        gen_uvm_common_scb(prj_name, author_name,common_utils_file, block_name)
        gen_uvm_common_lib_pkg(prj_name, author_name, common_utils_file, block_name)

        # creat doc in uvm_file_name
        doc_file = os.path.join(uvm_file_name, 'doc')
        os.mkdir(doc_file)

        #creat env in uvm_file_name
        env_file = os.path.join(uvm_file_name, 'env')
        os.mkdir(env_file)
        gen_uvm_env(prj_name,author_name,env_file, block_name,agent_arry)
        gen_uvm_env_cfg(prj_name,author_name,env_file, block_name,agent_arry)
        gen_uvm_rm(prj_name,author_name,env_file, block_name,agent_arry)
        gen_uvm_checker(prj_name, author_name, env_file, block_name, agent_arry)
        gen_uvm_vsqr(prj_name,author_name,env_file, block_name,agent_arry)

        # creat ral in uvm_file_name
        ral_file = os.path.join(uvm_file_name, 'ral')
        os.mkdir(ral_file)

        # creat self_utils in uvm_file_name
        self_utils_file = os.path.join(uvm_file_name, 'self_utils')
        os.mkdir(self_utils_file)

        #creat agent file
        for key,value in agent_arry.items() :
            tmp_agent_name = key
            agent_file = os.path.join(uvm_file_name, 'self_utils', tmp_agent_name+'_agent')
            if (os.path.exists(agent_file) == False):
                os.mkdir(agent_file)
            agent_src_file = os.path.join(uvm_file_name, 'self_utils', tmp_agent_name + '_agent', 'src')
            if  (os.path.exists(agent_src_file) == False):
                os.mkdir(agent_src_file)
            gen_uvm_agent_file(prj_name,author_name,agent_file,tmp_agent_name,block_name)
            gen_uvm_agent(prj_name,author_name,agent_src_file,tmp_agent_name,block_name)
            gen_uvm_agent_trans(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)
            gen_uvm_agent_dec(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)
            gen_uvm_agent_drv(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)
            gen_uvm_agent_mon(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)
            gen_uvm_agent_if(prj_name, author_name, agent_src_file,  tmp_agent_name, block_name)
            gen_uvm_agent_pkg(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)
            gen_uvm_agent_sqr(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)
            gen_uvm_agent_base_seq(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)
            gen_uvm_agent_cfg(prj_name, author_name, agent_src_file, tmp_agent_name, block_name)

        # creat harness in uvm_file_name
        harness_file = os.path.join(uvm_file_name, 'harness')
        os.mkdir(harness_file)
        gen_uvm_harness(prj_name, author_name, harness_file, block_name,agent_arry)

        # creat sim in uvm_file_name
        sim_file = os.path.join(uvm_file_name, 'sim')
        os.mkdir(sim_file)
        gen_uvm_makefile(prj_name,author_name,sim_file,block_name)
        sim_log_file = os.path.join(sim_file, 'log')
        os.mkdir(sim_log_file)
        sim_rc_file = os.path.join(sim_file, 'rc')
        os.mkdir(sim_rc_file)
        sim_wave_file = os.path.join(sim_file, 'wave')
        os.mkdir(sim_wave_file)

        # creat tc in uvm_file_name
        tc_file = os.path.join(uvm_file_name, 'tc')
        os.mkdir(tc_file)
        gen_uvm_tc_file(prj_name, author_name, tc_file, block_name)




# See PyCharm help at https://www.jetbrains.com/help/pycharm/
