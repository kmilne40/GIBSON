# VTAM / OMVS Tooling Test Plan

Test groups:
1. Live VTAM R05 proof: ASCII and TN3270 render paths with `BINKY` and no stale `GIBSON PRODUCTION LPAR`.
2. HOSTS.TXT: built-in aliases, R05 alias, authorisation and refusal of unscoped targets.
3. Nmap: Chapter 7/8 examples for ftp-anon, DB2, vtam-enum, full scan and existing NSE bridge.
4. OSINT: subfinder, dig, whois, shodan and ezrecon fixture flows.
5. Web/Db2/access: nikto Tomcat, db2connect, anonymous FTP and TShOcker safe JCL/CATSO simulation.
6. Task: add/list/done/projects/tags and per-user persistence.
7. Regression: ports 80/2023/8080/9080, removed ports, msfconsole and existing CICS/DVCA/CBSA paths.
