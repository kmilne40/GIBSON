# Chapter 7/8 Gibson Command Mapping

| Book example | Gibson command | Status |
|---|---|---|
| Full port scan | `nmap mainframe -p- -T4 --open` | Supported. |
| Service versions | `nmap mainframe -p21,23,443,50000 -sV -T4` | Supported with Gibson port mapping. |
| TN3270 screen | `nmap mainframe -p2023 --script tn3270-screen` | Supported via simulator bridge. |
| VTAM APPLID enum | `nmap mainframe -p2023 --script vtam-enum` | Supported. |
| TSO enum/brute | `nmap mainframe -p2023 --script tso-enum/tso-brute` | Supported via simulator bridge. |
| CICS enum/user enum | `nmap mainframe -p2023 --script cics-enum/cics-user-enum` | Supported. |
| FTP anonymous | `nmap mainframe -p21 --script ftp-anon -sV` | Supported; mirrors vuln/secure mode. |
| DB2 info | `nmap mainframe -p50000 --script db2-das-info -sV` | Supported. |
| DNS | `dig any sighberbank.com` | Supported fixture output. |
| WHOIS | `whois sighberbank.com` | Supported fixture output. |
| Shodan | `shodan search "IKJ56700A port:23"` | Supported fixture output. |
| Subdomains | `subfinder -d sighberbank.com -resolve` | Supported fixture output. |
| Tomcat scan | `nikto -h http://mainframe:8080/manager/html -id tomcat:tomcat -C all` | Supported. |
| Db2 client | `db2connect mainframe IBMUSER SYS1` | Supported. |
| TShOcker | `tshocker --print -p 21 -l --lport 40000 mainframe RUARIV SPRING26` | Safe JCL/CATSO simulation. |
| Tasks | `task add "Review SMF119 records" project:gibson pri:H +cti` | Supported. |
