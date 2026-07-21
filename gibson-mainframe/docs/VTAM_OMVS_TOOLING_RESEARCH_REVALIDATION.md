# VTAM / OMVS Tooling Research Revalidation

This update revalidates the simulator design against the attached Chapter 7 and Chapter 8 material and public tool behaviours. Taskwarrior's core workflow is add/list/done with optional project, priority, due-date and tags; Gibson implements that small local subset as a per-user JSON task store. Nmap's NSE-style output model is retained for service/version scans and mainframe-focused scripts such as tn3270-screen, vtam-enum, tso-enum, cics-enum, ftp-anon and db2-das-info. Nikto is represented as a command-line web scanner with Tomcat Manager findings, header observations and secure/vulnerable mode differences. Shodan, dig, whois, subfinder and EZrecon use offline fixtures by default, with API-key/online modes intentionally not enabled automatically.

Safety decisions:
- Active tools consult HOSTS.TXT and refuse unauthorised targets.
- Passive tools use SighberBank fixture data by default.
- No host command execution, shell=True, real exploit shell, real packet sniffing or arbitrary internet scanning is added.
- Online geolocation remains provider-controlled and private/home IPs are handled locally.
