# Baseline terminal key handling analysis

The package already contained partial ANSI/caret sequence handling in `gibson/render/input.py`, but ISPF panel code paths were inconsistent. Some read `res.key or res.text`, while others consumed `.text` directly. This allowed PF/TAB escape sequences such as `^[OR`, `^[[18~` and `^[[19~` to appear inside option fields.

The fix centralizes leaked-control recognition and normalizes ISPF-style panel input through `panel_input_value()` / `read_panel_command()`.
