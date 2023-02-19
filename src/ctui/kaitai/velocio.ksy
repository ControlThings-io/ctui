meta:
  id: velocio
  title: Velocio Protocol
  license: CCO-1.0
doc: The Velocio protocol is a propritary protcol used by Velocio vBuilder and vFactory to program the Velocio Ace and Branch PLCs.
seq:
  - id: prot_id
    size: 3
    doc: Magic number for Velocio protocol (56FFFF)
  - id: f_len
    size: 2
    doc: Length of full serial frame
  - id: func
    size: 1
    type: u1be
    enum: func_types
  - id: func_data
enums:
  func_types:
    0xF0: change_debug_state
    0xF1: change_execution_state
    0xF3: request_status
    0xF4: set_breakpoint
    0xF5: Stopped Object Request
    0x14: Get Device Properties
    0x10: enumerate_tags
    0x40: ??? (no changes)
    0x91: set_sime
    0x92: read_time
    0xAA: erase_program

