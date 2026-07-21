# OMVS Tooling Static Security Checks

Completed checks:
- `python -m compileall -q gibson tests` passed.
- No `shell=True` added.
- No host command execution added.
- No TFTP/TTP routes added.
- No React8999, port 3270, port 8082 or port 8999 restored.
- Active tooling consults HOSTS.TXT or built-in local aliases.
- Shodan, dig, whois, subfinder, EZrecon and geoloc use fixtures/offline/default-safe behaviour unless explicit providers are configured.
- TShOcker/CATSO is a safe simulation and does not spawn a real shell.
