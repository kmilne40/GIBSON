# Terminal key mapping implementation

Added central text/caret-form control sequence mapping in `gibson/render/aid_keys.py` and panel normalization helpers in `gibson/render/input.py`.

Recognised sequences include PF3/F3 (`^[OR`), PF7/F7 (`^[[18~`), PF8/F8 (`^[[19~`), PF12/F12 (`^[[24~`) and TAB. Recognised sequences are returned as logical key events and are not inserted as printable text into ISPF-style command fields.
