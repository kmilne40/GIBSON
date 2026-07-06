# ICSF Master Key Refresh SMF Implementation

Added a Gibson structured ICSF key-management record for `ICSF_MASTER_KEY_REFRESH`.

Fields include key type, key store, old/new verification pattern, refresh phase, result, reason, ICSF return/reason codes and correlation ID.

`ICSF REFRESH MASTERKEY` now emits this record and `SMF LIST ICSF` / `ZSEC ICSF` expose the evidence.
