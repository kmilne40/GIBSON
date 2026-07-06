# HOSTS.TXT Target Model

OMVS active tooling now reads `/u/<userid>/HOSTS.TXT`. Each block defines a lab target:

```ini
[mainframe]
host=127.0.0.1
aliases=localhost,BINKY,gibson
ports=21,23,80,443,2023,8080,9080,50000
services=ftp,tn3270,http,tomcat,cics,db2,fibs
authorized=true
vuln_profile=gibson-local
notes=Local Gibson training system
```

Active tools refuse targets unless the resolved entry is built-in local or has `authorized=true`.
