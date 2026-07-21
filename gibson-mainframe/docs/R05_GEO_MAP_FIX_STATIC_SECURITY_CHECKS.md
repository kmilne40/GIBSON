# Static Security Checks

- No `shell=True` added.
- No host command execution added.
- No external geolocation call is made by default.
- Private IPs are handled by local classifier/override and are not sent to providers.
- Unknown public IPs do not get fake coordinates.
- R05 live rendering uses internal VTAM/block-letter paths.
- No Scapy/live sniffing dependency from honeyZ was imported.
- No TFTP/TTP route added.
- Removed ports remain removed.
