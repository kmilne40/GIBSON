# Gibson Network Fingerprinting Enhancement

This release adds a compatibility-preserving network fingerprint layer for Gibson services. The goal is to make service-level scanning look more like a mainframe lab without spoofing the host operating system.

## Scope

The enhancement is limited to scanner-visible service behaviour:

- IBM-style FTP greeting and MVS `SYST` response.
- Conservative Telnet/TN3270 option prologue on the VTAM/TSO listener.
- Existing TN3270E listener negotiation retained and documented through shared constants.
- Deliberate HTTP headers for the dashboard and REST gateway.
- Central service profiles in `gibson/net/service_profiles.py`.

It does **not** attempt OS-level Nmap fingerprint spoofing. Nmap OS detection uses low-level TCP/IP stack traits that normal Python socket services should not attempt to forge.

## Files

- `gibson/net/fingerprints.py` — shared banner/header helpers.
- `gibson/net/telnet3270.py` — Telnet/TN3270/TN3270E constants and initial negotiation bytes.
- `gibson/net/service_profiles.py` — central profiles for scanner-visible service identity.
- `tests/test_protocol_fingerprints.py` — socket-level regression coverage for FTP and REST fingerprint responses.
- `tests/test_nmap_service_detection.py` — profile sanity tests.

## Expected scanner behaviour

On a host with Nmap installed, start Gibson and run:

```bash
./run_gibson.sh
nmap -sV -p 2023,2111,8082,8443,50000 127.0.0.1
```

A realistic result should include IBM-like FTP and HTTP/service banners. The exact labels are Nmap-version-dependent because stock Nmap service recognition comes from its local `nmap-service-probes` database.

For the optional TN3270E listener:

```bash
python -m gibson.cli --serve --with-ftp --with-rest --with-tn3270 --no-dashboard --no-db2
nmap -sV --version-all -p 2023,3270 127.0.0.1
```

The TN3270E listener emits Telnet BINARY, END-OF-RECORD, TERMINAL-TYPE and TN3270E negotiation. The line-mode VTAM/TSO listener sends a conservative Telnet/TN3270 prologue once per connection before the legacy welcome screen.

## FTP examples

```bash
ftp 127.0.0.1 2111
```

Expected initial response:

```text
220-FTPD1 IBM FTP CS V2R5 at GIBSON, HH:MM:SS on YYYY-MM-DD.
220 Connection will close if idle for more than 5 minutes.
```

Useful commands:

```text
SYST
FEAT
HELP
TYPE A
TYPE I
SITE FILETYPE=JES
SITE FILETYPE=SQL
```

## HTTP headers

Dashboard and REST responses include deliberate headers:

```text
Server: IBM_HTTP_Server
X-Powered-By: Gibson z/OS Simulator
X-Gibson-Service: z/OS-simulator
```

These headers replace accidental Python/Werkzeug-style identity leakage in the managed stdlib HTTP services.

## Limitations

- Stock Nmap recognition depends on the Nmap version and local `nmap-service-probes` database.
- Raw DB2 DRDA identification remains limited unless a full DRDA-compatible handshake is implemented later.
- OS fingerprinting is intentionally not attempted.
- This is simulation-only and must not be used as guidance for attacking real systems.

## Safety

All scanner-facing behaviour is passive or local to Gibson services. The enhancement does not add real exploit capability, does not scan external hosts, and does not change Gibson's existing safe `nmap-sim.py` workflows.
