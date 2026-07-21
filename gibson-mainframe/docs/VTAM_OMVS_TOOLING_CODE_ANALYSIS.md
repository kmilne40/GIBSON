# VTAM / OMVS Tooling Code Analysis

Key live VTAM paths inspected and changed:
- `gibson/core/state.py` now persists `system_hostname` to `system_identity.json` and exports it to `GIBSON_SYSTEM_HOSTNAME` when R05 changes identity.
- `gibson/services/telnet_server.py` already calls `coloured_ascii_vtam_screen(... system_name=self.state.get_system_hostname())` and compact mode with the same state accessor.
- `gibson/services/tn3270_server.py` already calls `tn3270_vtam_screen(... system_name=self.state.get_system_hostname())`.
- `gibson/screens/vtam_model.py` retains a static GIBSON default only when the selected hostname is exactly GIBSON. Other names use the block renderer.

OMVS tooling additions:
- `gibson/tools/host_aliases.py` now supports HOSTS.TXT blocks and authorisation.
- `gibson/tools/omvs_security_tools.py` implements subfinder, dig, whois, shodan, geoloc, nikto, db2connect, task, tshocker and ezrecon commands.
- `gibson/tools/omvs_nmap.py` now covers ftp-anon, vtam-enum, DB2/DRDA and service-version sweeps directly before falling through to the NSE simulator bridge.
- `gibson/services/ftp_server.py` supports anonymous FTP in Gibson vuln mode and JES-style completion messages.
