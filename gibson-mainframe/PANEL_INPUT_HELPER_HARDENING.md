# Panel Input Helper Hardening

The panel helper contract is preserved and tested:

- typed input such as `E 1` returns text and command as `E 1`;
- PF keys return an empty text field and a logical command such as `END`, `UP`, `DOWN` or `CANCEL`;
- leaked caret-form sequences such as `^[OR`, `^[[18~`, `^[[19~` and `^[[24~` are consumed as logical keys rather than rendered into panel input fields.

The DSLIST workflow now uses that contract without losing the original typed text required for line-command parsing.
