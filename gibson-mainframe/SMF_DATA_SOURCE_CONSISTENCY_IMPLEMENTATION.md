# SMF data-source consistency implementation

The SMF writer was already mirroring structured records into audit. This release strengthens zSecure views so they read both structured SMF and audit rows, de-duplicate mirrored records, and expose the same evidence consistently in `ZSEC EVENTS`, `ZSEC RARE`, `SMF LIST` and `SMF TIMELINE` workflows.
