# Gibson Mainframe Simulator

**Gibson** is a local mainframe security training simulator for learning mainframe operations, mainframe security, red-team techniques, blue-team investigation, and modern mainframe integration in a safe lab environment.

It gives learners a practical place to explore TSO, ISPF, RACF-style security, JES, SDSF, OMVS/USS, CICS, Db2, FTP, TELNET, APIs, dashboards, CTI/RSS-style workflows, and security evidence without needing access to a production mainframe.

> Gibson is a simulator. It is designed for authorised training, classroom use, defensive research, and controlled penetration-testing education. It is not a real z/OS system and it is not permission to test systems you do not own or have explicit authorisation to assess.

---

## Why Gibson exists

Mainframe security is difficult to learn safely.

Real mainframes are expensive, heavily controlled, business-critical, and rarely available for hands-on experimentation. That creates a gap: security professionals may be expected to assess or defend mainframe-connected environments without ever having had a safe place to practise the concepts.

Gibson was created to close that gap.

It provides a controlled local training system where learners can:

- log on through a mainframe-style terminal selector;
- practise TSO, ISPF, CICS, Db2, JES, SDSF, and OMVS workflows;
- learn RACF-style identity and access-control concepts;
- explore vulnerable and secure application behaviour;
- test local FTP, TELNET, API, Db2, CICS, and web application paths;
- understand how red-team actions create defensive evidence;
- build blue-team timelines from SMF-style records, dashboard alerts, logs, and security events.

Gibson’s purpose is teaching. It favours practical learning, repeatable labs, and security understanding over perfect emulation of IBM software.

---

## What Gibson includes

Gibson brings together traditional and modern mainframe security topics:

- VTAM-style selector and terminal access
- TSO `READY` command environment
- ISPF-style panels and editor workflows
- RACF-style users, groups, profiles, classes, permits, `SETROPTS`, and `RVARY`
- JES, JCL, spool, and SDSF-style review
- OMVS / USS shell commands and security tooling
- FTP and TELNET training services
- CICS transactions, CICS security concepts, DVCA, and Hack3270
- Db2, DB2I, SPUFI, SQL, catalogues, and privilege concepts
- FIBS banking training application
- CBSA-style REST API training
- OAuth/JWT/token security labs
- Dashboard and monitoring views
- CTI/RSS-style threat-context workflows
- SMF-style records and `SECEVENTS`
- Vulnerable and secure training modes

---

## Download

Clone the repository:

```bash
git clone https://github.com/<your-org>/<your-gibson-repo>.git
cd <your-gibson-repo>
```

Or download a release ZIP from the GitHub **Releases** page, then extract it:

```bash
unzip gibson-mainframe.zip
cd gibson-mainframe
```

Replace the placeholder repository URL with the actual GitHub repository path for your Gibson repo.

---


## Requirements
Although there is a recommended environment - any python3 (preferably Linux environment or WSL etc) will work
everything should install pretty simply with:

./install_gibson.sh --venv  (You may need sudo, depending on your distribution)

Then once that is complete simply run:

./gibsonctl.sh start

Then connect with netcat or a TN3270 client such as c3270 on port 2023.

nc 127.0.0.1 2023 (example, depends on your IP address)

Recommended environment:

- Linux, Kali, Debian, Ubuntu, or a compatible Linux VM
- Python 3
- `python3-venv`
- `ncat` or `nc`
- optional: `c3270`
- optional: Docker or Podman if using the browser-based terminal sidecar

On Debian/Ubuntu-style systems:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ncat curl unzip
```

Optional 3270 terminal:

```bash
sudo apt-get install -y c3270

