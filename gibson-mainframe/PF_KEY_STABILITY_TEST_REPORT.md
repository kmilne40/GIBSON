# PF Key Stability Test Report

PF key behaviour from the previous corrective package was preserved while fixing the DSLIST regression:

- `^[OR` maps to PF3/END.
- `^[[18~` maps to PF7/UP.
- `^[[19~` maps to PF8/DOWN.
- `^[[24~` maps to PF12/CANCEL.
- Typed commands such as `E 1` are still preserved as typed commands.
