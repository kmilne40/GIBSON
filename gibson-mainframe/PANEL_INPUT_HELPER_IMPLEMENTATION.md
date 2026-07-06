# Panel input helper implementation

`panel_input_value()` and `read_panel_command()` now normalize panel input by preferring `InputResult.key`, converting leaked caret-form escape text to logical keys, and stripping known leaked control tokens as a fallback. ISPF panel command reads were updated to use this helper where prior code consumed raw `.text` directly.