```

---



```bash
./gibsonctl.sh start --secure
```

Check status:

```bash
./gibsonctl.sh status
```


Stop Gibson:

```bash
./gibsonctl.sh stop
```

Restart Gibson:

```bash
./gibsonctl.sh restart
```

---

## Default ports

The exact service set depends on startup options, vulnerable/secure mode, and whether optional components are enabled.

| Port | Service | Use |
|---:|---|---|
| `80` | Welcome / orientation site | Start page and orientation content |
| `2022` | OMVS / USS-style path | USS-style shell path where enabled |
| `2023` | VTAM-style selector | Main terminal path for `L TSO`, `L CICS`, and `L DB2` |
| `2111` | FTP training service | FTP lab service |
| `3270` | TN3270 compatibility | 3270-style terminal compatibility where enabled |
| `8023` | Browser terminal | Optional Guacamole browser terminal |
| `8080` | Main app/API service | CBSA, DVCA, Hack3270, REST/API training paths |
| `8443` | Dashboard | Gibson monitoring and administration dashboard |
| `9080` | FIBS | Banking/security academy application |
| `50000` | Db2 listener | Db2-style listener |
| `50001` | Db2 interactive / WebSocket | Db2 interactive support where enabled |

Quick checks:

```bash
curl -i http://127.0.0.1/
curl -k -i https://127.0.0.1:8443/
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:9080/
ncat -vz 127.0.0.1 2023
ncat -vz 127.0.0.1 2111
```

---

## Port 80 welcome site

Open the Gibson welcome/orientation page:

```text
http://127.0.0.1/
```

This page is intended as the first browser stop after Gibson starts. It gives learners an orientation point before moving into terminal, dashboard, API, and application labs.

If port `80` is already in use or your system restricts low-numbered ports, check the Gibson logs and active listeners:

```bash
./gibsonctl.sh status
./gibsonctl.sh ports
ss -ltnp
```

---

## Dashboard on port 8443

Open the dashboard:

```text
https://127.0.0.1:8443/
```

Default dashboard credentials:

```text
Username: admin
Password: gibsonadmin!
```

Because Gibson uses a local training certificate, your browser may show a certificate warning. Proceed only when you are connecting to your own local Gibson instance.

Command-line check:

```bash
curl -k -i https://127.0.0.1:8443/
```

---

## IPL and master console process

Gibson includes an IPL-style startup workflow through the master console. During IPL, the operator responds to outstanding reply messages using `R nn,<reply>` syntax.

Typical Gibson IPL reply sequence:

| Reply | Purpose | Example |
|---|---|---|
| `R 01` | IPL/load parameter reply | `R 01,CLPA` |
| `R 02` | IEASYS/member/default reply | `R 02,U` |
| `R 03` | Continue IPL confirmation | `R 03,Y` |
| `R 04` | Define or confirm IPL MFA PIN | `R 04,4321` |
| `R 05` | Define simulated hostname/alias | `R 05,GIBSON` |
| `R 06` | Define DVCA/CBSA training PIN or skip | `R 06,1234` or `R 06,SKIP` |

Useful master console commands:

```text
D R,L
D IPLINFO
D SERVICES
D SECURITY,DAILY
D DVCAPIN
HELP
```

Meaning:

- `D R,L` shows outstanding reply requests.
- `D IPLINFO` shows IPL information and selected startup values.
- `D SERVICES` shows managed Gibson services.
- `D SECURITY,DAILY` shows a security-event summary.
- `D DVCAPIN` shows DVCA/CBSA training PIN status.

You can also start Gibson with a preselected IPL MFA PIN:

```bash
./gibsonctl.sh start --vuln --ipl-mfa-pin 4321
```

---

## Connect with `ncat`

The main terminal selector listens on port `2023`.

```bash
ncat 127.0.0.1 2023
```

You should see a selector similar to:

```text
LOGON using L TSO, L CICS or L DB2.

