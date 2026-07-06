# IND$FILE Native Transfer Compatibility

Implemented helper modules:

- `gibson/core/indfile_options.py`
- `gibson/core/indfile_protocol.py`
- `gibson/core/indfile_records.py`
- `gibson/services/tn3270_indfile.py`

These modules detect Transfer-style text and map common options to the safe command-mode transfer engine. Full byte-level 3270 structured-field compatibility is not claimed until live x3270/c3270/s3270 validation is completed.
