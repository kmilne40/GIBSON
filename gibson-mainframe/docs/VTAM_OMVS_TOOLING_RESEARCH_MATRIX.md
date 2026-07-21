# VTAM / OMVS Tooling Research Matrix

| Tool | Gibson command | Chapter link | Implementation |
|---|---|---|---|
| VTAM R05 | `R 05,NAME` | VTAM screen / tn3270-screen | Persisted system identity and live ASCII/TN3270 render-path proof. |
| Nmap | `nmap` | Chapter 7 active scanning | Rich service/version, tn3270-screen, vtam-enum, ftp-anon, DB2 and existing NSE simulator bridge. |
| CICSPWN | `CICSPWN`, `cicspwn` | CICS enumeration | Phase-based safe CICS assessment, transaction access, region summary and forensic correlation. |
| Subfinder | `subfinder -d sighberbank.com` | OSINT/subdomains | Offline SighberBank fixtures with optional output file and resolve mode. |
| dig/whois | `dig`, `whois` | DNS/domain research | Fixture DNS and WHOIS records for SighberBank and lab hosts. |
| Shodan | `shodan search`, `shodan host` | Shodan mainframe searches | Offline mainframe banner fixtures and safe API-key configured flag. |
| Nikto | `nikto -h ... -id ...` | Tomcat Manager | Tomcat Manager finding style with secure/vuln behaviour. |
| geoloc | `geoloc IP` | CTI/geo | FreeIPAPI-inspired command/provider pattern, Livingston override and JSON/CSV. |
| CTI RSS | `cti-rss` | CTI | Existing terminal CTI feed reader retained. |
| EZrecon | `ezrecon` | OSINT workflow | Fixture dorks, subdomain, email and report workflow. |
| Db2 | `db2connect`, `db2` | DB2/DRDA | DRDA banner, subsystem, auth and query output. |
| FTP/JES | `ftp`, Nmap `ftp-anon`, `tshocker` | Initial access | Anonymous FTP in vuln mode, JES messages and safe TShOcker/CATSO simulation. |
| task | `task` | Lab workflow | Taskwarrior-style add/list/done/projects/tags without sync. |