Logon Type:
```

At the selector, choose one of:

```text
L TSO
L CICS
L DB2
```

---

## Connect with `c3270`

Install `c3270` if needed:

```bash
sudo apt-get install -y c3270
```

Connect to Gibson:

```bash
c3270 127.0.0.1:2023
```

If you use a local host alias:

```bash
c3270 mainframe:2023
```

If your terminal profile requires a named LU or model, adjust the command for your local `c3270` configuration.

---

## Log on to TSO

Connect to port `2023`:

```bash
ncat 127.0.0.1 2023
```

Select TSO:

```text
L TSO
```

Use either default account:

```text
USERID: IBMUSER
PASSWORD: SYS1
```

or:

```text
USERID: GUEST
PASSWORD: GUEST
```

A successful TSO logon ends at:

```text
READY
```

Example first commands:

```text
HELP
PROFILE
LISTUSER IBMUSER
SECEVENTS
LOGOFF
```

---

## Log on to CICS

Connect to port `2023`:

```bash
ncat 127.0.0.1 2023
```

Select CICS:

```text
L CICS
```

When prompted, use either:

```text
IBMUSER / SYS1
```

or:

```text
GUEST / GUEST
```

You should reach the CICS transaction prompt:

```text
ENTER TRANSACTION:
```

Useful starter transactions:

```text
CESN
CESF
CEMT
CECI
CEDA
CEBR
CEDF
DVCA
HACK3270
```

---

## Log on to Db2

Connect to port `2023`:

```bash
ncat 127.0.0.1 2023
```

Select Db2:

```text
L DB2
```

When prompted, use either:

```text
IBMUSER / SYS1
```

or:

```text
GUEST / GUEST
```

You should reach a Db2-style command prompt:

```text
ENTER SQL OR COMMAND:
```

Useful starter commands:

```text
HELP
SHOW DBS
SHOW TABLES
SHOW USERS
SHOW PRIVS
SPUFI
RUN SQL SELECT * FROM SYSIBM.SYSTABLES
EXIT
```

---

## FTP training service

The FTP training service usually listens on port `2111`.

```bash
ftp 127.0.0.1 2111
```

Default credentials:

```text
IBMUSER / SYS1
GUEST / GUEST
```

Common FTP commands:

```text
ls
dir
get <file>
put <file>
bye
```

FTP is included for training. Treat it as a cleartext service and review the evidence it creates.

---

## TELNET compatibility

TELNET-style access can be used for simple terminal testing.

Main selector:

```bash
telnet 127.0.0.1 2023
```

Compatibility TELNET port where enabled:

```bash
telnet 127.0.0.1 23
```

Use `ncat` if your local TELNET client handles screen or line mode poorly.

---

## FIBS on port 9080

Open the FIBS banking/security application:

```text
http://127.0.0.1:9080/
```

Command-line check:

```bash
curl -i http://127.0.0.1:9080/
```

FIBS is used for banking-style application security labs, identity workflows, transaction review, and web/API evidence.

---

## Main API service on port 8080

Open the main application/API service:

```text
http://127.0.0.1:8080/
```

Command-line check:

```bash
curl -i http://127.0.0.1:8080/
```

Port `8080` is used for CBSA-style REST API training, DVCA/Hack3270 routes, and related web/API labs where enabled.

---

## Useful first-session workflow

After starting Gibson:

```bash
./gibsonctl.sh status
./gibsonctl.sh ports
curl -i http://127.0.0.1/
curl -k -i https://127.0.0.1:8443/
ncat 127.0.0.1 2023
```

Then at the selector:

```text
L TSO
IBMUSER
SYS1
HELP
PROFILE
SECEVENTS
LOGOFF
```

This confirms that the package is running, browser services respond, terminal access works, credentials are valid, and security-event review is available.

---

## Evidence-first learning

Gibson is designed to teach both action and evidence.

After security-relevant activity, review:

```text
SECEVENTS
SMF LIST
SMF TIMELINE
```

Where appropriate, also review:

- dashboard alerts on port `8443`;
- SDSF-style panels;
- API audit routes;
- local Gibson logs;
- service status and port listeners.

The aim is not only to run commands, but to understand what a defender could prove afterwards.

---

## Common troubleshooting

### Port is already in use

```bash
./gibsonctl.sh ports
ss -ltnp
```

Stop Gibson or the conflicting service:

```bash
./gibsonctl.sh stop
```

### Gibson did not start cleanly

```bash
./gibsonctl.sh status
tail -n 100 logs/gibson.log
```

### Terminal connects but commands do not work

Check which environment you are in:

| Prompt | Environment |
|---|---|
| `READY` | TSO |
| `ENTER TRANSACTION:` | CICS |
| `ENTER SQL OR COMMAND:` | Db2 |
| `IBMUSER:/u/ibmuser: >` | OMVS / USS |
| Master console display | Operator/master console |

Use the correct command set for the current environment.

### Browser shows a TLS warning on 8443

This is expected for a local training certificate. Proceed only for your own local Gibson instance.

### Web terminal not available on 8023

Check whether the optional browser terminal was installed and enabled:

```bash
./gibsonctl.sh web-status
./gibsonctl.sh web-status --show-credentials
```

Raw terminal access on port `2023` remains available without the browser terminal.

---

## Security and authorised use

Gibson includes deliberately vulnerable behaviours for teaching.

Use Gibson only:

- on your own machine;
- in a lab you control;
- in a classroom or range where you have permission;
- under written rules of engagement for authorised training or assessment.

Do not use Gibson lab commands, payloads, API tests, scanning, credentials, or techniques against third-party systems.

---

## Project status

Gibson is a training simulator and evolves over time. Commands, ports, routes, and lab behaviour may vary between releases.

Use the built-in help and status commands to confirm what is enabled in your current build:

```bash
./gibsonctl.sh status
./gibsonctl.sh ports
ncat 127.0.0.1 2023
```

Inside TSO:

```text
HELP
D SERVICES
SECEVENTS
```

---

## Licence and permitted use

Gibson is **source-available for non-commercial learning and research**.

The recommended licence model for this repository is:

- **Software:** PolyForm Noncommercial License 1.0.0
- **Documentation, manuals, diagrams, slides, and training material:** Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International, or a project-specific Gibson Training Materials Licence
- **Commercial or paid training use:** allowed only with prior written permission from the project owner

Gibson is free to use for personal learning, research, defensive study, authorised lab practice, and non-commercial education. It is not licensed for resale, commercial training delivery, commercial lab platforms, hosted cyber ranges, paid workshops, paid bootcamps, or incorporation into another commercial product or service without written permission.

### Permitted non-commercial use

You may use Gibson for:

- personal study;
- academic or independent research;
- internal skills development where Gibson itself is not sold as a service;
- free community talks and presentations;
- free workshops with prior written permission;
- demonstrations at security meetups, conferences, user groups, or educational events where access to Gibson is not sold as the product;
- authorised defensive training and controlled lab practice.

### Commercial use requires written permission

Commercial use includes, but is not limited to:

- selling Gibson or access to Gibson;
- using Gibson in a paid course, bootcamp, workshop, certification, or commercial training product;
- including Gibson in a commercial lab platform, cyber range, LMS, hosted service, or consulting deliverable;
- bundling Gibson with paid materials, subscriptions, or managed services;
- using Gibson to deliver paid professional services;
- modifying, rebranding, repackaging, or redistributing Gibson for commercial purposes;
- incorporating Gibson or substantial parts of Gibson into another product, service, appliance, course, or training environment.

To request permission for commercial use, paid training, redistribution, or integration into another product or platform, contact the project owner before using Gibson.

### Documentation and training material

Unless a separate written agreement says otherwise, Gibson manuals, diagrams, slides, lab guides, screenshots, and training material may not be republished, modified, sold, incorporated into paid training, or redistributed as part of another commercial offering without written permission.

### Not open source in the OSI sense

Because Gibson restricts commercial use, it should be described as **source-available** or **free for non-commercial use**, not as OSI-approved open source.


---

## Acknowledgements

Gibson exists to make mainframe security education more accessible, practical, and safe. It is intended for learners, instructors, defenders, penetration testers, and researchers who need a realistic place to practise mainframe security concepts without risking production systems.
