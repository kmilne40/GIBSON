# PF key auto-submit implementation

PF key auto-submit is implemented only as a panel-context logical AID dispatch, not as global ENTER injection. It is limited to ISPF-style command/option fields through the panel helper. OMVS, TSO READY, editor bodies and password/PIN fields do not use the panel helper and therefore do not auto-submit PF/control sequences.
