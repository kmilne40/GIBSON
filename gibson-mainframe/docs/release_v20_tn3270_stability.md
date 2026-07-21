# Gibson v20 TN3270 Stability Release Notes

## Summary

v20 fixes a TN3270-specific hang reported with `c3270` after entering `L TSO` on the VTAM selector.

## Changed files

- `gibson/render/screen3270.py`
- `gibson/net/telnet3270.py`
- `gibson/services/tn3270_server.py`
- `tests/test_v20_tn3270_stability.py`
- `docs/tn3270_hang_fix.md`
- `docs/tn3270_client_compatibility.md`

## Compatibility

- Netcat/telnet ASCII behaviour is preserved.
- The v19 `--secure` and `--vuln` mode split is preserved.
- The vulnerable training profile remains the compatibility default.
- No fingerprinting layer was reintroduced.

## Technical changes

- TN3270 Erase/Write screens now use WCC `0x42` to restore the keyboard and reset modified data state.
- A central TN3270 input-normalisation helper converts simple TN3270/NVT input into Gibson command strings.
- TN3270 packet reads are bounded with socket timeouts.
- EBCDIC is retained only as fallback/simple-field decoding for inbound TN3270 records.

## Validation

Run:

```bash
python3 -m compileall -q gibson legacy tests
python3 -m pytest -q tests/test_v20_tn3270_stability.py
```

Live client validation should be performed on a VM where `c3270` and `x3270` are installed.
