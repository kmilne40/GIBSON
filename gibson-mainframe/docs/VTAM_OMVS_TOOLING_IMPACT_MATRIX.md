# VTAM / OMVS Tooling Impact Matrix

| Area | Files | Risk | Mitigation |
|---|---|---:|---|
| VTAM R05 live render | `core/state.py`, existing telnet/TN3270 render calls | Medium | Persisted state, env bridge and live-path tests. |
| HOSTS.TXT scope | `tools/host_aliases.py` | Medium | Built-in local aliases and explicit `authorized=true`. |
| Nmap realism | `tools/omvs_nmap.py` | Low | Direct fixture output plus existing simulator compatibility. |
| OMVS tools | `tools/omvs_security_tools.py`, `apps/omvs.py` | Medium | No host commands, no shell=True, fixtures by default. |
| FTP anon/JES | `services/ftp_server.py` | Medium | Anonymous access only in vuln mode; normal auth unchanged. |
| msfconsole regression | `apps/msfconsole_sim.py` | Low | One-shot `-x` run now preselects the safe Tomcat module when needed. |
| Ports | no listener changes | Low | No removed port restored; port ownership preserved. |
