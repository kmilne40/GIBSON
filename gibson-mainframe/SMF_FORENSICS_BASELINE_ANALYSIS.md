# SMF Forensics Baseline Analysis

The previous Gibson audit layer provided SMF-style audit records through generic `AuditEvent` entries and helpers such as `record_smf80`, `record_smf30`, `record_smf7`, and `record_smf`. That was useful for lab signalling, but not detailed enough for forensic workshops.

The new implementation preserves the old audit/event behaviour and adds a structured SMF writer beneath it. Existing audit consumers continue to see `SMF80`, `SMF30`, `SMF7`, `SMF110`, `SMF119`, and similar components, while new SMF-aware commands and zSecure views can query richer structured records.
