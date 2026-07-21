# TLS and Secure Services

In `--secure` mode Gibson prioritises encrypted administrative and interactive access.

## TSO/TN3270 secure port

The primary VTAM/TSO listener uses port 1023 in secure mode.

```bash
./gibsonctl.sh start --secure
```

Expected startup banner:

```text
GIBSON SECURE MODE ACTIVE
TSO/TN3270 TLS PORT=1023 HTTPS PORT=8443
```

Gibson attempts to wrap the listener with TLS using a simulator-local self-signed certificate. The certificate and key are created under:

```text
~/mfsim/certs/gibson-selfsigned.crt
~/mfsim/certs/gibson-selfsigned.key
```

The key is not a production key. Operators may replace it by setting:

```bash
GIBSON_TLS_CERT=/path/to/cert.pem
GIBSON_TLS_KEY=/path/to/key.pem
```

If certificate generation fails because OpenSSL is unavailable, Gibson records a TLS-unavailable security event and documents the limitation in validation output.

## HTTPS dashboard/API

The dashboard/API remains on port 8443 and is TLS-wrapped in secure mode when certificate generation succeeds.

```bash
curl -k https://127.0.0.1:8443/
```

Plain HTTP routes should not be used for secure-mode administration.

## Vulnerable mode compatibility

`--vuln` preserves existing listener behaviour, including the normal VTAM/TSO port 2023 and classroom-compatible plaintext workflows.

## v20 terminal payload note

In secure mode the terminal listener remains on port 1023. Terminal payload handling uses Gibson's ANSI/ASCII-compatible command path; full EBCDIC/3270 field-map emulation is not required for live interaction.
