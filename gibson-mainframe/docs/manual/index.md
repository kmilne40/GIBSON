# Gibson Mainframe Simulator Technical Manual

> Imported from Gibson_Mainframe_Simulator_Technical_Manual_final-2105.pdf for the port 80 manual site.



<!-- page 1 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Gibson Mainframe Simulator
### Technical Security Training Manual
Version: final1805 source-backed manual
Built from code-derived inventories, command matrices, route matrices, and runtime smoke validation. README files
were not used as the source of truth.


<!-- page 2 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Table of Contents
 Front Matter
 Quick Start Guide
## Front Matter
This manual documents the Gibson Mainframe Simulator package gibson-mainframe-final1805.zip.
It is a practical training manual for mainframe security, penetration testing, blue-team monitoring,
and instructor-led labs. The manual is source-backed: the package code, command handlers,
runtime state objects, route definitions, seeded users, datasets, ports, and Phase 1 inventories are
treated as authoritative.
WARNING: Simulator boundary
Gibson is a simulator. It reproduces mainframe-like workflows, prompts, commands, outputs, and security
concepts for training. It is not a real z/OS system and should not be treated as a substitute for site-specific
IBM documentation or production change control.
IMPORTANT: Documentation source rule
Existing README files were intentionally not used as the source of truth for this manual. Where
README/version statements conflict with the code-derived inventory, the code-derived inventory wins and
the mismatch is recorded in Known Gaps.
### Audience
 Mainframe security analysts learning RACF, TSO, ISPF, SDSF, JES, CICS, Db2, OMVS and logging
concepts.
 Penetration testers and red-team trainers who need a safe environment for mainframe-style
enumeration and control-plane practice.
 Blue-team analysts who want to practise OPERLOG, SMF-like event review, alert triage and
service-state interpretation.
 Instructors building multi-day technical classes around a repeatable simulator.
### Manual conventions
### Convention Meaning
### READY command A command submitted to the simulated TSO READY command
processor.
Console command A command handled by the Master Console controller.
### Source evidence File and line or module evidence discovered in code-derived
inventories.
### Runtime validated Command sequence executed against a fresh temporary
GibsonState or safe command harness.
### Source validated Handler, route, command definition or inventory evidence


<!-- page 3 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
confirmed statically in code.


<!-- page 4 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 5 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
## Quick Start Guide
In this section we’ll get Gibson installed, started, and reachable from the tools you are likely to use
during a mainframe security lab. The goal is not to teach every subsystem yet. The goal is to get you
to a working console, prove the ports are listening, and understand what each window is showing
you before you move into the deeper labs.
IMPORTANT: source-backed quick start
This section was built from install_gibson.sh, gibsonctl.sh, gibson/cli.py, gibson/core/config.py, service
implementations, web-terminal/docker-compose.yml, and safe runtime checks. README material was not
used as authority unless confirmed by code.
### Download, unpack and start Gibson
Use this path when you are setting up a fresh Gibson training system. The useful part is that the
student can see the whole chain: download the package, unpack it, enter the project directory,
install into a Python virtual environment, start the simulator, then answer the first IPL/WTOR
prompts.
### Quick Start command flow
# Download Gibson from:
# https://offensivesec.org/gibson
unzip gibson-mainframe-final1805.zip
cd gibson-mainframe-final
chmod +x install_gibson.sh gibsonctl.sh
./install_gibson.sh --venv
./gibsonctl.sh start
### First IPL / WTOR replies
### R 01,CLPA
### R 02,U
### R 03,Y
### R 04,1234
In Gibson, these replies teach the discipline of responding to operator prompts before assuming the
system is ready. CLPA represents the controlled IPL path used by the simulator, U and Y are
confirmation-style replies in the lab flow, and R 04,1234 is the default MFA PIN reply for the
training build. On a real z/OS system, operator replies are controlled actions and should be visible
through console/automation evidence.
 Executive Summary
 Source Analysis and Validation Methodology
 Chapter 1. Mainframe and Gibson Foundations
 Chapter 2. Installation, Startup, IPL, and Operations
 Chapter 3. Application Architecture Deep Dive
 Chapter 4. Access, Logon, MFA, and VTAM


<!-- page 6 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
 Chapter 5. TSO READY Reference
 Chapter 6. RACF Administration and Security Model


<!-- page 7 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
ACF2
### Command
### Syntax Run From What It Does What To
### Look For
### Security
### Meaning
### Real ACF2
### Meaning
Lab
### ACF2 ACF2 TSO READY Switches the
READY
processor into
### ACF2 command
mode.
### ACF2 MODE
### ACTIVE and
### CURRENT
SETTING: LID.
### Tells the
learner they
are now using
### ACF2-style
commands
rather than
RACF
commands.
### Real systems
enter ACF2
through site-
defined
command
processors and
panels.
### ACF2-1
### SET LID SET LID or SET
ACF
### ACF2 mode Selects logonid
processing.
### LID SETTING
ACTIVE.
### LIDs are the
identity
records that
define who the
user or task is.
### Logonids are
### ACF2 identity
records.
### ACF2-1
LIST LIST userid |
LIST * | LIST
LIKE(mask) |
### LIST UID(n)
### ACF2 LID
setting
### Lists logonids
or selected
identity fields.
### SECURITY,
### NON-CNCL,
### GROUP, UID,
### HOME and
### OMVSPGM
fields.
### Identifies
privileged IDs,
### OMVS access
and grouping.
### LIST displays
logonid records
according to
setting and
scope.
### ACF2-1, ACF2-2
SHOW SHOW ACF2 |
SHOW TSO |
SHOW PSWD |
SHOW DDSN |
### SHOW OMVS
### ACF2 mode Displays ACF2
system, TSO,
password, data
set and OMVS
state.
### Database
names,
password
policy, current
mode and
### OMVS UID/GID
data.
### Shows whether
the security
environment is
enforceable,
auditable and
well
configured.
SHOW
commands
expose ACF2
control
information
subject to
authority.
### ACF2-1
### INSERT/
### CHANGE/
### DELETE LID
### INSERT userid
### PASSWORD(pw
) [SECURITY]
[GROUP(g)]
[UID(n)]
### ACF2 LID
setting
### Creates,
modifies or
deletes
simulated
logonids.
### LOGONID
### DEFINED,
### ALTERED or
### DELETED
messages.
### State-changing
identity
administration;
requires
### SPECIAL in
Gibson.
### Logonid
administration
is tightly
controlled and
auditable.
### ACF2-2
### SET RULE /
### RECKEY
SET RULE;
### RECKEY key
### ADD(resource
### UID(id)
### SERVICE(READ)
### ALLOW)
### ACF2 RULE
setting
### Creates or
updates data
set rule lines.
$KEY output,
### UID clauses
and
### ALLOW/PREVE
### NT service
decisions.
### Shows who can
access a
protected data
set and at what
service level.
### ACF2 rule sets
use
key/resource
and UID
matching
rather than
### RACF profile
syntax.
### ACF2-3
SET
### RESOURCE /
### RECKEY
SET
### RESOURCE(SUR
); RECKEY
### IBMUSER
ADD(IBMUSER.
### SUBMIT
### UID(ALICE)
### SERVICE(READ)
### ALLOW)
ACF2
### RESOURCE
setting
### Creates or
updates
resource rules
such as
### SURROGAT-
style submit-as
controls.
### TYPE(SUR), UID
and SERVICE
fields.
### Resource rules
can control
powerful non-
dataset
capabilities.
### ACF2 resource
rules
participate in
### SAF decisions
for protected
resources.
### ACF2-4
### ACCESS / TEST ACCESS
DSNAME('dsn');
TEST
DSNAME('dsn')
### LID(id)
### SERVICE(READ)
### ACF2 mode Displays
matching rules
or tests
simulated
access.
### ALLOW or
### PREVENT
decision and
matching rule
lines.
### Turns rule
listings into an
evidence-
backed access
decision.
### Real access
tests and
reporting are
central to audit
and
troubleshootin
g.
### ACF2-3, ACF2-4
### ACF2 Concept Gibson Meaning Real ACF2 Meaning RACF Analogue Why It Matters
Logonid / LID A simulated identity A 1-8 character ID and RACF USER profile. Identity attributes drive


<!-- page 8 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
record backed by the user
store.
associated logonid record. privilege and access
decisions.
### UID string UID/GROUP values used to
teach ACF2 grouping.
### A constructed string used
by rules to match users.
### Group/access-list
matching, but not
equivalent.
### Broad UID masks can
allow more access than
intended.
### RULE Dynamic data set rule
equivalent.
### Data set access rule set. DATASET class profile plus
access list.
### Rules answer who can
read, update or alter data.
### RESOURCE FAC/SUR/OPR/APL/VAR
mapped to SAF/RACF-style
classes.
### General resource rule
processing.
### FACILITY, SURROGAT,
### OPERCMDS, APPL,
RACFVARS classes.
### Non-dataset resources
often control powerful
operations.
### GSO / CONTROL Training view of global
options and data sets.
### Global System Options and
infostorage records.
### SETROPTS plus
class/system-wide
configuration.
### Global controls change
how the security manager
behaves.
### Output Field Meaning Why It Matters Follow-Up
### SECURITY / NOSECURITY Whether Gibson treats the logonid
as an administrator-style identity.
### SECURITY is a high-value privilege
indicator.
### LIST the ID, review group/UID,
and test whether state-changing
commands are permitted.
### NON-CNCL Gibson shows a common ACF2-
style flag in logonid output.
### Students learn to read flags, not
only user names.
### Ask what operational effect the
flag would have on a real site.
### UID(n) Simulated OMVS/UID value or
ACF2 grouping value.
### UID 0 or broad UID grouping can
change privilege assumptions.
SHOW OMVS or LIST UID(n).
$KEY(key) Rule-set key for a data set or
resource rule.
### Shows the protected namespace
being evaluated.
### Use ACCESS or TEST to turn a rule
into an access decision.
### UID(id) SERVICE(x)
### ALLOW/PREVENT
### Rule line granting or denying a
service to a UID/logonid.
### This is the evidence line for access
review.
Test
### READ/UPDATE/DELETE/EXECUTE
where appropriate.
### System Requirements
Gibson is a Python-based simulator with an optional Docker or Podman browser-terminal sidecar.
The core services run from the Python package. The Guacamole browser terminal is the part that
needs a container runtime.
### Requirement Purpose How to Check Notes
Python 3.10+ Runs the simulator
package and virtual
environment.
python3 --version install_gibson.sh
enforces Python 3.10
or newer.
### Bash Runs installer and
controller scripts.
bash --version The installer and
controller are Bash
scripts.
### Docker or Podman Runs the optional
### Guacamole browser
terminal sidecar.
docker --version or
podman --version
### Required for the 8023
browser-terminal
sidecar, not for the
core Python listeners.
### Docker Compose /
### Podman Compose
### Starts the Guacamole
sidecar stack.
docker compose
version
### Used by web-
terminal/docker-
compose.yml.


<!-- page 9 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Browser Opens dashboard,
### REST portal and
browser terminal.
### Open 8443, 8082, or
8023 when running.
### Dashboard uses Basic
authentication.
3270 emulator Provides a closer
terminal experience
than raw netcat.
c3270 -v or x3270 -v Useful for VTAM, TSO
and CICS-style
workflows.
docker --version
docker compose version
python3 --version
bash --version
### Package Layout
Before running commands it helps to know which files matter. From a tester’s point of view, the
useful part is separating the installer, the controller, the Python runtime, the services, and the state
directory.
### Path Purpose User Needs To Know
install_gibson.sh Installer Supports --venv, --system, --
python, --sim-root, --no-
upgrade-pip and --skip-deps.
gibsonctl.sh Runtime controller Starts, stops, checks and
manages Gibson services and
the optional browser terminal.
gibson/cli.py Main Python entry point Implements --serve, --secure, --
vuln, port overrides and
master console options.
gibson/core/config.py Default runtime config Defines default ports and
simulator state paths.
gibson/services/ Service listeners Terminal, USS, FTP, dashboard,
### REST, Db2 and web-terminal
services.
web-terminal/docker-
compose.yml
### Guacamole sidecar Defines gibson-guacd, gibson-
guacamole and gibson-web-
terminal.
~/mfsim Default simulator root Seeded files, transfers and
GACF.DB live here by default.
logs/gibson.log Runtime log Created by gibsonctl.sh start.
.gibson-pids/gibson.pid PID file Used by stop/status paths.


<!-- page 10 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Installing Gibson
The supported source-backed installation path is the installer script. The --venv option is confirmed
in the script and is also the default mode. It keeps the Python dependencies away from the system
Python, which is exactly what you want in a lab environment.
chmod +x install_gibson.sh
./install_gibson.sh --venv
The installer checks Python, prepares .venv when venv mode is used, upgrades packaging tools
unless told not to, installs Gibson in editable mode, verifies key Python packages, and seeds the
simulator root. By default that simulator root is $HOME/mfsim, but --sim-root PATH lets you place
it elsewhere.
TROUBLESHOOTING: common install failures
If venv creation fails, install the matching Python venv package for the distribution. If Docker checks fail,
remember that Docker is only required for the browser-terminal sidecar. If the script is not executable, run
chmod +x install_gibson.sh. If dependency installation fails, rerun after checking network access or use --
skip-deps only when you know the environment already has the required packages.
### Starting Gibson
The normal controller path is gibsonctl.sh. It wraps the Python package, picks .venv/bin/python
when it exists, creates a PID file, writes logs to logs/gibson.log, starts the service listeners and opens
the master console unless you suppress it.
./gibsonctl.sh start
### Command Purpose Expected Result Notes
./gibsonctl.sh start Start Gibson services
and launch the master
console when
interactive.
Service listeners start;
logs/gibson.log is
written.
### Use --no-master or --
detach for background
operation.
./gibsonctl.sh status Show PID, listening
ports, web terminal
status and matching
processes.
### Ports show
occupied/free state.
### Good first diagnostic
command.
./gibsonctl.sh ports Print managed port
ownership.
### Each port is listed with
owning PID if present.
### Useful when 2023 or
8443 is already busy.
./gibsonctl.sh master --
plain
### Open plain master
console.
### Text-mode master
console starts.
### Use this if curses
rendering is awkward.
./gibsonctl.sh stop --
force
### Stop services and
force-kill stubborn
listeners.
### PID and port holders
are terminated.
### Use carefully when
ports are held by
another lab.


<!-- page 11 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Choosing a Runtime Mode
Gibson has explicit secure and vulnerable modes. In normal training, --vuln is the classroom-
friendly compatibility mode. For defensive comparison, --secure applies a CIS-aligned simulator
profile, moves the primary terminal listener to 1023, enables additional audit posture, and disables
selected plain services in the CLI service path.
./gibsonctl.sh start --vuln
./gibsonctl.sh start --secure
### Option Mode What It
### Changes Best For Security
### Meaning
### Validation
### Status
--vuln Vulnerable/
classroom
### Default
compatibility
mode on 2023
with training-
friendly
services.
### Penetration
testing labs
and
demonstratio
ns.
### Intentionally
exposes
learning
surfaces.
### Source
verified
--secure Secure/CIS-
aligned
### Sets security
mode to
secure,
primary
terminal port
to 1023,
dashboard to
8443, disables
### USS/FTP in CLI
startup path.
### Defensive
comparison
and
hardening
demonstratio
ns.
### Shows how
service
posture
changes when
secure profile
is applied.
### Source
verified
--no-ftp Service
suppression
### Starts package
without FTP.
### Focused labs
where FTP
noise is not
needed.
### Reduces
exposed
training
surface.
### Source
verified
--no-rest Service
suppression
### Starts package
without REST
gateway.
### Terminal-only
labs.
### Removes API
training
surface.
### Source
verified
--with-tn3270 Optional
listener
### Enables
separate
### TN3270
listener on
3270.
### TN3270/NSE-
style
discovery
labs.
### Creates a
more
recognisable
TN3270 target.
### Source
verified
--with-web-
terminal
### Browser
terminal
### Enables
### Guacamole
browser
terminal
### Browser-
based classes.
Adds
### Docker/HTTP
browser
access on
### Source
verified


<!-- page 12 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
sidecar/start
path.
8023.
### Ports and Services
At this point, you have evidence that the simulator is more than one port. Treat the port map as
your first operational checklist. If the wrong port is closed, the later labs will feel broken even
when the commands are fine.
### Port Protocol Service How to
### Connect Purpose Lab Use Notes
2023 TCP VTAM/
### TSO/CICS
selector
nc/telnet/
c3270/x3270
127.0.0.1:20
23
### Primary
simulator
terminal
listener.
### Quick start,
### TSO, CICS,
### DB2, VTAM
labs
### Runtime
smoke
checked
with nc.
2022 TCP USS/OMVS
listener
nc 127.0.0.1
2022
### Dedicated
z/OS UNIX
style shell
listener
unless
disabled/sec
ure.
### USS labs Runtime
listener
verified.
2111 TCP FTP/JES/SQL
simulator
ftp 127.0.0.1
2111
### Shared-
state FTP
server
when --
with-ftp is
used.
### FTP/JES
transfer
labs
### Runtime
listener
verified.
8443 HTTP/
HTTPS
### Gibson
dashboard /
### Master
### Console-
style web
view
https://
127.0.0.1:84
43 with
### Basic auth
admin:gibso
nadmin!
### Dashboard,
service
state, audit,
ports,
sessions,
alert view.
### Secure
mode
wraps with
TLS.
### Console and
monitoring
labs
### Runtime
listener
verified;
/api/state
requires
auth.
8082 HTTP DB2 REST /
banking lab
/ IND$FILE
API
http://
127.0.0.1:80
82/
### REST portal,
### Db2 query,
banking
lab,
### Hack3270,
### REST/API,
### Hack3270,
### PassTicket,
IND$FILE
labs
### Runtime
/bank/sessio
n checked.


<!-- page 13 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### PassTicket,
IND$FILE
upload/dow
nload.
50000 TCP DB2DAS /
### DRDA-style
listener
nmap/nc
127.0.0.1
50000
Db2
### DAS/DRDA
style
listener.
Db2/
network
enumeratio
n labs
### Runtime
listener
verified.
50001 WebSocket/
TCP
DB2
### WebSocket
shell
websocket
client to
127.0.0.1:50
001
Db2
### WebSocket
shell.
### Db2 web
shell labs
### Runtime
listener
verified.
3270 TN3270/
### TN3270E
### Separate
### TN3270
discovery
listener
c3270
127.0.0.1:32
70
### Optional
### TN3270
listener
enabled
with --with-
tn3270.
### TN3270 and
### NSE-style
labs
### Source
verified; not
enabled by
gibsonctl
default.
8023 HTTP Guacamole
browser
terminal
sidecar
http://
127.0.0.1:80
23/
### Containeris
ed browser
terminal
wrapper
when
sidecar is
enabled.
### Browser
terminal
labs
### Source
verified
from web-
terminal
compose/he
lper; Docker
availability
required.
1023 TCP Secure
profile
### TSO/TN3270
compatibilit
y port
c3270/nc
127.0.0.1:10
23
### Secure
mode
moves
primary
terminal
listener to
1023.
### Secure-
mode
comparison
lab
### Source
verified in
build_state(
).
8081 HTTP Legacy
vulnerable
frontend
monitor
port
legacy/
vuln_gatew
ay.py or
status/port
manageme
nt
### Legacy
vulnerable
gateway
monitored
by gibsonctl
stop/status.
### Legacy
compatibilit
y only
### Source
verified; not
part of
default
modern
start path.
ss -lntp
docker ps
docker compose ps


<!-- page 14 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
curl -k -u admin:gibsonadmin! https://127.0.0.1:8443/api/state
nc -vz 127.0.0.1 2023
On a real z/OS system, these ports would usually represent different address spaces, started tasks, TCP/IP
listeners, VTAM applications or middleware front doors. Gibson compresses those ideas into a lab-friendly
runtime so you can see the relationships without needing a live LPAR.
### First Connections
The first connection does not need to be elegant. Start with netcat to prove the listener is alive, then
move to c3270 or x3270 when you want a more realistic terminal experience.
nc 127.0.0.1 2023
telnet 127.0.0.1 2023
c3270 127.0.0.1:2023
x3270 127.0.0.1:2023
curl -k -u admin:gibsonadmin! https://127.0.0.1:8443/api/state
curl http://127.0.0.1:8082/bank/session
Netcat is useful because it proves the port responds. It is not a proper 3270 emulator, so do not
judge every screen behaviour from netcat. For ISPF, CICS and keyboard-driven work, c3270 or
x3270 will give you a better feel for how a real terminal session behaves.
On a real z/OS system, a 3270 client normally connects through TN3270 or TN3270E to a VTAM application
such as TSO or CICS. Gibson’s 2023 selector gives you a safe training version of that workflow.
### Your First Gibson Session
Connect to the primary terminal listener, look for the Gibson production LPAR banner, then use
the displayed application flow. Where implemented, L TSO, L CICS and L DB2 move you into the
corresponding simulated environment. MFA behaviour is driven by the current package state and
startup sequence; if an MFA PIN has been defined, the token follows the simulator’s PIN plus
current HHMM pattern.
nc 127.0.0.1 2023
# or
c3270 127.0.0.1:2023
The useful first commands are HELP, LISTUSER, LISTCAT and NETSTAT PORTLIST once you reach a
READY-style prompt. These are low-risk commands that prove the command path, state model and
service map are behaving as expected.
### Understanding the Master Console
The Master Console is where Gibson tries to teach the operator view. It is not a perfect clone of a
live mainframe console. It is a teaching surface that brings service state, terminal activity,
OPERLOG-style messages and alertable events into one place.


<!-- page 15 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Figure QS-1: Gibson Master Console and runtime components.
### Console Area What It Shows Source
### Component Why It Matters Troubleshooting
### Terminal / 3270
pane
### VTAM/TSO/CICS-
style session
activity.
### Telnet/TN3270
service and
session state.
### Shows the learner
what the user is
doing.
### If blank, check
2023 and
terminal client.
### OPERLOG / alert
stream
### Operator
messages, logon
events, port
touches and
alerts.
### Gibson state,
audit/event
manager and
master-console
polling.
### Connects user
action to
defensive
evidence.
### Use --demo-
events or trigger
a logon/port
event.
### Service and port
status
### Whether key
listeners are up.
### Service manager
and port checks.
### Fast way to triage
lab failures.
### Run ./gibsonctl.sh
status and ss
-lntp.
### Docker/container
status
### Browser terminal
sidecar health.
web-terminal
helper and
Docker/Compose.
### Explains 8023
browser terminal
behaviour.
### Run ./gibsonctl.sh
web-status or
preflight.
### Dashboard/API
relationship
### Dashboard on
8443, REST on
8082.
dashboard.py and
rest_gateway.py.
### Shows how
browser and API
labs fit together.
### Check /api/state
and
/bank/session.


<!-- page 16 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Gibson Docker and Service Architecture
### The core simulator is a Python process. Docker is used for the optional Guacamole browser
terminal sidecar. That distinction matters: if Docker is broken, the core terminal services can still
be healthy, but the browser terminal on 8023 will not be.
Figure QS-2: Gibson Docker and service architecture.
### Component Container/
### Process Port(s) Role Logs/State How to
### Validate
### Gibson
package
python -m
gibson.cli
2023,2022,211
1,8443,8082,50
000,50001
Main
simulator
process
hosting
service
listeners.
logs/
gibson.log, .gi
bson-pids/gibs
on.pid
./gibsonctl.sh
status
### Guacamole
daemon
gibson-guacd 4822 internal Guacamole
protocol
daemon.
web-
terminal/
generated
docker
compose ps
### Guacamole
webapp
gibson-
guacamole
8080 internal Guacamole
web
application.
web-
terminal/
generated/
guacamole-
home
docker
compose ps


<!-- page 17 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Web terminal
wrapper
gibson-web-
terminal
8023 -> 80 Nginx
wrapper for
browser
terminal
landing page.
web-
terminal/
generated/
wrapper-root
curl
http://127.0.0.1
:8023/
### Dashboard GIBDASH
thread
8443 Dashboard
and state API.
### Gibson state curl -k -u
admin:gibson
admin!
https://127.0.0.
1:8443/api/stat
e
### REST gateway GIBREST
thread
8082 Db2 REST,
banking,
### Hack3270,
### PassTicket,
IND$FILE
endpoints.
### Banking lab
state
curl
http://127.0.0.1
:8082/bank/ses
sion
### Checking That Gibson Is Healthy
Health checks are not glamorous, but they stop you wasting a lab chasing the wrong problem.
Check the controller, then the ports, then the browser/API endpoints.
./gibsonctl.sh status
./gibsonctl.sh ports
docker ps
docker compose ps
ss -lntp
curl -k -u admin:gibsonadmin! https://127.0.0.1:8443/api/state
nc -vz 127.0.0.1 2023
### Check Command Good Result Bad Result Fix
### Controller status ./gibsonctl.sh
status
### Package PID
running and
ports listed.
### No PID or ports
free.
### Start Gibson or
inspect
logs/gibson.log.
### Primary terminal nc -vz 127.0.0.1
2023
### Connection
succeeds.
### Connection
refused or
timeout.
### Check start mode,
port conflict and
status output.
### Dashboard curl -k -u
admin:gibsonadm
in!
https://127.0.0.1:8
443/api/state
### JSON state
returned.
401/connection
refused.
### Use confirmed
credentials and
check dashboard
listener.
### REST curl Banking lab JSON 404/connection Start with --with-


<!-- page 18 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
http://127.0.0.1:80
82/bank/session
returned. refused. rest or check
service state.
### Browser terminal ./gibsonctl.sh
web-status
### Sidecar status
shown.
### Docker/Compose
error.
### Run preflight and
fix
Docker/Compose.
### Quick Troubleshooting
### Symptom Likely Cause Check Fix
install script fails Missing Python, venv,
pip or permissions.
### Run python3 --version
and python3 -m venv
/tmp/testvenv.
### Install Python venv/pip
package and rerun.
### Docker permission
denied
### User cannot access
### Docker socket or
daemon stopped.
docker ps. Start Docker and add
user to docker group,
or use approved sudo
workflow.
### Port already in use Another process owns
the listener.
./gibsonctl.sh ports or
ss -lntp.
### Stop the owning
process or use --port
overrides.
2023 does not respond Gibson not running,
secure mode moved
primary port, or port
conflict.
./gibsonctl.sh status. Start in --vuln or
connect to 1023 in --
secure mode.
c3270/x3270 connects
but screen looks
wrong
### Client negotiation or
wrong port.
### Try nc first and
confirm 2023 banner.
### Use c3270 against the
confirmed listener;
enable --with-tn3270
for 3270 port.
### Browser certificate
warning
### Dashboard may be
### HTTPS/self-signed in
secure mode.
curl -k to /api/state. Accept lab certificate
warning only in the
controlled lab.
### Master Console loads
but no events appear
### No recent activity or
polling delay.
### Trigger a logon or use
--demo-events.
### Wait for poll interval
or generate demo
events.
### API returns 404/500 Wrong path, REST not
started, or invalid
request.
curl /bank/session on
8082.
### Use confirmed
endpoints and start
with --with-rest.
### MFA fails PIN/time token
mismatch or IPL/MFA
state not set.
### Review startup
sequence and current
time.
### Re-run prestart
console and set PIN as
required.


<!-- page 19 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Quick Start Labs
### Lab QS-1: Install Gibson with a virtual environment
### Command context
Start from: Linux host shell in the Gibson package directory
Commands run from: Linux shell
Do not run these from: TSO, ISPF, OMVS, CICS, FTP or Master Console
Why context matters: This is host-side setup work. It prepares the simulator; it is not a mainframe
command.
### Why this lab matters
In this lab we’ll work through install gibson with a virtual environment as a practical evidence
exercise, not as a command checklist. The concept being taught is installation control and
dependency isolation. From a tester’s point of view, the aim is to produce a specific piece of
evidence: executable script state, virtual environment creation and dependency installation output.
From a defender’s point of view, the same evidence explains what should be controlled, logged or
challenged before the activity becomes normalised. By the end of the lab, you should be able to say
why each command was used and what changed in your understanding of the Gibson
environment.
### What the commands do
chmod +x install_gibson.sh: marks the installer as executable so the shell can run it directly. It
proves the package is being prepared from the correct directory rather than from a copied
command in isolation.
./install_gibson.sh --venv: runs the Gibson installer and asks it to build/use a Python virtual
environment. The useful evidence is dependency installation and creation of an isolated runtime
so later failures are not confused with host Python state.
### Starting state
Start in the extracted Gibson package directory on a Linux host. You should be able to see
install_gibson.sh before you run chmod or the installer. Do not run the command from a copied
subdirectory because the installer expects the package layout to be intact.
### Lab steps
chmod +x install_gibson.sh
./install_gibson.sh --venv
### What the output tells us
For `chmod +x install_gibson.sh`, confirm the file mode now includes execute permission. That tells
you the installer can be launched directly from the host shell; if it does not change, check your
directory and filesystem permissions before running the install.
### On a real z/OS system


<!-- page 20 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
A real z/OS LPAR is not installed this way; Gibson uses Linux shell scripts and Python packaging to
emulate services that would be separate started tasks, address spaces and subsystem configuration
on z/OS.
### Defensive takeaway
Treat installation as supply-chain and lab-integrity evidence. Confirm the source directory, script
permissions, dependency set and log output before students trust later results.
### Troubleshooting
If the script is not executable, chmod is the fix. If --venv fails, check python3-venv, write
permissions and whether the working directory is the Gibson package root.
### Instructor note
Teach install gibson with a virtual environment by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup
No simulator data cleanup is required, but you can remove the created virtual environment only if
you intend to reinstall. Do not delete it before running later Quick Start labs.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
chmod +x
install_gibson.sh
### Runs the Gibson
installer. The script
prepares the Python
runtime, creates a
virtual environment
when requested and
checks the local service
prerequisites.
--venv tells the installer
to isolate dependencies
in a local virtual
environment rather
than relying on system
Python packages.
### A clean install is your
foundation. If the lab
starts from a broken
install, every later
symptom becomes
misleading.
### Evidence is a
completed install, a
usable .venv and no
missing-dependency
errors.
./install_gibson.sh --
venv
### Runs the Gibson
installer. The script
prepares the Python
runtime, creates a
virtual environment
when requested and
checks the local service
prerequisites.
--venv tells the installer
to isolate dependencies
in a local virtual
environment rather
than relying on system
Python packages.
### A clean install is your
foundation. If the lab
starts from a broken
install, every later
symptom becomes
misleading.
### Evidence is a
completed install, a
usable .venv and no
missing-dependency
errors.
### Lab QS-2: Start Gibson and confirm services
### Command context
Start from: Linux host shell in the Gibson package directory
Commands run from: Gibson install/control shell


<!-- page 21 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Do not run these from: TSO READY, ISPF, OMVS or CICS
Why context matters: gibsonctl.sh controls the simulator runtime and Docker/process state, not a
z/OS subsystem.
### Why this lab matters
In this lab we’ll work through start gibson and confirm services as a practical evidence exercise,
not as a command checklist. The concept being taught is runtime control plane, mode selection and
service readiness. From a tester’s point of view, the aim is to produce a specific piece of evidence:
status output, open-port list and mode-specific service behaviour. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
./gibsonctl.sh start --no-master: starts the simulator control plane without dropping into the
interactive master console. This is useful for health checks because you can keep the shell available
for status and port checks.
./gibsonctl.sh status: reports whether the main Gibson services believe they are running. Treat it as
the control-plane view, not as proof that every socket is reachable.
./gibsonctl.sh ports: prints the Gibson service-to-port map. It connects the abstract subsystem
names in the manual to the actual listener numbers a tester will touch.
2023: is the main local terminal listener used by the Quick Start labs. Evidence on this port proves
the terminal path is alive before you test TSO, CICS or panel workflows.
### Starting state
Start after installation has completed. Use a shell in the Gibson package root. If another copy of
Gibson is already running, stop it or choose a clean runtime before checking status and ports.
### Lab steps
./gibsonctl.sh start --no-master
./gibsonctl.sh status
./gibsonctl.sh ports
2023
### What the output tells us
For `./gibsonctl.sh start --no-master`, confirm the status line, service banner or port list that follows.
The useful point is whether the control script started the expected Gibson process profile, not
merely that the shell accepted the command.
### On a real z/OS system
On real z/OS, operators start and stop subsystems with JCL procedures and console commands
rather than a single Linux wrapper. The same discipline applies: prove the system is in the
expected mode before interpreting test output.
### Defensive takeaway


<!-- page 22 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Defenders should know which listeners are expected in secure versus vulnerable modes and alert
when a lab-only service appears unexpectedly.
### Troubleshooting
If status shows stopped or ports are missing, inspect gibsonctl logs, check for occupied ports and
confirm Docker/Python services started cleanly.
### Instructor note
### Teach start gibson and confirm services by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup
Leave Gibson running if you are continuing to the connection labs. Stop it with the documented
control command when the teaching block is complete.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
./gibsonctl.sh start --no-
master
Uses Gibson’s
controller script to
start, stop, inspect or
report the simulator
services.
start launches the
service set; status
reports current state;
ports shows the
listener map; --vuln
and --secure select the
training security
posture.
### The controller is the
quickest way to prove
what is supposed to be
running before you
connect to any
simulated subsystem.
### Evidence is a service
status line and the
expected listener list.
./gibsonctl.sh status Uses Gibson’s
controller script to
start, stop, inspect or
report the simulator
services.
start launches the
service set; status
reports current state;
ports shows the
listener map; --vuln
and --secure select the
training security
posture.
### The controller is the
quickest way to prove
what is supposed to be
running before you
connect to any
simulated subsystem.
### Evidence is a service
status line and the
expected listener list.
./gibsonctl.sh ports Uses Gibson’s
controller script to
start, stop, inspect or
report the simulator
services.
start launches the
service set; status
reports current state;
ports shows the
listener map; --vuln
and --secure select the
training security
posture.
### The controller is the
quickest way to prove
what is supposed to be
running before you
connect to any
simulated subsystem.
### Evidence is a service
status line and the
expected listener list.
2023 Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.


<!-- page 23 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab QS-3: Connect with netcat
### Command context
Start from: Linux host shell or browser
Commands run from: Host-side client, not inside Gibson
Do not run these from: READY, ISPF, OMVS, FTP or CICS
Why context matters: These commands create the session used for later mainframe work.
### Why this lab matters
In this lab we’ll work through connect with netcat as a practical evidence exercise, not as a
command checklist. The concept being taught is terminal and browser access paths. From a tester’s
point of view, the aim is to produce a specific piece of evidence: successful socket connection, 3270
screen or web console response. From a defender’s point of view, the same evidence explains what
should be controlled, logged or challenged before the activity becomes normalised. By the end of
the lab, you should be able to say why each command was used and what changed in your
understanding of the Gibson environment.
### What the commands do
nc 127.0.0.1 2023: opens a raw TCP session to the terminal listener. It is a deliberately low-level
check: useful for proving the socket answers, but not a replacement for a 3270-aware emulator.
2023: is the main local terminal listener used by the Quick Start labs. Evidence on this port proves
the terminal path is alive before you test TSO, CICS or panel workflows.
### Starting state
Start with Gibson running and the terminal/web listeners enabled. Confirm the requested port is
part of the current runtime profile before blaming the client.
### Lab steps
nc 127.0.0.1 2023
2023
### What the output tells us
For `nc 127.0.0.1 2023`, confirm whether the terminal listener returns a banner, prompt or clean
refusal. A connected socket proves reachability; a usable front-door prompt proves the training
terminal path is ready.
### On a real z/OS system
Real mainframe access commonly uses TN3270/TN3270E through VTAM applications, plus browser
access to z/OSMF, CICS web, z/OS Connect or site portals. Gibson compresses those ideas into local
ports.
### Defensive takeaway
Monitor connection attempts, failed logons, unusual client sources and new listeners. Port
reachability is the first operational clue that a service is exposed.


<!-- page 24 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
If a client connects but the screen is unreadable, use a 3270-aware client rather than raw netcat. If
a browser endpoint fails, check TLS/certificate warnings and service status.
### Instructor note
Teach connect with netcat by asking students to explain the purpose of each command before they
run it and then identify the exact field, line or state change that proves the point of the lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
nc 127.0.0.1 2023 Opens a raw TCP
session to the selected
listener.
127.0.0.1 is the
loopback address; 2023
is the primary Gibson
terminal listener in the
vulnerable training
profile.
### Netcat is the simplest
proof that a service
answers before you
spend time debugging a
3270 client.
### Evidence is a banner,
prompt, or immediate
connection response.
2023 Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
### Lab QS-4: Connect with c3270 or x3270
### Command context
Start from: Linux host shell or browser
Commands run from: Host-side client, not inside Gibson
Do not run these from: READY, ISPF, OMVS, FTP or CICS
Why context matters: These commands create the session used for later mainframe work.
### Why this lab matters
In this lab we’ll work through connect with c3270 or x3270 as a practical evidence exercise, not as a
command checklist. The concept being taught is terminal and browser access paths. From a tester’s
point of view, the aim is to produce a specific piece of evidence: successful socket connection, 3270
screen or web console response. From a defender’s point of view, the same evidence explains what
should be controlled, logged or challenged before the activity becomes normalised. By the end of
the lab, you should be able to say why each command was used and what changed in your
understanding of the Gibson environment.


<!-- page 25 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### What the commands do
c3270 127.0.0.1:2023: starts a console 3270 emulator against the terminal listener. This matters
because PF keys, AID keys and formatted screens need a 3270 client to behave like a host session.
x3270 127.0.0.1:2023: starts a graphical 3270 emulator against the same listener. Use it when you
want to see screen layout, copy/paste and emulator menu behaviour clearly.
2023: is the main local terminal listener used by the Quick Start labs. Evidence on this port proves
the terminal path is alive before you test TSO, CICS or panel workflows.
### Starting state
Start with Gibson running and the terminal/web listeners enabled. Confirm the requested port is
part of the current runtime profile before blaming the client.
### Lab steps
c3270 127.0.0.1:2023
x3270 127.0.0.1:2023
2023
### What the output tells us
For `c3270 127.0.0.1:2023`, confirm that the emulator reaches the Gibson front-door or 3270-style
panel. If the window connects but the screen is garbled or blank, troubleshoot terminal mode
rather than RACF or TSO.
### On a real z/OS system
Real mainframe access commonly uses TN3270/TN3270E through VTAM applications, plus browser
access to z/OSMF, CICS web, z/OS Connect or site portals. Gibson compresses those ideas into local
ports.
### Defensive takeaway
Monitor connection attempts, failed logons, unusual client sources and new listeners. Port
reachability is the first operational clue that a service is exposed.
### Troubleshooting
If a client connects but the screen is unreadable, use a 3270-aware client rather than raw netcat. If
a browser endpoint fails, check TLS/certificate warnings and service status.
### Instructor note
Teach connect with c3270 or x3270 by asking students to explain the purpose of each command
before they run it and then identify the exact field, line or state change that proves the point of the
lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status


<!-- page 26 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
c3270 127.0.0.1:2023 Starts a 3270 terminal
emulator and connects
to the Gibson terminal
listener.
host:port selects the
local terminal
endpoint; c3270 is text-
mode and x3270 is
graphical.
### A real mainframe
assessment normally
needs a 3270-aware
client because TSO,
### ISPF and CICS are
screen-oriented rather
than line-oriented.
### Evidence is a
### VTAM/logon style panel
that reacts correctly to
Enter and PF keys.
x3270 127.0.0.1:2023 Starts a 3270 terminal
emulator and connects
to the Gibson terminal
listener.
host:port selects the
local terminal
endpoint; c3270 is text-
mode and x3270 is
graphical.
### A real mainframe
assessment normally
needs a 3270-aware
client because TSO,
### ISPF and CICS are
screen-oriented rather
than line-oriented.
### Evidence is a
### VTAM/logon style panel
that reacts correctly to
Enter and PF keys.
2023 Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
### Lab QS-5: Open the browser console
### Command context
Start from: Linux host shell or browser
Commands run from: Host-side client, not inside Gibson
Do not run these from: READY, ISPF, OMVS, FTP or CICS
Why context matters: These commands create the session used for later mainframe work.
### Why this lab matters
In this lab we’ll work through open the browser console as a practical evidence exercise, not as a
command checklist. The concept being taught is operator console, event stream and system-state
evidence. From a tester’s point of view, the aim is to produce a specific piece of evidence: console
display output, WTOR state, event line or security summary. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
https://127.0.0.1:8443: opens the HTTPS browser entry point. The evidence is not the TLS warning; it
is whether the dashboard or console view loads and shows expected simulator state.
### Starting state


<!-- page 27 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
https://127.0.0.1:8443
### What the output tells us
For `https://127.0.0.1:8443`, confirm which page or API response appears and whether
authentication is required. Browser success means the web/dashboard path is alive; it does not
prove terminal services are working.
### On a real z/OS system
### Real operators use MVS/JES commands, OPERLOG/SYSLOG, WTOR replies and automation
products. Gibson models the idea so students can practise interpreting operational evidence safely.
### Defensive takeaway
Console and OPERLOG visibility should be baselined. Logon events, high-port events and WTOR
replies are operational signals that defenders should explain.
### Troubleshooting
If a panel is empty, check polling/refresh, event generation, service health and whether the action
you performed is meant to emit an event.
### Instructor note
### Teach open the browser console by asking students to explain the purpose of each command
before they run it and then identify the exact field, line or state change that proves the point of the
lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
https://127.0.0.1:8443 Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
### Lab QS-6: Confirm runtime mode behaviour
### Command context
Start from: Linux host shell in the Gibson package directory


<!-- page 28 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Commands run from: Gibson install/control shell
Do not run these from: TSO READY, ISPF, OMVS or CICS
Why context matters: gibsonctl.sh controls the simulator runtime and Docker/process state, not a
z/OS subsystem.
### Why this lab matters
In this lab we’ll work through confirm runtime mode behaviour as a practical evidence exercise,
not as a command checklist. The concept being taught is runtime control plane, mode selection and
service readiness. From a tester’s point of view, the aim is to produce a specific piece of evidence:
status output, open-port list and mode-specific service behaviour. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
--vuln: selects the vulnerable training posture where unsafe or intentionally exposed behaviours
are available for labs. It should only be used in the lab context.
--secure: selects the hardened posture where some unsafe behaviours should be absent or
restricted. Comparing it with --vuln helps students see configuration as a security control.
### Starting state
Start after installation has completed. Use a shell in the Gibson package root. If another copy of
Gibson is already running, stop it or choose a clean runtime before checking status and ports.
### Lab steps
--vuln
--secure
### What the output tells us
If the output does not match this intent, stop at that point. A different response is not just noise; it
tells you that the context, state, service profile or authority path is different from the one this lab is
designed to teach.
### On a real z/OS system
On real z/OS, operators start and stop subsystems with JCL procedures and console commands
rather than a single Linux wrapper. The same discipline applies: prove the system is in the
expected mode before interpreting test output.
### Defensive takeaway
Defenders should know which listeners are expected in secure versus vulnerable modes and alert
when a lab-only service appears unexpectedly.
### Troubleshooting
If status shows stopped or ports are missing, inspect gibsonctl logs, check for occupied ports and
confirm Docker/Python services started cleanly.


<!-- page 29 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Instructor note
### Teach confirm runtime mode behaviour by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup
Leave Gibson running if you are continuing to the connection labs. Stop it with the documented
control command when the teaching block is complete.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
--vuln Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
--secure Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
### Lab QS-7: Read the event and alert stream
### Command context
Start from: Master Console or browser dashboard
Commands run from: Master Console/dashboard controls, or from the subsystem that triggers the
event
Do not run these from: ISPF editor, FTP or CICS unless generating the event intentionally
Why context matters: Detection labs separate activity generation from defender observation.
### Why this lab matters
In this lab we’ll work through read the event and alert stream as a practical evidence exercise, not
as a command checklist. The concept being taught is operator console, event stream and system-
state evidence. From a tester’s point of view, the aim is to produce a specific piece of evidence:
console display output, WTOR state, event line or security summary. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do


<!-- page 30 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
2023: is the main local terminal listener used by the Quick Start labs. Evidence on this port proves
the terminal path is alive before you test TSO, CICS or panel workflows.
### Starting state
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
2023
### What the output tells us
If the output does not match this intent, stop at that point. A different response is not just noise; it
tells you that the context, state, service profile or authority path is different from the one this lab is
designed to teach.
### On a real z/OS system
### Real operators use MVS/JES commands, OPERLOG/SYSLOG, WTOR replies and automation
products. Gibson models the idea so students can practise interpreting operational evidence safely.
### Defensive takeaway
Console and OPERLOG visibility should be baselined. Logon events, high-port events and WTOR
replies are operational signals that defenders should explain.
### Troubleshooting
If a panel is empty, check polling/refresh, event generation, service health and whether the action
you performed is meant to emit an event.
### Instructor note
Teach read the event and alert stream by asking students to explain the purpose of each command
before they run it and then identify the exact field, line or state change that proves the point of the
lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
2023 Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
### Area Command / Syntax Description Expected Validation


<!-- page 31 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Option Result Status
### Installer ./
install_gibson.
sh
./
install_gibson.
sh
### Runs the
### Gibson
installer.
### Installer
accepts option
and performs
action
### Source
verified
### Installer --venv ./
install_gibson.
sh --venv
### Install
into .venv;
this is the
default mode.
### Installer
accepts option
and performs
action
### Source
verified
### Installer --system ./
install_gibson.
sh --system
### Install into
active/system
### Python rather
than .venv.
### Installer
accepts option
and performs
action
### Source
verified
### Installer --python PATH ./
install_gibson.
sh --python
PATH
### Use a specific
### Python
interpreter.
### Installer
accepts option
and performs
action
### Source
verified
### Installer --sim-root
PATH
./
install_gibson.
sh --sim-root
PATH
Seed
simulator root
at supplied
path; default
is
$HOME/mfsim
.
### Installer
accepts option
and performs
action
### Source
verified
### Installer --no-upgrade-
pip
./
install_gibson.
sh --no-
upgrade-pip
Skip
pip/setuptools/
wheel
upgrades.
### Installer
accepts option
and performs
action
### Source
verified
### Installer --skip-deps ./
install_gibson.
sh --skip-deps
### Install Gibson
without
resolving
### Python
dependencies.
### Installer
accepts option
and performs
action
### Source
verified
### Installer -h, --help ./
install_gibson.
sh -h, --help
### Show installer
help.
### Installer
accepts option
and performs
action
### Source
verified
### Controller start ./gibsonctl.sh
start
### Controller
action start
### Action is
accepted by
gibsonctl
### Source
verified
### Controller stop ./gibsonctl.sh Controller Action is Source


<!-- page 32 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
stop action stop accepted by
gibsonctl
verified
### Controller restart ./gibsonctl.sh
restart
### Controller
action restart
### Action is
accepted by
gibsonctl
### Source
verified
### Controller master ./gibsonctl.sh
master
### Controller
action master
### Action is
accepted by
gibsonctl
### Source
verified
### Controller status ./gibsonctl.sh
status
### Controller
action status
### Action is
accepted by
gibsonctl
### Source
verified
### Controller ports ./gibsonctl.sh
ports
### Controller
action ports
### Action is
accepted by
gibsonctl
### Source
verified
### Controller web-status ./gibsonctl.sh
web-status
### Controller
action web-
status
### Action is
accepted by
gibsonctl
### Source
verified
### Controller web-logs ./gibsonctl.sh
web-logs
### Controller
action web-
logs
### Action is
accepted by
gibsonctl
### Source
verified
### Controller web-restart ./gibsonctl.sh
web-restart
### Controller
action web-
restart
### Action is
accepted by
gibsonctl
### Source
verified
### Controller web-clean ./gibsonctl.sh
web-clean
### Controller
action web-
clean
### Action is
accepted by
gibsonctl
### Source
verified
### Controller web-enable ./gibsonctl.sh
web-enable
### Controller
action web-
enable
### Action is
accepted by
gibsonctl
### Source
verified
### Controller web-disable ./gibsonctl.sh
web-disable
### Controller
action web-
disable
### Action is
accepted by
gibsonctl
### Source
verified
### Controller preflight ./gibsonctl.sh
preflight
### Controller
action
preflight
### Action is
accepted by
gibsonctl
### Source
verified
### Controller install-deps ./gibsonctl.sh
install-deps
### Controller
action install-
deps
### Action is
accepted by
gibsonctl
### Source
verified
### Controller --secure ./gibsonctl.sh Start CIS- Option is Source


<!-- page 33 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
option start --secure aligned secure
simulator
profile;
forwards --
secure to
gibson.cli;
mutually
exclusive with
--vuln.
accepted by
gibsonctl
where
applicable
verified
### Controller
option
--vuln ./gibsonctl.sh
start --vuln
Start
vulnerable/cla
ssroom
training
profile;
default
compatibility
mode;
mutually
exclusive with
--secure.
### Option is
accepted by
gibsonctl
where
applicable
### Source
verified
### Controller
option
--legacy ./gibsonctl.sh
start --legacy
### Also stop
legacy
standalone
services/script
s.
### Option is
accepted by
gibsonctl
where
applicable
### Source
verified
### Controller
option
--force, -f ./gibsonctl.sh
start --force, -f
### Escalate stop
from TERM to
### KILL and use
fuser on
occupied
ports.
### Option is
accepted by
gibsonctl
where
applicable
### Source
verified
### Controller
option
--dry-run ./gibsonctl.sh
start --dry-run
### Show actions
without
running them.
### Option is
accepted by
gibsonctl
where
applicable
### Source
verified
### Controller
option
--port N ./gibsonctl.sh
start --port N
### Also manage
an extra TCP
port.
### Option is
accepted by
gibsonctl
where
applicable
### Source
verified
### Inventory area Count


<!-- page 34 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Python modules 75
### Functions 1188
### Classes 142
### Curated command families 117
### Raw command-like tokens 1966
### API/route rows 18
### Service/port rows 12
### Seeded users 16
### Seeded RACF profiles 107
### Safe command smoke tests 14
### Validation status Definition
### Runtime validated The command or flow was executed in a temporary
GibsonState or safe smoke harness.
### Source validated The command, route or feature is present in code inventory but
was not fully exercised interactively.
### Matrix validated The feature appears in command, route, service, user, dataset
or RACF profile matrices.
### Known gap A mismatch, failing test, version conflict or data-quality issue
carried forward into the manual.
## Chapter 1. Mainframe and
### Gibson Foundations
This section gives the conceptual foundation required to use Gibson without mistaking it for a
production mainframe. It explains z/OS-like concepts, training boundaries, safe use, and the
simulator model.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This foundation chapter introduces the boundary between Gibson training behaviour and real z/OS
operations. The useful model is simple: identify the environment, prove where a command runs,
and keep track of whether the action reads state, changes simulator state, or demonstrates a
controlled weakness.


<!-- page 35 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value here is orientation. Students learn to separate simulator proof from production
claims; defenders learn to ask what evidence a real system would create before trusting a finding.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Primary
### Command /
### Feature
### Syntax Run From What It Does What To
### Look For
### Gibson
### Behaviour
### Real ISPF
### Behaviour
Lab
### SAVE SAVE ISPF editor
### Command
===> or PF
key
### Writes editor
buffer to the
target
dataset/mem
ber and
remains in
the editor
with DATA
SAVED.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A
### END / PF3 /
F3
### END or PF3 ISPF editor
### Command
===> or PF
key
### Exits the
editor if data
is clean. If
data is dirty,
### Gibson
prompts to
SAVE,
### CANCEL or
END again.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A/09B
### CANCEL /
### CAN / PF12 /
F12
### CANCEL or
PF12
### ISPF editor
### Command
===> or PF
key
### Restores the
original lines
and exits
without
saving the
edit buffer.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09B
### HELP / PF1 /
F1
### HELP ISPF editor
### Command
===> or PF
key
### Displays
available
primary and
focus
commands.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### FIND / F FIND string ISPF editor
### Command
### Searches for
a string and
### INVALID
EDIT
### Source-
backed in
### ISPF edit
primary
### Lab 09C


<!-- page 36 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
===> or PF
key
positions the
cursor on a
match.
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Gibson editor command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### RFIND RFIND ISPF editor
### Command
===> or PF
key
### Repeats the
previous
FIND.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### CHANGE / C CHANGE old
new [ALL]
### ISPF editor
### Command
===> or PF
key
### Changes the
next or all
matching
strings,
depending on
ALL.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### RCHANGE RCHANGE ISPF editor
### Command
===> or PF
key
### Repeats the
previous
CHANGE.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### TOP TOP ISPF editor
### Command
===> or PF
key
### Moves the
view to the
top of data.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### BOTTOM /
BOT
### BOTTOM ISPF editor
### Command
===> or PF
key
### Moves the
view to the
bottom of
data.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference


<!-- page 37 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### BROWSE/VIE
### W as appli
### LOCATE / L LOCATE n or
### LOCATE text
### ISPF editor
### Command
===> or PF
key
### Locates a line
number or
searches for
text.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
CAPS CAPS ON|
OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
upper-case
normalizatio
n in the
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
HEX HEX ON|OFF ISPF editor
### Command
===> or PF
key
### Toggles
### Gibson hex
display state
message.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### RECOVERY /
### RECOVER
### RECOVERY
ON|OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
recovery
state in the
editor profile.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### AUTOSAVE AUTOSAVE
ON|OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
autosave
state in
profile; SAVE
remains
explicit in
labs.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
NULLS NULLS ON|
OFF
### ISPF editor
### Command
===> or PF
### Toggles null
display/profil
e state.
### INVALID
EDIT
### COMMAND,
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
### Reference


<!-- page 38 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
key NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
ofile/key
concept; see
### IBM ISPF Edit
docs
TABS TABS ON|
OFF
### ISPF editor
### Command
===> or PF
key
### Toggles tab
profile state.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### PROFILE PROFILE ISPF editor
### Command
===> or PF
key
### Displays
editor profile
settings:
### RECOVERY,
### CAPS, NULLS,
TABS,
### AUTOSAVE
and HEX.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### RESET RESET /
### RESET X /
RESET
### EXCLUDED
### ISPF editor
### Command
===> or PF
key
### Clears
excluded line
state.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
CUT CUT [start
[end]]
### ISPF editor
### Command
===> or PF
key
### Cuts current
or numbered
range into
copy buffer.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
PASTE PASTE [line]
[BEFORE]
### ISPF editor
### Command
===> or PF
key
### Pastes copy
buffer after
line or before
line when
### BEFORE is
specified.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference


<!-- page 39 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### W as appli
### EXCLUDE EXCLUDE
ALL |
EXCLUDE n |
### EXCLUDE
string
### ISPF editor
### Command
===> or PF
key
### Excludes
matching
lines or
numeric line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### SUB / SUBMIT SUB or
### SUBMIT
### ISPF editor
### Command
===> or PF
key
### Submits
current
editor text as
### JCL via
configured
submitter if
available.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09F
### LINE / LC /
### LINECMD /
LN
### LINE, LC, LN
or LC n
command
### ISPF editor
### Command
===> or PF
key
### Moves focus
to line-
command
area or
executes
explicit line
command for
a numbered
line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09D
### TEXT / TXT /
DATA
### TEXT, TEXT n
text, or n text
### ISPF editor
### Command
===> or PF
key
### Moves focus
to text area
or replaces a
numbered
line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A
~ ~ ISPF editor
### Command
===> or PF
key
### Moves focus
back to the
command
field.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### TAB TAB key ISPF editor
### Command
===> or PF
key
### Cycles
between
command,
line-
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
### Lab 09E


<!-- page 40 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
command
and text
fields in the
interactive
editor.
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
concept; see
### IBM ISPF Edit
docs
### PF7/PF8 PF7/PF8 ISPF editor
### Command
===> or PF
key
### Pages up and
down in the
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
Line
### Command
### Syntax Type What It
Does
### Target
Required?
### Example Gibson
### Behaviour
### Real ISPF
### Behaviour
Lab
### I I or In line
command
### Inserts one
or n blank
lines at the
target line.
### No I Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09A
### D D or Dn line
command
### Deletes one
or n lines.
### No D Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09A
### DD DD ... DD block line
command
### Deletes a
marked
block of
lines.
### Second
marker
### DD Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### C C or Cn line
command
### Copies one
or n lines
into the
buffer.
### Requires
### A/B/P to
place.
### No C Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### CC CC ... CC block line
command
### Copies a
marked
block into
the buffer.
### Second
marker
### CC Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### M M or Mn line
command
### Moves one
or n lines
into the
buffer by
removing
them from
source.
### Requires
### A/B/P to
place.
### No M Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### MM MM ... MM block line
command
### Moves a
marked
block into
### Second
marker
### MM Implement
ed
### Real ISPF
equivalent
or marked
### Lab 09D


<!-- page 41 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
the buffer. real-only
### A A or An target line
command
### Places
copied/mov
ed lines
after the
target line.
### Yes A Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### B B or Bn target line
command
### Places
copied/mov
ed lines
before the
target line.
### Yes B Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### P P or Pn target line
command
### Places
copied/mov
ed lines
after the
target line;
### Gibson
synonym
for paste
target.
### Yes P Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### R R or Rn line
command
### Repeats
one line n
times.
### No R Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### RR RR ... RR block line
command
### Repeats a
marked
block of
lines.
### Second
marker
### RR Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### X X or Xn line
command
### Excludes
one or n
lines from
display.
### No X Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09E
### XX XX ... XX block line
command
### Excludes a
marked
block of
lines.
### Second
marker
### XX Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09E
### O O or On line
command
### Marks one
or n lines
as overlay
source.
### No O Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Reference
### OO OO ... OO block line
command
### Marks a
block as
overlay
source.
### Second
marker
### OO Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Reference
### S/F/L show-
excluded
### S/F/L real ISPF
line
commands
Not
implement
ed in
### Gibson line-
command
regex.
### Document
as real ISPF
### No S/F/L No - real
### ISPF only
### Real ISPF
equivalent
or marked
real-only
### No lab


<!-- page 42 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
only.
shift
commands
((, )), <, >
(, ), <, > real ISPF
line
commands
Not
implement
ed in
### Gibson line-
command
regex.
### Document
as real ISPF
only.
### No (, No - real
### ISPF only
### Real ISPF
equivalent
or marked
real-only
### No lab
### Feature Type Behaviour Where Used Gibson
### Behaviour
### Real ISPF
### Behaviour
### Common
### Mistake
### PF3 / F3 PF key Maps to END. Editor session Warns on dirty
data.
### Common ISPF
exit/end key.
### Assuming PF3
always saves.
### PF12 / F12 PF key Maps to
CANCEL.
### Editor session Discards
changes.
### Often CANCEL
depending
panel/keylist.
### Cancelling
useful work.
### TAB UI behaviour Cycles field
focus.
### Interactive
editor
### Terminal-
friendly field
cycling.
3270 fields are
cursor-
addressable.
### Typing line
commands into
text.
~ Special
command
### Returns to
command field.
### Interactive
editor
### Gibson
convenience
command.
### Not a standard
ISPF command.
### Treating it as
real z/OS
syntax.
### CAPS/HEX/
### PROFILE
### Switches Show or alter
profile state.
Command ===> Simulated
profile state.
### Real ISPF
profile settings.
### Not checking
profile before
interpreting
behaviour.
PROFILE, CAPS, HEX, RESET, TAB, PF3, PF12 and the Gibson-specific ~ focus command are included
here because they control how editing feels. The safety lesson is simple: know whether you are
changing data, saving data, exiting cleanly or cancelling a bad edit.
### ISPF Editor Switches, PF Keys and Special Behaviour
Line commands are the part of ISPF that make the editor feel different from a normal shell. They
are typed beside a line, not at READY. Gibson also supports command-line fallbacks such as LC 5 I
or I3 5 for terminal sessions where cursor placement is awkward. Teach both the concept and the
fallback, but always explain the real ISPF line-command area.
### ISPF Editor Line Commands
From a mainframe security point of view, ISPF edit is where authority becomes practical. If you
can edit JCL, REXX, CLISTs, PROCs or configuration members, you may be able to change what later
executes. Gibson gives you a safe editor subset so that students learn the workflow before touching
a real system.
ISPF edit is its own command environment. A student who types LISTUSER at the ISPF primary
menu is in the wrong place; a student who types SAVE at TSO READY is also in the wrong place. In
this section we'll keep the contexts separate: primary commands run on the editor Command ===>


<!-- page 43 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
line, line commands run in the left line-command area, and TSO/RACF commands belong at READY
or ISPF option 6.
### ISPF Editor Primary Commands
### Syntax Direction Run From What It Does What To
### Watch For
### Real z/OS
### Equivalent
### Security
### Relevance
cp source.txt
target.txt
### USS file to USS
file
### OMVS/USS shell Copies text
from a USS file
in the
simulated USS
tree to another
USS path.
### Returns no
output on
success.
cp: <source>:
unsupported
source when
source is absent
or a directory.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18A
cp
"//'IBMUSER.TE
ST.DATA'"
sample.txt
### MVS dataset to
### USS file
### OMVS/USS shell Reads the
simulated MVS
dataset/membe
r through
dataset services
and writes the
content into a
USS file.
cp: <source>:
data set not
found; cp:
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18B
cp from_uss.txt
"//'IBMUSER.TE
ST.COPY'"
### USS file to MVS
dataset
### OMVS/USS shell Reads the USS
file and writes
content into the
target MVS
dataset name.
unsupported
source if the
### USS path is
absent or a
directory;
permission
denied if
dataset write is
blocked.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18C
cp
"//'IBMUSER.A.D
ATA'"
"//'IBMUSER.B.D
ATA'"
### MVS dataset to
### MVS dataset
### OMVS/USS shell Reads one
simulated
dataset/membe
r and writes an
identical target
dataset/membe
r.
data set not
found;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document and
include in
reference;
optional lab
step.
cp
"//'IBMUSER.PD
S.CODE(TIME)'"
member.txt
### PDS/PDSE
member to USS
file
### OMVS/USS shell Reads the
named member
and writes a
USS file.
data set not
found if
member does
not exist.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18D
cp
new_member.t
xt
"//'IBMUSER.PD
### S.CODE(NEWO
### USS file to
### PDS/PDSE
member
### OMVS/USS shell Writes the USS
file contents
into the target
### PDS/PDSE
unsupported
source;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
### Add Lab 18D


<!-- page 44 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
NE)'" member. attributes/conv
ersion
considerations).
cp
//IBMUSER.TEST
.DATA file.txt
### Unquoted
dataset
notation
### OMVS/USS shell Parser accepts //
followed by a
dataset name,
but quoted
notation is safer
and is the
documented
teaching path.
### Shell quoting or
special
characters may
change the
operand before
### Gibson receives
it.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document as
supported/avoi
d unless simple.
cp -B or
conversion
options
### Binary/code-
page
conversion
### OMVS/USS shell Not
implemented.
### Gibson uses
### UTF-8/text style
content for
teaching.
### Options are not
parsed as
conversion
controls.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document as
real z/OS note
only.
### Symptom Likely Cause Check Fix
cp: source: data set not found Dataset/member name is
wrong.
### LISTCAT or ISPF 3.4. Correct the quoted dataset
name.
cp: permission denied Dataset read/write is blocked. Inspect DATASET profile if
authorised.
### Use a permitted training
object.
cp: source: unsupported
source
### Source path missing or
directory.
ls -l source. Create file or choose
supported source.
No output UNIX success convention. cat target or read dataset. Verify the target rather than
expecting a success banner.
### Common cp Failures and What They Teach
The important syntax is the double-slash dataset operand. A USS file looks like sample.txt or
/u/ibmuser/sample.txt. An MVS dataset operand is written as //'HLQ.DATASET'. A PDS or PDSE
member adds parentheses inside the dataset name, for example //'IBMUSER.REXX(ENUM)'. In the
labs, quote the operand because it teaches the safest habit and avoids shell parsing surprises.
In this section we'll use Gibson to practise one of the most useful bridge skills in z/OS: moving data
between UNIX System Services and traditional MVS datasets. On a real system, this is how scripts,
JCL, reports, configuration snippets and evidence often move between the UNIX and TSO worlds.
### Copying Between USS and MVS Data Sets with cp
### Section labs
### Lab 01: Orient to simulator boundaries
### Command context
Start from: Context stated in the lab prerequisite


<!-- page 45 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through orient to simulator boundaries as a practical evidence exercise, not
as a command checklist. The concept being taught is TSO READY command context and simulator
boundary. From a tester’s point of view, the aim is to produce a specific piece of evidence: help
text, catalog view, network view or command response at READY. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.
LISTCAT: shows catalog-style dataset information. It gives the learner a safe way to practise moving
from a command prompt to dataset discovery.
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTCAT
### NETSTAT PORTLIST
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
The TSO READY prompt is the command environment for interactive TSO/E work. On real systems,
commands may call RACF, catalog services, JES, TCP/IP, CLIST/REXX or installation exits.
### Defensive takeaway
READY activity should be tied to user identity, command authorisation and audit trails. Unexpected
enumeration commands can indicate reconnaissance.
### Troubleshooting


<!-- page 46 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
Teach orient to simulator boundaries by asking students to explain the purpose of each command
before they run it and then identify the exact field, line or state change that proves the point of the
lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### HELP Displays the available
command surface for
the current Gibson
context.
### A command name after
### HELP narrows the
output where
implemented.
### Help is safe
enumeration. It tells
you what the simulator
exposes without
changing state.
### Evidence is a command
list or help panel that
can be compared with
the command
appendix.
### LISTCAT Lists cataloged data
sets known to the
simulator.
### A high-level qualifier
may narrow results
where implemented.
### Catalog enumeration
tells you what objects
exist before you test
RACF or edit paths.
### Evidence is a list of
data set names and
attributes.
### NETSTAT PORTLIST Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### Field Value
### Difficulty Beginner
### Estimated time 25 minutes
### Objective Identify simulator components and distinguish Gibson
behaviour from production z/OS.
Prerequisites Package extracted and service inventory available.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 47 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
## Chapter 2. Installation, Startup,
### IPL, and Operations
This section explains package operation from a code-derived perspective: entry points,
configuration, startup flags, default ports, optional services, state creation and reset behaviour.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This startup chapter follows the host, container, service and console path from installation to a
listening training system. The operational model is not abstract: scripts prepare the environment,
services bind to ports, the console receives WTORs, and readiness is proven through health checks.
### Security relevance
The security value is knowing when the platform is really ready and what startup choices changed
its posture. A defender would care about startup replies, enabled services, open ports and whether
secure or vulnerable mode was selected.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 02: Verify ports and service model
### Command context
Start from: TSO READY for NETSTAT/PING or Linux host shell for nmap-sim/nc checks
Commands run from: The context stated beside each command
Do not run these from: ISPF editor or CICS
Why context matters: Network commands can be host-side tools or simulated TSO commands; the
manual must keep them separate.


<!-- page 48 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
In this lab we’ll work through verify ports and service model as a practical evidence exercise, not
as a command checklist. The concept being taught is TCP/IP listener and connection enumeration.
From a tester’s point of view, the aim is to produce a specific piece of evidence: listener list, active
connection list, ping/traceroute response or service display. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
D SVC,L: displays service-related information in the simulator, giving an operator-style view of
active services and service definitions.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
### NETSTAT PORTLIST
### D SVC,L
### What the output tells us
For `NETSTAT PORTLIST`, confirm the listener list and port/service names. The evidence is the
exposed service map, which is what a tester uses for attack-surface planning and a defender uses
for baselining.
### On a real z/OS system
z/OS Communications Server provides commands such as NETSTAT, PING and TRACERTE for
network monitoring. Open ports should be interpreted with subsystem ownership and network
controls such as SERVAUTH/NETACCESS.
### Defensive takeaway
Baseline listeners and alert on unexpected high ports, new services or sessions from unusual
sources.
### Troubleshooting
If a listener is missing, confirm the service was started and that the selected runtime profile
enables it.
### Instructor note
Ask students to translate every listening port into a subsystem hypothesis and a defender question.
This keeps scanning from becoming a screenshot exercise.
### Cleanup


<!-- page 49 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### NETSTAT PORTLIST Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### D SVC,L Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### Field Value
### Difficulty Beginner
### Estimated time 30 minutes
### Objective Map default ports to simulator subsystems and identify
optional web-terminal behaviour.
Prerequisites Fresh package and service matrix.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
## Chapter 3. Application
### Architecture Deep Dive
This section maps Gibson internals: CLI, configuration, runtime state, command dispatch, RACF
stores, dataset access, REST services, dashboard and security features.
### Implementation evidence
### Area Source evidence
### CLI / startup gibson/cli.py
### Configuration gibson/core/config.py


<!-- page 50 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Runtime state gibson/core/state.py
### TSO command processor gibson/apps/tso.py
RACF dynamic store gibson/core/racf_dynamic.py
### Dataset catalog gibson/core/datasets.py
### Operational model
This architecture chapter maps user-facing commands to handlers, state stores, panels and routes.
### The point is to understand which layer answers a command before interpreting output as
evidence.
### Security relevance
The security value is traceability. Attackers and testers follow command surfaces; defenders follow
the same path in reverse to understand what component should have authenticated, authorised,
logged or rejected the action.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 03: Trace a READY command to implementation
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through trace a ready command to implementation as a practical evidence
exercise, not as a command checklist. The concept being taught is TSO READY command context
and simulator boundary. From a tester’s point of view, the aim is to produce a specific piece of
evidence: help text, catalog view, network view or command response at READY. From a defender’s
point of view, the same evidence explains what should be controlled, logged or challenged before
the activity becomes normalised. By the end of the lab, you should be able to say why each
command was used and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.


<!-- page 51 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
LISTUSER IBMUSER: queries the simulated RACF profile for IBMUSER. It is an identity enumeration
step: attributes and account state can change the whole assessment path.
NETSTAT CONN: shows connection/session-oriented network state. It answers who is connected
rather than merely what is listening.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTUSER IBMUSER
### NETSTAT CONN
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
The TSO READY prompt is the command environment for interactive TSO/E work. On real systems,
commands may call RACF, catalog services, JES, TCP/IP, CLIST/REXX or installation exits.
### Defensive takeaway
READY activity should be tied to user identity, command authorisation and audit trails. Unexpected
enumeration commands can indicate reconnaissance.
### Troubleshooting
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
Teach trace a ready command to implementation by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### HELP Displays the available
command surface for
the current Gibson
### A command name after
### HELP narrows the
output where
### Help is safe
enumeration. It tells
you what the simulator
### Evidence is a command
list or help panel that
can be compared with


<!-- page 52 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
context. implemented. exposes without
changing state.
the command
appendix.
### LISTUSER IBMUSER Displays a simulated
### RACF user profile and
optional segments.
### ALL asks for broad
profile detail; a user ID
such as IBMUSER or
### MANLAB selects the
account to inspect.
### User profile review is
one of the first ways to
identify powerful
attributes, segment
data and
authentication
controls.
### Evidence includes
attributes, owner,
default group,
### TSO/OMVS/MFA
segments and
revoke/status
indicators.
### NETSTAT CONN Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Trace HELP, LISTUSER and NETSTAT from command matrix to
handler evidence.
Prerequisites Phase 1 command matrix.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
## Chapter 4. Access, Logon, MFA,
and VTAM
This section documents access paths, logon flow, PIN + HHMM MFA behaviour, optional services
and authentication-related alerts.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv


<!-- page 53 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Operational model
This access chapter follows a session from the front-door application choice into TSO, CICS, Db2 or
MFA-protected flows. The operational model is session-driven: what you can type depends on
where the logon path placed you.
### Security relevance
The security value is identity assurance. Students should watch for accepted APPLIDs, failed
credentials, MFA state and logon alerts, because those are the same clues a defender would use to
separate normal access from probing.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 04: Review MFA and user state
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through review mfa and user state as a practical evidence exercise, not as a
command checklist. The concept being taught is identity, class, profile and authority analysis. From
a tester’s point of view, the aim is to produce a specific piece of evidence: user attributes, profile
class, UACC, access list, WARNING or audit fields. From a defender’s point of view, the same
evidence explains what should be controlled, logged or challenged before the activity becomes
normalised. By the end of the lab, you should be able to say why each command was used and
what changed in your understanding of the Gibson environment.
### What the commands do
MFA STATUS: shows the simulator MFA state. It proves whether the authentication layer is active
before students test logon or PassTicket behaviour.
LISTUSER IBMUSER ALL: asks for the fuller identity view. In a real RACF workflow, the ALL-style
view is where default group, attributes, revoke/protected state and audit-relevant details become
visible.


<!-- page 54 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
UADS LIST: lists legacy-style user/session data in Gibson. Its teaching value is to compare modern
RACF/MFA thinking with older TSO account concepts.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### MFA STATUS
### LISTUSER IBMUSER ALL
### UADS LIST
### What the output tells us
For `MFA STATUS`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### MFA STATUS Displays or manages
Gibson’s simulated
MFA posture.
### STATUS reports
global/user state;
### ENROLL/VERIFY/RESET
change or test MFA
state where
### MFA is part of the
logon control path. A
tester cares because
weak recovery or
bypass paths matter as
### Evidence is MFA status
or a verification result.


<!-- page 55 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
implemented. much as the password.
### LISTUSER IBMUSER
ALL
### Displays a simulated
### RACF user profile and
optional segments.
### ALL asks for broad
profile detail; a user ID
such as IBMUSER or
### MANLAB selects the
account to inspect.
### User profile review is
one of the first ways to
identify powerful
attributes, segment
data and
authentication
controls.
### Evidence includes
attributes, owner,
default group,
### TSO/OMVS/MFA
segments and
revoke/status
indicators.
### UADS LIST Inspects simulated
legacy TSO user
attribute data.
### LIST reports the legacy-
style inventory.
### Legacy identity stores
are useful because
older controls can
remain in place beside
RACF-style logic.
### Evidence is a user/state
listing.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Determine MFA global state and user-specific segment status.
Prerequisites IBMUSER access.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
## Chapter 5. TSO READY
### Reference
### This section covers READY prompt behaviour and all TSO-facing commands, including command
syntax, expected outputs and security relevance.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
### The READY prompt is the command processor context for many RACF, catalog, network and JES
actions. In Gibson, READY is where command dispatch becomes explicit; inside ISPF you must use
option 6 or return to READY for the same class of commands.


<!-- page 56 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value is command authority. READY commands can reveal identities, datasets, profiles
and jobs, so students must learn both what the command returns and what a real system would log
or restrict.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### ISPF launcher START Launches the ISPF menu. gibson/apps/tso.py
LEGACY_HELP
### ISPF launcher ISPF Launches the ISPF menu. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY EXIT Exits the session. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY LOGOFF Logs off the current user. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY CONSOLE Enters the system console
mode (SPECIAL only).
gibson/apps/tso.py
LEGACY_HELP
### SDSF launcher SDSF Displays the SDSF screen. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY IPLINFO Restricted command. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY LISTCAT LEVEL(SYS1) Lists SYS1 level files. gibson/apps/tso.py
LEGACY_HELP
TSO/READY SEND Sends a message. Format:
SEND 'message'
USER(username) NOW|
LOGON.
gibson/apps/tso.py
LEGACY_HELP
### TSO/READY EDIT Edits a data set or member. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY REXX Executes a REXX script. gibson/apps/tso.py
LEGACY_HELP
### TSO/READY LISTCAT Lists files in your catalog. gibson/apps/tso.py
LEGACY_HELP
This section has 29 command-family entries; complete command pages appear in the full
command reference appendix.
### Section labs
### Lab 05: Baseline READY commands
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step


<!-- page 57 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through baseline ready commands as a practical evidence exercise, not as a
command checklist. The concept being taught is TSO READY command context and simulator
boundary. From a tester’s point of view, the aim is to produce a specific piece of evidence: help
text, catalog view, network view or command response at READY. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.
LISTCAT: shows catalog-style dataset information. It gives the learner a safe way to practise moving
from a command prompt to dataset discovery.
LISTDS IBMUSER.JCL.LAB: looks up a specific dataset-like object. It turns catalog discovery into a
targeted question: does this training dataset exist and can the current context see it?
SESSIONSTATS: summarises the current simulator session. It helps students separate command
output from session-level evidence.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTCAT
### LISTDS IBMUSER.JCL.LAB
### SESSIONSTATS
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
The TSO READY prompt is the command environment for interactive TSO/E work. On real systems,
commands may call RACF, catalog services, JES, TCP/IP, CLIST/REXX or installation exits.
### Defensive takeaway
READY activity should be tied to user identity, command authorisation and audit trails. Unexpected
enumeration commands can indicate reconnaissance.


<!-- page 58 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
### Teach baseline ready commands by asking students to explain the purpose of each command
before they run it and then identify the exact field, line or state change that proves the point of the
lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### HELP Displays the available
command surface for
the current Gibson
context.
### A command name after
### HELP narrows the
output where
implemented.
### Help is safe
enumeration. It tells
you what the simulator
exposes without
changing state.
### Evidence is a command
list or help panel that
can be compared with
the command
appendix.
### LISTCAT Lists cataloged data
sets known to the
simulator.
### A high-level qualifier
may narrow results
where implemented.
### Catalog enumeration
tells you what objects
exist before you test
RACF or edit paths.
### Evidence is a list of
data set names and
attributes.
### LISTDS
### IBMUSER.JCL.LAB
### Displays simulated data
set information.
### The data set name
selects the object to
inspect.
### Data set visibility helps
you decide what can be
read, edited, submitted
or protected.
### Evidence is data set
metadata or content
availability.
### SESSIONSTATS Runs or inspects a
### Gibson command in
the current subsystem.
### Review the command
operands in context;
### Gibson implements a
training subset of the
real command surface.
### The command is part of
a larger assessment
chain and should be
interpreted as evidence
rather than a magic
incantation.
### Evidence is the
returned prompt,
panel, row, job ID,
event or error message.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Run safe READY commands and interpret output.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 59 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
## Chapter 6. RACF Administration
and Security Model
This section covers users, groups, dynamic profiles, dataset profiles, resource profiles, SETROPTS-
like settings, password policy, UADS, MFA segments and auditing attributes.
### Implementation evidence
### Area Source evidence
### RACF repository gibson/core/racf.py
Dynamic RACF gibson/core/racf_dynamic.py
### TSO integration gibson/apps/tso.py
### Operational model
This chapter works with RACF-style identity, group and resource profiles. The operational model is
profile-driven: commands inspect or change users, groups, classes, UACC, access lists and training-
mode controls.
### Security relevance
The security value is access-control interpretation. A tester looks for dangerous attributes, broad
permits, WARNING mode and impersonation paths; a defender looks for class activation, least
privilege, audit events and change control.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### RACF ADDUSER ADDUSER userid
PASSWORD(pw)|PASS(pw)
[SPECIAL|OPERATIONS|
AUDITOR|ROAUDIT|UAUDIT]
[TSO(...)] [OMVS(...)] [DFP(...)]
gibson/apps/tso.py
LEGACY_HELP
### RACF ALTUSER ALTUSER userid
PASSWORD(pw)|REVOKE|
RESUME [ROAUDIT|
NOROAUDIT] [TSO(...)|
NOTSO] [OMVS(...)|NOOMVS]
[DFP(...)|NODFP] [MFA(...)|
NOMFA].
gibson/apps/tso.py
LEGACY_HELP
### RACF SETROPTS LIST Displays system options
(restricted).
gibson/apps/tso.py
LEGACY_HELP
### RACF SEARCH CLASS(USER) Lists users with SPECIAL gibson/apps/tso.py


<!-- page 60 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
privileges. LEGACY_HELP
### RACF RACLIST Displays RACF profile details. gibson/apps/tso.py
LEGACY_HELP
RACF LISTUSER LISTUSER userid [ALL|TSO|
OMVS|DFP|MFA] - displays
user details and segments.
gibson/apps/tso.py
LEGACY_HELP
### RACF ADDGROUP ADDGROUP groupname -
define a RACF group.
gibson/apps/tso.py
LEGACY_HELP
RACF LISTGRP LISTGRP [group|*] - list RACF
groups.
gibson/apps/tso.py
LEGACY_HELP
### RACF CONNECT CONNECT userid
### GROUP(group)
[AUTHORITY(USE)].
gibson/apps/tso.py
LEGACY_HELP
### RACF REMOVE REMOVE userid
GROUP(group).
gibson/apps/tso.py
LEGACY_HELP
### RACF RDEFINE RDEFINE class profile
[UACC(access)].
gibson/apps/tso.py
LEGACY_HELP
### RACF RLIST RLIST class profile. gibson/apps/tso.py
LEGACY_HELP
This section has 28 command-family entries; complete command pages appear in the full
command reference appendix.
### Section labs
### Lab 06: Create, alter and review a training user
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through create, alter and review a training user as a practical evidence
exercise, not as a command checklist. The concept being taught is identity, class, profile and
authority analysis. From a tester’s point of view, the aim is to produce a specific piece of evidence:
user attributes, profile class, UACC, access list, WARNING or audit fields. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do


<!-- page 61 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### ADDUSER MANLAB PASSWORD(PASS123) TSO(ACCTNUM(ACCT#) PROC(ISPFPROC))
OMVS(UID(9001) HOME(/u/manlab)): creates a controlled training user with TSO and OMVS
attributes. It is state-changing and should be treated as proof that account provisioning controls
matter.
LISTUSER MANLAB ALL: confirms the created profile and exposes the exact attributes added by
ADDUSER.
ALTUSER MANLAB ROAUDIT MFA(PIN(1234)): alters the training user so students can see how
account properties and authentication controls change after creation.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### ADDUSER MANLAB PASSWORD(PASS123) TSO(ACCTNUM(ACCT#) PROC(ISPFPROC)) OMVS(UID(9001)
### HOME(/u/manlab))
### LISTUSER MANLAB ALL
### ALTUSER MANLAB ROAUDIT MFA(PIN(1234))
### What the output tells us
For `ADDUSER MANLAB PASSWORD(PASS123) TSO(ACCTNUM(ACCT#) PROC(ISPFPROC))
OMVS(UID(9001) HOME(/u/manlab))`, identify the exact returned line, return code, panel state or
dataset change that proves the lab objective. If that item is not present, pause and troubleshoot the
current command context before continuing.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your


<!-- page 62 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### ADDUSER MANLAB
### PASSWORD(PASS123)
### TSO(ACCTNUM(ACCT#)
### PROC(ISPFPROC))
### OMVS(UID(9001)
### HOME(/u/manlab))
### Creates a simulated
RACF user profile.
### PASSWORD sets the
initial credential; TSO()
adds TSO segment data;
### OMVS() adds UNIX
identity data.
### User creation teaches
how identity, TSO logon
capability and UNIX
identity are separate
but connected controls.
### Evidence is a LISTUSER
profile showing base,
### TSO and OMVS
segments.
### LISTUSER MANLAB
ALL
### Displays a simulated
### RACF user profile and
optional segments.
### ALL asks for broad
profile detail; a user ID
such as IBMUSER or
### MANLAB selects the
account to inspect.
### User profile review is
one of the first ways to
identify powerful
attributes, segment
data and
authentication
controls.
### Evidence includes
attributes, owner,
default group,
### TSO/OMVS/MFA
segments and
revoke/status
indicators.
### ALTUSER MANLAB
### ROAUDIT
### MFA(PIN(1234))
### Alters an existing
simulated RACF user
profile.
### ROAUDIT and MFA/PIN
style operands change
audit and
authentication posture
in Gibson.
### ALTUSER is
operationally powerful;
in the wrong hands it
becomes persistence,
privilege or
authentication control.
### Evidence is the
changed LISTUSER
output.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Create a user, add OMVS/TSO segments, apply ROAUDIT and
review output.
Prerequisites SPECIAL user such as IBMUSER.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 07: Create a resource profile and permit access
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists


<!-- page 63 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through create a resource profile and permit access as a practical evidence
exercise, not as a command checklist. The concept being taught is identity, class, profile and
authority analysis. From a tester’s point of view, the aim is to produce a specific piece of evidence:
user attributes, profile class, UACC, access list, WARNING or audit fields. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
RDEFINE FACILITY LAB.PROFILE UACC(NONE): defines a FACILITY-class resource profile with no
universal access. It teaches resource protection rather than user creation.
PERMIT LAB.PROFILE CLASS(FACILITY) ID(MANLAB) ACCESS(READ): adds an access-list entry so
MANLAB can read the protected resource. The teaching point is that access is explicit, class-based
and reviewable.
RLIST FACILITY LAB.PROFILE: lists the resource profile so students can validate UACC and the
access list rather than assume PERMIT worked.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### RDEFINE FACILITY LAB.PROFILE UACC(NONE)
### PERMIT LAB.PROFILE CLASS(FACILITY) ID(MANLAB) ACCESS(READ)
### RLIST FACILITY LAB.PROFILE
### What the output tells us
For `RDEFINE FACILITY LAB.PROFILE UACC(NONE)`, identify the exact returned line, return code,
panel state or dataset change that proves the lab objective. If that item is not present, pause and
troubleshoot the current command context before continuing.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting


<!-- page 64 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### RDEFINE FACILITY
### LAB.PROFILE
### UACC(NONE)
### Defines a simulated
### RACF general resource
profile.
### CLASS selects the
resource class; UACC
controls universal
access.
### Resource profiles
protect FACILITY,
### OPERCMDS, SERVAUTH
and other security-
sensitive controls.
### Evidence is the profile
visible through RLIST.
### PERMIT LAB.PROFILE
### CLASS(FACILITY)
### ID(MANLAB)
### ACCESS(READ)
### Adds an access
permission to a
simulated RACF
resource profile.
### ID names the
user/group and ACCESS
sets the authority.
### PERMIT is where a
profile becomes usable
by a specific identity;
that is often where
least privilege fails.
### Evidence is the profile
access list showing the
new permit.
### RLIST FACILITY
### LAB.PROFILE
### Displays a simulated
### RACF general resource
profile.
### CLASS identifies the
resource class; AUTH
or ALL asks for access
list and authority
detail.
### RLIST converts a
profile name into
evidence: owner, UACC,
warning state and
access list.
### Evidence is the profile
detail and any explicit
permits.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Define a FACILITY resource, grant READ access and verify
RLIST output.
Prerequisites MANLAB user created or use IBMUSER.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 65 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab 08: Create and inspect a dataset profile
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through create and inspect a dataset profile as a practical evidence exercise,
not as a command checklist. The concept being taught is identity, class, profile and authority
analysis. From a tester’s point of view, the aim is to produce a specific piece of evidence: user
attributes, profile class, UACC, access list, WARNING or audit fields. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
ADDSD IBMUSER.MANUAL.TEST UACC(READ) WARNING: creates a dataset profile with READ
universal access and WARNING behaviour. This is intentionally risky because WARNING can
log/allow behaviour that looks enforced but is not fully blocking.
LISTDSD DATASET(IBMUSER.MANUAL.TEST) ALL: lists the dataset profile so UACC, WARNING and
access information can be interpreted as security evidence.
### Starting state
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### ADDSD IBMUSER.MANUAL.TEST UACC(READ) WARNING
### LISTDSD DATASET(IBMUSER.MANUAL.TEST) ALL
### What the output tells us
For `ADDSD IBMUSER.MANUAL.TEST UACC(READ) WARNING`, identify the exact returned line,
return code, panel state or dataset change that proves the lab objective. If that item is not present,
pause and troubleshoot the current command context before continuing.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway


<!-- page 66 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
ADDSD
### IBMUSER.MANUAL.TES
### T UACC(READ)
### WARNING
### Defines a simulated
RACF data set profile.
### UACC sets default
access; WARNING
allows violations to be
logged rather than
blocked in real RACF
concepts.
### Creating a controlled
profile lets you practise
the same data-set
protection workflow
without touching real
SYS1 data.
### Evidence is the new
profile visible through
LISTDSD.
### LISTDSD
### DATASET(IBMUSER.MA
### NUAL.TEST) ALL
### Displays a simulated
RACF data set profile.
### DATASET() selects the
data set profile; ALL
requests full detail.
### Data set profiles are the
boundary between
ordinary users and
sensitive system
libraries, JCL,
credentials and
configuration.
### Evidence includes
### UACC, WARNING,
owner, audit settings
and access lists.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
Objective Create a training dataset profile and review LISTDSD output.
Prerequisites SPECIAL user.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 67 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The next labs move from RACF-style users, groups, classes and profiles into ACF2-style logonids,
UID strings, rules and GSO/control records. Keep comparing the evidence. The syntax changes, but
the security questions stay familiar: who is the identity, what resource is protected, who can use it,
what audit trail exists, and what would a defender change?
## Expanded RACF Security Labs
This RACF lab sequence comes before ACF2 because RACF is the clearest place to learn users,
groups, resource classes, profiles, UACC, access lists and policy posture. The later ACF2 labs
deliberately compare a different security-manager model against this RACF baseline.
### Lab RACF-1: Inspect your RACF identity with LISTUSER
### Command context
Run from TSO READY or ISPF option 6. Do not run LISTUSER from ISPF 3.4, the ISPF editor, FTP or
CICS.
### Why this lab matters
In this lab we turn a user ID into security evidence. LISTUSER is one of the first RACF commands a
tester uses because account state, group membership and special attributes can change the whole
assessment path.
### What the commands do
LISTUSER displays a simulated RACF user profile. The ALL form asks for the fuller view, including
attributes, default group, password/account state and group connections where Gibson exposes
them.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### LISTUSER IBMUSER ALL
### LISTUSER GUEST ALL
### What the output tells us
### Look for SPECIAL, OPERATIONS, AUDITOR, REVOKE, PROTECTED, default group and last-access
style fields. These fields tell you whether the ID is powerful, usable, disabled or intended as a
service account.
### On a real z/OS system
On real z/OS, LISTUSER queries RACF profile information through the RACF command processor.
Viewing privileged attributes may itself be restricted by site policy and can be audited depending
on configuration.
### Defensive takeaway


<!-- page 68 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Defenders should review privileged, stale and unexpected active accounts. A tester should treat
privileged usable IDs as high-value evidence requiring careful validation.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-2: Review group membership and inherited authority
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
Groups are where RACF privilege often becomes less obvious. A user may look ordinary until group
connections reveal inherited access to datasets, resources or operational functions.
### What the commands do
LISTGRP shows group-level information, while LISTUSER shows which groups a user is connected
to. Together they help explain inherited authority.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### LISTUSER IBMUSER ALL
### LISTGRP SYS1
### LISTGRP OPERATIONS
### What the output tells us
Look for connected groups and owner/authority relationships. The evidence is the link between a
user and the group that could carry access.
### On a real z/OS system


<!-- page 69 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Real RACF group structures are central to administration and delegation. Group-SPECIAL,
ownership and connect authority can materially change risk.
### Defensive takeaway
Defenders should review powerful groups, unexpected connects and stale group membership.
Group privilege is often easier to miss than direct user attributes.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-3: Discover RACF profiles with SEARCH
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
SEARCH changes the question from “what do I already know?” to “what protected resources can I
discover?”. It is a reconnaissance command for RACF profile space.
### What the commands do
SEARCH lists matching profiles in a RACF class. FILTER narrows the search so the learner can focus
on a dataset HLQ or resource family.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
SEARCH CLASS(DATASET) FILTER(IBMUSER.*)
SEARCH CLASS(FACILITY) FILTER(*)
### What the output tells us
Look for profile names, class names and whether generic patterns appear. The result tells you
where to use RLIST or LISTDSD next.


<!-- page 70 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
On real z/OS, SEARCH access and output may be controlled. Profile discovery can expose naming
conventions, sensitive resources and weak control boundaries.
### Defensive takeaway
Defenders should assume profile names can become reconnaissance evidence and should monitor
unusual broad searches in sensitive classes where auditing is enabled.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-4: Inspect a dataset profile with LISTDSD and RLIST
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
Dataset profiles turn a dataset name into an access-control decision. This lab teaches how UACC
and access lists explain who can read, update or alter data.
### What the commands do
LISTDSD and RLIST inspect dataset protection. LISTDSD is dataset-focused; RLIST gives a general
RACF resource-profile view where supported.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
LISTDSD DATASET('IBMUSER.JCL.LAB') ALL
### RLIST DATASET IBMUSER.JCL.LAB ALL
### What the output tells us


<!-- page 71 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Look for UACC, WARNING, OWNER and access list entries. UPDATE or ALTER on source, JCL, REXX
or APF-related libraries is the evidence that matters.
### On a real z/OS system
Real RACF DATASET profiles protect MVS datasets. Generic profiles, discrete profiles and access
lists are core to real mainframe security reviews.
### Defensive takeaway
Defenders should baseline sensitive HLQs, review ID(*) access, and investigate broad
UPDATE/ALTER grants on executable or configuration libraries.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-5: Find WARNING mode profiles
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
WARNING mode is useful during staged policy rollout, but forgotten WARNING profiles can allow
access while only recording that access would have failed. This lab teaches why “logged but
allowed” is still a risk.
### What the commands do
### SEARCH ALL WARNING NOMASK looks for profiles marked WARNING. RLIST then confirms the
profile and shows access details.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps


<!-- page 72 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### SEARCH ALL WARNING NOMASK
### RLIST DATASET IBMUSER.WARN.LIB ALL
### What the output tells us
### Look for the WARNING attribute and any access entries that would otherwise be denied. The
profile is important because it may train users, jobs or applications around a control that is not
actually enforcing.
### On a real z/OS system
On real RACF, WARNING can log access that would fail without denying it. Sites use it carefully
during migration or policy testing, but it requires review and expiry discipline.
### Defensive takeaway
Defenders should track WARNING profiles, owners and expiry plans. WARNING on sensitive data
or executable libraries should be treated as a finding until justified.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-6: Review SURROGAT submit-as exposure
### Command context
Run from TSO READY or ISPF option 6 for RACF review. JCL submission happens later from READY,
ISPF edit or FTP/JES depending on the lab.
### Why this lab matters
SURROGAT controls whether one user can submit work as another. From a tester’s point of view
this can become a batch impersonation path; from a defender’s point of view it is a high-value
control class.
### What the commands do
### SEARCH locates submit-as profiles. RLIST shows who is permitted to the specific SURROGAT
resource.
### Starting state


<!-- page 73 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)
### RLIST SURROGAT IBMUSER.SUBMIT ALL
### What the output tells us
Look for <userid>.SUBMIT profiles and the access list. A permitted submitter can become
operationally significant if the target ID owns privileged batch workflows.
### On a real z/OS system
Real JES/RACF checks SURROGAT when USER= appears on a JOB card or when submit-as behaviour
is requested. The job output often records acceptance or rejection evidence.
### Defensive takeaway
Defenders should review SURROGAT permits, especially to privileged IDs, and monitor submitted
jobs that specify USER= or unexpected submitter/owner combinations.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-7: Review SERVAUTH, FACILITY and OPERCMDS exposure
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters
### Not all mainframe risk is in datasets. FACILITY, SERVAUTH and OPERCMDS protect sensitive
services, network access and operator functions. This lab teaches students to look beyond users
and data.
### What the commands do


<!-- page 74 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
These SEARCH commands enumerate profiles in classes that often gate sensitive system, network
or operator capabilities.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
SEARCH CLASS(FACILITY) FILTER(*)
SEARCH CLASS(SERVAUTH) FILTER(*)
SEARCH CLASS(OPERCMDS) FILTER(*)
### What the output tells us
Look for broad profiles, ID(*) access, weak UACC and names that map to operator commands,
network zones or privileged services.
### On a real z/OS system
On real z/OS, these classes are part of SAF/RACF control for sensitive functions. Poorly controlled
FACILITY, SERVAUTH or OPERCMDS profiles can expose powerful capabilities.
### Defensive takeaway
Defenders should treat broad access in these classes as high priority and review whether each
permit aligns with a documented operational need.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-8: Review SETROPTS policy posture
### Command context
Run from TSO READY or ISPF option 6.
### Why this lab matters


<!-- page 75 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
SETROPTS LIST gives the policy backdrop for the profile evidence gathered so far. It helps students
understand which classes are active and which password/audit controls are in force.
### What the commands do
SETROPTS LIST displays global RACF options such as class activity, generics, password controls and
other security posture indicators where Gibson simulates them.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### SETROPTS LIST
### What the output tells us
Look for active classes, audit-related settings and password policy indicators. A profile in an
inactive class may not protect what students think it protects.
### On a real z/OS system
Real RACF SETROPTS controls global RACF behaviour. It is administrative and sensitive; output
interpretation requires care and site context.
### Defensive takeaway
Defenders should baseline SETROPTS output and review changes through change control, because
a single global setting can alter enforcement across many resources.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-9: Protect ICSF-related resources
### Command context
Run from TSO READY or ISPF option 6 for RACF commands, and use the Master Console/ICSF lab
where the manual directs you.


<!-- page 76 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
ICSF key-store datasets and control-plane functions are critical. This lab links RACF thinking to
cryptographic service protection and alerting.
### What the commands do
### The RLIST commands review simulated CKDS, PKDS and TKDS dataset protection. ZSEC ICSF
provides the training summary where implemented.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### RLIST DATASET SYS1.CSF.CKDS ALL
### RLIST DATASET SYS1.CSF.PKDS ALL
### RLIST DATASET SYS1.CSF.TKDS ALL
### ZSEC ICSF
### What the output tells us
Look for broad READ, UPDATE or ALTER access and for alert/event output when ICSF refresh or
key-store activity is simulated.
### On a real z/OS system
On real z/OS, ICSF uses datasets such as CKDS, PKDS and TKDS and is tightly integrated with
RACF/SAF controls. Poor protection can become a serious cryptographic-control weakness.
### Defensive takeaway
### Defenders should monitor key-store access, refresh commands and unexpected changes. ICSF
dataset protection should be part of privileged access review.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.


<!-- page 77 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab RACF-10: Add an APF library with UACC UPDATE for training review
### Command context
### Run from TSO READY or ISPF option 6. This is a Gibson-only misconfiguration exercise in a
disposable training state.
### Why this lab matters
APF-authorized libraries are trusted code paths. Giving everyone UPDATE to an APF library is the
kind of configuration that turns ordinary dataset access into a privilege-escalation concern.
### What the commands do
The commands create or inspect a training APF-library exposure, grant broad UPDATE access, then
review the evidence using RACF and security-tool views.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### RDEFINE DATASET GIBSON.APF.LIB UACC(UPDATE)
PERMIT 'GIBSON.APF.LIB' ID(*) ACCESS(UPDATE)
### RLIST DATASET GIBSON.APF.LIB ALL
### ENUM APF
### SYS0WN
### What the output tells us
Look for UACC(UPDATE), ID(*) UPDATE or an equivalent broad permit on the APF-related library.
That is the evidence that the trusted code boundary is exposed.
### On a real z/OS system
On real z/OS, APF libraries are controlled through system configuration such as PROGxx/SETPROG
and protected by dataset access controls. UPDATE to APF libraries is a high-risk finding.
### Defensive takeaway
Defenders should restrict APF library update access to tightly controlled build/deploy IDs and alert
on APF list changes or broad access to APF datasets.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup


<!-- page 78 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Remove the training profile/permit or reset Gibson before continuing. Never treat this lab as
production change guidance.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-11: Create a WARNING-mode library
### Command context
Run from TSO READY or ISPF option 6. This is a Gibson-only controlled misconfiguration exercise.
### Why this lab matters
This lab creates a profile that illustrates WARNING mode. The point is to show how an apparently
protected resource may still allow access while producing warning/audit evidence.
### What the commands do
RDEFINE creates a training dataset profile with WARNING. RLIST confirms the profile. SEARCH
ALL WARNING NOMASK finds WARNING profiles for follow-up.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### RDEFINE DATASET GIBSON.WARN.LIB UACC(NONE) WARNING
### RLIST DATASET GIBSON.WARN.LIB ALL
### SEARCH ALL WARNING NOMASK
### What the output tells us
Look for the WARNING attribute. If Gibson simulates an access test, look for evidence that the
access would have failed but was allowed because the profile is in WARNING.
### On a real z/OS system
Real RACF WARNING mode is used for staged control rollout and testing. It should not remain
indefinitely on sensitive datasets because enforcement is not hard denial.
### Defensive takeaway
### Defenders should maintain an owner, reason and expiry for every WARNING profile and alert
when sensitive libraries are left in WARNING mode.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note


<!-- page 79 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Delete the training profile or reset Gibson after the lab if the next class section expects a clean
RACF state.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-12: Create a SURROGAT submit-as path and submit JCL
### Command context
Run RACF setup from TSO READY or ISPF option 6. Submit JCL from READY or ISPF edit. Review
output in SDSF/JES.
### Why this lab matters
### This lab joins RACF, SURROGAT and JES. It teaches that batch submission can become an
impersonation path when one ID is permitted to submit work as another.
### What the commands do
### The RACF commands establish a training submit-as path. The SUBMIT command starts a simple
job, and SDSF/JES review provides the evidence of how the job was accepted or rejected.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### ADDUSER SUBMITR DFLTGRP(SYS1)
### RDEFINE SURROGAT IBMUSER.SUBMIT UACC(NONE)
### PERMIT IBMUSER.SUBMIT CLASS(SURROGAT) ID(SUBMITR) ACCESS(READ)
SUBMIT 'IBMUSER.JCL(SURRJOB)'
### SDSF ST
### What the output tells us
Look for the SURROGAT profile, the submitter permit, the JOB USER= target and the resulting job
ID/return code or rejection message.
### On a real z/OS system
On real z/OS, SURROGAT controls submit-as behaviour for batch. JES and RACF evidence can show
who submitted the job and which user the job ran as.
### Defensive takeaway
Defenders should review SURROGAT permits to privileged IDs and monitor jobs where submitter
and execution user differ unexpectedly.


<!-- page 80 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Remove the training SURROGAT permit/profile and training user, or reset Gibson before returning
to the baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### Lab RACF-13: Convert RACF evidence into a security finding
### Command context
Use evidence from the previous RACF labs. This is a reporting exercise, not a configuration step.
### Why this lab matters
### A penetration test does not end with a command. This lab teaches students to convert RACF
evidence into a finding with impact, proof and remediation.
### What the commands do
The “command” here is the reporting workflow: select evidence, explain why it matters and
propose a defensible remediation.
### Starting state
Start from TSO READY. If you are in ISPF, use =6 before entering RACF commands. Use the Gibson
training state, not a production mainframe.
### Lab steps
### Review evidence from RACF-1 through RACF-12
Write: Title, Evidence, Impact, Likelihood, Remediation, Defensive validation
### What the output tells us
A good finding names the resource, shows the risky field or permit, explains the impact and gives
the owner a practical validation step.
### On a real z/OS system
Real mainframe findings must distinguish discovery from exploitability and must map evidence to
RACF, JES, APF or operational control points.
### Defensive takeaway


<!-- page 81 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Defenders should be able to reproduce the evidence, confirm whether access is required, and apply
or verify the corrective control.
### Troubleshooting
If the command is rejected, confirm you are at READY or ISPF option 6, then confirm the class,
profile name and user ID exist in the Gibson training state.
### Instructor note
Ask students to identify the one field or access entry that changes the risk decision. The goal is
evidence interpretation, not command memorisation.
### Cleanup
Reset the simulator state or remove the created training object if the class run needs to continue
from a clean baseline.
### Validation status
Source validated against Gibson command coverage and previous proof matrices; safe runtime
validation is recommended in the teaching environment.
### From RACF to ACF2
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup
Ask students to defend their severity rating with the output, not opinion.
### Instructor note
If the finding sounds generic, add the resource name, class, user/group and access level.
### Troubleshooting
Defenders should be able to validate the fix by rerunning the same command or report and seeing
the risky condition removed.
### Defensive takeaway
Real assessment reports should separate evidence, impact, exploitability and remediation, with
enough detail for administrators to reproduce and fix the issue.
### On a real z/OS system
A good answer links an exact command output line to a control failure and a remediation. For
example, APF UACC UPDATE is stronger evidence than “APF looks bad.”
### What the output tells us
Choose one previous RACF lab result.
Write: Evidence, Impact, Likelihood, Recommendation, Defensive Validation.


<!-- page 82 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
Use LISTUSER, RLIST, LISTDSD, SEARCH, ZSEC, ENUM and JES/SDSF evidence from previous labs to
write a concise finding.
### What the commands do
This capstone forces students to turn RACF evidence into a finding. The value is in explaining
impact, not collecting another page of output.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
## ACF2 Security Model and Gibson
### ACF2 Commands
### Why ACF2 matters in Gibson
### ACF2 is one of the major external security managers used on mainframes. Gibson implements
ACF2 command equivalents so students can compare RACF-style profiles with ACF2-style logonids,
UID strings, data set rules and resource rules. From a tester's point of view, this matters because
two sites can protect similar resources through very different command languages. From a
defender's point of view, it teaches why you must read the security product that is actually
running, rather than forcing every finding into RACF terminology.
### Command context
### Start from TSO READY. Enter ACF2 to switch the READY command processor into Gibson ACF2
mode. Use RACF to return to RACF command syntax. If you are already inside ISPF, use option 6
first, then enter ACF2 and the related commands. Do not type ACF2 commands at the ISPF primary
menu, in the ISPF editor line-command area, inside CICS, inside FTP, or at the OMVS shell unless a
documented bridge is being used.
### Gibson ACF2 simulation scope
Gibson maps ACF2 training concepts onto the simulator state. LID commands work against the
seeded user store and dynamic RACF-style backend. RULE commands store data set rule
equivalents. RESOURCE commands map ACF2 resource types such as FAC, SUR and OPR onto
SAF/RACF-style classes so the learner can practise the thought process safely. The point is not to


<!-- page 83 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
claim Gibson is a full ACF2 implementation. The point is to give students enough behaviour to
understand how ACF2 changes the security assessment workflow.
### ACF2 command reference
### ACF2 concept map
### ACF2 output interpretation
### Lab ACF2-1: Enter ACF2 mode and list logonids
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
In this lab we'll prove the ACF2 command context before doing anything state-changing. The
security lesson is simple: the same simulator can teach RACF and ACF2, but the commands and
mental model are different.
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
ACF2
### SHOW MODE
### SHOW DDSN
LIST *
### LIST IBMUSER
### What the output tells us
You should see ACF2 MODE ACTIVE, database dataset names and logonid records. The important
evidence is the identity fields, not just that the command ran. On a real ACF2 system, listing
logonids would be controlled by administrative scope and would feed user-review or privileged-ID
review.


<!-- page 84 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
### Lab ACF2-2: Create and change a training logonid
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
This lab shows how identity administration changes state. In a production system, this is high-risk
activity; in Gibson it is a safe way to see what privileged ACF2 administration looks like.
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps


<!-- page 85 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
ACF2
### SET LID
### INSERT ALICE PASSWORD(TEST123) SECURITY GROUP(LAB) UID(2001)
### LIST ALICE
### CHANGE ALICE NOSECURITY GROUP(SYS1) NO-OMVS
### LIST ALICE
### What the output tells us
The evidence is the transition from SECURITY to NOSECURITY and the OMVS/UID fields. Defenders
care because logonid creation and privilege changes are audit-significant events.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
### Lab ACF2-3: Build and test a data set rule
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
Here we move from identity to access. ACF2 rules answer the question: can this logonid use this
data set at this service level?
### What the commands do


<!-- page 86 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
ACF2
### SET RULE
### INSERT IBMUSER.SECRET.DATA
### RECKEY IBMUSER ADD(SECRET.DATA UID(ALICE) SERVICE(READ) ALLOW)
### LIST IBMUSER.SECRET.DATA
ACCESS DSNAME('IBMUSER.SECRET.DATA')
TEST DSNAME('IBMUSER.SECRET.DATA') LID(ALICE) SERVICE(READ)
### What the output tells us
Look for the $KEY, UID(ALICE), SERVICE(READ), ALLOW and TEST ALLOW lines. On real z/OS, this
would be paired with ACF2 rule reporting and access/audit records.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.


<!-- page 87 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab ACF2-4: Review a SURROGAT-style resource rule
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
This lab connects ACF2 resource-rule thinking to a familiar security risk: submit-as authority. Even
if the syntax differs, the question is the same: who can act as whom?
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
ACF2
### SET RESOURCE(SUR)
### RECKEY IBMUSER ADD(IBMUSER.SUBMIT UID(ALICE) SERVICE(READ) ALLOW)
### LIST IBMUSER.SUBMIT
### ACCESS RESOURCE(IBMUSER.SUBMIT) TYPE(SUR)
TEST IBMUSER RSRCNAME('IBMUSER.SUBMIT') LID(ALICE) SERVICE(READ)
### What the output tells us
The evidence is TYPE(SUR) and the allowed UID/service line. Defenders should treat submit-as
authority as privilege delegation, not as a harmless batch convenience.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note


<!-- page 88 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
### Lab ACF2-5: Translate ACF2 evidence into a security finding
### Command context
Start from TSO READY. If you are inside ISPF, use =6 first. Commands run from ACF2 mode unless
the step explicitly says otherwise.
### Why this lab matters
This capstone lab forces the student to stop collecting output and start explaining risk. ACF2 output
should turn into a finding only when the affected identity, rule, resource and consequence are
clear.
### What the commands do
The commands in this lab either set the active ACF2 processing context, list records, create training
records, or test access decisions. Read each output line as evidence about identity, rule, resource or
decision state.
### Starting state
Use the seeded Gibson state as IBMUSER. State-changing labs should be run in a disposable training
copy.
### Lab steps
Choose one previous ACF2 output line.
Write: Evidence, Impact, Likelihood, Recommendation, Defensive Validation.
### What the output tells us
A good answer explains the protected resource, the logonid or UID that can use it, the service level,
and the control that should govern the access. On real z/OS, that evidence would be supported by
ACF2 reports, SMF/security records and change history.
### On a real z/OS system
ACF2 uses logonid records, UID strings, rules, resource rules and global options rather than RACF
syntax. Equivalent activity would be controlled by ACF2 administrative authority, scope and site
audit policy.
### Defensive takeaway


<!-- page 89 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The defender should be able to explain which logonids are privileged, which UID/rule clauses grant
access, which resource rules delegate sensitive functions and where the evidence is logged.
### Troubleshooting
If LIST or SHOW gives an authorization error, check that you are using a privileged training ID. If
### LIST returns no rules, confirm that SET RULE or SET RESOURCE was issued before the
INSERT/RECKEY step.
### Instructor note
### Ask students to compare one ACF2 line with the closest RACF equivalent. The goal is not
memorising syntax; it is learning to translate security intent across ESMs.
### Cleanup
For state-changing labs, either continue with the created training objects for the comparison lab or
delete the test logonid/rules in a disposable state. Do not run cleanup that removes seeded users.
### Validation status
Source validated from gibson/core/acf2.py and tests/test_acf2_equivalents.py; runtime validation is
recommended when teaching live.
## Chapter 7. ISPF and Editor
### Workflows
This section covers ISPF launcher behaviour, dataset listing/editing, member concepts and guided
editor-style workflows.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
ISPF is not a general shell; it is a panel and editor environment with its own command areas.
### Navigation commands, primary edit commands and line commands each belong in different
places, and Gibson uses that distinction to teach real mainframe habits.


<!-- page 90 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value is change control. Editing source, JCL, REXX or configuration members can
change how work runs, so students should treat editor access as a security boundary, not just a
convenience.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 09: Launch ISPF and inspect datasets
### Command context
Start from: TSO READY, then enter ISPF
If you are currently in ISPF: Use =6 for TSO commands, =3.4 for dataset lists, and the editor
command line only after opening a member.
Commands run from: ISPF primary menu, ISPF 3.4, or ISPF editor depending on the step
Do not run these from: CICS, FTP or OMVS
Why context matters: ISPF is a panel environment. READY commands such as LISTCAT need
READY or option 6; editor commands such as SAVE need an open edit session.
### Why this lab matters
In this lab we’ll work through launch ispf and inspect datasets as a practical evidence exercise, not
as a command checklist. The concept being taught is interactive dataset navigation and edit access.
From a tester’s point of view, the aim is to produce a specific piece of evidence: panel entry,
dataset/member display, edit or browse state. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
ISPF: enters the panel environment. It marks a shift from command-line TSO thinking to panel-
driven dataset and utility workflows.
LISTCAT: shows catalog-style dataset information. It gives the learner a safe way to practise moving
from a command prompt to dataset discovery.
VIEW IBMUSER.JCL.LAB: opens a dataset-like object in view mode. The distinction from edit
matters: view should let you inspect without changing state.
### Starting state
Start from READY and make sure the dataset named in the lab exists. Use view-oriented actions
first so you understand what you are looking at before attempting edits in later labs.


<!-- page 91 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab steps
ISPF
### LISTCAT
### VIEW IBMUSER.JCL.LAB
### What the output tells us
For `ISPF`, look for the editor state change: inserted text, deleted lines, a saved member or a
discarded buffer. The edit is proven by the member content, not by the key press alone.
### On a real z/OS system
ISPF is the panel-driven workbench for TSO users. Edit primary commands, line commands and
DSLIST actions can change JCL, CLISTs, REXX and configuration members, so sites protect datasets
heavily.
### Defensive takeaway
Focus on who can browse or edit operational datasets, especially PROCLIB, PARMLIB, JCL libraries
and application control libraries.
### Troubleshooting
If ISPF navigation fails, confirm the option path, dataset name and whether you are in browse or
edit mode. Edit commands only make sense inside an edit panel.
### Instructor note
Have students say out loud whether they are browsing, viewing or editing before they press Enter.
The misconception to correct is that a panel is harmless simply because it looks like a menu.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### ISPF Enters the simulated
### ISPF menu
environment.
### No option is required
to reach the primary
menu.
### ISPF is the workbench
for data sets, members,
### JCL and edit workflows,
so the lab moves from
line commands into
screen-driven
operation.
### Evidence is the ISPF
primary option menu.
### LISTCAT Lists cataloged data
sets known to the
simulator.
### A high-level qualifier
may narrow results
where implemented.
### Catalog enumeration
tells you what objects
exist before you test
RACF or edit paths.
### Evidence is a list of
data set names and
attributes.
VIEW
### IBMUSER.JCL.LAB
### Opens a data set or
member in a read-
oriented view/edit-style
### The data set name
selects the target.
### Viewing before editing
is good assessment
discipline; you collect
### Evidence is the
displayed member or
data set content.


<!-- page 92 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
path. evidence before
changing state.
### Field Value
### Difficulty Beginner
### Estimated time 30 minutes
### Objective Use the TSO launcher and dataset catalog commands to prepare
for ISPF work.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Command What It Does Important Options Why It Matters Expected Evidence
### I / In Insert blank line(s). Optional count such as
I3.
### Creates room for new
content.
n LINE(S) INSERTED
### D / Dn Delete line(s). Optional count. Removes content
deliberately.
n LINE(S) DELETED
### SAVE Persist changes. None. Commits buffer to
dataset/member.
### DATA SAVED
### END / PF3 Leave edit when clean. PF3 maps to END. Exits after save. Editor exits or dirty
prompt
### Command What It Does Important Options Why It Matters Expected Evidence
### CHANGE Modify text in buffer. CHANGE old new. Creates a deliberate
unsaved change.
n OCCURRENCE(S)
### CHANGED
### CANCEL / PF12 Discard changes. CAN alias supported. Leaves without save. Original content
remains
### Command What It Does Important Options Why It Matters Expected Evidence
### FIND / F Search for text. FIND string. Locates evidence. CHARS string FOUND
### RFIND Repeat prior search. No operands. Moves through
evidence.
### FOUND/NOT FOUND
### CHANGE / C Replace text. CHANGE old new
[ALL].
### State-changing edit. n OCCURRENCE(S)
### CHANGED
### RCHANGE Repeat previous
change.
### No operands. Reuses last
replacement.
n OCCURRENCE(S)
### CHANGED
### Command What It Does Important Options Why It Matters Expected Evidence
### C / CC Copy line/block. C, Cn, CC...CC. Stages source lines. n LINE(S) COPIED
### M / MM Move line/block. M, Mn, MM...MM. Removes source and
stages it.
n LINE(S) MOVED
### A / B Place buffer. After/before target. Controls destination. n LINE(S) INSERTED
### R / RR Repeat line/block. R, Rn, RR...RR. Duplicates patterns. n LINE(S) REPEATED
### D / DD Delete line/block. D, Dn, DD...DD. Removes content. n LINE(S) DELETED
### Command What It Does Important Options Why It Matters Expected Evidence


<!-- page 93 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### PROFILE Display settings. None. Shows active editor
state.
### Profile message
### CAPS Toggle uppercase. ON/OFF. Explains case
behaviour.
### CAPS ON/OFF
### HEX Toggle hex state. ON/OFF. Introduces byte-level
thinking.
### HEX ON/OFF
### RESET Clear excluded state. RESET X. Restores display. n LINE(S) RESET
~ / TAB Change focus. Gibson helper / key. Prevents wrong-field
errors.
### COMMAND FIELD or
focus movement
### PF3 / PF12 END/CANCEL. PF keys. Safe exit choices. END/CANCEL
behaviour
### Command What It Does Important Options Why It Matters Expected Evidence
### EDIT / E Open member in edit. ISPF 3.4 action. Confirms update path. Editor opens
### SAVE Persist member. None. Commits change. DATA SAVED
### SUB / SUBMIT Submit current JCL
where configured.
### Editor or READY
context.
### Connects edit to
execution.
### JOB SUBMITTED/job
output
### SDSF ST/H/O Review output. SDSF context. Confirms execution
evidence.
### Spool output
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If SUBMIT fails, separate the problems: did the member save, is it valid JCL, and are you submitting
from the right context?
### Troubleshooting
Review UPDATE/ALTER to executable libraries and correlate member changes with JES execution
evidence.
### Defensive takeaway
On real z/OS, libraries in SYSPROC, SYSEXEC, PROCLIB, JCLLIB or scheduler paths can be trusted by
humans or automation. RACF DATASET controls and SMF/JES evidence matter.
### On a real z/OS system
The evidence chain is edit authority -> saved content -> optional execution evidence. That is a
security workflow, not just an editor workflow.
### What the output tells us


<!-- page 94 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
1. Open a safe scratch JCL or REXX member.
2. Add a harmless comment or display statement.
3. SAVE.
4. If safe JCL and submitter are configured, SUBMIT.
5. Review output in SDSF/JES context.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll connect ISPF editing to mainframe security. UPDATE access to JCL, REXX, CLIST or
PROC libraries can become an execution path when another user, scheduler or started task trusts
that content.
### Why this lab matters
Start in ISPF edit on a scratch JCL/REXX member. Run TSO commands from READY or option 6;
review jobs from SDSF/JES, not inside the editor.
### Command context
### Lab 09F: Security impact of edit access to JCL or REXX
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If text appears in the member, you were in the data field. Use ~ or TAB to return to command focus.
### Troubleshooting
Reliable evidence requires reliable editing. If a student cannot prove whether they saved, cancelled
or simply changed focus, their assessment notes will be weak.
### Defensive takeaway
Real ISPF profiles and keylists are site-customisable. Gibson simplifies them but preserves the
training lesson: know your profile and key behaviour.
### On a real z/OS system
The output tells you the editor's state and where your next input will go. That matters because
wrong-field typing is a common 3270 learning failure.


<!-- page 95 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### What the output tells us
1. Run PROFILE.
2. Toggle CAPS OFF and ON.
3. Toggle HEX ON and OFF.
4. Exclude a line with X, then run RESET.
5. Use TAB or ~ to return to command focus.
6. Use PF3/PF12 only when you know whether you want END or CANCEL.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll focus on editor state. The command may be correct, but if the cursor is in the
wrong field or the profile behaves differently, the learner will misread the result.
### Why this lab matters
Start in ISPF edit. PROFILE, CAPS, HEX, RESET, TAB and ~ are editor behaviours. PF3 maps to END
and PF12 maps to CANCEL.
### Command context
### Lab 09E: ISPF editor switches and PF keys
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
### If A or B says NO COPIED/MOVED LINES, copy or move first. If a block command says BLOCK
STARTED, mark the second boundary line.
### Troubleshooting
Watch for unauthorised or unreviewed changes to libraries where block edits can alter execution
paths.
### Defensive takeaway
Real ISPF block editing is daily mainframe work. It is powerful enough to duplicate EXEC steps,
remove DD statements or change job behaviour if used carelessly.
### On a real z/OS system


<!-- page 96 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Line-count messages and the new member layout prove what happened. Students should be able to
identify source lines, buffered lines and target placement.
### What the output tells us
1. Copy one line with C and place it with A.
2. Copy a block with CC at first and last line, then place with B.
3. Move a line with M and place it with A.
4. Repeat a line with R3.
5. Delete a block with DD at first and last line.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll use the commands that make ISPF editing efficient: copy, move, repeat and block
delete. These are the commands students need before editing JCL safely.
### Why this lab matters
Start in ISPF edit. Use the line-command area or Gibson fallbacks. A and B are placement targets;
they are not standalone copy commands.
### Command context
### Lab 09D: ISPF copy, move, repeat and block line-command workflow
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If RFIND says NO PRIOR FIND, run FIND first. If CHANGE is blocked, you are in browse/view or lack
edit authority.
### Troubleshooting
Review UPDATE/ALTER access to executable and configuration libraries. Diffs to JCL, PROCs and
REXX are evidence defenders should preserve.
### Defensive takeaway
Real ISPF FIND/CHANGE is central to JCL/config review. Changing a PROC, REXX or RACF-command
member can alter system behaviour.


<!-- page 97 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
FIND proves where the evidence is; CHANGE proves you can alter it. The distinction between read
evidence and write capability is the security lesson.
### What the output tells us
1. Open a member containing repeated words.
2. Run FIND USER.
3. Run RFIND.
4. Run CHANGE 'USER' 'STUDENT'.
5. Run RCHANGE or CHANGE 'USER' 'STUDENT' ALL.
6. SAVE only if using a scratch member.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll search and replace within a member. Mainframe security work often means
quickly finding user IDs, dataset names, program names, ports or control statements in long
JCL/REXX/config members.
### Why this lab matters
Start in ISPF edit. FIND, RFIND, CHANGE and RCHANGE run on Command ===>. They are not
READY commands.
### Command context
### Lab 09C: ISPF FIND and CHANGE workflow
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If the change persists, the student probably saved it. Reset the scratch member and repeat.
### Troubleshooting
Teach students to prove edit authority without unnecessarily changing state. A cancelled edit can
be a safer proof-of-access during training.
### Defensive takeaway


<!-- page 98 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
On real z/OS, CANCEL is a practical safety mechanism when you realise you are in the wrong
member or about to save a bad edit.
### On a real z/OS system
The proof is negative evidence: the change should not be there after reopening. That tells the
student CANCEL restored the original buffer.
### What the output tells us
1. Open a safe member.
2. Run CHANGE 'OLD' 'NEW' or insert a test line.
3. Type CANCEL or press PF12.
4. Reopen the same member and confirm the change is gone.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll prove that CANCEL discards an unsafe or unwanted edit. The goal is to understand
the difference between a dirty edit buffer and a committed dataset change.
### Why this lab matters
Start in ISPF edit. CANCEL and PF12 are editor actions. Do not treat CANCEL as a TSO command.
### Command context
### Lab 09B: ISPF edit cancel/no-save workflow
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If I or D appears as text, your cursor is in the data field. Use the line-command area or Gibson's LC
n command fallback.
### Troubleshooting
### Edit access to JCL/REXX/config libraries is sensitive. Defenders should know who has
UPDATE/ALTER access and who changed executable members.
### Defensive takeaway


<!-- page 99 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Real ISPF separates primary commands from line commands. Dataset profiles, library
management and ENQ/locking decide whether a save is allowed.
### On a real z/OS system
The useful evidence is the line-count message and DATA SAVED. That proves the editor processed
line commands and then wrote the result.
### What the output tells us
1. Open a safe training member in ISPF edit.
2. Insert a blank line with I or LC n I.
3. Add a harmless comment line.
4. Delete a scratch line with D.
5. Type SAVE.
6. Type END or press PF3.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll use Gibson to practise the core edit loop: insert a line, delete a line and save
deliberately. This is the same foundation students need before editing JCL, REXX or configuration
members.
### Why this lab matters
Start in ISPF edit. Primary commands go on Command ===>. Line commands go in the line-
command area or through Gibson fallbacks such as LC 5 I. Do not run I, D or SAVE at TSO READY.
### Command context
### Lab 09A: ISPF edit insert/delete/save workflow
## Code Interpreters
### Why code matters on the mainframe
In this section we’ll move from using Gibson to interrogate a system into using Gibson to write,
submit and interpret code. That matters because real mainframes are not only login screens and
command prompts. They are programmable operating environments where JCL starts work, REXX
automates TSO and dataset activity, COBOL carries business logic, and assembler sits close to the
platform boundary. In Gibson, these capabilities are deliberately bounded so students can practise
the evidence trail without executing arbitrary host code.


<!-- page 100 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Gibson’s code execution model
Gibson supports REXX execution through a bounded interpreter, JCL/JES submission through a
parser and spool model, and COBOL source-aware compile simulation through the JES runner.
HLASM is included here as a real z/OS concept and a future enhancement: the source package does
not contain an HLASM interpreter or assembler runner. Code is normally written in ISPF edit or
copied through USS/MVS transfer paths, executed through TSO EX, SUBMIT, JES, FTP/JES or
supported simulator routes, and then reviewed through terminal output or SDSF/JES spool files.
### Interpreter Gibson status Primary entry
point
### Output to inspect Security lesson
### REXX Implemented
bounded
interpreter
### REXX, EXEC, EX
or %exec from
### TSO READY / ISPF
option 6
### SAY output, TSO
command output,
### EXECIO dataset
changes
### Automation can
inspect or change
state; script
libraries need
protection
### JCL/JES Implemented
parser and JES
runner
### SUBMIT
dataset(member),
### ISPF editor
### SUB/SUBMIT,
### FTP/JES where
enabled
### Job ID, RC,
### JESMSGLG,
### JESJCL,
### JESYSMSG,
### SYSOUT/SYSPRIN
T
### Batch is an
execution path;
### SURROGAT and
spool access
matter
### COBOL Implemented
compile
simulation, not a
full runtime
### JCL EXEC
PGM=IGYCRCTL
or COBOL with
SYSIN
### IGYCRCTL listing,
### DISPLAY text in
### SYSPRINT
### Source structure
and compiler
output teach
business-code
evidence
### HLASM Not implemented
as an interpreter
### Conceptual only /
future
enhancement
### N/A in Gibson Assembler is a
high-trust real
z/OS skill; do not
pretend Gibson
assembles code
### REXX interpreter
REXX is the most useful first programming language for Gibson students because it sits beside TSO.
A small exec can print variables, accept arguments, call TSO commands, and read or write datasets
through EXECIO. In a security lab, this turns a single command into repeatable evidence collection.
In a production z/OS environment, the same idea is powerful and therefore sensitive:
SYSEXEC/SYSPROC libraries, dataset write access and ADDRESS TSO use should be governed and
audited.
### REXX element Syntax Gibson behaviour Real z/OS
meaning
### Security /
learning value


<!-- page 101 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### SAY SAY expression evaluates
expression and
writes line to
output
REXX
display/output
instruction
helps prove exec
ran and exposes
automation
output
### PARSE ARG PARSE ARG var1
var2
splits invocation
arguments into
variables
common TSO/E
### REXX argument
parsing
teaches
parameterised
tooling
### ARG(n) ARG(1) returns nth
invocation
argument
real REXX
argument access
concept
reduces hard-
coded scripts
### ADDRESS TSO ADDRESS TSO
command
routes command
to Gibson TSO
processor
### TSO/E REXX
external
command
environment
automation can
list users/datasets
or submit jobs
EXECIO DISKR EXECIO * DISKR
dsn (STEM stem.
reads dataset
lines into stem
variables
reads z/OS
datasets in REXX
evidence
collection and
dataset review
EXECIO DISKW EXECIO * DISKW
dsn (STEM stem.
writes stem
variables to a
dataset
writes z/OS
datasets in REXX
state-changing
automation risk
DO/END DO i = 1 TO 3 ...
END
bounded
counted/while
loops
### REXX looping automation and
repeated checks
IF/THEN/ELSE IF expr THEN ...
ELSE ...
conditional
execution
### REXX branch
logic
risk decisions in
scripts
SYSVAR SYSVAR('SYSUID') returns simulated
system/user
values
### TSO/E system
variable query
identity-aware
scripts
TIME/DATE TIME(); DATE() returns current
time/date
### REXX time/date
functions
audit/time
stamping in
scripts
### JCL interpreter and JES runner
JCL is how batch work is described. In Gibson, the parser reads JOB, EXEC and DD statements, JES
creates a job ID and spool, and the runner simulates selected programs such as IEFBR14,
IEBGENER, IKJEFT01, BPXBATCH, DSNTEP2/DSNTIAD and IGYCRCTL. The important habit is to read
the job as a set of security decisions: who owns it, what program runs, what datasets are read or
written, what SYSIN says, and what output appears in spool.
### JCL Syntax Gibson behaviour Real z/OS Security /


<!-- page 102 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
statement/keywor
d
meaning learning value
### JOB //NAME JOB
(acct),'desc',CLAS
S=A,MSGCLASS=A
creates job
identity,
owner/class/mess
age class
defines batch job
to JES
job owner and
### SURROGAT risk
USER= USER(userid) submit-as identity
checked through
### SURROGAT
batch job
execution user
impersonation/
privilege risk
### EXEC PGM //STEP EXEC
PGM=IEFBR14
extracts program
and simulates
supported PGMs
defines job step
program
program choice
determines
impact
PARM PARM='value' operands
captured;
### BPXBATCH/TShOc
ker style parms
partly parsed
passes
parameters to
programs
parameters can
alter run
behaviour
### DD //DDNAME DD ... inventory and
instream DD
capture
defines
input/output
datasets/devices
### DDs can
expose/write
datasets
SYSIN DD * //SYSIN DD * ... /* passes instream
block to program
simulation
inline program
control input
what you send to
utilities matters
SYSOUT=* //SYSPRINT DD
SYSOUT=*
routes program
output to JES
spool
writes output to
### JES SYSOUT
spool may leak
sensitive data
### Program Purpose Gibson
behaviour
### Inputs Outputs Security
relevance
### IEFBR14 Safe no-op
step
### Returns RC
0000
### JCL step JESYSMSG/
### JESMSGLG
### Baseline job
submission
and spool
review
### IEBGENER Copy utility
simulation
### Copies SYSUT1
to SYSUT2
where
possible
### SYSUT1/
### SYSUT2 DDs
### IEB144I
records
written
### Dataset copy
paths can
expose or
alter data
### IKJEFT01 /
### IKJEFTxx
### TSO batch
driver
### Runs SYSTSIN
commands
through TSO
processor
### SYSTSIN TSO command
output in
spool
### Batch can
automate
privileged
commands


<!-- page 103 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### BPXBATCH USS batch
bridge
### Simulates
UNIX
processor and
selected
output
### STDPARM/
STDIN
### BPXBATCH
messages
### Batch-to-USS
bridge needs
strong
controls
### DSNTEP2 /
### DSNTIAD
### SQL processor
simulation
### Formats Db2
query output
### SYSIN/
### SYSTSIN SQL
### SQL output
spool
### Database
enumeration
evidence
### IGYCRCTL /
COBOL
COBOL
compile
simulation
### Validates
divisions and
extracts
### DISPLAY lines
### SYSIN COBOL
source
### Compile
listing and
### SYSPRINT
### Business-code
evidence
without
runtime
execution
### COBOL compile simulation
Gibson does not run arbitrary COBOL. It simulates the compiler evidence that a beginner needs to
understand: required divisions, DISPLAY output, condition code and informational recognition of
EXEC CICS or EXEC SQL. That distinction matters. A student can learn what a compile listing
proves, but should not claim that Gibson has executed a COBOL load module.
### COBOL element Syntax Gibson behaviour Real COBOL
meaning
### Security /
learning value
### IDENTIFICATION
### DIVISION
### IDENTIFICATION
DIVISION.
required marker
for compile
simulation
real COBOL
identification
division
shows source
structure
### PROCEDURE
### DIVISION
### PROCEDURE
DIVISION.
required marker
for compile
simulation
real COBOL
executable
procedure
division
where program
logic lives
DISPLAY DISPLAY 'text'. literal extraction
into SYSPRINT-
like output
COBOL
output/display
statement
proves program
path and data
disclosure
### EXEC CICS EXEC CICS ... END-
EXEC
recognised and
emits
informational
message
### CICS API call in
COBOL
teaches
transaction-tier
linkage without
execution
### EXEC SQL EXEC SQL ... END-
EXEC
recognised and
emits
precompiler-style
message
embedded SQL in
COBOL
teaches Db2
linkage without
execution


<!-- page 104 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### HLASM status and real-system context
HLASM is documented here because students will encounter assembler in real mainframe security
work, especially around exits, authorised programs, SVCs and low-level utilities. Gibson does not
currently implement an HLASM interpreter, assembler, link-editor or runtime. Treat HLASM
examples in this manual as real z/OS context and future enhancement material only unless a later
Gibson package adds a source-backed runner.
### HLASM element Gibson status Real z/OS meaning Manual treatment
### START / CSECT / USING
/ END
### Not implemented Program organisation
and addressability in
HLASM
### Conceptual only
### STM / LM / LR / LA / L /
### ST / MVC / CLI /
branches
### Not implemented Machine-level register,
storage and branch
logic
### Future enhancement
### WTO macros and
assembler exits
### Not implemented Operator messages
and low-level system
interfaces
### Conceptual security
discussion only
### Editing, storing and running code
A typical Gibson coding workflow is deliberately mainframe-shaped: create or open a PDS member
in ISPF edit, enter REXX, JCL or COBOL source, SAVE or END the member, then execute it from the
correct context. REXX runs from TSO READY or ISPF option 6 using EX/EXEC/REXX. JCL is submitted
from READY, ISPF editor SUB/SUBMIT or FTP/JES. COBOL source is normally compiled through a
JCL step using IGYCRCTL or COBOL. USS cp can move source files between UNIX-style paths and
MVS dataset members, but the execution context still matters.
### Security implications of code execution
Code execution is one of the places where mainframe security stops being theoretical. Write access
to a REXX, JCL, COBOL or PROC library can change what future work does. SUBMIT authority can
turn a dataset member into running work. SURROGAT can make that work run as another user.
SDSF and JES controls decide who can read the evidence. In Gibson, these behaviours are bounded,
but the teaching point is real: source libraries, execution libraries, JES submission and spool
visibility are all security boundaries.
### Lab CI-1: Write and run a simple REXX program
### Command context
Start from: TSO READY or ISPF option 6; use ISPF editor first if creating the member. Do not run
these commands from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX
execution belongs at READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT
or FTP/JES where enabled; spool review belongs in SDSF/JES output.


<!-- page 105 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. SAY, PARSE ARG and SYSVAR
prove that the exec ran, accepted input and knew the current user.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
EX 'IBMUSER.REXX.TEST(HELLO)' 'GIBSON'
### What the output tells us
The evidence is the SAY output. If the argument appears in the output, PARSE ARG worked; if
SYSUID appears, the exec is running under the expected simulator identity.
### On a real z/OS system
On real z/OS, TSO/E REXX is often used for administration, reporting and automation.
SYSEXEC/SYSPROC libraries and dataset writes deserve the same attention as shell scripts on
distributed systems.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status


<!-- page 106 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-2: Use REXX to issue a TSO command
### Command context
Start from: TSO READY or ISPF option 6. Do not run these commands from unrelated contexts. Code
creation belongs in ISPF edit or USS; REXX execution belongs at READY/option 6; JCL submission
belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where enabled; spool review belongs in
SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. ADDRESS TSO is the bridge from
script logic into TSO command processing. In Gibson it routes the command back through the
current TSO processor.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
EX 'IBMUSER.REXX.TEST(TSOCMD)'
### What the output tells us
The evidence is both the REXX output and the TSO command response. If REXX starts but LISTCAT
or LISTUSER output is absent, the script ran but the command bridge did not return the expected
evidence.
### On a real z/OS system
### On real z/OS, ADDRESS TSO can automate powerful commands. A defender cares where the exec
came from, which user ran it, and what TSO commands were issued.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting


<!-- page 107 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-3: Submit simple JCL and read spool output
### Command context
Start from: Create or edit a JCL member in ISPF; submit from READY, ISPF editor SUB/SUBMIT, or
option 6 as documented. Do not run these commands from unrelated contexts. Code creation
belongs in ISPF edit or USS; REXX execution belongs at READY/option 6; JCL submission belongs at
READY, ISPF editor SUB/SUBMIT or FTP/JES where enabled; spool review belongs in SDSF/JES
output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. JOB, EXEC and DD are the core
language of batch work. IEFBR14 gives a safe baseline job with a clean RC.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
SUBMIT 'IBMUSER.JCL.TEST(BR14)'
SDSF
ST
### What the output tells us


<!-- page 108 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The evidence is the JOB ID, RC 0000 and JES spool files. This proves that JES accepted the job and
that the simulated step completed cleanly.
### On a real z/OS system
On real z/OS, JCL submission creates JES evidence and may allocate or change datasets. Submit
authority and SDSF output access are security controls.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-4: Use JCL with SYSIN and SYSOUT
### Command context
Start from: JCL member submitted through READY or ISPF editor. Do not run these commands
from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution belongs at
READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where
enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. SYSIN provides input to a
program and SYSOUT/SYSPRINT routes output to spool. IEBGENER and IKJEFT01 demonstrate two
different styles: utility copy and TSO batch.
### What the commands do


<!-- page 109 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
SUBMIT 'IBMUSER.JCL.TEST(GENER)'
SDSF
O
### What the output tells us
The evidence is the utility message, records-written count or TSO batch output in spool. If SYSOUT
is missing, check DD names and instream input.
### On a real z/OS system
### On real z/OS, SYSIN and SYSOUT show what control data was supplied and what the program
produced. They are often where assessment evidence and sensitive leakage appear.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.


<!-- page 110 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab CI-5: Compile a small COBOL source member
### Command context
Start from: JCL member with EXEC PGM=IGYCRCTL or COBOL. Do not run these commands from
unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution belongs at
READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where
enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. The COBOL simulation checks
required divisions and extracts DISPLAY literals. It teaches compiler evidence rather than runtime
execution.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
SUBMIT 'IBMUSER.JCL.TEST(COBOLJ)'
SDSF
O
### What the output tells us
The evidence is the IGYCRCTL listing, maximum condition code and SYSPRINT DISPLAY line.
Missing required divisions produce IGY-style errors and a higher condition code.
### On a real z/OS system
On real z/OS, COBOL compilation would produce object code and normally feed link-edit and load
libraries. Gibson stops at compile simulation, so do not claim load-module execution.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note


<!-- page 111 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-6: Copy source code between USS and MVS datasets
### Command context
Start from: OMVS/USS shell for cp; ISPF/TSO for later edit or execute. Do not run these commands
from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution belongs at
READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES where
enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. This lab connects the previous
cp work to code. Moving source between USS and MVS is operationally useful and security-relevant
when scripts, JCL or evidence cross subsystem boundaries.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.
### Lab steps
cp rexxdemo.rexx "//'IBMUSER.REXX.TEST(REXXCP)'"
cp "//'IBMUSER.JCL.TEST(BR14)'" br14.jcl
### What the output tells us
The evidence is the target file/member content after the copy. For source movement, success is not
just the copy message; it is the ability to open and understand the destination.
### On a real z/OS system
On real z/OS, USS-to-MVS copy uses dataset pathnames and is controlled by UNIX permissions,
dataset profiles and site policy. Moving code into executable libraries should be controlled.


<!-- page 112 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.
### Lab CI-7: Security impact of editable source and JCL
### Command context
Start from: ISPF editor for source change; TSO READY or ISPF editor for submit. Do not run these
commands from unrelated contexts. Code creation belongs in ISPF edit or USS; REXX execution
belongs at READY/option 6; JCL submission belongs at READY, ISPF editor SUB/SUBMIT or FTP/JES
where enabled; spool review belongs in SDSF/JES output.
### Why this lab matters
In this lab we’ll use Gibson to practise a focused coding workflow. This lab shows why edit
authority is a finding. A small change to source or JCL can alter what future execution does and
what evidence appears in spool.
### What the commands do
The commands in this lab are chosen to demonstrate the hand-off between source, execution and
evidence. Edit commands create or change the member, execution commands run the bounded
simulator path, and SDSF/JES or terminal output tells you what actually happened.
### Starting state
Gibson should be running with the TSO, ISPF, JES/SDSF and dataset simulation available. Use
IBMUSER or another lab user with access to the named training datasets, or create the member
earlier in the lab if it does not exist.


<!-- page 113 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab steps
ISPF
=3.4
### E IBMUSER.JCL.TEST(BR14)
### CHANGE IEFBR14 IEBGENER
SAVE
SUB
### What the output tells us
The evidence is the changed source member and the new job output. If the member changed but
the job output did not, the wrong member may have been submitted.
### On a real z/OS system
On real z/OS, source/JCL libraries are often protected by RACF DATASET profiles and change
control. Defenders should monitor update access, submits and spool access together.
### Defensive takeaway
Defenders should link source changes, execution attempts and output review. A source update
without an approved change, a job submission under a privileged user, or unexpected spool reads
can all be part of the same story.
### Troubleshooting
If the source member cannot be opened, check the dataset name and command context. If SUBMIT
fails, confirm that the member contains JCL and that you are at READY, option 6 or inside the
editor submit path. If output is missing, open SDSF ST/O and verify the job ID and owner.
### Instructor note
Ask students to identify three pieces of evidence: where the code was stored, how it was executed,
and where the result appeared. This prevents the common mistake of treating successful editing as
successful execution.
### Cleanup
Leave harmless training members in place if later labs depend on them. If the lab changed an
existing member, restore the original text or reset Gibson to the chapter baseline.
### Validation status
Source validated from Gibson interpreter and JES code. Runtime validation is recommended when
teaching the lab interactively because dataset names and seeded members can differ by package
version.


<!-- page 114 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
## Chapter 8. SDSF, JES, JCL, and
NJE
This section covers job panels, JES queues, JES2 commands, NJE node/line controls and JCL-related
training flows.
### Implementation evidence
### Area Source evidence
### SDSF gibson/apps/sdsf.py
### JES gibson/core/jes.py
### NJE gibson/core/nje.py
### Operational model
This chapter connects submitted work to JES queues and SDSF-style output. The operational path is
job text to job ID to spool files to return code, with NJE/JES commands adding the operator and
network-job view.
### Security relevance
The security value is evidence handling. Spool output can expose commands, dataset names, return
codes and errors, while JES controls determine who can submit, cancel, hold, release or read other
users' work.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### JES/JCL/NJE TRANSMIT TRANSMIT userid
DA('dataset')
[OUTDSN('package')] - create a
simulated XMIT package.
gibson/apps/tso.py
LEGACY_HELP
### JES/JCL/NJE XMIT Alias of TRANSMIT. gibson/apps/tso.py
LEGACY_HELP
JES/JCL/NJE RECEIVE RECEIVE INDSN('package')
[DA('target')] - restore a
transmitted data set.
gibson/apps/tso.py
LEGACY_HELP
### JES/JCL/NJE SUBMIT Submits a JCL job. gibson/apps/tso.py
LEGACY_HELP
### JES/JCL/NJE JES Simulated Job Entry
Subsystem commands: JES
### STATUS, JES SUBMIT
gibson/apps/tso.py
LEGACY_HELP


<!-- page 115 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
<description>.
SDSF ST/DA/I/O/H/AD/AS SDSF panel command gibson/apps/sdsf.py:260
### SDSF LOG/SYSLOG/OPERLOG/
### SMF80/SMF7/ULOG/SR
SDSF panel command gibson/apps/sdsf.py:263
### SDSF JC/INIT/MAS/PR/PUN/RDR/
### PROC/JES/JG/J0/JRI/JRJ/RM/
### RMA/SO/SP
SDSF panel command gibson/apps/sdsf.py:276
SDSF PS/FS/BPXO SDSF panel command gibson/apps/sdsf.py:278
### SDSF SYS/SYM/APF/CK/DYNX/ENQ/
### ENQC/GT/LLS/LNK/LPA/LPD/
### PAG/PARM/PC/SSI/SVC/SYSP
SDSF panel command gibson/apps/sdsf.py:280
### SDSF FILTER/SORT/OWNER/
### PREFIX/SYSNAME/RESET/
### REFRESH
SDSF primary command gibson/apps/sdsf.py:623
JES2 $(D|C|P|A|H) JOB(jobid) JES2 operator command gibson/core/jes.py:481
This section has 13 command-family entries; complete command pages appear in the full
command reference appendix.
### Section labs
### Lab 10: Review JES state and SDSF status panel
### Command context
Start from: TSO READY or ISPF menu path to SDSF
Commands run from: SDSF panels and JES/spool output views
Do not run these from: FTP, CICS, OMVS or ISPF editor
Why context matters: SDSF reviews jobs and output; it is not the same context as FTP/JES
submission.
### Why this lab matters
In this lab we’ll work through review jes state and sdsf status panel as a practical evidence
exercise, not as a command checklist. The concept being taught is JES spool, job status and
operator-style visibility. From a tester’s point of view, the aim is to produce a specific piece of
evidence: job ID, return code, spool entry or JES2 display response. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
JES STATUS: summarises the simulated job-entry environment. It is the starting point before
creating or browsing job output.
JES SUBMIT MANUALJOB: submits a controlled training job and should produce a job identifier or
equivalent state change.


<!-- page 116 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
SDSF ST: opens the status-oriented SDSF view where job state, return codes and output availability
become visible.
### Starting state
Start from READY with JES/SDSF simulation available. If a job ID is referenced, either submit the
training job first or replace the ID with one that exists in your current state.
### Lab steps
### JES STATUS
### JES SUBMIT MANUALJOB
### SDSF ST
### What the output tells us
For `JES STATUS`, look for the JES job identifier, status, return code or spool entry that proves the
job or JES command was processed. Without job/spool evidence, you cannot explain what actually
ran.
### On a real z/OS system
SDSF sits over JES and operator functions. Access to job output can expose commands, dataset
names, errors and sometimes secrets; access is commonly governed by SDSF/SAF resources such as
JESSPOOL and panel controls.
### Defensive takeaway
Watch job submission, spool reads, operator commands and access to output owned by other users.
Spool access is often underestimated.
### Troubleshooting
If a job is not visible, check the job name/owner, whether it has completed and which panel/filter is
active.
### Instructor note
Point students to the job ID, owner and return code before they open output. Students often jump
straight to spool text without asking whether they should be allowed to see it.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### JES STATUS Enters or queries the
simulated SDSF/JES
view.
ST is the status panel;
### H/O style panels expose
held or output data
### SDSF is where job
status and output
become evidence. It is
### Evidence is a job list,
output panel or JES
state summary.


<!-- page 117 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
where implemented. also where credentials
and system messages
often leak.
### JES SUBMIT
### MANUALJOB
### Submits a simulated
JES job.
### The job/member name
selects the JCL or
canned workload.
### Submission is how
batch work becomes
executable on z/OS;
attackers and admins
both care about what
runs and as whom.
### Evidence is a JOBID or
JES status entry.
### SDSF ST Enters or queries the
simulated SDSF/JES
view.
ST is the status panel;
### H/O style panels expose
held or output data
where implemented.
### SDSF is where job
status and output
become evidence. It is
also where credentials
and system messages
often leak.
### Evidence is a job list,
output panel or JES
state summary.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Submit a simple simulator job and review JES/SDSF status.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 11: Explore JES2 and NJE commands
### Command context
Start from: TSO READY or ISPF menu path to SDSF
Commands run from: SDSF panels and JES/spool output views
Do not run these from: FTP, CICS, OMVS or ISPF editor
Why context matters: SDSF reviews jobs and output; it is not the same context as FTP/JES
submission.
### Why this lab matters
In this lab we’ll work through explore jes2 and nje commands as a practical evidence exercise, not
as a command checklist. The concept being taught is JES spool, job status and operator-style
visibility. From a tester’s point of view, the aim is to produce a specific piece of evidence: job ID,
return code, spool entry or JES2 display response. From a defender’s point of view, the same
evidence explains what should be controlled, logged or challenged before the activity becomes
normalised. By the end of the lab, you should be able to say why each command was used and
what changed in your understanding of the Gibson environment.
### What the commands do


<!-- page 118 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
$D NJEDEF: issues a JES2-style display of NJE definition information. It teaches operator-style
discovery of network job-entry configuration.
$D NODE: displays known JES2/NJE nodes, turning the question from “is NJE present?” into “who is
trusted or defined?”
$D JOB(JOB00001): queries a specific job by identifier. It teaches targeted job-status investigation
rather than broad spool browsing.
### Starting state
Start from READY with JES/SDSF simulation available. If a job ID is referenced, either submit the
training job first or replace the ID with one that exists in your current state.
### Lab steps
$D NJEDEF
$D NODE
$D JOB(JOB00001)
### What the output tells us
For `$D NJEDEF`, look for the JES job identifier, status, return code or spool entry that proves the
job or JES command was processed. Without job/spool evidence, you cannot explain what actually
ran.
### On a real z/OS system
SDSF sits over JES and operator functions. Access to job output can expose commands, dataset
names, errors and sometimes secrets; access is commonly governed by SDSF/SAF resources such as
JESSPOOL and panel controls.
### Defensive takeaway
Watch job submission, spool reads, operator commands and access to output owned by other users.
Spool access is often underestimated.
### Troubleshooting
If a job is not visible, check the job name/owner, whether it has completed and which panel/filter is
active.
### Instructor note
Point students to the job ID, owner and return code before they open output. Students often jump
straight to spool text without asking whether they should be allowed to see it.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence


<!-- page 119 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
$D NJEDEF Issues a JES2-style
display command.
$D asks JES2 to display
configuration or object
state such as NJEDEF,
NODE or JOB.
### Operator commands
reveal the batch and
network job entry
control plane.
Evidence is a $HASP-
style response or
simulated object detail.
$D NODE Issues a JES2-style
display command.
$D asks JES2 to display
configuration or object
state such as NJEDEF,
NODE or JOB.
### Operator commands
reveal the batch and
network job entry
control plane.
Evidence is a $HASP-
style response or
simulated object detail.
$D JOB(JOB00001) Issues a JES2-style
display command.
$D asks JES2 to display
configuration or object
state such as NJEDEF,
NODE or JOB.
### Operator commands
reveal the batch and
network job entry
control plane.
Evidence is a $HASP-
style response or
simulated object detail.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Identify operator-style JES2/NJE control commands and safe
display flows.
Prerequisites Source-validated command matrix.
Validation Source validated; runtime depends on interactive console
context
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
## Chapter 9. Master Console and
### OPERLOG
This section covers WTOR replies, IPL replies, service control, security displays, console metrics
and alert/OPERLOG workflows.
### Implementation evidence
### Area Source evidence
Master Console gibson/apps/master_console.py
Console events gibson/apps/master_console_events.py
### Operational model
The Master Console chapter is about operator evidence: WTORs, display commands, service state,
alerts and OPERLOG-style messages. It is the place to prove whether a system action reached the
console path and whether an operator response changed simulator progress.


<!-- page 120 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value is defensive visibility. Logons, high-port listeners, ICSF refreshes and startup
replies should be visible operational events, not silent background details.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### Master Console R nn,reply R 01,CLPA or R nn,reply gibson/apps/
master_console.py:397
Master Console D R,L / D R,R D R,L | D R,R gibson/apps/
master_console.py:407
### Master Console D SVC,L / DISPLAY SERVICES D SVC,L gibson/apps/
master_console.py:415
### Master Console D A,L D A,L gibson/apps/
master_console.py:420
### Master Console D
### CPU/MEMORY/DASD/IPLINFO
D CPU|D MEMORY|D DASD|D
### IPLINFO
gibson/apps/
master_console.py:372
Master Console D SECURITY,RARE|DAILY|
WEEKLY|MONTHLY
### D SECURITY,period gibson/apps/
master_console.py:383
Master Console D ICSF / F ICSF,... D ICSF | F ICSF,REFRESH,... gibson/apps/
master_console.py:397
Master Console S/START service S service | START service gibson/apps/
master_console.py:434
### Master Console P/STOP/PAUSE/RESUME
service
P service | STOP service |
PAUSE service | RESUME
service
gibson/apps/
master_console.py:441
### Section labs
### Lab 12: Review console metrics and security summary commands
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through review console metrics and security summary commands as a
practical evidence exercise, not as a command checklist. The concept being taught is operator
console, event stream and system-state evidence. From a tester’s point of view, the aim is to
produce a specific piece of evidence: console display output, WTOR state, event line or security


<!-- page 121 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
summary. From a defender’s point of view, the same evidence explains what should be controlled,
logged or challenged before the activity becomes normalised. By the end of the lab, you should be
able to say why each command was used and what changed in your understanding of the Gibson
environment.
### What the commands do
D CPU: shows CPU/system state in the simulator console model.
D MEMORY: shows memory/resource state in the console model.
D DASD: shows disk/storage state in the console model.
D SECURITY,DAILY: shows the simulator security summary view. Its value is tying technical actions
to security reporting.
D R,L: displays outstanding replies/WTOR-like prompts. It is the evidence source before replying to
IPL prompts.
### Starting state
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
D CPU
### D MEMORY
### D DASD
### D SECURITY,DAILY
D R,L
### What the output tells us
For `D CPU`, confirm the console response and any follow-on OPERLOG line. Console commands
matter because they show whether an operator-path action was accepted, rejected or left
outstanding.
### On a real z/OS system
### Real operators use MVS/JES commands, OPERLOG/SYSLOG, WTOR replies and automation
products. Gibson models the idea so students can practise interpreting operational evidence safely.
### Defensive takeaway
Console and OPERLOG visibility should be baselined. Logon events, high-port events and WTOR
replies are operational signals that defenders should explain.
### Troubleshooting
If a panel is empty, check polling/refresh, event generation, service health and whether the action
you performed is meant to emit an event.
### Instructor note
Teach review console metrics and security summary commands by asking students to explain the
purpose of each command before they run it and then identify the exact field, line or state change
that proves the point of the lab.


<!-- page 122 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### D CPU Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D MEMORY Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D DASD Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D SECURITY,DAILY Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### D R,L Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### Field Value
### Difficulty Intermediate
### Estimated time 40 minutes
### Objective Use Master Console display commands to review simulated IPL,
activity and security summaries.
Prerequisites Master Console access.


<!-- page 123 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Validation Source validated; command handlers identified
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 13: Respond to IPL WTOR
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through respond to ipl wtor as a practical evidence exercise, not as a
command checklist. The concept being taught is operator console, event stream and system-state
evidence. From a tester’s point of view, the aim is to produce a specific piece of evidence: console
display output, WTOR state, event line or security summary. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
R 01,CLPA: replies to WTOR 01 with CLPA, modelling an IPL/startup operator response. This
changes system progress and must be understood before using the console.
D R,R: reviews outstanding replies after the response so students can prove the prompt was
handled.
### Starting state
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
### R 01,CLPA
D R,R
### What the output tells us
For `R 01,CLPA`, confirm that the CLPA reply is accepted and the IPL WTOR sequence advances.
That is operator evidence: the system progressed because the expected reply was given.
### On a real z/OS system
### Real operators use MVS/JES commands, OPERLOG/SYSLOG, WTOR replies and automation
products. Gibson models the idea so students can practise interpreting operational evidence safely.


<!-- page 124 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
Console and OPERLOG visibility should be baselined. Logon events, high-port events and WTOR
replies are operational signals that defenders should explain.
### Troubleshooting
If a panel is empty, check polling/refresh, event generation, service health and whether the action
you performed is meant to emit an event.
### Instructor note
Teach respond to ipl wtor by asking students to explain the purpose of each command before they
run it and then identify the exact field, line or state change that proves the point of the lab.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### R 01,CLPA Responds to a
simulated write-to-
operator-with-reply
prompt.
### The reply number and
response text pair the
command with the
outstanding request.
### WTOR handling is
operator control-plane
work. Bad replies can
change IPL or system
behaviour.
### Evidence is the cleared
request or continuation
message.
### D R,R Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Understand the IPL WTOR reply workflow and use R 01,CLPA
safely.
Prerequisites Console state at IPL prompt.
Validation Source validated; depends on console lifecycle
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 125 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### WTOR IPL and MFA Reply Sequence
The Master Console IPL flow now needs to show the complete reply contract because this is where
students see operator control and MFA setup meet. In Gibson, the IPL sequence is deliberately
explicit: reply 01 supplies CLPA, reply 02 continues the operator/user prompt, reply 03 answers the
MFA enablement question, and reply 04 sets the four-digit PIN used with the current HHMM token.
### Reply Meaning in Gibson What to watch for Security relevance
### R 01,CLPA Responds to the CLPA
### IPL WTOR and allows
startup to progress
### Console confirmation
and next outstanding
reply
### Shows operator IPL
control and must be
logged
### R 02,U Responds to the
second startup WTOR
in the Gibson IPL
contract
### Next prompt appears
rather than dropping
to terminal
### Teaches that IPL is a
sequence, not a single
command
### R 03,Y Enables MFA PIN
initialization for this
IPL
### MFAPIN WTOR
appears
### MFA setup is an
operational security
decision
### R 04,1357 Defines the 4-digit
MFA PIN; use your
chosen PIN, not
necessarily 1357
### MFA token becomes
PIN+HHMM
### PIN should not be
echoed or logged;
token is time-bound
### Example startup reply flow
### R 01,CLPA
### R 02,U
### R 03,Y
### R 04,1357
After this sequence, an MFA-protected logon uses the configured four-digit PIN followed by the
current host HHMM value. For example, if the PIN is 1357 and the host time is 09:42, the training
token is 13570942. On a real system, MFA product behaviour is site-specific, but the operational
principle is the same: startup security choices should be controlled, logged and recoverable.
## Chapter 10. CICS and Banking
Lab
### This section covers CICS transaction handling, CEMT/CEDA/CECI utility transactions,
CICSPWN/PWNPROBE and GMVB/MCGM banking lab screens.


<!-- page 126 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Implementation evidence
### Area Source evidence
### CICS app gibson/apps/cics.py
Region model gibson/core/cics_region.py
### Operational model
This CICS chapter uses transactions and banking panels to show how application logic sits behind
3270 screens. The operational model is transaction-driven: a short transaction ID invokes an
application path with its own security context.
### Security relevance
The security value is host-side validation. Screen fields, hidden flags and transaction IDs are not
security controls unless the CICS program and external security manager enforce them.
### Commands and features in scope
### Subsystem Command Syntax Evidence
CICS HELP/? HELP gibson/apps/cics.py:133
CICS CEMT CEMT [INQUIRE|SET|
PERFORM...]
gibson/apps/cics.py:165
CICS CEDA CEDA [DEFINE PROGRAM|
TRANSACTION...]
gibson/apps/cics.py:168
CICS CECI CECI EXEC CICS READ|
WRITE|READQ|WRITEQ...
gibson/apps/cics.py:171
### CICS CEBR/CEDF/CESL/CMSG/
### CESN/CESF
transaction ID gibson/apps/cics.py:142
CICS CICSPWN/PWNPROBE CICSPWN | PWNPROBE gibson/apps/cics.py:189
CICS Banking Lab GMVB/MCGM GMVB [MENU|CARG|ORDE|
ORDR|ACCT|STMT|XFER|
APRV|HACK|ADMN]
gibson/apps/cics.py:191,950
### Section labs
### Lab 14: Explore CICS transaction help
### Command context
Start from: VTAM/front-door or CICS entry point
Commands run from: CICS blank screen or CICS transaction context
Do not run these from: TSO READY, ISPF or OMVS
Why context matters: CICS transaction IDs are application commands, not TSO commands.


<!-- page 127 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
In this lab we’ll work through explore cics transaction help as a practical evidence exercise, not as
a command checklist. The concept being taught is CICS transaction and business-application
exposure. From a tester’s point of view, the aim is to produce a specific piece of evidence:
transaction response, GMVB menu path or transaction help. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.
CEMT: opens or invokes the CICS master-terminal style control surface. In real CICS this is powerful
and heavily protected.
CEDA: relates to CICS resource definition administration. Its presence tells testers that management
transactions are part of the region exposure story.
CECI: is the CICS command-level interpreter. It is useful for learning but dangerous if exposed
because it can exercise CICS commands interactively.
GMVB MENU: enters the Gibson banking application menu, turning subsystem knowledge into a
business-application workflow.
### Starting state
Start from a terminal session that can reach the CICS/GMVB command path. If you are still at
READY, use the documented application path before issuing transaction commands.
### Lab steps
HELP
CEMT
CEDA
CECI
### GMVB MENU
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
CICS regions expose transaction IDs such as CEMT, CECI, CEDA, CESN and CESF. Security depends
on region settings and the external security manager checking transactions, commands and
resources.
### Defensive takeaway
Monitor access to system transactions, default-user activity and unusual business transaction
paths. CICS is often the business tier, not just a screen.


<!-- page 128 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
If a transaction fails, confirm APPLID/session state, transaction spelling and whether the terminal
is at a CICS prompt rather than READY.
### Instructor note
Frame the lab as application-tier testing. Students should understand that a four-character
transaction can be a business function or a system-control function.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### HELP Displays the available
command surface for
the current Gibson
context.
### A command name after
### HELP narrows the
output where
implemented.
### Help is safe
enumeration. It tells
you what the simulator
exposes without
changing state.
### Evidence is a command
list or help panel that
can be compared with
the command
appendix.
### CEMT Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### CEDA Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### CECI Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB MENU Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
### Evidence is a
transaction panel,
menu or action result.


<!-- page 129 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
controls are behaving
safely.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
### Objective Identify CICS commands, management transactions and
GMVB/MCGM lab entry points.
Prerequisites CICS session.
Validation Source validated; interactive CICS session required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 15: Run the GMVB banking navigation path
### Command context
Start from: VTAM/front-door or CICS entry point
Commands run from: CICS blank screen or CICS transaction context
Do not run these from: TSO READY, ISPF or OMVS
Why context matters: CICS transaction IDs are application commands, not TSO commands.
### Why this lab matters
In this lab we’ll work through run the gmvb banking navigation path as a practical evidence
exercise, not as a command checklist. The concept being taught is CICS transaction and business-
application exposure. From a tester’s point of view, the aim is to produce a specific piece of
evidence: transaction response, GMVB menu path or transaction help. From a defender’s point of
view, the same evidence explains what should be controlled, logged or challenged before the
activity becomes normalised. By the end of the lab, you should be able to say why each command
was used and what changed in your understanding of the Gibson environment.
### What the commands do
GMVB MENU: enters the Gibson banking application menu, turning subsystem knowledge into a
business-application workflow.
GMVB ACCT: navigates to account-oriented functionality in the training banking app.
GMVB STMT: shows statement-style data, useful for understanding data exposure paths.
GMVB XFER: models transfer functionality, where authorization and validation matter.
GMVB HACK: opens the intentionally insecure path used to teach application-control and 3270-style
testing concepts.
### Starting state


<!-- page 130 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Start from a terminal session that can reach the CICS/GMVB command path. If you are still at
READY, use the documented application path before issuing transaction commands.
### Lab steps
### GMVB MENU
### GMVB ACCT
### GMVB STMT
### GMVB XFER
### GMVB HACK
### What the output tells us
For `GMVB MENU`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
CICS regions expose transaction IDs such as CEMT, CECI, CEDA, CESN and CESF. Security depends
on region settings and the external security manager checking transactions, commands and
resources.
### Defensive takeaway
Monitor access to system transactions, default-user activity and unusual business transaction
paths. CICS is often the business tier, not just a screen.
### Troubleshooting
If a transaction fails, confirm APPLID/session state, transaction spelling and whether the terminal
is at a CICS prompt rather than READY.
### Instructor note
Frame the lab as application-tier testing. Students should understand that a four-character
transaction can be a business function or a system-control function.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### GMVB MENU Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.


<!-- page 131 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### GMVB ACCT Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB STMT Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB XFER Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### GMVB HACK Drives the simulated
### CICS transaction or
banking workflow.
### CEMT/CEDA/CECI are
powerful supplied-style
transactions; GMVB is
the Gibson banking lab
application path.
### CICS is the business
transaction tier. Testing
it shows whether
application access,
system transactions
and default-user
controls are behaving
safely.
### Evidence is a
transaction panel,
menu or action result.
### Field Value
### Difficulty Intermediate
### Estimated time 50 minutes
### Objective Navigate GMVB/MCGM screens, identify training functions and
document security observations.
Prerequisites CICS banking lab enabled.
Validation Source validated; interactive screen flow required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 132 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
## Chapter 11. Db2 and SQL
### Simulation
This section covers DSN, SPUFI, RUN SQL, Db2 status commands, job submission from Db2 shell
and SQL training commands.
### Implementation evidence
### Area Source evidence
### Db2 app gibson/apps/db2.py
Db2 simulator gibson/apps/db2_sim.py
Db2 service gibson/services/db2_server.py
### Operational model
This Db2 chapter treats SQL and catalog visibility as a data-access workflow. Queries, REST paths
and simulated database roles show how application and database layers meet.
### Security relevance
The security value is data exposure. Catalog access, DDF/DRDA exposure and application SQL paths
can reveal structure and privileges that shape the next assessment step.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### Db2 DSN Starts simulated DB2
command processing.
gibson/apps/tso.py
LEGACY_HELP
### Db2 SPUFI Runs the simulated DB2/SPUFI
interface.
gibson/apps/tso.py
LEGACY_HELP
### Db2 RUN SQL Runs SQL through the
simulated DB2 engine.
gibson/apps/tso.py
LEGACY_HELP
Db2 HELP HELP gibson/apps/db2.py:171
### Db2 SHOW DBS/SHOW
### USERS/DISPLAY GROUP/OMVS
### STATUS/ID UID
command gibson/apps/db2.py:173
Db2 RUN SQL <query> RUN SQL SELECT ... gibson/apps/db2.py:185
### Db2 SUBMIT JOB / STATUS JOBS /
### CANCEL JOB
SUBMIT JOB name | STATUS
JOBS | CANCEL JOB id
gibson/apps/db2.py:187
### Db2 SQL SELECT/INSERT/UPDATE/
### DELETE/GRANT/REVOKE/
SQL text gibson/apps/db2.py:88


<!-- page 133 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### DISPLAY
### Section labs
### Lab 16: Enumerate Db2 catalog tables
### Command context
Start from: Db2 command/query context or Gibson route documented by the lab
Commands run from: Db2 simulation panel/API/query context
Do not run these from: ISPF editor or CICS unless the lab explicitly enters that bridge
Why context matters: Database commands require a database context; TSO and REST/API
examples must be kept separate.
### Why this lab matters
In this lab we’ll work through enumerate db2 catalog tables as a practical evidence exercise, not as
a command checklist. The concept being taught is Db2 catalog and privilege visibility. From a
tester’s point of view, the aim is to produce a specific piece of evidence: catalog table rows,
authority rows or query response. From a defender’s point of view, the same evidence explains
what should be controlled, logged or challenged before the activity becomes normalised. By the
end of the lab, you should be able to say why each command was used and what changed in your
understanding of the Gibson environment.
### What the commands do
DSN: enters the Db2 command/processor concept in the simulator. It marks the transition from
general TSO to database access.
SPUFI: represents SQL Processor Using File Input style interactive SQL. It is the teaching bridge to
on-host Db2 query workflows.
RUN SQL SELECT * FROM SYSIBM.SYSTABLES: queries the catalog map of table objects. It is
reconnaissance because catalog visibility often reveals where sensitive data lives.
### Starting state
### Start from the Db2-capable command path. The simulator catalog must be available, and SQL
commands should be entered exactly as shown because the SQL parser is training-oriented.
### Lab steps
DSN
SPUFI
RUN SQL SELECT * FROM SYSIBM.SYSTABLES
### What the output tells us
For `DSN`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.


<!-- page 134 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### On a real z/OS system
Db2 catalog tables in DSNDB06 describe tables, columns, privileges, plans and packages. DDF/DRDA
and on-host tooling expose Db2 through different paths with RACF/SAF and Db2 authorities
shaping access.
### Defensive takeaway
Limit catalog visibility, review powerful authorities and monitor remote and on-host query paths.
Catalog enumeration can become a map of sensitive data.
### Troubleshooting
If SQL output is empty, check the simulated SQL syntax, catalog table name and whether the Db2
session/processor is active.
### Instructor note
Ask students which catalog row would drive their next test. The aim is to turn SQL output into a
target map, not merely to prove that SELECT works.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### DSN Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
### SPUFI Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
RUN SQL SELECT *
FROM
### SYSIBM.SYSTABLES
### Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
### Field Value
### Difficulty Beginner


<!-- page 135 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Estimated time 35 minutes
Objective Use DSN/SPUFI/RUN SQL to list simulator catalog entries.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 17: Exercise SQL privilege-oriented queries
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through exercise sql privilege-oriented queries as a practical evidence
exercise, not as a command checklist. The concept being taught is Db2 catalog and privilege
visibility. From a tester’s point of view, the aim is to produce a specific piece of evidence: catalog
table rows, authority rows or query response. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
RUN SQL SELECT * FROM SYSIBM.SYSUSERAUTH: queries system-level Db2 authority information,
showing who has powerful database privileges.
RUN SQL SELECT * FROM SYSIBM.SYSDBAUTH: queries database-level authority information,
shifting from global authority to object/database-specific privilege.
### Starting state
### Start from the Db2-capable command path. The simulator catalog must be available, and SQL
commands should be entered exactly as shown because the SQL parser is training-oriented.
### Lab steps
RUN SQL SELECT * FROM SYSIBM.SYSUSERAUTH
RUN SQL SELECT * FROM SYSIBM.SYSDBAUTH
### What the output tells us


<!-- page 136 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
For `RUN SQL SELECT * FROM SYSIBM.SYSUSERAUTH`, identify the exact returned line, return
code, panel state or dataset change that proves the lab objective. If that item is not present, pause
and troubleshoot the current command context before continuing.
### On a real z/OS system
Db2 catalog tables in DSNDB06 describe tables, columns, privileges, plans and packages. DDF/DRDA
and on-host tooling expose Db2 through different paths with RACF/SAF and Db2 authorities
shaping access.
### Defensive takeaway
Limit catalog visibility, review powerful authorities and monitor remote and on-host query paths.
Catalog enumeration can become a map of sensitive data.
### Troubleshooting
If SQL output is empty, check the simulated SQL syntax, catalog table name and whether the Db2
session/processor is active.
### Instructor note
Ask students which catalog row would drive their next test. The aim is to turn SQL output into a
target map, not merely to prove that SELECT works.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
RUN SQL SELECT *
FROM
### SYSIBM.SYSUSERAUTH
### Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
RUN SQL SELECT *
FROM
### SYSIBM.SYSDBAUTH
### Runs a simulated
Db2/SQL workflow.
### SPUFI/DSN move the
learner into a Db2-like
environment; RUN SQL
executes a selected
query in Gibson.
### Db2 catalogue
enumeration is useful
because metadata often
tells you where
sensitive data and
powerful authorities
live.
### Evidence is SQL output,
catalogue rows or an
error that proves the
boundary.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Run SQL commands against simulator tables and discuss


<!-- page 137 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
privilege/security relevance.
Prerequisites Db2 simulator available.
### Validation Runtime/static validated by SQL command family
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
## Chapter 12. OMVS/USS and
### Transfer Bridges
This section covers the USS shell command set, MVS/USS transfer commands, OGET, OPUT, OCOPY
and IND$FILE.
### Implementation evidence
### Area Source evidence
### OMVS shell gibson/apps/omvs.py
USS service gibson/services/uss_server.py
### Operational model
This USS chapter follows data as it moves between UNIX paths, MVS datasets and TSO command
bridges. The operational model is context-sensitive: cp belongs in OMVS, TSO commands need
tso/tsocmd or READY, and quoted dataset pathnames change the target world.
### Security relevance
The security value is movement. Scripts, JCL, configuration and evidence often cross between USS
and MVS datasets, and each copy operation should have a clear owner, permission check and audit
expectation.
### Commands and features in scope
### Subsystem Command Syntax Evidence
### OMVS/USS transfer OMVS Launches the OMVS shell. gibson/apps/tso.py
LEGACY_HELP
### OMVS/USS transfer OEDIT Edits a z/OS UNIX file using
ISPF File Edit.
gibson/apps/tso.py
LEGACY_HELP
### OMVS/USS transfer OGET Copies a z/OS UNIX file into an
MVS data set.
gibson/apps/tso.py
LEGACY_HELP
### OMVS/USS transfer OPUT Copies an MVS data set into a gibson/apps/tso.py


<!-- page 138 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
z/OS UNIX file. LEGACY_HELP
### OMVS/USS pwd cd ls cat echo touch
mkdir rm cp mv id whoami
hostname uname env export
extattr
shell command gibson/apps/omvs.py:397
OMVS/USS tso/tsocmd tso <cmd> gibson/apps/omvs.py:397
OMVS/USS oget/oput/ocopy oget dataset file | oput file
dataset | ocopy src dst
gibson/apps/omvs.py:397
### OMVS/USS su/sudo/python3/vi/ps/df/
clear/exit
command gibson/apps/omvs.py:397
### Section labs
### Lab 18: Review OMVS shell and identity commands
### Command context
Start from: TSO READY then OMVS, or an existing USS shell
Commands run from: OMVS/USS shell
Do not run these from: ISPF primary menu, ISPF editor, FTP or CICS
Why context matters: UNIX commands and MVS dataset pathname syntax are interpreted by USS,
not by ISPF panels.
### Why this lab matters
In this lab we’ll work through review omvs shell and identity commands as a practical evidence
exercise, not as a command checklist. The concept being taught is z/OS UNIX shell and USS/MVS
bridge. From a tester’s point of view, the aim is to produce a specific piece of evidence: current
directory, identity, hostname, copied file or dataset bridge output. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
OMVS: enters the z/OS UNIX style shell context. Commands after this point follow UNIX-style
assumptions rather than TSO command syntax.
pwd: prints the current USS working directory so the student knows where file operations will
happen.
id: shows the effective UNIX identity and group context.
whoami: prints the current user name, a simple but important identity check.
hostname: shows the host name, useful when correlating shell output with services and logs.
### Starting state


<!-- page 139 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Start from READY and enter OMVS when required. Keep track of whether you are typing UNIX-
style commands, TSO commands through the bridge, or dataset copy helpers.
### Lab steps
OMVS
pwd
id
whoami
hostname
### What the output tells us
For `OMVS`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
OMVS provides a z/OS UNIX shell. z/OS UNIX commands can work with HFS/zFS files and, through
supported syntax or utilities, move data to and from MVS datasets.
### Defensive takeaway
Monitor movement of scripts, JCL, data extracts and credentials between USS and MVS. Cross-
environment copy is operationally useful and attacker-useful.
### Troubleshooting
If a path fails, distinguish UNIX paths from MVS dataset names and confirm the object exists. Copy
failures are often syntax or permission problems.
### Instructor note
### Keep students aware of the boundary between USS paths and MVS dataset names. Many
mainframe file-handling mistakes begin at that boundary.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### OMVS Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
pwd Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
id Inspects the simulated pwd/id/whoami/ UNIX identity is a Evidence is the current


<!-- page 140 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
z/OS UNIX shell identity
or environment.
hostname report
location, UID/name and
host identity.
separate but connected
part of the mainframe
security model.
path, userid/UID or
host name.
whoami Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
hostname Inspects the simulated
z/OS UNIX shell identity
or environment.
pwd/id/whoami/
hostname report
location, UID/name and
host identity.
### UNIX identity is a
separate but connected
part of the mainframe
security model.
### Evidence is the current
path, userid/UID or
host name.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
Objective Launch OMVS and run safe identity/navigation commands.
Prerequisites User with OMVS segment such as IBMUSER.
Validation Source validated; interactive OMVS shell required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 19: Bridge OMVS and TSO commands
### Command context
Start from: TSO READY then OMVS, or an existing USS shell
Commands run from: OMVS/USS shell
Do not run these from: ISPF primary menu, ISPF editor, FTP or CICS
Why context matters: UNIX commands and MVS dataset pathname syntax are interpreted by USS,
not by ISPF panels.
### Why this lab matters
In this lab we’ll work through bridge omvs and tso commands as a practical evidence exercise, not
as a command checklist. The concept being taught is z/OS UNIX shell and USS/MVS bridge. From a
tester’s point of view, the aim is to produce a specific piece of evidence: current directory, identity,
hostname, copied file or dataset bridge output. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
tso LISTCAT: runs a TSO-style command from the OMVS bridge, proving the simulator can cross
command environments.


<!-- page 141 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
oget IBMUSER.JCL.LAB /tmp/lab.txt: copies a dataset-like object into USS space so students can see
host data moving into a UNIX path.
oput /tmp/lab.txt IBMUSER.JCL.LAB: copies a USS file back into dataset space. This is operationally
useful and security-sensitive.
### Starting state
### Start from READY and enter OMVS when required. Keep track of whether you are typing UNIX-
style commands, TSO commands through the bridge, or dataset copy helpers.
### Lab steps
tso LISTCAT
oget IBMUSER.JCL.LAB /tmp/lab.txt
oput /tmp/lab.txt IBMUSER.JCL.LAB
### What the output tells us
For `tso LISTCAT`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
OMVS provides a z/OS UNIX shell. z/OS UNIX commands can work with HFS/zFS files and, through
supported syntax or utilities, move data to and from MVS datasets.
### Defensive takeaway
Monitor movement of scripts, JCL, data extracts and credentials between USS and MVS. Cross-
environment copy is operationally useful and attacker-useful.
### Troubleshooting
If a path fails, distinguish UNIX paths from MVS dataset names and confirm the object exists. Copy
failures are often syntax or permission problems.
### Instructor note
### Keep students aware of the boundary between USS paths and MVS dataset names. Many
mainframe file-handling mistakes begin at that boundary.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
tso LISTCAT Lists cataloged data
sets known to the
### A high-level qualifier
may narrow results
### Catalog enumeration
tells you what objects
### Evidence is a list of
data set names and


<!-- page 142 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
simulator. where implemented. exist before you test
RACF or edit paths.
attributes.
oget
### IBMUSER.JCL.LAB
/tmp/lab.txt
### Moves data between
the simulated UNIX and
TSO/MVS-style worlds.
### Source and target
identify whether data
flows from USS to data
set or data set to USS.
### File movement is
operationally normal
but security-significant:
scripts, JCL, keys and
data often cross this
bridge.
### Evidence is a created
file/data set or
successful copy
message.
oput /tmp/lab.txt
### IBMUSER.JCL.LAB
### Moves data between
the simulated UNIX and
TSO/MVS-style worlds.
### Source and target
identify whether data
flows from USS to data
set or data set to USS.
### File movement is
operationally normal
but security-significant:
scripts, JCL, keys and
data often cross this
bridge.
### Evidence is a created
file/data set or
successful copy
message.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Use tso/tsocmd from the USS command set and review dataset
transfer patterns.
Prerequisites OMVS shell.
Validation Source validated; transfer requires interactive shell state
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Command What It Does Important Options Why It Matters Expected Evidence
cp Copy file. cp source target. Proves USS file copy. No output on success
cat Display target. cat target. Verifies content. Copied text
### Command What It Does Important Options Why It Matters Expected Evidence
cp Dataset to USS. cp "//'DSN'" file. Bridges MVS to USS. No output on success
cat Display USS copy. cat file. Verifies moved content. Dataset text appears
### Command What It Does Important Options Why It Matters Expected Evidence
cp USS to dataset. cp file "//'DSN'". Writes into MVS. No output on success
cat Read target dataset. cat "//'DSN'". Verifies MVS target. Copied text appears
### Command What It Does Important Options Why It Matters Expected Evidence
cp Member to USS. cp "//'PDS(MEM)'" file. Extracts member. No output on success
cp USS to member. cp file
"//'PDS(NEWMEM)'".
### Creates/replaces
member.
### No output on success
cat Verify content. cat file or cat //
operand.
### Checks both sides. Expected text
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.


<!-- page 143 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If the member is not found, check the containing PDS and member spelling.
### Troubleshooting
Monitor updates to executable libraries and member additions in JCL/REXX/CLIST paths.
### Defensive takeaway
PDS/PDSE members are how z/OS stores many operational artefacts. Member write access can be
an execution-path risk.
### On a real z/OS system
The evidence is the same content moving across the USS/MVS boundary at member level.
### What the output tells us
1. Use or create IBMUSER.PDS.CODE.
2. Run cp "//'IBMUSER.PDS.CODE(TIME)'" time.rexx.
3. Create new_member.txt.
4. Run cp new_member.txt "//'IBMUSER.PDS.CODE(NEWONE)'".
5. Verify the new member.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll practise member-level movement, which is the useful case for JCL, REXX, CLIST and
source libraries.
### Why this lab matters
Start from OMVS/USS shell. Put the member in parentheses inside the quoted dataset operand.
### Command context
### Lab 18D: Copy a PDS member between USS and MVS
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup


<!-- page 144 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
If target verification fails, check quotes and exact dataset name.
### Troubleshooting
Review who can write to datasets from multiple access paths: ISPF, OMVS, FTP and batch.
### Defensive takeaway
Real z/OS checks dataset authority and attributes when writing MVS data from USS.
### On a real z/OS system
A successful copy means UNIX-side content became an MVS dataset object. That is useful and
security-sensitive.
### What the output tells us
1. Create from_uss.txt.
2. Run cp from_uss.txt "//'IBMUSER.TEST.CATCOPY'".
3. Run cat "//'IBMUSER.TEST.CATCOPY'".
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll write a USS file back to MVS. This is the direction that becomes sensitive when the
target is a JCL, REXX or configuration dataset.
### Why this lab matters
Start from OMVS/USS shell. Source is USS; target is a quoted // dataset operand.
### Command context
### Lab 18C: Copy a USS file into an MVS dataset
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
Quote the dataset operand and verify the HLQ/member spelling.


<!-- page 145 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Troubleshooting
Dataset reads followed by USS file creation can be legitimate or suspicious staging. Defenders need
context and audit evidence.
### Defensive takeaway
IBM documents z/OS shell copying to and from MVS datasets. RACF DATASET profiles and dataset
attributes govern real access.
### On a real z/OS system
The evidence is MVS dataset text now visible as a USS file. Failure usually means name or access
issue.
### What the output tells us
1. Confirm a safe training dataset exists.
2. Run cp "//'IBMUSER.TEST.DATA'" sample_from_ds.txt.
3. Run cat sample_from_ds.txt.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll pull MVS content into USS. This is how dataset evidence becomes searchable and
portable with UNIX-style tools.
### Why this lab matters
Start from OMVS/USS shell. Use a quoted //'HLQ.DATA' operand.
### Command context
### Lab 18B: Copy an MVS dataset into USS
Source validated against Gibson code; runtime validated where covered by tests/smoke checks.
### Validation status
Remove scratch files or members created in this lab unless a later lab explicitly uses them.
### Cleanup
### Ask students to explain the command context before they run anything. The most common
mainframe mistake is running a valid command in the wrong environment.
### Instructor note
Use pwd and ls -l if cp reports unsupported source.
### Troubleshooting
Monitor unusual file staging in USS home, tmp or executable directories.


<!-- page 146 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
On real z/OS UNIX, cp behaves like a UNIX command for UNIX files, subject to permissions and
filesystem controls.
### On a real z/OS system
No output from cp is normal. The proof is the target file content.
### What the output tells us
1. Create source.txt in OMVS.
2. Run cp source.txt target.txt.
3. Run cat target.txt.
### Lab steps
Use a scratch dataset, member or USS file created for training. Do not use production-style names
except where Gibson has seeded safe training objects.
### Starting state
### What the commands do
In this lab we'll prove the ordinary UNIX side of cp first. That gives students a clean baseline before
adding MVS dataset operands.
### Why this lab matters
Start from OMVS/USS shell. Run cp at the USS prompt only.
### Command context
### Lab 18A: Copy a USS file to another USS file
## Chapter 13. FTP, TCP/IP and
### Network Enumeration
### This section covers NETSTAT, PING, TRACERTE, FTP client behaviour and service discovery
boundaries.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv


<!-- page 147 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Operational model
This network chapter starts with listeners and connections, then moves to FTP and enumeration
tools. The operational model is service-facing: open ports identify where a learner can connect and
which subsystem answers.
### Security relevance
The security value is attack-surface mapping. A defender should be able to explain why each
listener exists, who can reach it and what telemetry a connection creates.
### Commands and features in scope
### Subsystem Command Syntax Evidence
TCP/IP NETSTAT NETSTAT HOME|CONN|ALL|
DEVLINKS|ROUTE|ARP|
PORTLIST|TELNET|FTP.
gibson/apps/tso.py
LEGACY_HELP
### TCP/IP PING PING host - simulated z/OS
TCP/IP ping.
gibson/apps/tso.py
LEGACY_HELP
### TCP/IP TRACERTE TRACERTE host - simulated
z/OS traceroute.
gibson/apps/tso.py
LEGACY_HELP
FTP client FTP FTP host [port] - enters the
z/OS style FTP client
subcommand environment.
gibson/apps/tso.py
LEGACY_HELP
### Section labs
### Lab 20: Enumerate simulator TCP/IP listeners
### Command context
Start from: TSO READY for NETSTAT/PING or Linux host shell for nmap-sim/nc checks
Commands run from: The context stated beside each command
Do not run these from: ISPF editor or CICS
Why context matters: Network commands can be host-side tools or simulated TSO commands; the
manual must keep them separate.
### Why this lab matters
In this lab we’ll use Gibson to practise a first-pass TCP/IP listener review. On a real z/OS system,
open ports tell you which subsystems are reachable: TN3270 for terminal access, FTP for file and
JES workflows, DRDA for Db2, CICS web interfaces, REST services, NJE and sometimes site-specific
high ports. From a tester’s point of view, this is where the attack surface starts to become concrete.
From a defender’s point of view, it is also where you should be able to explain why each listener
exists, who can reach it, and what evidence a connection creates.
### What the commands do


<!-- page 148 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
NETSTAT CONN: shows connection/session-oriented network state. It answers who is connected
rather than merely what is listening.
PING 127.0.0.1: checks basic IP reachability to the local host. In this simulator it proves the network
command path before deeper enumeration.
TRACERTE 127.0.0.1: shows route/path behaviour. Against localhost it is simple by design; the point
is command-path validation.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
### NETSTAT PORTLIST
### NETSTAT CONN
### PING 127.0.0.1
### TRACERTE 127.0.0.1
### What the output tells us
At this point, you should have evidence of the simulated listeners, any current connections and
whether the basic TCP/IP command path is alive. The useful part is not simply that the commands
ran. The useful part is that you can now explain which services Gibson is presenting to the learner
and which ones would matter during a real assessment.
### On a real z/OS system
On a real z/OS system, this type of review would normally be paired with TCP/IP profile review,
SERVAUTH/NETACCESS checks, firewall scope, SMF records, daemon logs and subsystem-specific
evidence. An unexpected listener is not automatically a vulnerability, but it is always a question:
who started it, who can reach it, what data crosses it, and how is it monitored?
### Defensive takeaway
Defenders should be able to baseline expected listeners and alert on changes, especially high ports
or services that appear outside an approved change window. In Gibson, this connects directly to
the Master Console and OPERLOG/event-stream labs, where logon and high-port activity become
visible training evidence.
### Troubleshooting
If a listener is missing, confirm the service was started and that the selected runtime profile
enables it.
### Instructor note
Ask students to translate every listening port into a subsystem hypothesis and a defender question.
This keeps scanning from becoming a screenshot exercise.
### Cleanup


<!-- page 149 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### NETSTAT PORTLIST Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### NETSTAT CONN Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### PING 127.0.0.1 Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### TRACERTE 127.0.0.1 Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### Field Value
### Difficulty Beginner
### Estimated time 30 minutes
Objective Use NETSTAT, PING and TRACERTE to build a network map.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 21: Enter z/OS-style FTP client environment
### Command context
Start from: FTP session after connecting from host or Gibson FTP client context
Commands run from: ftp> prompt; JES review happens after leaving FTP or in SDSF


<!-- page 150 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Do not run these from: TSO READY unless invoking FTP itself
Why context matters: SITE, PUT, STOR and GET are FTP subcommands; SDSF is a separate review
context.
### Why this lab matters
In this lab we’ll work through enter z/os-style ftp client environment as a practical evidence
exercise, not as a command checklist. The concept being taught is host file transfer and JES-style
workflows. From a tester’s point of view, the aim is to produce a specific piece of evidence: FTP
banner, connection state or transfer prompt. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
FTP 127.0.0.1 2111: starts the z/OS-style FTP client workflow against the simulator FTP listener.
### Starting state
Start with the FTP listener enabled and Gibson running. Confirm port 2111 is listening before
opening the client path.
### Lab steps
### FTP 127.0.0.1 2111
### What the output tells us
For `FTP 127.0.0.1 2111`, identify the exact returned line, return code, panel state or dataset change
that proves the lab objective. If that item is not present, pause and troubleshoot the current
command context before continuing.
### On a real z/OS system
z/OS FTP can transfer USS files and MVS datasets and, where configured, can interact with JES.
IND$FILE-style transfers are common in 3270 environments.
### Defensive takeaway
Monitor file transfers, JES mode usage and movement of JCL or data extracts. FTP is often a bridge
between workstation and host.
### Troubleshooting
If FTP fails, check port, credentials/session state, filetype mode and whether the simulator service is
enabled.
### Instructor note
Teach enter z/os-style ftp client environment by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup


<!-- page 151 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### FTP 127.0.0.1 2111 Opens the simulated
### FTP client/server
workflow.
### The host and port select
the target listener.
### FTP is historically
common on z/OS and
matters because it can
move files or submit
### JES jobs depending on
configuration.
### Evidence is an FTP
banner, login prompt
or session response.
### Field Value
### Difficulty Intermediate
### Estimated time 35 minutes
### Objective Identify FTP client syntax and discuss FTP/JES/SQL mode
boundaries.
Prerequisites FTP service configured.
Validation Source validated; interactive FTP service required
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
## Chapter 14. REST API,
### Dashboard, and Web Interfaces
This section covers REST gateway routes, banking routes, dashboard state endpoints and optional
browser/web terminal considerations.
### Implementation evidence
### Area Source evidence
REST gateway gibson/services/rest_gateway.py
### Dashboard gibson/services/dashboard.py
### Operational model
This API chapter maps browser and curl activity to routes, state and training workflows. The
operational model is request/response: route, method, parameters, authentication and side effects
all matter.


<!-- page 152 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Security relevance
The security value is automation control. APIs make training repeatable, but a real environment
would require authentication, authorisation, input validation and useful audit records.
### Commands and features in scope
### Method Route Handler Source
### GET / index gibson/services/
rest_gateway.py:599
GET /bank/session bank_session gibson/services/
rest_gateway.py:605
### POST /query query gibson/services/
rest_gateway.py:611
POST /query-form query_form gibson/services/
rest_gateway.py:616
POST /bank/login bank_login gibson/services/
rest_gateway.py:623
GET /bank/account bank_account gibson/services/
rest_gateway.py:635
POST /bank/transfer bank_transfer gibson/services/
rest_gateway.py:647
POST /bank/statement bank_statement gibson/services/
rest_gateway.py:659
POST /bank/terminal bank_terminal gibson/services/
rest_gateway.py:670
POST /bank/hack3270 bank_hack gibson/services/
rest_gateway.py:678
POST /bank/passticket/generate bank_passticket_generate gibson/services/
rest_gateway.py:685
POST /bank/passticket/use bank_passticket_use gibson/services/
rest_gateway.py:692
POST /indfile/upload indfile_upload gibson/services/
rest_gateway.py:699
GET /indfile/download indfile_download gibson/services/
rest_gateway.py:708
POST /bank/passticket/scenario bank_passticket_scenario gibson/services/
rest_gateway.py:720
GET / _DashboardHandler.do_GET gibson/services/dashboard.py
GET /api/state _DashboardHandler._snapsho
t
gibson/services/dashboard.py
POST /poweron /quit /poweroff _DashboardHandler.do_POST gibson/services/dashboard.py


<!-- page 153 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Section labs
### Lab 22: Map API routes to training workflows
### Command context
Start from: Host-side REST client or browser
Commands run from: curl/API client or documented web/API panel
Do not run these from: TSO READY, ISPF, OMVS or CICS
Why context matters: REST calls exercise Gibson routes; they are not 3270 commands.
### Why this lab matters
In this lab we’ll work through map api routes to training workflows as a practical evidence
exercise, not as a command checklist. The concept being taught is REST endpoints and automation
surface. From a tester’s point of view, the aim is to produce a specific piece of evidence: HTTP
method, route, status code and response body. From a defender’s point of view, the same evidence
explains what should be controlled, logged or challenged before the activity becomes normalised.
By the end of the lab, you should be able to say why each command was used and what changed in
your understanding of the Gibson environment.
### What the commands do
GET /api/state: requests simulator state from a REST endpoint. It is read-oriented and useful for
confirming dashboard/API agreement.
POST /query: submits a query-style API request. It teaches parameterised automation rather than
screen-driven use.
POST /bank/login: tests the banking login path through the API surface.
### Starting state
Start with the dashboard/API service enabled. Confirm the web endpoint responds before testing
individual routes.
### Lab steps
### GET /api/state
### POST /query
### POST /bank/login
### What the output tells us
For `GET /api/state`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
Real z/OS APIs may be provided through z/OS Connect, CICS web services, Db2 REST services or site
middleware. API controls sit alongside RACF/SAF and network controls.
### Defensive takeaway


<!-- page 154 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Monitor endpoint use, authentication failures, parameter abuse and unexpected automation
against training or production routes.
### Troubleshooting
If an endpoint returns 404 or 500, confirm method, path, authentication and request body.
### Instructor note
Teach map api routes to training workflows by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### GET /api/state Exercises a Gibson
### REST or dashboard
endpoint.
GET retrieves state;
### POST changes state or
submits a query
depending on the
endpoint.
### APIs are the
automation surface.
### They can expose
mainframe functions to
modern tooling and to
attackers.
### Evidence is an HTTP
response, JSON payload
or state change.
### POST /query Exercises a Gibson
### REST or dashboard
endpoint.
GET retrieves state;
### POST changes state or
submits a query
depending on the
endpoint.
### APIs are the
automation surface.
### They can expose
mainframe functions to
modern tooling and to
attackers.
### Evidence is an HTTP
response, JSON payload
or state change.
### POST /bank/login Exercises a Gibson
### REST or dashboard
endpoint.
GET retrieves state;
### POST changes state or
submits a query
depending on the
endpoint.
### APIs are the
automation surface.
### They can expose
mainframe functions to
modern tooling and to
attackers.
### Evidence is an HTTP
response, JSON payload
or state change.
### Field Value
### Difficulty Beginner
### Estimated time 35 minutes
### Objective Use the route matrix to identify banking, PassTicket, query and
IND$FILE endpoints.
Prerequisites API route matrix.
### Validation Source validated route matrix
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 155 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Lab 23: Exercise PassTicket API and TSO status comparison
### Command context
Start from: Host-side REST client or browser
Commands run from: curl/API client or documented web/API panel
Do not run these from: TSO READY, ISPF, OMVS or CICS
Why context matters: REST calls exercise Gibson routes; they are not 3270 commands.
### Why this lab matters
In this lab we’ll work through exercise passticket api and tso status comparison as a practical
evidence exercise, not as a command checklist. The concept being taught is application
authentication token workflow. From a tester’s point of view, the aim is to produce a specific piece
of evidence: token status, generated ticket or use/replay result. From a defender’s point of view, the
same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
PTKTSTAT: shows PassTicket-related simulator state from the TSO/command side.
POST /bank/passticket/generate: generates a simulated PassTicket through the banking API path.
POST /bank/passticket/use: attempts to use the generated simulated PassTicket, proving whether
the token path works and whether replay/state controls are visible.
### Starting state
Start with the banking API and PassTicket simulation enabled. Use one generated ticket at a time so
replay and use-state are clear.
### Lab steps
### PTKTSTAT
### POST /bank/passticket/generate
### POST /bank/passticket/use
### What the output tells us
For `PTKTSTAT`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
RACF PassTickets use secured application keys and PTKTDATA profiles to create time-limited
credentials for applications. Misconfiguration can create replay or scope problems.
### Defensive takeaway


<!-- page 156 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Review PTKTDATA definitions, key management, application names, replay protection and logs
around ticket generation/use.
### Troubleshooting
If generation fails, check application name, user state, server mode and whether the API route
expects JSON or form data.
### Instructor note
Teach exercise passticket api and tso status comparison by asking students to explain the purpose
of each command before they run it and then identify the exact field, line or state change that
proves the point of the lab.
### Cleanup
This lab changes simulator state. In a clean teaching run, reset Gibson to the chapter baseline after
the demonstration or document the created user/profile/job/ticket/file before moving on. If your
build includes delete/remove commands for the created objects, use those; otherwise use the
simulator reset workflow.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### PTKTSTAT Inspects or exercises
simulated PassTicket
behaviour.
### APPL() or endpoint
parameters select the
application and ticket
operation where
implemented.
### PassTickets remove
reusable password
transmission, but weak
setup or replay
windows become
security findings.
### Evidence is a
generated, accepted,
rejected or listed ticket
state.
POST
/bank/passticket/genera
te
### Exercises a Gibson
### REST or dashboard
endpoint.
GET retrieves state;
### POST changes state or
submits a query
depending on the
endpoint.
### APIs are the
automation surface.
### They can expose
mainframe functions to
modern tooling and to
attackers.
### Evidence is an HTTP
response, JSON payload
or state change.
POST
/bank/passticket/use
### Exercises a Gibson
### REST or dashboard
endpoint.
GET retrieves state;
### POST changes state or
submits a query
depending on the
endpoint.
### APIs are the
automation surface.
### They can expose
mainframe functions to
modern tooling and to
attackers.
### Evidence is an HTTP
response, JSON payload
or state change.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
Objective Compare PTKTSTAT with REST PassTicket routes.
Prerequisites REST gateway route matrix and TSO session.
### Validation Runtime/static plus source route validation
### Users IBMUSER unless stated otherwise


<!-- page 157 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
## Chapter 15. Security Training
### Playbooks
This section combines attacker and defender workflows into coherent learning paths:
enumeration, privilege analysis, dataset exposure, CICS/Db2/FTP abuse, alert review and reporting.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This playbook chapter chains individual commands into assessment workflows. The operational
model is evidence-driven: enumerate, confirm, interpret, then decide whether the next step is
testing, reporting or defensive review.
### Security relevance
The security value is judgement. Students learn to turn command output into findings; defenders
learn which control should have prevented, detected or explained the activity.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.


<!-- page 158 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Section labs
Security Tooling: ZREXX, ZSEC,
### ENUM and SEARCHRX
This section turns the simulator into a security-analysis classroom. The goal is not to pretend that
Gibson is IBM zSecure or that every external REXX audit tool is built in. The goal is to show
students how to use supported training commands, recognise the difference between simulator
reports and real z/OS evidence, and turn enumeration output into defensible findings.
The workflow is deliberately simple: run the report from the right command context, identify the
high-value control point, validate the result with a more specific command where Gibson supports
it, and then explain what a real z/OS defender would review. This is the practical bridge between
command output and mainframe security judgement.
### ZREXX Security Automation
ZREXX is treated in this manual as security-automation material for TSO/E REXX. The uploaded
ZREXX material describes a hardened real z/OS REXX audit package, but the current Gibson source
tree does not contain a runnable ZREXX command handler or complete executable ZREXX source.
That distinction matters. In Gibson, REXX automation is taught through the Code Interpreters
section and through supported security-search commands such as SEARCHRX and ENUM. ZREXX
remains a conceptual and future-integration workflow unless the actual exec is supplied and
staged into a dataset or source member.
### Comman
d / Option
### Syntax Run
From
### What It
Does
### Output
To
### Review
### Security
### Question
### Answere
d
### Real z/OS
### Comparis
on
Lab
ZREXX
audit exec
EX
'HLQ.ZRE
XX' or
site-
specific
invocatio
n
### Conceptu
al / future
TSO
### READY or
ISPF
option 6
Would
run a
security-
audit
### REXX exec
when
executabl
e source is
available
### Finding
report
such as
IBMUSER.
### ZREXX.OU
T
Can
automatio
n
summaris
e
### RACF/secu
rity
weakness
es?
TSO/E
REXX
execs can
issue host
command
s and
produce
audit
reports if
authorise
d
### ZR-1/ZR-2
conceptua
l
### SEARCHR
X
### SEARCHR
X
TSO
### READY or
Runs
Gibson’s
### WARNING
, dataset,
Which
RACF
### A real
security
SR-1


<!-- page 159 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
ISPF
option 6
supported
security-
search
workflow
### BPX and
### SURROGA
### T sections
search
leads
deserve
follow-
up?
### REXX exec
would
wrap
RACF
### SEARCH/R
### LIST/LIST
### DSD and
parse
output
### ZSEC and zSecure-Style Security Analysis
ZSEC is Gibson’s zSecure-style training interface. It is not IBM Security zSecure, and the manual
must say that clearly. The useful part for students is the reporting model: a single command can
summarise privileged users, UID(0) users, SURROGAT profiles, SERVAUTH controls, ICSF posture,
SETROPTS policy, CICS/Db2 exposure and event/alert evidence. On a real estate, those questions
would be answered through RACF, SMF, zSecure Admin/Audit, site policy and operational
evidence.
ZSEC
### Command /
### Option
### Syntax Run From Report
### Produced
### What To
### Look For
### Security
### Meaning
Lab
### Main menu ZSEC or
### ZSECURE
### TSO READY
or ISPF
option 6
### Training
topic list
### Available
report
categories
### Shows what
posture
reports can
be
requested
ZS-1
### Privilege
review
ZSEC
### PRIVILEGE
### TSO READY
or ISPF
option 6
### Privileged/
audit
attributes
### SPECIAL,
### OPERATION
### S, AUDITOR,
### ROAUDIT,
### UAUDIT
### Identifies
### IDs that
deserve
strict
ownership
and
monitoring
ZS-1
### UID(0)
review
### ZSEC UID0 TSO READY
or ISPF
option 6
OMVS
### UID(0) users
### UID 0 and
HOME
fields
### Finds UNIX
superuser-
equivalent
IDs
ZS-1
### SURROGAT
review
ZSEC
### SURROGAT
### TSO READY
or ISPF
option 6
### SURROGAT
profiles
userid.SUB
MIT
resources
### Highlights
batch
submit-as
risk
ZS-2
### ICSF review ZSEC ICSF TSO READY ICSF key CKDS/ Connects ZS-2


<!-- page 160 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
or ISPF
option 6
dataset
posture
### PKDS/TKDS
and CSF
class
references
cryptograp
hic services
to RACF/SAF
protection
### Event/alert
review
ZSEC
### EVENTS /
### ZSEC SMF /
ZSEC
### ALERTS
### TSO READY
or ISPF
option 6
### Security
events and
alerts
User,
command/a
ction,
result,
severity
### Shows the
defensive
evidence
trail
ZS-1
### Report Category What It Checks Relevant RACF /
z/OS Area
### Evidence
### Produced
### Defensive
### Follow-Up
### Privilege Privileged and
audit attributes
### RACF user
profiles
### User IDs with
sensitive
attributes
### Review
ownership, need
and monitoring
### SURROGAT Submit-as and
surrogate profiles
### SURROGAT class /
### JES submission
### Profiles and
submit targets
Review USER=
usage and
permitted
submitters
### APF APF history and
library risk
APF,
### LINKLIST/LPA,
dataset profiles
### APF library
indicators
### Review write
access and
change controls
### ICSF Key dataset and
service posture
ICSF,
### CKDS/PKDS/TKDS,
### CSFKEYS/CSFSER
V
### Protected
dataset/service
indicators
### Alert on
refresh/change
and restrict key
dataset access
### Events/Alerts Security
telemetry
### SMF-like events,
### OPERLOG, alerts
### Recent events
and exceptions
### Triage, correlate
and report
### ENUM Mainframe Security Enumeration
ENUM gives students a compact way to run security enumeration checks before they drill down
with RACF commands. In Gibson, ENUM is implemented as a simulated security tool path that can
return focused views such as SEC, APF and ALL. The right teaching point is not that ENUM replaces
RACF commands. It gives audit leads: APF libraries to inspect, SURROGAT rules to verify,
WARNING profiles to test, and service controls to explain.
ENUM
### Mode /
### Option
### Syntax Run From What It
### Enumerate
s
### What To
### Look For
### Security
### Meaning
Lab
### SEC ENUM SEC TSO READY
or ISPF
option 6
### General
security
posture
### Warnings,
privileged
surfaces,
### A quick
first-pass
security
EN-1


<!-- page 161 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
leads policy hints triage
### APF ENUM APF TSO READY
or ISPF
option 6
### APF-related
exposure
### Authorized
library
references
and risky
update
paths
### APF write
access can
become
privileged
code
execution
risk
EN-2
### ALL ENUM ALL TSO READY
or ISPF
option 6
All
supported
sections
### Summary of
### SEC/APF/SV
### C/WHO/PAT
### H-style
results
### Prioritises
the next
manual
checks
EN-3
### SEARCHRX SEARCHRX TSO READY
or ISPF
option 6
### Prebuilt
security
search
report
### WARNING,
### BPX and
### SURROGAT
sections
### Turns RACF
search
output into
audit leads
SR-1
### Lab ZS-1: Run a ZSEC zSecure-style RACF report
### Command context
Start from: TSO READY.
If you are inside ISPF: use =6 first, then enter the ZSEC command.
Commands run from: TSO READY or ISPF option 6.
Do not run these from: ISPF 3.4, the ISPF editor, CICS, FTP or OMVS.
### Why this lab matters
In this lab we’ll use ZSEC as a training representation of a zSecure-style security review. The aim is
to move beyond individual commands and ask broader control questions: which users are
privileged, which IDs have UID(0), what events exist, and which posture areas deserve deeper
review.
### What the commands do
ZSEC opens the simulated security-analysis menu. ZSEC PRIVILEGE focuses on users with sensitive
attributes. ZSEC UID0 checks OMVS superuser-equivalent IDs. ZSEC SETROPTS brings
password/class policy into the same discussion. ZSEC EVENTS or ZSEC ALERTS connects the report
view to the defensive event stream.
### Starting state
Use a seeded Gibson training system with TSO READY available. If no security events exist yet, run
a harmless prior lab such as LISTUSER or NETSTAT first so the event views have context.
### Lab steps


<!-- page 162 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
ZSEC
### ZSEC PRIVILEGE
### ZSEC UID0
### ZSEC SETROPTS
### ZSEC EVENTS
### ZSEC ALERTS
### What the output tells us
The evidence is the set of report headings and the rows under each heading. A privileged-user row
changes the question from “does the command work?” to “who owns this authority and why?” A
UID(0) row points to UNIX superuser risk. An event row shows that Gibson can tie actions to
defensive review.
### On a real z/OS system
On a real z/OS system, IBM Security zSecure and RACF reporting are used to analyse users, groups,
profiles, access and audit data. Gibson does not read a live RACF database; it teaches the reporting
questions a student should ask before touching production evidence.
### Defensive takeaway
Defenders should treat privileged attribute reports, UID(0) reports and alert/event reports as triage
inputs. The follow-up is ownership review, access justification, SMF/RACF evidence review and
change-control validation.
### Troubleshooting
If ZSEC returns the menu instead of a report, check the topic spelling. If EVENT or ALERT views are
empty, generate a safe event first or explain that the absence of rows is also a finding about current
simulator state.
### Instructor note
Ask students to pick one ZSEC report row and turn it into a follow-up question. The common
mistake is to copy the whole report without deciding which line actually changes risk.
### Cleanup
Read-only in Gibson. Leave generated events if the next lab uses them for reporting; otherwise
reset simulator state between classes.
### Validation status
### Source validated from Gibson TSO ZSEC handlers and v26 zSecure-style functions. Runtime
validation is recommended in the class profile used for delivery.
### Lab ZS-2: Review APF, SURROGAT and ICSF posture with ZSEC
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: ZSEC topic commands.
Do not run these from: CICS, FTP or the ISPF editor.


<!-- page 163 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Why this lab matters
This lab targets three high-value control points: APF-authorized code, SURROGAT submit-as
authority and ICSF key-service protection. These are different controls, but they share one security
lesson: a short report can reveal where a tester should spend the next hour validating authority
and evidence.
### What the commands do
ZSEC APF reviews APF-related history or risk where Gibson has state. ZSEC SURROGAT lists submit-
as style profiles. ZSEC ICSF summarises simulated CKDS/PKDS/TKDS protection and CSF class
review points.
### Starting state
Use the standard seeded state. The ICSF section is most useful after reading the ICSF Control-Plane
Protection and Alerting section.
### Lab steps
### ZSEC APF
### ZSEC SURROGAT
### ZSEC ICSF
### What the output tells us
For APF, look for authorized library references that would become serious if writable. For
SURROGAT, look for profile names ending in .SUBMIT. For ICSF, look for protected key dataset lines
and CSFKEYS/CSFSERV review prompts. Each line tells you what to validate next with more specific
commands or lab evidence.
### On a real z/OS system
On real z/OS, APF libraries define trusted code paths, SURROGAT controls submit-as authority and
ICSF protects cryptographic services and key datasets. These areas are usually protected by
RACF/SAF profiles, dataset rules, operational procedures and audit records.
### Defensive takeaway
### Defenders should baseline APF libraries, review SURROGAT access, protect CKDS/PKDS/TKDS
datasets and alert on refresh or control-plane changes. A report is not the control; it is the evidence
that tells you which control to check.
### Troubleshooting
If APF output is empty, check whether the APF lab/state has been exercised. If SURROGAT has no
rows, run the SURROGAT discovery lab or explain that no seeded profile is present. If ICSF output is
generic, cross-reference the ICSF command table.
### Instructor note
Teach this as prioritisation. Students should not treat APF, SURROGAT and ICSF as one topic; they
should explain why each one can change the security boundary in a different way.
### Cleanup
Read-only in Gibson. Do not reset events if the next reporting lab will use them.


<!-- page 164 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Validation status
Source validated from Gibson ZSEC and ICSF handlers. APF depth depends on the simulator state
available in the selected package.
### Lab EN-1: Run ENUM SEC for first-pass security triage
### Command context
Start from: TSO READY.
If you are inside ISPF: use =6 first.
Commands run from: TSO READY or ISPF option 6.
### Why this lab matters
ENUM SEC is a fast security-triage lab. The purpose is to teach the student how an audit helper can
collect leads without replacing interpretation. The output should tell you where to look next, not
what to blindly report.
### What the commands do
ENUM SEC asks Gibson to run the security-oriented enumeration mode. It is expected to produce a
compact view of relevant controls or weakness candidates. The follow-up is to validate each lead
with the specific RACF, APF, ICSF or dataset command that owns the evidence.
### Starting state
Use a TSO READY session with the security training state loaded.
### Lab steps
### ENUM SEC
### What the output tells us
The evidence is the SEC-mode section heading and the weakness candidates beneath it. A useful
result names a control point: a profile, dataset, attribute, APF surface or policy item. The student
should write down the top two items and identify the validating command.
### On a real z/OS system
On a real z/OS system, local REXX or CLIST audit helpers often wrap RACF, catalog, dataset and
system commands to speed up review. The helper is only as good as the commands it runs and the
authority of the user running it.
### Defensive takeaway
Defenders should know which local audit tools exist, who can run them and where their output
goes. Audit automation can expose sensitive security metadata, so reports need the same handling
as assessment evidence.
### Troubleshooting


<!-- page 165 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
If ENUM SEC is not recognised, confirm you are at READY or ISPF option 6 and that the Gibson
package includes the ENUM path. If it returns a generic response, record the mode as source-
inferred and use SEARCHRX or ZSEC for the supported lab path.
### Instructor note
Ask students to separate “lead” from “finding.” ENUM output creates leads. A finding requires
validation, risk statement and remediation.
### Cleanup
Read-only in Gibson.
### Validation status
### Source validated from Gibson TSO simulated REXX tool handling and seeded ENUM placeholder
material.
### Lab EN-2: Use ENUM APF to review authorized-library risk
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: ENUM mode command.
### Why this lab matters
APF is one of the fastest ways to explain why source-library and program-library permissions
matter. If a user can update code that runs from an authorized path, the risk can move from data
access to control-plane compromise. ENUM APF gives a training view of that question.
### What the commands do
ENUM APF asks for the APF-focused section of the enumeration tool. In Gibson it is used as an
educational surface; on a real assessment the follow-up would include APF lists, dataset access
review, change history and program-library ownership.
### Starting state
Use the standard training state. Cross-reference the APF and ELV.APF privilege concept section if
present.
### Lab steps
### ENUM APF
### What the output tells us
The evidence is any APF library reference, history line or risk note. The useful interpretation is not
“APF exists”; it is whether the library is writable, who owns it, and whether changes are monitored.
### On a real z/OS system
On real z/OS, APF authorization is defined through system configuration such as PROGxx and is
visible through operator/system display paths. Dataset protection determines whether users can
alter authorized libraries.


<!-- page 166 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
Defenders should monitor APF library lists and protect those datasets with strict UPDATE/ALTER
controls. Any change to an APF library should be treated as security-sensitive.
### Troubleshooting
If the ENUM APF output is sparse, confirm whether APF state exists in this Gibson build and use
ZSEC APF as a comparison command.
### Instructor note
Ask students why read-only visibility of APF is still valuable to an attacker and why write access
changes the severity.
### Cleanup
Read-only in Gibson.
### Validation status
Source validated from ENUM/ZSEC APF command paths where present; real-world depth requires
live APF dataset evidence.
### Lab EN-3: Run ENUM ALL and prioritise follow-up
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: ENUM mode command.
### Why this lab matters
ENUM ALL is useful because it creates too much information on purpose. That is the teaching
point: mainframe security review is not just running tools; it is prioritising what the tool tells you.
### What the commands do
### ENUM ALL requests every supported enumeration section. The student should identify which
sections represent identity risk, dataset risk, APF risk, service risk and operational evidence.
### Starting state
Use a clean training state or a state where earlier labs have generated security evidence.
### Lab steps
### ENUM ALL
### What the output tells us
The evidence is the set of section headings and summary lines. A good student answer should
identify the highest-risk line and the command that would validate it next, such as RLIST, LISTDSD,
ZSEC, ICSF DISPLAY or NETSTAT.
### On a real z/OS system


<!-- page 167 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
On a real z/OS system, broad audit scripts can quickly create long reports. Experienced assessors
triage by control impact: privileged IDs, writable trusted code, SURROGAT, weak dataset controls,
exposed services and missing audit coverage first.
### Defensive takeaway
Defenders should require audit reports to be actionable. A report that does not identify owner,
control, evidence and remediation is just noise.
### Troubleshooting
### If ENUM ALL is too short, run ENUM SEC and ENUM APF separately to confirm which modes are
supported in this build.
### Instructor note
Teach prioritisation. Ask students to choose only three follow-up items and defend their choice.
### Cleanup
Read-only in Gibson.
### Validation status
Source validated from Gibson ENUM handling; exact sections depend on package state.
### Lab SR-1: Use SEARCHRX to turn RACF searches into audit leads
### Command context
Start from: TSO READY or ISPF option 6.
Commands run from: SEARCHRX simulated REXX workflow.
### Why this lab matters
### SEARCHRX is the bridge between raw RACF search commands and a security-audit thought
process. Instead of asking the student to remember every SEARCH command, the lab shows how an
automation helper can organise WARNING mode, dataset, BPX and SURROGAT leads.
### What the commands do
SEARCHRX runs Gibson’s supported simulated REXX search workflow. It calls into the same ideas
as SEARCH ALL WARNING NOMASK and SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT), then
presents the output as sections the student can review.
### Starting state
Use TSO READY or ISPF option 6. If you have not run any RACF profile labs yet, the report may still
show seeded examples.
### Lab steps
### SEARCHRX
### What the output tells us


<!-- page 168 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
The evidence is the sectioned report. WARNING mode lines indicate profiles that may log but still
allow access. BPX/FACILITY lines point to UNIX-related controls. SURROGAT lines point to submit-
as authority. Each section should map to a manual follow-up command.
### On a real z/OS system
### On real z/OS, security REXX execs are often used to standardise RACF searches and produce
reports. The exec itself requires authority to see the data and should be controlled as a security
tool.
### Defensive takeaway
Defenders should control who can run audit execs and where output is stored. The content can
reveal high-value datasets, classes and privilege relationships.
### Troubleshooting
If SEARCHRX is not recognised, confirm command context and package version. If output is empty,
validate the underlying RACF commands manually.
### Instructor note
Ask students to pick one SEARCHRX section and turn it into a specific RACF follow-up command.
### Cleanup
Read-only in Gibson.
### Validation status
Source validated from Gibson TSO simulated REXX tool handler.
### Lab REP-1: Turn ZSEC, ENUM and SEARCHRX evidence into a finding
### Command context
Start from: the outputs generated in the ZSEC, ENUM or SEARCHRX labs.
Commands run from: none required unless re-running evidence commands at TSO READY.
### Why this lab matters
This lab closes the loop. A technical report is not complete because a tool printed a line. The learner
must explain the evidence, impact, likelihood, control failure and remediation in language a
technical manager can act on.
### What the commands do
ZSEC, ENUM and SEARCHRX provide the evidence source. The student’s job is to select one line,
validate it where possible, and write the finding in a short professional format.
### Starting state
Complete at least one of the ZSEC, ENUM or SEARCHRX labs first.
### Lab steps


<!-- page 169 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Review one ZSEC/ENUM/SEARCHRX output line.
Identify the affected control.
Write: Evidence, Impact, Likelihood, Remediation, Defensive validation.
### What the output tells us
The evidence is the written finding. It should cite the command, output line, affected control and
recommended next step. A weak answer repeats the tool output. A strong answer explains why the
line matters.
### On a real z/OS system
On real z/OS, findings should be backed by RACF profile output, SMF/audit records, dataset access
listings, system display output or product reports such as zSecure. The principle is the same: tool
output must become evidence-backed risk.
### Defensive takeaway
Defenders should be able to validate the finding independently and identify which owner or
control process must change.
### Troubleshooting
If students cannot explain impact, require them to return to the relevant command section: APF,
SURROGAT, ICSF, SETROPTS, dataset access or user privilege.
### Instructor note
Teach report discipline. The common mistake is to paste a tool line without explaining affected
asset, control and remediation.
### Cleanup
No cleanup required.
### Validation status
Manual exercise; source validated through the commands used in prior labs.
### Lab 24: ENUM security enumeration
 Chapter 15. Security Training Playbooks
 Security Tooling: ZREXX, ZSEC, ENUM and SEARCHRX
### Lab 25: SEARCHRX security search workflow
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup
Ask students to choose one ENUM line and name the exact verification command.


<!-- page 170 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Instructor note
If ENUM syntax requires EX form in your package, run the equivalent exec path documented in
Appendix A.
### Troubleshooting
Do not stop at the summary. Follow up with RLIST, LISTDSD, ZSEC, SYS0WN or SDSF depending on
what ENUM reports.
### Defensive takeaway
Real estates often use local REXX/CLIST tools or commercial products to summarise RACF and
system posture. ENUM is the Gibson training equivalent.
### On a real z/OS system
Look for APF candidates, SURROGAT-style exposure, weak dataset/profile signals and summary
lines that point to follow-up commands.
### What the output tells us
### ENUM SEC
### ENUM APF
### ENUM ALL
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
ENUM SEC checks security posture. ENUM APF focuses on APF libraries. ENUM ALL collects the
broad simulator view.
### What the commands do
ENUM gives students a fast triage view before they drill down into individual RACF profiles. Use it
to decide what deserves deeper review.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
### Lab 26: SYS0WN APF and ownership review
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup


<!-- page 171 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students how SEARCHRX differs from a single SEARCH command.
### Instructor note
If the exec is missing, confirm the dataset/member name or use the direct SEARCH commands.
### Troubleshooting
Review who can run and modify audit execs; a broken search script can hide risk or create false
confidence.
### Defensive takeaway
Real sites often use REXX/CLIST automation to standardise RACF searches and evidence collection.
The script itself needs change control.
### On a real z/OS system
The evidence is the grouped report output: warning-mode datasets, submit-as profiles and other
candidates that need a RACF follow-up command.
### What the output tells us
EX 'IBMUSER.SEARCHRX.RX'
### SEARCH ALL WARNING NOMASK
SEARCH CLASS(SURROGAT) FILTER(*.SUBMIT)
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
### EX IBMUSER.SEARCHRX.RX runs the SEARCHRX exec where implemented. It commonly wraps
WARNING, SURROGAT, APF and dataset searches into a repeatable report.
### What the commands do
SEARCHRX sits between raw RACF SEARCH output and security reporting. It teaches students how
to turn several searches into audit leads.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
### Lab 27: FTP JES submission with QUOTE SITE FILETYPE=JES
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup


<!-- page 172 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to prove both trust and writeability before calling it high risk.
### Instructor note
If SYS0WN is not available, run D PROG,APF and ENUM APF as the supported alternative.
### Troubleshooting
Alert on APF list changes and broad UPDATE/ALTER to authorised libraries. Review owner/group
relationships as carefully as permits.
### Defensive takeaway
### Real APF/library ownership review combines APF list, PROGxx/SETPROG state, RACF dataset
profiles and change-control evidence.
### On a real z/OS system
The evidence is an APF library or execution path paired with risky ownership or update authority.
### What the output tells us
### D PROG,APF
### EX SYS0WN.RX
### ENUM APF
### ZSEC APF
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
### EX SYS0WN.RX reviews APF, execution-path or ownership style exposure where Gibson
implements the training exec. D PROG,APF and ENUM APF provide corroborating evidence.
### What the commands do
SYS0WN teaches a privilege-escalation thought process safely: find trusted paths, then check
whether the wrong users can update them.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context
### Lab 28: SQL and TSh0cker-style workflow in Gibson
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup


<!-- page 173 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Ask students to separate submission evidence from execution evidence.
### Instructor note
If the server does not accept JES mode, confirm the FTP service profile and port.
### Troubleshooting
Monitor FTP logins, SITE FILETYPE=JES usage, submitted USER= values and job output retrieval
from network sessions.
### Defensive takeaway
Real z/OS FTP can support FILETYPE=JES where configured, allowing job submission and output
retrieval through FTP. It must be tightly controlled.
### On a real z/OS system
The evidence is the FTP 226-style completion message and the JES job/spool entry. The FTP prompt
proves submission path; SDSF proves JES processed it.
### What the output tells us
ftp 127.0.0.1 2022
quote site filetype=jes
put job.jcl
quit
### SDSF ST
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
QUOTE SITE FILETYPE=JES switches the FTP session into JES submission mode. PUT/STOR submits
the JCL. SDSF/JES review happens after the upload path completes.
### What the commands do
FTP/JES matters because file transfer can become job submission. The lab teaches why an ordinary
network service can cross into batch execution.
### Why this lab matters
Start from the FTP prompt. FTP commands run at ftp>. Verify results later in SDSF/JES. Do not type
SDSF commands inside FTP.
### Command context
### Lab 29: Security evidence to finding
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.


<!-- page 174 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Cleanup
Ask students what Gibson proves and what would still need a real authorised test environment.
### Instructor note
### If TSh0cker is not implemented, keep the lab conceptual and use supported RUN SQL/FTP
SQL/banking SQLi paths only.
### Troubleshooting
### Monitor SQL execution routes, FTP SQL mode, CICS/REST query inputs and privileged catalog
queries.
### Defensive takeaway
Real TShOcker-style discussions involve abusing service paths and SQL execution context. Gibson
should teach the reasoning and evidence safely.
### On a real z/OS system
### The evidence is SQL output, SQLCODE/SQLSTATE, or the banking/API trace showing the unsafe
branch. Unsupported TSh0cker behaviour must be called conceptual.
### What the output tells us
### RUN SQL SELECT CURRENT SQLID FROM SYSIBM.SYSDUMMY1
### RUN SQL SELECT USERID, AUTHORITY FROM SYSIBM.SYSUSERAUTH
# If FTP SQL mode is enabled:
quote site filetype=sql
put whoadm.sql
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
RUN SQL executes simulator SQL. FTP SITE FILETYPE=SQL processes uploaded SQL where enabled.
The banking lab includes SQL-like unsafe input branches for education.
### What the commands do
This lab teaches SQL/TSh0cker-style risk as a bounded Gibson workflow. The goal is to show how
unsafe SQL paths and FTP SQL processing can change data or reveal authority in a lab, not to fake
production exploitation.
### Why this lab matters
### Start from the Db2/SQL simulator, CICS banking lab, REST SQL gateway or FTP SQL mode
depending on which path is enabled. Do not claim a real exploit unless the simulator explicitly
supports it.
### Command context


<!-- page 175 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Missing and Conceptual Security Tool Capabilities
The current Gibson package supports ZSEC, ENUM, SEARCHRX and SYS0WN-style training surfaces,
but a complete executable ZREXX package is not present in the Gibson source tree. The uploaded
ZREXX material is valuable as a hardening and design reference, but it is not enough to claim a
built-in ZREXX command. The manual therefore treats ZREXX as security-automation concept and
future integration until source is supplied.
 Chapter 16. Instructor Guide and Assessment
 Appendix A. Command Reference by Execution Context
### Lab 30: Privilege and exposure triage
### Command context
Start from: TSO READY
If you are currently in ISPF: Use =6 first, then enter the TSO/RACF command.
Commands run from: TSO READY or ISPF option 6
Do not run these from: ISPF 3.4, ISPF editor, OMVS, FTP or CICS unless a documented bridge exists
Why context matters: RACF commands are TSO command processors. Running them at the wrong
panel teaches confusion rather than security.
### Why this lab matters
In this lab we’ll work through privilege and exposure triage as a practical evidence exercise, not as
a command checklist. The concept being taught is identity, class, profile and authority analysis.
From a tester’s point of view, the aim is to produce a specific piece of evidence: user attributes,
profile class, UACC, access list, WARNING or audit fields. From a defender’s point of view, the same
evidence explains what should be controlled, logged or challenged before the activity becomes
normalised. By the end of the lab, you should be able to say why each command was used and
what changed in your understanding of the Gibson environment.
### What the commands do
LISTUSER IBMUSER ALL: asks for the fuller identity view. In a real RACF workflow, the ALL-style
view is where default group, attributes, revoke/protected state and audit-relevant details become
visible.
LISTGRP *: lists group information. Group membership often explains access inherited by users.
SETROPTS LIST: lists RACF-wide options and class status. It shows whether classes are active and
whether profile decisions are cached or enforced.
RLIST DATASET SYS1.PARMLIB: reviews a high-value dataset profile. SYS1.PARMLIB is security-
relevant because it holds system configuration on real z/OS.
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
### Starting state


<!-- page 176 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Start at the READY prompt with the standard seeded training state. If this lab creates MANLAB or a
profile, run it in a disposable simulator state or reset the state before repeating.
### Lab steps
### LISTUSER IBMUSER ALL
LISTGRP *
### SETROPTS LIST
### RLIST DATASET SYS1.PARMLIB
### NETSTAT PORTLIST
### What the output tells us
For `LISTUSER IBMUSER ALL`, look for the RACF field that answers the security question: attribute,
class, profile, UACC, WARNING, access list or policy setting. That field is the evidence you would cite
in a finding.
### On a real z/OS system
RACF commands such as LISTUSER, RLIST and LISTDSD expose security metadata; create/alter
commands require delegated authority and can drive SMF type 80 audit records depending on
auditing settings.
### Defensive takeaway
Defenders should review who can list or change sensitive profiles, whether WARNING is masking
enforcement problems and whether access lists match business need.
### Troubleshooting
If RACF commands fail, check the class name, profile spelling and whether the profile was created
in an earlier step. In Gibson, context and spelling usually explain most failures.
### Instructor note
Ask students to identify the one RACF field that changes their assessment most: attribute, UACC,
### WARNING, access list or group membership. The common mistake is to read the command as
administration rather than evidence.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### LISTUSER IBMUSER
ALL
### Displays a simulated
### RACF user profile and
optional segments.
### ALL asks for broad
profile detail; a user ID
such as IBMUSER or
### MANLAB selects the
account to inspect.
### User profile review is
one of the first ways to
identify powerful
attributes, segment
data and
authentication
controls.
### Evidence includes
attributes, owner,
default group,
### TSO/OMVS/MFA
segments and
revoke/status
indicators.


<!-- page 177 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
LISTGRP * Lists RACF group
information.
* requests a broader
inventory where
supported by Gibson.
### Groups are how many
z/OS environments
delegate authority, so
group membership
often explains
unexpected access.
### Evidence is a group list,
owner data or
connected users.
### SETROPTS LIST Displays or alters
simulated RACF
system-wide settings.
### LIST reports effective
options;
### CLASSACT/RACLIST/RE
### FRESH style operands
model class activation
and caching.
### SETROPTS explains the
security manager
posture, not just a
single user or profile.
### Evidence is a policy
summary or
activation/refresh
message.
### RLIST DATASET
### SYS1.PARMLIB
### Displays a simulated
### RACF general resource
profile.
### CLASS identifies the
resource class; AUTH
or ALL asks for access
list and authority
detail.
### RLIST converts a
profile name into
evidence: owner, UACC,
warning state and
access list.
### Evidence is the profile
detail and any explicit
permits.
### NETSTAT PORTLIST Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### Field Value
### Difficulty Intermediate
### Estimated time 60 minutes
### Objective Build a security snapshot from users, groups, SETROPTS,
dataset profiles and listeners.
Prerequisites IBMUSER session.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### Lab 31: OPERLOG and security event review
### Command context
Start from: Master Console or browser dashboard
Commands run from: Master Console/dashboard controls, or from the subsystem that triggers the
event
Do not run these from: ISPF editor, FTP or CICS unless generating the event intentionally
Why context matters: Detection labs separate activity generation from defender observation.
### Why this lab matters
In this lab we’ll work through operlog and security event review as a practical evidence exercise,
not as a command checklist. The concept being taught is operator console, event stream and


<!-- page 178 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
system-state evidence. From a tester’s point of view, the aim is to produce a specific piece of
evidence: console display output, WTOR state, event line or security summary. From a defender’s
point of view, the same evidence explains what should be controlled, logged or challenged before
the activity becomes normalised. By the end of the lab, you should be able to say why each
command was used and what changed in your understanding of the Gibson environment.
### What the commands do
SECEVENTS: shows simulator security events so students can connect actions to event evidence.
SDSF OPERLOG: opens the OPERLOG view through SDSF-style workflow, providing console/security
event context.
D SECURITY,DAILY: shows the simulator security summary view. Its value is tying technical actions
to security reporting.
### Starting state
Start with the Master Console or console command path available. For WTOR work, the simulator
must be in a state where the outstanding reply exists.
### Lab steps
### SECEVENTS
### SDSF OPERLOG
### D SECURITY,DAILY
### What the output tells us
For `SECEVENTS`, identify the exact returned line, return code, panel state or dataset change that
proves the lab objective. If that item is not present, pause and troubleshoot the current command
context before continuing.
### On a real z/OS system
### Real operators use MVS/JES commands, OPERLOG/SYSLOG, WTOR replies and automation
products. Gibson models the idea so students can practise interpreting operational evidence safely.
### Defensive takeaway
Console and OPERLOG visibility should be baselined. Logon events, high-port events and WTOR
replies are operational signals that defenders should explain.
### Troubleshooting
If a panel is empty, check polling/refresh, event generation, service health and whether the action
you performed is meant to emit an event.
### Instructor note
### Teach operlog and security event review by asking students to explain the purpose of each
command before they run it and then identify the exact field, line or state change that proves the
point of the lab.
### Cleanup


<!-- page 179 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson handlers and existing matrices. Runtime behaviour depends on the
selected service profile, so confirm the listener or endpoint before delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### SECEVENTS Reviews simulated
security events or
OPERLOG-style output.
### The panel or command
selects event/log
visibility.
### Logs are where proof
becomes defensible.
### They also show
whether the simulator
raises the right signals.
### Evidence is an event
line, command audit
record or console log
entry.
### SDSF OPERLOG Enters or queries the
simulated SDSF/JES
view.
ST is the status panel;
### H/O style panels expose
held or output data
where implemented.
### SDSF is where job
status and output
become evidence. It is
also where credentials
and system messages
often leak.
### Evidence is a job list,
output panel or JES
state summary.
### D SECURITY,DAILY Displays simulated
console or system
status information.
### The operand selects the
subsystem or metric:
### CPU, MEMORY, DASD,
### R,L, SECURITY and
similar.
### Console display
commands are read-
only but high-value;
they show what the
operator can see and
what defenders can
monitor.
### Evidence is an
IEE/$HASP-style
response or console
metric.
### Field Value
### Difficulty Intermediate
### Estimated time 45 minutes
### Objective Review security events and determine what activities should be
reported.
Prerequisites IBMUSER session.
### Validation Runtime/static plus source panel validation
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only
### ICSF Control-Plane Protection and Alerting
ICSF matters because cryptography on z/OS is not just an application feature; it is a platform
service. Real sites protect callable services, key labels and key data sets such as CKDS, PKDS and
TKDS with RACF classes and strict operational controls. Gibson does not hold real keys, but it gives
students a safe control-plane model: display status, inspect CKDS/PKDS/TKDS state, attempt refresh
actions, and verify that the action created audit or console evidence.
### Command Run from Gibson behaviour Real z/OS concept Defensive focus
### ICSF STATUS / TSO READY or Displays ICSF operational Who can view


<!-- page 180 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### ICSF DISPLAY
### STATUS
### ISPF option 6 simulated ICSF
status
status and control
plane
cryptographic
service state
### ICSF DISPLAY
### CKDS/PKDS/TKDS
### TSO READY or
### ISPF option 6
### Displays
simulated key
dataset status
messages
### CKDS/PKDS/TKDS
contain sensitive
key/token
material or
metadata in real
systems
### Dataset and key-
label access
should be tightly
controlled
### ICSF REFRESH
### CKDS/PKDS/TKDS
### TSO READY or
### ISPF option 6
### Simulates refresh
and records
### SMF80-style
evidence
### Operational
refresh of key
data set state
### Any refresh
should be
authorised,
change-controlled
and alerted
### D ICSF / F
### ICSF,REFRESH,TK
DS
### Master Console Displays or
modifies ICSF
state through
console path
### Operator
command path
for ICSF control
### Console
commands need
separation of
duties and
monitoring
### ZSEC ICSF TSO READY Shows posture
summary for ICSF
protection
### Security posture
review of
cryptographic
services
Check
### CSFSERV/CSFKEY
### S-like controls
and dataset
protection
### Lab ICSF-1: Protect simulated ICSF datasets and alert on refresh activity
### Command context
Start from TSO READY or ISPF option 6 for TSO commands. Use the Master Console for D/F ICSF
commands. Do not run ICSF REFRESH from CICS, FTP, OMVS or ISPF 3.4. Review alerts in the
Master Console or OPERLOG after the action.
### Why this lab matters
In this lab we’ll use Gibson to practise the defensive question that matters around ICSF: who can
see or change cryptographic control-plane state, and does a change leave evidence? The lab is safe
because Gibson does not store real key material, but the risk model is real.
### What the commands do
### ICSF STATUS establishes the baseline. ICSF DISPLAY CKDS/PKDS/TKDS shows the simulated
protected key dataset surfaces. ICSF REFRESH CKDS tests whether the current user can perform a
change-like operation. D ICSF and F ICSF,REFRESH,TKDS show the console path for the same
control-plane idea. ZSEC ICSF gives a security posture view.
### Starting state


<!-- page 181 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Use a lab user such as IBMUSER for the authorised path, then repeat the refresh attempt as a lower-
privilege user if available. The Master Console should be available so that alerts and audit evidence
can be reviewed.
### Lab steps
### ICSF STATUS
### ICSF DISPLAY CKDS
### ICSF DISPLAY PKDS
### ICSF DISPLAY TKDS
### ZSEC ICSF
### ICSF REFRESH CKDS
### D ICSF
### F ICSF,REFRESH,TKDS
### What the output tells us
The baseline commands should show simulated ICSF status and key dataset surfaces. The refresh
command should produce a clear status or denial and should create audit/console evidence. If the
display succeeds but refresh is denied, the simulator is teaching read versus update authority. If a
refresh succeeds silently, the defensive control path is incomplete and should be treated as a
documentation or product issue.
### On a real z/OS system
Real ICSF protects callable services and key material through RACF/SAF controls such as CSFSERV,
CSFKEYS and related cryptographic classes, plus dataset protection for CKDS, PKDS and TKDS. Real
key stores and master-key operations are highly sensitive and normally require strict separation of
duties, change records and operational logging.
### Defensive takeaway
Defenders should baseline who can display ICSF status, who can refresh key data sets, who can
access key labels, and whether refresh/change attempts create timely alerts. Protect the datasets,
protect the callable services, and alert on any unexpected display or refresh activity.
### Troubleshooting
If ICSF commands are not recognised, confirm you are at TSO READY or ISPF option 6. If console
commands fail, confirm you are in the Master Console path. If refresh appears to succeed but no
alert appears, check OPERLOG, dashboard alert polling and SMF80-style audit entries.
### Instructor note
Teach this as a control-plane lab, not a key-management lab. The point is not to show keys; the
point is to show why key services, key datasets and refresh commands need access control and
monitoring.
### Cleanup
No real keys are changed. If the lab increments a simulated key dataset version or creates an alert,
leave it as evidence for the detection discussion or reset Gibson to the chapter baseline before the
next cohort.
### Validation status


<!-- page 182 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Source validated from Gibson ICSF documentation, TSO handlers, console handlers and v24 tests.
Runtime validation is recommended in the selected classroom profile.
## Chapter 16. Instructor Guide
and Assessment
This section provides course flow, timing, reset points, demo sequencing, capstone tasks and
answer-key guidance.
### Implementation evidence
### Area Source evidence
### Primary evidence Phase 1 code inventory
Command evidence command_matrix.csv
Runtime evidence safe_command_validation.csv
### Operational model
This instructor chapter turns Gibson features into teachable sequences. The operational model is
facilitation: set the state, run the workflow, ask what changed, and make students explain the
evidence.
### Security relevance
The security value is assessment quality. A good class does not reward command completion; it
rewards correct interpretation, safe boundaries and defensible reporting.
### Commands and features in scope
Relevant commands are cross-referenced in the full command reference appendix and lab index.
### Section labs
### Lab 26: Run a capstone readiness check
### Command context
Start from: Context stated in the lab prerequisite
Commands run from: Use the command context beside each step
Do not run these from: Any other subsystem unless explicitly directed


<!-- page 183 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
Why context matters: Mainframe commands are context-sensitive. Check where you are before
typing the next command.
### Why this lab matters
In this lab we’ll work through run a capstone readiness check as a practical evidence exercise, not
as a command checklist. The concept being taught is TSO READY command context and simulator
boundary. From a tester’s point of view, the aim is to produce a specific piece of evidence: help
text, catalog view, network view or command response at READY. From a defender’s point of view,
the same evidence explains what should be controlled, logged or challenged before the activity
becomes normalised. By the end of the lab, you should be able to say why each command was used
and what changed in your understanding of the Gibson environment.
### What the commands do
HELP: shows the command surface available in the current context. In a lab, HELP is how you
prevent guessing and confirm which command language you are actually in.
LISTCAT: shows catalog-style dataset information. It gives the learner a safe way to practise moving
from a command prompt to dataset discovery.
MFA STATUS: shows the simulator MFA state. It proves whether the authentication layer is active
before students test logon or PassTicket behaviour.
JES STATUS: summarises the simulated job-entry environment. It is the starting point before
creating or browsing job output.
NETSTAT PORTLIST: shows the service-facing listener view: which simulated ports exist and what
they represent.
PTKTSTAT: shows PassTicket-related simulator state from the TSO/command side.
### Starting state
Start from the chapter baseline and confirm the relevant listener, panel or prompt is available
before running the lab.
### Lab steps
HELP
### LISTCAT
### MFA STATUS
### JES STATUS
### NETSTAT PORTLIST
### PTKTSTAT
### What the output tells us
For `HELP`, identify the exact returned line, return code, panel state or dataset change that proves
the lab objective. If that item is not present, pause and troubleshoot the current command context
before continuing.
### On a real z/OS system
The TSO READY prompt is the command environment for interactive TSO/E work. On real systems,
commands may call RACF, catalog services, JES, TCP/IP, CLIST/REXX or installation exits.


<!-- page 184 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Defensive takeaway
READY activity should be tied to user identity, command authorisation and audit trails. Unexpected
enumeration commands can indicate reconnaissance.
### Troubleshooting
If a command is not recognised, confirm the prompt is READY rather than ISPF, OMVS, CICS or an
API route. Use HELP to confirm the implemented command surface.
### Instructor note
Teach run a capstone readiness check by asking students to explain the purpose of each command
before they run it and then identify the exact field, line or state change that proves the point of the
lab.
### Cleanup
This lab is read-oriented in the simulator. No state cleanup is required beyond closing panels,
leaving the client session cleanly or returning to READY for the next lab.
### Validation status
Source validated from Gibson command handlers, package scripts and existing matrices. Runtime
validation is recommended in the target teaching environment before publication delivery.
### Command What It Does Important Options Why It Matters Expected Evidence
### HELP Displays the available
command surface for
the current Gibson
context.
### A command name after
### HELP narrows the
output where
implemented.
### Help is safe
enumeration. It tells
you what the simulator
exposes without
changing state.
### Evidence is a command
list or help panel that
can be compared with
the command
appendix.
### LISTCAT Lists cataloged data
sets known to the
simulator.
### A high-level qualifier
may narrow results
where implemented.
### Catalog enumeration
tells you what objects
exist before you test
RACF or edit paths.
### Evidence is a list of
data set names and
attributes.
### MFA STATUS Displays or manages
Gibson’s simulated
MFA posture.
### STATUS reports
global/user state;
### ENROLL/VERIFY/RESET
change or test MFA
state where
implemented.
### MFA is part of the
logon control path. A
tester cares because
weak recovery or
bypass paths matter as
much as the password.
### Evidence is MFA status
or a verification result.
### JES STATUS Enters or queries the
simulated SDSF/JES
view.
ST is the status panel;
### H/O style panels expose
held or output data
where implemented.
### SDSF is where job
status and output
become evidence. It is
also where credentials
and system messages
often leak.
### Evidence is a job list,
output panel or JES
state summary.
### NETSTAT PORTLIST Interrogates the
simulated
TCP/IP/network state.
### PORTLIST shows
listening services;
### CONN shows
connections;
### PING/TRACERTE test
reachability.
### Network enumeration
turns a black box into
an attack-surface map.
### Evidence is a listener,
connection or
reachability result.
### PTKTSTAT Inspects or exercises APPL() or endpoint PassTickets remove Evidence is a


<!-- page 185 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
simulated PassTicket
behaviour.
parameters select the
application and ticket
operation where
implemented.
reusable password
transmission, but weak
setup or replay
windows become
security findings.
generated, accepted,
rejected or listed ticket
state.
### Field Value
### Difficulty Advanced
### Estimated time 60 minutes
### Objective Verify lab prerequisites, services, seeded data and known gaps
before class delivery.
Prerequisites Fresh lab environment.
### Validation Runtime/static validated
### Users IBMUSER unless stated otherwise
### Datasets/files Only seeded or lab-created datasets
### Risk Low - training simulator state only


<!-- page 186 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Appendix A. Command
### Reference by Execution Context
### Use this appendix when you know what you are trying to test but cannot remember where the
command belongs. Mainframe commands are context-sensitive. LISTUSER belongs at READY or
ISPF option 6. SAVE belongs inside the ISPF editor. SITE FILETYPE=JES belongs inside FTP. Mixing
those contexts is one of the fastest ways to confuse yourself, so this appendix is organised by where
the command actually runs.
### A.1 Gibson host and runtime commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.2 Connection commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
nc 127.0.0.1
2023
### Linux host
shell
nc 127.0.0.1
2023
### Connects to
the
simulator
terminal
service as a
raw TCP
client.
### Banner/
front-door
prompt;
simple text
response.
### Proves the
service is
reachable
but not full
3270
behaviour.
### A raw TCP
test, not a
normal
3270
terminal
session.
### QS-3 Read-only
connection
c3270
127.0.0.1:20
23
### Linux host
shell
c3270
127.0.0.1:20
23
### Opens a
3270
terminal
emulator to
the training
service.
3270/logon
panel or
front-door
screen.
### Correct
client for
### ISPF/CICS-
style
workflows.
### TN3270/
### TN3270E
client
access to
VTAM apps.
### QS-4 Session
state
### A.3 VTAM/front-door commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### L TSO VTAM/
front-door
prompt
### L TSO Selects the
simulated
TSO
### TSO logon
prompt or
READY
### Moves from
application
selection to
VTAM
### APPLID
selection/lo
### QS-7 Session
transition


<!-- page 187 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
application. path. user
command
environme
nt.
gon.
### A.4 TSO READY commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### ISPF TSO READY ISPF Launches
the ISPF
panel
environme
nt.
ISPF
primary
menu
appears.
### After this,
READY
commands
need option
6 or exit to
READY.
### ISPF dialog
manager.
### Lab 09 Session
transition
### LISTCAT TSO READY
or ISPF
option 6
### LISTCAT
### LVL(userid)
Lists
catalog
entries
matching a
level.
### Datasets
under the
HLQ;
missing
dataset
evidence.
### Dataset
discovery
and lab
prerequisit
e checking.
### Catalog
search via
### TSO/E/IDCA
### MS-type
facilities.
### Lab 09 Read-only
### LISTUSER TSO READY
or ISPF
option 6
### LISTUSER
userid
### Displays a
### RACF-style
user
profile.
### Attributes,
default
group,
revoke
state, last
access.
### Identifies
privileged,
stale or
usable
accounts.
### RACF user
profile
display.
### RACF labs Read-only
### SEARCH
ALL
### WARNING
### NOMASK
### TSO READY
or ISPF
option 6
### SEARCH
ALL
### WARNING
### NOMASK
Finds
profiles in
### WARNING
mode
where
supported.
### Profiles
that warn
rather than
fully deny.
### A classic
mainframe
security
finding:
logged
violation
but allowed
access.
RACF
### SEARCH
against
active
profiles.
### WARNING
mode lab
### Read-only
discovery
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
### TSO READY
or ISPF
option 6
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
Finds
### SURROGAT
submit-as
resources.
userid.SUB
### MIT style
resource
names.
### Identifies
potential
batch
impersonat
ion paths.
RACF
### SURROGAT
class profile
discovery.
### SURROGAT
lab
### Read-only
discovery
RLIST
### SURROGAT
profile ALL
### TSO READY
or ISPF
option 6
RLIST
### SURROGAT
### IBMUSER.S
### UBMIT ALL
### Inspects a
specific
### SURROGAT
resource.
UACC,
owner and
permitted
users/group
s.
### Shows who
may submit
jobs as
another
user.
RACF
resource
profile
listing.
### SURROGAT
lab
### Read-only
### A.5 RACF commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### LISTUSER TSO READY
or ISPF
### LISTUSER
userid
### Displays a
### RACF-style
### Attributes,
default
### Identifies
privileged,
### RACF user
profile
### RACF labs Read-only


<!-- page 188 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
option 6 user
profile.
group,
revoke
state, last
access.
stale or
usable
accounts.
display.
### SEARCH
ALL
### WARNING
### NOMASK
### TSO READY
or ISPF
option 6
### SEARCH
ALL
### WARNING
### NOMASK
Finds
profiles in
### WARNING
mode
where
supported.
### Profiles
that warn
rather than
fully deny.
### A classic
mainframe
security
finding:
logged
violation
but allowed
access.
RACF
### SEARCH
against
active
profiles.
### WARNING
mode lab
### Read-only
discovery
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
### TSO READY
or ISPF
option 6
### SEARCH
### CLASS(SUR
### ROGAT)
FILTER(*.S
### UBMIT)
Finds
### SURROGAT
submit-as
resources.
userid.SUB
### MIT style
resource
names.
### Identifies
potential
batch
impersonat
ion paths.
RACF
### SURROGAT
class profile
discovery.
### SURROGAT
lab
### Read-only
discovery
RLIST
### SURROGAT
profile ALL
### TSO READY
or ISPF
option 6
RLIST
### SURROGAT
### IBMUSER.S
### UBMIT ALL
### Inspects a
specific
### SURROGAT
resource.
UACC,
owner and
permitted
users/group
s.
### Shows who
may submit
jobs as
another
user.
RACF
resource
profile
listing.
### SURROGAT
lab
### Read-only
### A.6 USS/OMVS commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
cp
"//'HLQ.DAT
A'" file.txt
### OMVS/USS
shell
cp
"//'HLQ.DAT
A'" file.txt
### Copies an
MVS
dataset into
a USS file
where
supported.
### Created
USS file;
content
visible with
cat.
Shows
movement
between
dataset
world and
UNIX
world.
z/OS UNIX
MVS
dataset
pathname
support /
### OCOPY/OPU
T
equivalents
.
### USS copy
lab
### May create
file
### Syntax Direction Run From What It Does What To
### Watch For
### Real z/OS
### Equivalent
### Security
### Relevance
cp source.txt
target.txt
### USS file to USS
file
### OMVS/USS shell Copies text
from a USS file
in the
simulated USS
tree to another
USS path.
### Returns no
output on
success.
cp: <source>:
unsupported
source when
source is absent
or a directory.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18A
cp
"//'IBMUSER.TE
ST.DATA'"
sample.txt
### MVS dataset to
### USS file
### OMVS/USS shell Reads the
simulated MVS
dataset/membe
r through
dataset services
and writes the
content into a
cp: <source>:
data set not
found; cp:
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
### Add Lab 18B


<!-- page 189 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
USS file. considerations).
cp from_uss.txt
"//'IBMUSER.TE
ST.COPY'"
### USS file to MVS
dataset
### OMVS/USS shell Reads the USS
file and writes
content into the
target MVS
dataset name.
unsupported
source if the
### USS path is
absent or a
directory;
permission
denied if
dataset write is
blocked.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18C
cp
"//'IBMUSER.A.D
ATA'"
"//'IBMUSER.B.D
ATA'"
### MVS dataset to
### MVS dataset
### OMVS/USS shell Reads one
simulated
dataset/membe
r and writes an
identical target
dataset/membe
r.
data set not
found;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document and
include in
reference;
optional lab
step.
cp
"//'IBMUSER.PD
S.CODE(TIME)'"
member.txt
### PDS/PDSE
member to USS
file
### OMVS/USS shell Reads the
named member
and writes a
USS file.
data set not
found if
member does
not exist.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18D
Updated coverage: USS/OMVS cp supports USS-to-USS, MVS-to-USS, USS-to-MVS, MVS-to-MVS and
### PDS/PDSE member copy patterns where the operands are supported by Gibson. Run these only
from the OMVS/USS shell.
### A.7 ISPF navigation commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
=6 ISPF
primary
menu
=6 Jumps to
the ISPF
command
shell/panel
for TSO
commands.
A TSO
command
entry
panel.
### Correct
way to run
### TSO/RACF
commands
once inside
ISPF.
### ISPF option
6.
### Lab 09,
### RACF labs
Panel
transition
### A.8 ISPF editor primary commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
### SAVE ISPF editor
command
line
### SAVE Saves the
current edit
buffer.
### Member/
data set
content
persists
after
leaving
editor.
### Edit access
to
### JCL/REXX/c
onfig is
security-
sensitive.
### ISPF Edit
SAVE.
### ISPF edit
lab
### State-
changing


<!-- page 190 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Primary
### Command /
### Feature
### Syntax Run From What It Does What To
### Look For
### Gibson
### Behaviour
### Real ISPF
### Behaviour
Lab
### SAVE SAVE ISPF editor
### Command
===> or PF
key
### Writes editor
buffer to the
target
dataset/mem
ber and
remains in
the editor
with DATA
SAVED.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A
### END / PF3 /
F3
### END or PF3 ISPF editor
### Command
===> or PF
key
### Exits the
editor if data
is clean. If
data is dirty,
### Gibson
prompts to
SAVE,
### CANCEL or
END again.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A/09B
### CANCEL /
### CAN / PF12 /
F12
### CANCEL or
PF12
### ISPF editor
### Command
===> or PF
key
### Restores the
original lines
and exits
without
saving the
edit buffer.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09B
### HELP / PF1 /
F1
### HELP ISPF editor
### Command
===> or PF
key
### Displays
available
primary and
focus
commands.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### FIND / F FIND string ISPF editor
### Command
===> or PF
key
### Searches for
a string and
positions the
cursor on a
match.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### RFIND RFIND ISPF editor
### Command
### Repeats the
previous
### INVALID
EDIT
### Source-
backed in
### ISPF edit
primary
### Lab 09C


<!-- page 191 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
===> or PF
key
### FIND. COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Gibson editor command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### CHANGE / C CHANGE old
new [ALL]
### ISPF editor
### Command
===> or PF
key
### Changes the
next or all
matching
strings,
depending on
ALL.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### RCHANGE RCHANGE ISPF editor
### Command
===> or PF
key
### Repeats the
previous
CHANGE.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09C
### TOP TOP ISPF editor
### Command
===> or PF
key
### Moves the
view to the
top of data.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### BOTTOM /
BOT
### BOTTOM ISPF editor
### Command
===> or PF
key
### Moves the
view to the
bottom of
data.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### LOCATE / L LOCATE n or
### LOCATE text
### ISPF editor
### Command
===> or PF
key
### Locates a line
number or
searches for
text.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference


<!-- page 192 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### BROWSE/VIE
### W as appli
CAPS CAPS ON|
OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
upper-case
normalizatio
n in the
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
HEX HEX ON|OFF ISPF editor
### Command
===> or PF
key
### Toggles
### Gibson hex
display state
message.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### RECOVERY /
### RECOVER
### RECOVERY
ON|OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
recovery
state in the
editor profile.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### AUTOSAVE AUTOSAVE
ON|OFF
### ISPF editor
### Command
===> or PF
key
### Toggles
autosave
state in
profile; SAVE
remains
explicit in
labs.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
NULLS NULLS ON|
OFF
### ISPF editor
### Command
===> or PF
key
### Toggles null
display/profil
e state.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
TABS TABS ON|
OFF
### ISPF editor
### Command
===> or PF
### Toggles tab
profile state.
### INVALID
EDIT
### COMMAND,
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
### Lab 09E


<!-- page 193 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
key NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
ofile/key
concept; see
### IBM ISPF Edit
docs
### PROFILE PROFILE ISPF editor
### Command
===> or PF
key
### Displays
editor profile
settings:
### RECOVERY,
### CAPS, NULLS,
TABS,
### AUTOSAVE
and HEX.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### RESET RESET /
### RESET X /
RESET
### EXCLUDED
### ISPF editor
### Command
===> or PF
key
### Clears
excluded line
state.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
CUT CUT [start
[end]]
### ISPF editor
### Command
===> or PF
key
### Cuts current
or numbered
range into
copy buffer.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
PASTE PASTE [line]
[BEFORE]
### ISPF editor
### Command
===> or PF
key
### Pastes copy
buffer after
line or before
line when
### BEFORE is
specified.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference
### EXCLUDE EXCLUDE
ALL |
EXCLUDE n |
### EXCLUDE
string
### ISPF editor
### Command
===> or PF
key
### Excludes
matching
lines or
numeric line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Reference


<!-- page 194 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### W as appli
### SUB / SUBMIT SUB or
### SUBMIT
### ISPF editor
### Command
===> or PF
key
### Submits
current
editor text as
### JCL via
configured
submitter if
available.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09F
### LINE / LC /
### LINECMD /
LN
### LINE, LC, LN
or LC n
command
### ISPF editor
### Command
===> or PF
key
### Moves focus
to line-
command
area or
executes
explicit line
command for
a numbered
line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09D
### TEXT / TXT /
DATA
### TEXT, TEXT n
text, or n text
### ISPF editor
### Command
===> or PF
key
### Moves focus
to text area
or replaces a
numbered
line.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09A
~ ~ ISPF editor
### Command
===> or PF
key
### Moves focus
back to the
command
field.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### TAB TAB key ISPF editor
### Command
===> or PF
key
### Cycles
between
command,
line-
command
and text
fields in the
interactive
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
concept; see
### IBM ISPF Edit
docs
### Lab 09E
### PF7/PF8 PF7/PF8 ISPF editor
### Command
===> or PF
key
### Pages up and
down in the
editor.
### INVALID
EDIT
### COMMAND,
### NO PRIOR
### Source-
backed in
### Gibson editor
### ISPF edit
primary
command/pr
ofile/key
### Reference


<!-- page 195 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### FIND/CHANG
### E, DATA
### CANNOT BE
### CHANGED IN
### BROWSE/VIE
### W as appli
concept; see
### IBM ISPF Edit
docs
Updated coverage: primary commands are editor commands. They are not TSO READY commands.
### A.9 ISPF editor line commands
The commands in this context are covered in the grouped tables and lab-specific context blocks.
Use the Command-to-Lab index when you need the teaching path rather than a raw command list.
Line
### Command
### Syntax Type What It
Does
### Target
Required?
### Example Gibson
### Behaviour
### Real ISPF
### Behaviour
Lab
### I I or In line
command
### Inserts one
or n blank
lines at the
target line.
### No I Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09A
### D D or Dn line
command
### Deletes one
or n lines.
### No D Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09A
### DD DD ... DD block line
command
### Deletes a
marked
block of
lines.
### Second
marker
### DD Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### C C or Cn line
command
### Copies one
or n lines
into the
buffer.
### Requires
### A/B/P to
place.
### No C Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### CC CC ... CC block line
command
### Copies a
marked
block into
the buffer.
### Second
marker
### CC Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### M M or Mn line
command
### Moves one
or n lines
into the
buffer by
removing
them from
source.
### Requires
### A/B/P to
place.
### No M Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### MM MM ... MM block line
command
### Moves a
marked
block into
the buffer.
### Second
marker
### MM Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D


<!-- page 196 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### A A or An target line
command
### Places
copied/mov
ed lines
after the
target line.
### Yes A Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### B B or Bn target line
command
### Places
copied/mov
ed lines
before the
target line.
### Yes B Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### P P or Pn target line
command
### Places
copied/mov
ed lines
after the
target line;
### Gibson
synonym
for paste
target.
### Yes P Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### R R or Rn line
command
### Repeats
one line n
times.
### No R Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### RR RR ... RR block line
command
### Repeats a
marked
block of
lines.
### Second
marker
### RR Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09D
### X X or Xn line
command
### Excludes
one or n
lines from
display.
### No X Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09E
### XX XX ... XX block line
command
### Excludes a
marked
block of
lines.
### Second
marker
### XX Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Lab 09E
### O O or On line
command
### Marks one
or n lines
as overlay
source.
### No O Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Reference
### OO OO ... OO block line
command
### Marks a
block as
overlay
source.
### Second
marker
### OO Implement
ed
### Real ISPF
equivalent
or marked
real-only
### Reference
### S/F/L show-
excluded
### S/F/L real ISPF
line
commands
Not
implement
ed in
### Gibson line-
command
regex.
### Document
as real ISPF
only.
### No S/F/L No - real
### ISPF only
### Real ISPF
equivalent
or marked
real-only
### No lab
shift (, ), <, > real ISPF Not No (, No - real Real ISPF No lab


<!-- page 197 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
commands
((, )), <, >
line
commands
implement
ed in
### Gibson line-
command
regex.
### Document
as real ISPF
only.
### ISPF only equivalent
or marked
real-only
Updated coverage: line commands are entered in the left line-command area, or through Gibson
terminal fallbacks such as LC n command.
### A.10 SDSF/JES commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### ST SDSF panel ST Displays
jobs/status
in SDSF
where
implement
ed.
### Job list,
owner,
status and
return
code.
Spool
output
often
contains
sensitive
evidence.
### SDSF Status
panel.
### SDSF lab Read-only
unless line
actions
change
state
### A.11 FTP/JES commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
SITE
FILETYPE=J
ES
### FTP session QUOTE
SITE
FILETYPE=J
ES
### Switches
z/OS FTP to
### JES mode
where
implement
ed.
### FTP server
accepts jobs
as internal
reader
input.
File
transfer
can become
job
execution.
z/OS FTP
SITE
FILETYPE=J
ES.
### FTP/JES lab Changes
### FTP mode
### A.12 CICS transactions and commands
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs Linux host ./ Installs Successful Build Linux QS-1 State-


<!-- page 198 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
on.sh --
venv
shell install_gibs
on.sh --
venv
### Gibson
dependenci
es using a
virtual
environme
nt.
install
messages;
venv
created; no
missing
packages.
hygiene
and
reproducibl
e lab setup.
install
process; not
z/OS.
changing
on host
CEMT
### INQUIRE
### SYSTEM
CICS
transaction
context
CEMT
### INQUIRE
### SYSTEM
### Queries
### CICS system
details
when
authorised.
### CICS level,
region/syst
em state.
### CICS admin
visibility
and
transaction
protection.
CICS
supplied
transaction
protected
by
### ESM/transa
ction
security.
### CICS lab Read-only
if inquiry
### A.13 Db2 commands and workflows
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.14 REST/API and browser workflows
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.15 nmap-sim.py and external security tools
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
python3
nmap-
### Linux host
shell
python3
nmap-
### Runs safe
standalone
### CONFIRME
### D, DENIED,
### Teaches
enumeratio
### NSE-style
### TN3270/TS
nmap-sim
lab
### Read-only/
offline by


<!-- page 199 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
sim.py --
script tso-
enum
sim.py --
offline --
script tso-
enum
### TSO user
enumeratio
n
simulation.
### UNAVAILA
### BLE user
states.
n without
touching
real
accounts.
O
enumeratio
n concept.
design
### A.16 Master Console / OPERLOG / alert actions
### Command
/ Action Run From Syntax What It
Does
### What To
### Look For
### Security
### Meaning
### Real z/OS
### Equivalent
Lab
### Reference
State
### Impact
install_gibs
on.sh --
venv
### Linux host
shell
./
install_gibs
on.sh --
venv
### Installs
### Gibson
dependenci
es using a
virtual
environme
nt.
### Successful
install
messages;
venv
created; no
missing
packages.
Build
hygiene
and
reproducibl
e lab setup.
Linux
install
process; not
z/OS.
### QS-1 State-
changing
on host
### A.17 ACF2 commands and security-manager comparison
Use this reference when the command syntax stops looking like RACF. ACF2 commands in Gibson
run from TSO READY after entering ACF2 mode. If you are in ISPF, use option 6 first. ACF2 material
is deliberately grouped because students need to compare LID, RULE, RESOURCE and SHOW
commands side by side.
ACF2
### Command
### Syntax Run From What It Does What To
### Look For
### Security
### Meaning
### Real ACF2
### Meaning
Lab
### ACF2 ACF2 TSO READY Switches the
READY
processor into
### ACF2 command
mode.
### ACF2 MODE
### ACTIVE and
### CURRENT
SETTING: LID.
### Tells the
learner they
are now using
### ACF2-style
commands
rather than
RACF
commands.
### Real systems
enter ACF2
through site-
defined
command
processors and
panels.
### ACF2-1
### SET LID SET LID or SET
ACF
### ACF2 mode Selects logonid
processing.
### LID SETTING
ACTIVE.
### LIDs are the
identity
records that
define who the
user or task is.
### Logonids are
### ACF2 identity
records.
### ACF2-1
LIST LIST userid |
LIST * | LIST
LIKE(mask) |
### LIST UID(n)
### ACF2 LID
setting
### Lists logonids
or selected
identity fields.
### SECURITY,
### NON-CNCL,
### GROUP, UID,
### HOME and
### OMVSPGM
fields.
### Identifies
privileged IDs,
### OMVS access
and grouping.
### LIST displays
logonid records
according to
setting and
scope.
### ACF2-1, ACF2-2
SHOW SHOW ACF2 |
SHOW TSO |
SHOW PSWD |
SHOW DDSN |
### SHOW OMVS
### ACF2 mode Displays ACF2
system, TSO,
password, data
set and OMVS
state.
### Database
names,
password
policy, current
mode and
### OMVS UID/GID
data.
### Shows whether
the security
environment is
enforceable,
auditable and
well
configured.
SHOW
commands
expose ACF2
control
information
subject to
authority.
### ACF2-1
### INSERT/
### CHANGE/
### INSERT userid
### PASSWORD(pw
### ACF2 LID Creates,
modifies or
### LOGONID
### DEFINED,
### State-changing
identity
### Logonid
administration
### ACF2-2


<!-- page 200 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
DELETE LID ) [SECURITY]
[GROUP(g)]
[UID(n)]
setting deletes
simulated
logonids.
### ALTERED or
### DELETED
messages.
administration;
requires
### SPECIAL in
Gibson.
is tightly
controlled and
auditable.
### SET RULE /
### RECKEY
SET RULE;
### RECKEY key
### ADD(resource
### UID(id)
### SERVICE(READ)
### ALLOW)
### ACF2 RULE
setting
### Creates or
updates data
set rule lines.
$KEY output,
### UID clauses
and
### ALLOW/PREVE
### NT service
decisions.
### Shows who can
access a
protected data
set and at what
service level.
### ACF2 rule sets
use
key/resource
and UID
matching
rather than
### RACF profile
syntax.
### ACF2-3
SET
### RESOURCE /
### RECKEY
SET
### RESOURCE(SUR
); RECKEY
### IBMUSER
ADD(IBMUSER.
### SUBMIT
### UID(ALICE)
### SERVICE(READ)
### ALLOW)
ACF2
### RESOURCE
setting
### Creates or
updates
resource rules
such as
### SURROGAT-
style submit-as
controls.
### TYPE(SUR), UID
and SERVICE
fields.
### Resource rules
can control
powerful non-
dataset
capabilities.
### ACF2 resource
rules
participate in
### SAF decisions
for protected
resources.
### ACF2-4
### ACCESS / TEST ACCESS
DSNAME('dsn');
TEST
DSNAME('dsn')
### LID(id)
### SERVICE(READ)
### ACF2 mode Displays
matching rules
or tests
simulated
access.
### ALLOW or
### PREVENT
decision and
matching rule
lines.
### Turns rule
listings into an
evidence-
backed access
decision.
### Real access
tests and
reporting are
central to audit
and
troubleshootin
g.
### ACF2-3, ACF2-4
 Appendix B. Security Testing Workflow Reference
 Appendix C. Output Interpretation Reference
### Appendix B. Security Testing
### Workflow Reference
Use this appendix by task. A tester rarely starts with an alphabetical command list; they start with
a security question. Each row below links the task, the command family, the expected evidence and
the defensive follow-up.
### Task Command /
### Tool Run From What It Proves Follow-Up Defensive
### Evidence Lab Reference
### Reconnaissance
and OSINT
### Browser, whois,
dig, Shodan-
style thinking,
### SighberBank
clues
### Host-side
browser/shell
### Likely users,
technologies,
services and
naming
patterns
### Move to service
discovery and
safe
enumeration
### OSINT record,
scope notes and
source
timestamps
### Security OSINT
lab
### Service
discovery and
port review
gibsonctl ports,
ss, nc, nmap-
sim tn3270-
screen
### Linux host shell Which Gibson
services are
reachable
### Choose
terminal/API/CI
### CS/Db2 path
### Connection
attempts,
### Master Console
events where
implemented
### QS-2, QS-3,
nmap-sim labs
### TSO user
enumeration
nmap-sim tso-
enum;
nmap-sim tool / CONFIRMED,
### DENIED or
### Avoid noisy
guesses; check
### Logon failures
and identity
TSO
enumeration


<!-- page 201 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### LISTUSER
where
authorised
### TSO READY UNAVAILABLE
identity
evidence
lockout policy audit trail lab
RACF
### WARNING
testing
### SEARCH ALL
### WARNING
NOMASK;
### LISTDSD/RLIST
### TSO READY or
### ISPF option 6
### Profiles that
warn rather
than enforce
### Inspect profile,
validate access
and report risk
### RACF/SMF
access and
warning
evidence
### WARNING
mode lab
### SURROGAT
testing
### SEARCH
### CLASS(SURROG
AT); RLIST
SURROGAT; JCL
USER=
TSO
### READY/option 6
and JCL
submission
context
### Submit-as
relationships
### Check whether
privileged IDs
can be
impersonated
### JES/RACF
messages and
job ownership
evidence
### SURROGAT lab
### APF-library
review
D PROG,APF;
ENUM APF;
### ELV.APF LIST
where
supported
### Console/SDSF or
uploaded tool
context
### Trusted
libraries and
dangerous
write access
### Inspect permits
and change
controls
### Console output,
### RACF permits,
change records
### APF lab
CICS
transaction
testing
cics-info, cics-
enum,
### CESN/CEMT/CE
### CI/CEDA
nmap-sim tool
or CICS context
### Reachable,
denied or
disabled
transactions
Check
transaction
security and
default user
exposure
### CICS security
events and
transaction logs
### CICS labs
### FTP/JES testing SITE
FILETYPE=JES;
PUT; GET; SDSF
review
### FTP session
then SDSF
### Whether file
transfer can
submit jobs
### Review JCL, job
owner and
spool output
### FTP logs, JES
output,
### JESSPOOL
controls
### FTP/JES lab
### Defensive
detection and
reporting
### Master Console,
### OPERLOG, alert
stream, lab
evidence
### Browser/Master
### Console plus
source
subsystem
### Whether action
is visible to
defenders
### Write finding
with evidence
and
remediation
### OPERLOG/
### SYSLOG/SMF-
like events
### Detection and
report labs
### Appendix C. Output
### Interpretation Reference
### Use this appendix after a command has run. The important question is not only whether the
command completed; it is what the output proves. These tables explain the fields and statuses
students should learn to read.
### C.1 LISTUSER output fields
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### USER The RACF user profile
being displayed.
### Ties output to the
identity under review.
### User profiles are
governed by RACF and
may be audited when
listed depending on site
policy.
### Check attributes and
groups.


<!-- page 202 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
DEFAULT-GROUP The user's default
connected group.
### Shows inherited
context and likely
dataset HLQ/group
access.
### Group connection can
influence access and
ownership.
### Follow with LISTGRP or
CONNECT review.
### ATTRIBUTES SPECIAL, OPERATIONS,
### AUDITOR or similar
high-value attributes.
### These can change the
entire risk profile of
the account.
### RACF administrative
privileges should be
tightly controlled and
audited.
### Report unexpected
privilege.
### SPECIAL RACF administrative
authority.
### Potential to alter RACF
controls.
### Comparable to high
administrative
authority in RACF.
### Check if required and
monitored.
### OPERATIONS Broad dataset access
capabilities.
### Can expose data even
when normal permits
are absent.
### Should be rare and
closely audited.
### Review dataset access
risk.
### REVOKE Whether the account is
disabled for logon.
### Active privileged users
are higher risk than
revoked ones.
### Revocation affects
authentication but not
all ownership traces.
Confirm logon status.
### LAST-ACCESS Last recorded access
date/time.
### Useful for stale account
and recent activity
review.
### Real sites use
### RACF/SMF and
reporting tools for this.
### Compare against
expected use.
### C.2 SEARCH, RLIST and LISTDSD interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### CLASS The RACF class being
searched or listed.
### Determines what kind
of resource is
protected.
### Classes such as
### DATASET, SURROGAT,
### FACILITY, OPERCMDS
and SERVAUTH have
different meanings.
### Pick the right follow-up
command.
### PROFILE The resource profile
name.
### Shows the protected
object or generic
pattern.
### Generic profiles can
protect broad resource
sets.
### Inspect with
RLIST/LISTDSD.
### UACC Universal access level. High UACC can expose
data to broad
populations.
### UACC is a central
access-control signal in
RACF.
### Report inappropriate
READ/UPDATE/ALTER.
### WARNING Access may be logged
but allowed.
### This is a high-value
security training
finding.
### RACF WARNING mode
is often used for testing
but risky if left in place.
### Validate whether
access is truly enforced.
### Access list Users/groups explicitly
permitted.
### Identifies who can
read, update or control
resources.
### Permits drive SAF
authorization
decisions.
### Check groups and
privileged IDs.
### C.3 SETROPTS LIST interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### Password interval /
syntax
### Global password age
and syntax settings.
### Weak policy enables
credential attacks.
### RACF SETROPTS
controls system-wide
### Compare against
policy.


<!-- page 203 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
options.
### Failed logon controls Revocation or lockout
behaviour after
failures.
### Determines whether
brute force or spraying
is safe/in-scope.
### Failed attempts can
produce RACF/SMF
evidence.
### Prefer low-noise
testing.
### Class activation Whether resource
classes are active.
### Inactive classes do not
protect resources as
expected.
### SETROPTS
### CLASSACT/RACLIST
controls are key
hardening points.
### Review sensitive
classes.
### Auditing options Which events are
logged.
### Detection depends on
audit configuration.
### RACF auditing is
central to
accountability.
### Map to defender
evidence.
### C.4 SURROGAT interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
userid.SUBMIT A SURROGAT resource
naming an execution
user.
### It may allow another
user to submit batch
work as that ID.
### Controlled by RACF
### SURROGAT class and
checked at job
submission.
### Inspect with RLIST and
test only in scope.
USER= on JOB card The execution user
coded in JCL.
### This is where submit-as
becomes operational.
### If authorised, JES/RACF
may allow the job to
run under that user.
### Review job owner and
messages.
### C.5 APF interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### APF library A trusted load-module
library.
### Write access can
become privileged-code
injection risk.
### APF list is defined
through system
configuration such as
### PROGxx and displayed
by operator/SDSF
mechanisms.
### Review UPDATE/ALTER
permits.
### UPDATE/ALTER access Ability to modify or
replace content.
### Dangerous when
applied to trusted
libraries.
### Can undermine the
trusted computing base
if misconfigured.
Report as high risk.
### C.6 ISPF editor interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
Command ===> Primary command line. SAVE, END, CANCEL,
### FIND and CHANGE
belong here.
### ISPF Edit has its own
command language.
### Do not type these at
READY.
### Line-command area Left column beside
data lines.
### I, D, C, M, R and block
commands belong
here.
### Line commands change
the edit buffer and may
change JCL/REXX/config
content.
### SAVE or CANCEL
intentionally.


<!-- page 204 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Output / Symptom Meaning Why It Matters Follow-Up
### No output Copy succeeded by UNIX
convention.
### Students must validate target
rather than waiting for a
banner.
cat target or read dataset.
data set not found MVS dataset/member operand
cannot be read.
### May be spelling or access-path
issue.
### LISTCAT/ISPF 3.4 and quoted
operand check.
permission denied Dataset read/write authority
is blocked.
### This is security evidence. Review DATASET profile if
authorised.
unsupported source USS path absent or a
directory.
Copy did not run. ls -l and create source file.
### C.6a cp and USS/MVS copy interpretation
### C.7 SDSF/JES interpretation
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### Job ID JES identifier assigned
to submitted work.
### Links submission to
spool output and
evidence.
### JES2 assigns and tracks
jobs through
queues/spool.
Open ST/O/H output.
### Return code Completion status for
job steps.
### RC 0000 is not always
security-safe; it only
means the job step
succeeded.
### Operations teams
review RC and
SYSOUT/JES messages.
### Inspect JESMSGLG,
JESJCL, JESYSMSG.
### C.8 CICS transaction states
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### CONFIRMED The transaction or
region evidence
appears reachable.
### Candidate attack
surface or training
path.
### Real CICS transactions
are protected by
transaction security
and ESM integration.
### Check authority and
logs.
### DENIED The transaction exists
or is implied but access
is restricted.
### Good defensive signal
and useful
enumeration evidence.
### CICS/RACF transaction
security should reject
unauthorised use.
### Report protection and
verify scope.
### DISABLED The transaction exists
but is disabled.
### Configuration
evidence, not
immediate access.
### Disabled transactions
may become risk if
enabled later.
### Review change
controls.
### C.9 nmap-sim.py statuses
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### CONFIRMED The simulated object
appears valid or
reachable.
### Candidate entry point
or confirmed surface.
### Real NSE-style probes
may create
connection/logon
evidence.
### Validate safely in
Gibson first.


<!-- page 205 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### INFERRED The response suggests
possible existence but
is ambiguous.
### Requires follow-up
before reporting.
### Ambiguous terminal
responses are common
in mainframe
enumeration.
### Gather corroborating
evidence.
### DENIED Access appears
restricted.
### Shows control exists
and object may still be
interesting.
### Real systems may log
the denial.
### Check defensive
evidence.
### UNAVAILABLE Object not found or not
exposed.
### Reduces the current
attack path.
### Absence of evidence is
not evidence of
absence across all
LPARs.
### Try scoped
alternatives.
### Correlation ID nmap-sim run
identifier.
### Links tool output to
forensic/training
evidence.
### Equivalent to keeping
traceability in a real
assessment.
Record in notes.
### C.10 Master Console / OPERLOG alert fields
### Output Field / Status What It Means Why It Matters Real z/OS Security
### Relevance Follow-Up
### Timestamp When the event
occurred.
### Supports timeline
building.
### Real defenders
correlate
### SYSLOG/OPERLOG/SMF
times.
### Compare with
command time.
### User/session Identity or session
involved.
### Connects action to
accountability.
### RACF/SAF/SMF
evidence ties action to
IDs where configured.
Investigate privileges.
### Event type Logon, high-port,
command, API or demo
event.
### Shows what defensive
story the lab is
teaching.
### Real sites use logs,
consoles and SIEM
enrichment.
Write evidence line.
### C.13 ACF2 output interpretation
### Output Field Meaning Why It Matters Follow-Up
### SECURITY / NOSECURITY Whether Gibson treats the logonid
as an administrator-style identity.
### SECURITY is a high-value privilege
indicator.
### LIST the ID, review group/UID,
and test whether state-changing
commands are permitted.
### NON-CNCL Gibson shows a common ACF2-
style flag in logonid output.
### Students learn to read flags, not
only user names.
### Ask what operational effect the
flag would have on a real site.
### UID(n) Simulated OMVS/UID value or
ACF2 grouping value.
### UID 0 or broad UID grouping can
change privilege assumptions.
SHOW OMVS or LIST UID(n).
$KEY(key) Rule-set key for a data set or
resource rule.
### Shows the protected namespace
being evaluated.
### Use ACCESS or TEST to turn a rule
into an access decision.
### UID(id) SERVICE(x)
### ALLOW/PREVENT
### Rule line granting or denying a
service to a UID/logonid.
### This is the evidence line for access
review.
Test
### READ/UPDATE/DELETE/EXECUTE
where appropriate.
 Appendix D. Identity, Group and Privilege Reference
 Appendix E. Dataset and File Reference
 Appendix F. Services, Ports and Connection Reference


<!-- page 206 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
 Appendix G. RACF Profile Interpretation Guide
 Appendix H. Lab-to-Command and Command-to-Lab Index
### Appendix D. Identity, Group and
### Privilege Reference
Use this appendix when a lab mentions a user, group or privilege and you need to know why it
matters. Do not treat users as sample names only; in mainframe security, identity, default group
and special attributes often define the attack path.
### User / Group Role Privilege Signal What To Check Real z/OS
### Comparison Lab Reference
### IBMUSER Training/default
high-value ID
### Often privileged in
training
environments
### Check SPECIAL,
### OPERATIONS,
### AUDITOR and
revoke state
### Default system ID
concept; should be
protected/revoked
after build
### RACF/security labs
### GUEST Low-privilege
training ID
### Demonstrates
weak/default
access and
restricted
commands
### Check whether
login works and
what commands
are denied
### Guest/default IDs
are risky even
when limited
### Initial access labs
### SYSADM / RUARIV /
### CICSUSR
### Role-based
training IDs
### Used for admin,
### RACF or CICS
scenarios
depending on seed
state
### Check group
membership and
service access
### Privileged or
application IDs
need strong
control
### Security labs
### Appendix E. Dataset and File
### Reference
Use this appendix when a lab moves between datasets, members and USS files. Mainframe security
students must learn the difference between a sequential dataset, PDS/PDSE member, catalog entry
and USS path because each has different access controls and command contexts.
### Object Type Example Syntax Run From Why It Matters Security
### Relevance Lab Reference
Sequential dataset 'HLQ.DATA' TSO READY, ISPF,
### USS dataset path
where supported
### A named MVS data
object.
### Dataset profiles
may control
### READ/UPDATE/ALT
ER.
### LISTCAT, LISTDSD,
cp labs
PDS/PDSE member 'HLQ.PDS(MEMBE
R)'
### ISPF 3.4/member
list/editor, TSO
### EX/SUBMIT where
supported
### Stores JCL, REXX,
CLISTs or source.
### Edit access can
become execution
or configuration
risk.
### ISPF edit, JCL labs


<!-- page 207 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### USS file /u/user/file.txt OMVS/USS shell UNIX-side file in
z/OS UNIX.
### Permissions,
scripts and copied
data matter.
### OMVS labs
### MVS dataset path
in USS
//'HLQ.DATA' OMVS/USS shell
where supported
### Bridge between
### UNIX commands
and MVS datasets.
### Easy way to move
data/scripts
between worlds.
### USS copy labs
### Syntax Direction Run From What It Does What To
### Watch For
### Real z/OS
### Equivalent
### Security
### Relevance
cp source.txt
target.txt
### USS file to USS
file
### OMVS/USS shell Copies text
from a USS file
in the
simulated USS
tree to another
USS path.
### Returns no
output on
success.
cp: <source>:
unsupported
source when
source is absent
or a directory.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18A
cp
"//'IBMUSER.TE
ST.DATA'"
sample.txt
### MVS dataset to
### USS file
### OMVS/USS shell Reads the
simulated MVS
dataset/membe
r through
dataset services
and writes the
content into a
USS file.
cp: <source>:
data set not
found; cp:
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18B
cp from_uss.txt
"//'IBMUSER.TE
ST.COPY'"
### USS file to MVS
dataset
### OMVS/USS shell Reads the USS
file and writes
content into the
target MVS
dataset name.
unsupported
source if the
### USS path is
absent or a
directory;
permission
denied if
dataset write is
blocked.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18C
cp
"//'IBMUSER.A.D
ATA'"
"//'IBMUSER.B.D
ATA'"
### MVS dataset to
### MVS dataset
### OMVS/USS shell Reads one
simulated
dataset/membe
r and writes an
identical target
dataset/membe
r.
data set not
found;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document and
include in
reference;
optional lab
step.
cp
"//'IBMUSER.PD
S.CODE(TIME)'"
member.txt
### PDS/PDSE
member to USS
file
### OMVS/USS shell Reads the
named member
and writes a
USS file.
data set not
found if
member does
not exist.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Add Lab 18D
cp
new_member.t
xt
"//'IBMUSER.PD
### USS file to
### PDS/PDSE
member
### OMVS/USS shell Writes the USS
file contents
into the target
### PDS/PDSE
unsupported
source;
permission
denied.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
### Add Lab 18D


<!-- page 208 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### S.CODE(NEWO
NE)'"
member. system has full
attributes/conv
ersion
considerations).
cp
//IBMUSER.TEST
.DATA file.txt
### Unquoted
dataset
notation
### OMVS/USS shell Parser accepts //
followed by a
dataset name,
but quoted
notation is safer
and is the
documented
teaching path.
### Shell quoting or
special
characters may
change the
operand before
### Gibson receives
it.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document as
supported/avoi
d unless simple.
cp -B or
conversion
options
### Binary/code-
page
conversion
### OMVS/USS shell Not
implemented.
### Gibson uses
### UTF-8/text style
content for
teaching.
### Options are not
parsed as
conversion
controls.
z/OS UNIX cp
can copy
to/from MVS
data sets (real
system has full
attributes/conv
ersion
considerations).
### Document as
real z/OS note
only.
Use this reference when a lab moves data between USS and traditional MVS datasets. The key
teaching point is context: these examples run from OMVS/USS, not from TSO READY or the ISPF
primary menu.
### E.5 USS/MVS Copy Syntax Reference
### Appendix F. Services, Ports and
### Connection Reference
Use this appendix when you need to connect to the right service. Ports are not just numbers in a
mainframe lab: each one represents an exposed subsystem, a client choice and a likely evidence
trail.
### Port Service Connect
With
### What It
### Exposes
### Offensive
Use
### Defensive
### Monitoring
### Gibson
### Behaviour
### Real z/OS
### Context
Lab
### Reference
2023 Gibson
### VTAM/TN3
270-style
terminal
nc, telnet,
c3270,
x3270,
nmap-
sim.py
### Front-door
application
s such as
### TSO/CICS/D
b2 where
configured
### Enumerate
### APPLIDs
and logon
paths
### Connection/
logon
events
### Primary
training
terminal
service
### TN3270/
### TN3270E to
VTAM
application
s
### Quick Start,
nmap-sim
8443 / 8082 Dashboard,
### Master
### Console or
web/API
endpoints
where
configured
### Browser,
curl
Web
control/visi
bility
surfaces
### Review
state and
API
exposure
### HTTP(S)
access logs,
dashboard
auth, event
streams
### Gibson web
training
surface
z/OSMF/z/
OS
### Connect/we
b interfaces
conceptuall
y
### Quick Start,
### API labs


<!-- page 209 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### FTP/JES
port where
configured
FTP
training
service
ftp client File
transfer
and
possible JES
workflow
Test
upload/dow
nload/JES
submission
if
supported
### FTP logs,
### JES records,
job output
### Source-
validated
only where
implement
ation
supports it
z/OS
### Communic
ations
### Server FTP
### FTP/JES
labs
### Appendix G. RACF Profile
### Interpretation Guide
Use this appendix when RACF output stops being obvious. A profile is not just a name; it tells you
what class is involved, what resource is protected, who owns it, whether WARNING mode is active
and which users or groups can access it.
### Class Profile UACC WARNING Access List
/ Permits
### What It
### Protects
### Why It
### Matters
### Inspect
With
Lab
### Reference
DATASET HLQ.** or
specific
dataset
NONE/
READ/
### UPDATE/
ALTER
### May be
active
### Users/
groups with
access
levels
MVS
datasets
and
members
### Weak UACC
or
### UPDATE/AL
### TER on
sensitive
datasets
can expose
data or
code paths.
### LISTDSD or
RLIST
### DATASET
### Dataset and
### WARNING
labs
### SURROGAT userid.SUB
MIT
### Usually
NONE
### Should be
controlled
### Submitters
allowed to
run batch
as target
user
Batch
submit-as
capability
Broad
permits
create
impersonat
ion and
privilege
escalation
paths.
### SEARCH
### CLASS(SUR
ROGAT);
RLIST
### SURROGAT
### SURROGAT
lab
### FACILITY Site-defined
facility
profile
### Varies Varies Users/
groups with
facility
access
### System/
service
capabilities
### Controls
access to
powerful
functions
outside
dataset
scope.
RLIST
### FACILITY
profile ALL
### RACF labs
### OPERCMDS Command
resource
### Varies Varies Operator
command
authorities
### MVS/JES/
operator
commands
### Can allow
display or
modificatio
n of system
state.
RLIST
### OPERCMDS
profile ALL
### Console/
### SDSF labs
### SERVAUTH Network/
resource
profile
### Varies Varies Network
access
permits
### TCP/IP
network
resources
### Important
for
controlling
who can
use specific
RLIST
### SERVAUTH
profile ALL
### Network/
security
labs


<!-- page 210 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
network
resources.
### Appendix H. Lab-to-Command
and Command-to-Lab Index
### Use this appendix to move between learning and reference. If you find a command here, you
should be able to locate the lab that teaches it. If a lab uses a command, you should be able to find
the reference and output interpretation.
### Lab ID / Title Commands / Tools
### Used Context Required Appendix
### References
### Output
### Interpretation
### Reference
### Cleanup Needed
### Lab QS-1: Install
### Gibson with a
virtual
environment
### See lab command
table and context
block
Start from: Linux
host shell in the
### Gibson package
directory
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-2: Start
### Gibson and
confirm services
### See lab command
table and context
block
Start from: Linux
host shell in the
### Gibson package
directory
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-3: Connect
with netcat
### See lab command
table and context
block
Start from: Linux
host shell or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-4: Connect
with c3270 or
x3270
### See lab command
table and context
block
Start from: Linux
host shell or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-5: Open the
browser console
### See lab command
table and context
block
Start from: Linux
host shell or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-6: Confirm
runtime mode
behaviour
### See lab command
table and context
block
Start from: Linux
host shell in the
### Gibson package
directory
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab QS-7: Read the
event and alert
stream
### See lab command
table and context
block
Start from: Master
### Console or
browser
dashboard
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 01: Orient to
simulator
boundaries
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 02: Verify
ports and service
model
### See lab command
table and context
block
Start from: TSO
### READY for
### NETSTAT/PING or
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
### Specific cleanup in
lab


<!-- page 211 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Linux host shell
for nmap-sim/nc
checks
command family
### Lab 03: Trace a
### READY command
to implementation
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 04: Review
### MFA and user state
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 05: Baseline
### READY commands
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 06: Create,
alter and review a
training user
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 07: Create a
resource profile
and permit access
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 08: Create and
inspect a dataset
profile
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 09: Launch
### ISPF and inspect
datasets
### See lab command
table and context
block
Start from: TSO
### READY, then enter
ISPF
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 10: Review JES
state and SDSF
status panel
### See lab command
table and context
block
Start from: TSO
### READY or ISPF
menu path to SDSF
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 11: Explore
### JES2 and NJE
commands
### See lab command
table and context
block
Start from: TSO
### READY or ISPF
menu path to SDSF
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 12: Review
console metrics
and security
summary
commands
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 13: Respond to
### IPL WTOR
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 14: Explore
### CICS transaction
help
### See lab command
table and context
block
Start from:
### VTAM/front-door
or CICS entry point
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
### Specific cleanup in
lab


<!-- page 212 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
command family
### Lab 15: Run the
### GMVB banking
navigation path
### See lab command
table and context
block
Start from:
### VTAM/front-door
or CICS entry point
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 16: Enumerate
### Db2 catalog tables
### See lab command
table and context
block
Start from: Db2
command/query
context or Gibson
route documented
by the lab
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 17: Exercise
### SQL privilege-
oriented queries
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 18: Review
### OMVS shell and
identity commands
### See lab command
table and context
block
Start from: TSO
### READY then OMVS,
or an existing USS
shell
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 19: Bridge
### OMVS and TSO
commands
### See lab command
table and context
block
Start from: TSO
### READY then OMVS,
or an existing USS
shell
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 20: Enumerate
simulator TCP/IP
listeners
### See lab command
table and context
block
Start from: TSO
### READY for
### NETSTAT/PING or
### Linux host shell
for nmap-sim/nc
checks
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 21: Enter z/OS-
style FTP client
environment
### See lab command
table and context
block
Start from: FTP
session after
connecting from
host or Gibson FTP
client context
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 22: Map API
routes to training
workflows
### See lab command
table and context
block
Start from: Host-
side REST client or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 23: Exercise
### PassTicket API and
### TSO status
comparison
### See lab command
table and context
block
Start from: Host-
side REST client or
browser
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 24: Privilege
and exposure
triage
### See lab command
table and context
block
Start from: TSO
READY
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 25: OPERLOG
and security event
review
### See lab command
table and context
block
Start from: Master
### Console or
browser
dashboard
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
command family
### Specific cleanup in
lab
### Lab 26: Run a
capstone readiness
check
### See lab command
table and context
block
Start from: Context
stated in the lab
prerequisite
### Appendix A, C and
### I as applicable
### Check output
interpretation
entry for the
### Specific cleanup in
lab


<!-- page 213 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
command family
### H.2 Command-to-lab mapping
### Command / Tool Context Labs Using It Primary Learning
### Outcome
### Related Output
### Interpretation
### LISTUSER TSO READY / ISPF
option 6
### RACF and identity labs Interpret user profile
privilege and account
state
### C.1 LISTUSER fields
### SEARCH TSO READY / ISPF
option 6
### WARNING, SURROGAT
and dataset discovery
labs
### Find RACF profiles and
weak patterns
C.2
### SEARCH/RLIST/LISTDS
D
### SAVE / CANCEL / END ISPF editor ISPF edit labs Control whether edit-
buffer changes persist
### C.6 ISPF editor
SITE FILETYPE=JES FTP session FTP/JES labs Understand file-
transfer-to-execution
risk
### C.10 FTP/JES response
codes
nmap-sim.py Linux host shell nmap-sim security labs Practise bounded NSE-
style enumeration
### C.9 nmap-sim.py
statuses
### Lab Commands / Features Context Reference
09A I, D, SAVE, END ISPF editor A.8, A.9, C.6
09B CHANGE, CANCEL/PF12 ISPF editor A.8, C.6
09C FIND, RFIND, CHANGE,
### RCHANGE
### ISPF editor A.8, C.6
09D C, CC, M, MM, A, B, R, RR, D,
DD
### ISPF editor A.9, C.6
09E CAPS, HEX, PROFILE, TAB, ~,
### PF3, PF12
### ISPF editor A.8, C.6
09F EDIT, SAVE, SUBMIT, SDSF
review
### ISPF/TSO/SDSF contexts B, H, I
18A cp USS to USS OMVS/USS A.6, E.5, I
18B cp dataset to USS OMVS/USS A.6, E.5, I
18C cp USS to dataset OMVS/USS A.6, E.5, I
18D cp PDS member to/from USS OMVS/USS A.6, E.5, I
### H.6 Added cp and ISPF editor labs
### H.6 ACF2 lab-to-command mapping
### Lab Commands Learning Outcome
ACF2-1 ACF2, SHOW MODE, SHOW DDSN, LIST * Enter ACF2 mode and read identity/database
context
### ACF2-2 INSERT, CHANGE, LIST Understand state-changing logonid


<!-- page 214 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
administration
### ACF2-3 SET RULE, RECKEY, ACCESS, TEST Build and test a dataset access rule
### ACF2-4 SET RESOURCE(SUR), RECKEY, LIST, ACCESS,
TEST
### Understand resource-rule and submit-as risk
### ACF2-5 Evidence review Translate ACF2 output into a finding
 Appendix I. Real z/OS Comparison Reference


<!-- page 215 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Appendix I. Real z/OS
### Comparison Reference
Use this appendix to keep Gibson honest. Gibson is a training simulator. It can teach the workflow,
the evidence and the risk, but a real z/OS system has RACF/SAF authority checks, JES and SDSF
controls, SMF records, OPERLOG/SYSLOG, site exits, parmlib configuration, network policy and
operational change controls.
### Area What Gibson
### Simulates What Real z/OS Adds Authority / Logging
### Consideration
### Defensive Evidence
### Mapping
### TSO/RACF commands RACF-style command
output and state
changes where
implemented
### Actual RACF database,
command processors,
class activation and
exits
### RACF authorities and
### SMF type 80/audit
policy may apply
### RACF reports, SMF,
console messages
### ISPF Panel navigation,
dataset
browsing/editing and
editor commands
where implemented
### Real ISPF dialog
services, dataset
allocation rules,
### ENQ/locks and site exits
### Dataset profiles and
### ISPF configuration
affect access
### Dataset access logs,
change records, job
output
### USS/OMVS UNIX-like shell and
dataset path simulation
where implemented
z/OS UNIX permissions,
### BPX authorities, code
page conversion and
dataset protection
### BPX.SUPERUSER,
filesystem permissions,
### RACF dataset profiles
### Shell history, audit
records, dataset access
logs
### JES/SDSF Job/spool concepts and
panel output
### JES2 queues, spool
datasets, SDSF SAF
controls and operator
commands
### JESSPOOL, OPERCMDS
and SDSF resources
govern access
### JESMSGLG, JESJCL,
### JESYSMSG, SDSF logs
### CICS Transaction exposure
and safe
denied/confirmed
states
### CICS regions, APPLID,
transaction security,
### ESM integration and
### CICS logs
### CICS transactions and
resources protected
through security
manager
### CICS security events,
### SMF, application logs
### Network/nmap-sim Safe local/offline
enumeration outcomes
### Real TN3270, FTP,
### DRDA, CICS web, z/OS
### Connect and firewall
policy
### SERVAUTH,
### NETACCESS, TLS and
daemon logs matter
### Network telemetry,
daemon logs, SIEM,
### OPERLOG
### I.6 USS/MVS cp and ISPF Edit Real z/OS Comparison
Real z/OS supports a richer version of both areas. IBM documents the z/OS UNIX cp command as
supporting copy operations to and from MVS data sets, while ISPF Edit and Edit Macros documents
the edit primary and line commands. Gibson implements a source-backed training subset. Where
Gibson lacks a real ISPF command, the manual marks it as real z/OS only rather than pretending it
works.
### Area Gibson Behaviour Real z/OS Behaviour Student Lesson
cp between USS and MVS Text-oriented copy using // Full z/OS UNIX and MVS Learn context and syntax


<!-- page 216 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
dataset operands. dataset integration, with
attributes and conversion
considerations.
first; understand production
has more controls.
### ISPF primary commands Training subset with
terminal-friendly focus
commands.
### Full ISPF primary command
set, macros and site profiles.
### Know what runs on
Command ===>.
### ISPF line commands I/D/C/M/R/A/B/P/O/X and block
forms.
### Much broader line-command
set.
### Know what belongs in the
line-command area.
### SAVE/END/CANCEL Simplified but safety-oriented. ISPF profiles and site
behaviour may vary.
### Never confuse exit, save and
cancel.


<!-- page 217 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Appendix J. Code Interpreter
### Language Reference
Use this appendix when you know which language surface you are working with and need to check
what Gibson actually supports. The tables deliberately separate Gibson behaviour from real z/OS
meaning so students do not mistake a bounded training interpreter for a production compiler or
runtime.
### J.1 REXX supported statements and functions
### Statement /
function
### Syntax Gibson behaviour Real z/OS
meaning
Lab
### SAY SAY expression evaluates
expression and
writes line to
output
REXX
display/output
instruction
CI-1
### PARSE ARG PARSE ARG var1
var2
splits invocation
arguments into
variables
common TSO/E
### REXX argument
parsing
CI-1
### ARG(n) ARG(1) returns nth
invocation
argument
real REXX
argument access
concept
CI-1
### ADDRESS TSO ADDRESS TSO
command
routes command
to Gibson TSO
processor
### TSO/E REXX
external
command
environment
CI-2
EXECIO DISKR EXECIO * DISKR
dsn (STEM stem.
reads dataset
lines into stem
variables
reads z/OS
datasets in REXX
CI-2
EXECIO DISKW EXECIO * DISKW
dsn (STEM stem.
writes stem
variables to a
dataset
writes z/OS
datasets in REXX
### CI-2/CI-10
DO/END DO i = 1 TO 3 ...
END
bounded
counted/while
loops
### REXX looping CI-1
IF/THEN/ELSE IF expr THEN ...
ELSE ...
conditional
execution
### REXX branch
logic
CI-1
SYSVAR SYSVAR('SYSUID') returns simulated TSO/E system CI-1


<!-- page 218 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
system/user
values
variable query
TIME/DATE TIME(); DATE() returns current
time/date
### REXX time/date
functions
CI-1
### J.2 JCL supported statements, keywords and programs
### Statement /
program
### Syntax Gibson behaviour Real z/OS
meaning
Lab
### JOB //NAME JOB
(acct),'desc',CLAS
S=A,MSGCLASS=A
creates job
identity,
owner/class/mess
age class
defines batch job
to JES
CI-3
USER= USER(userid) submit-as identity
checked through
### SURROGAT
batch job
execution user
### CI-3/CI-10
### EXEC PGM //STEP EXEC
PGM=IEFBR14
extracts program
and simulates
supported PGMs
defines job step
program
CI-3
PARM PARM='value' operands
captured;
### BPXBATCH/TShOc
ker style parms
partly parsed
passes
parameters to
programs
CI-4
### DD //DDNAME DD ... inventory and
instream DD
capture
defines
input/output
datasets/devices
CI-4
SYSIN DD * //SYSIN DD * ... /* passes instream
block to program
simulation
inline program
control input
CI-4
SYSOUT=* //SYSPRINT DD
SYSOUT=*
routes program
output to JES
spool
writes output to
### JES SYSOUT
### CI-3/CI-4
### IEFBR14 EXEC
PGM=IEFBR14
no-op RC 0000
step
allocation/test
utility pattern
CI-3
### IEBGENER EXEC
PGM=IEBGENER
copies SYSUT1 to
### SYSUT2 where
possible
sequential copy
utility
CI-4
### IKJEFT01 EXEC
PGM=IKJEFT01;
runs TSO batch TSO batch driver CI-4


<!-- page 219 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### SYSTSIN
commands
commands
### BPXBATCH EXEC
PGM=BPXBATCH
simulates z/OS
### UNIX command
processor
run UNIX
shell/program
from batch
CI-4
### J.3 COBOL supported simulation elements
### Element Syntax Gibson behaviour Real COBOL
meaning
Lab
### IDENTIFICATION
### DIVISION
### IDENTIFICATION
DIVISION.
required marker
for compile
simulation
real COBOL
identification
division
CI-5
### PROCEDURE
### DIVISION
### PROCEDURE
DIVISION.
required marker
for compile
simulation
real COBOL
executable
procedure
division
CI-5
DISPLAY DISPLAY 'text'. literal extraction
into SYSPRINT-
like output
COBOL
output/display
statement
CI-5
### EXEC CICS EXEC CICS ... END-
EXEC
recognised and
emits
informational
message
### CICS API call in
COBOL
CI-5
### EXEC SQL EXEC SQL ... END-
EXEC
recognised and
emits
precompiler-style
message
embedded SQL in
COBOL
CI-5
### J.4 HLASM status
### Element Gibson behaviour Real z/OS meaning Manual treatment
### HLASM assembler
runtime
### Not implemented Real HLASM
assembles, link-edits
and runs low-level
programs
### Conceptual / future
enhancement only
### J.5 ICSF and WTOR additions
### Area Syntax Gibson behaviour Security meaning Lab/section
### ICSF ICSF STATUS shows simulated detect control- ICSF-1


<!-- page 220 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### ICSF control-
plane status
plane health and
access
### ICSF ICSF REFRESH
CKDS
refreshes
simulated key
dataset version
and audits
change should be
protected and
alerted
### ICSF-1
ICSF D ICSF; F
### ICSF,REFRESH,TK
DS
console control
path for ICSF
simulation
console actions
require strong
controls
### ICSF-1
### WTOR R 01,CLPA responds to IPL
### CLPA prompt
bootstrap order
and audit
evidence
WTOR
### WTOR R 02,U continues
### IPL/user step in
startup contract
ensures console
flow is complete
WTOR
### WTOR R 03,Y enables MFA PIN
prompt
### MFA policy
choice
WTOR
### WTOR R 04,1357 sets 4-digit MFA
### PIN for IPL
PIN+HHMM
token model
WTOR


<!-- page 221 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 222 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 223 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 224 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 225 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2


<!-- page 226 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### J.6 ZREXX, ZSEC, ENUM and SEARCHRX Security Tool Reference
Use this reference when a lab moves from individual RACF commands into security-tool output.
The context remains TSO READY or ISPF option 6 unless a future tool specifically documents
another execution path.
I.7 Real z/OS comparison: zSecure-style reporting and REXX audit
automation
Real z/OS estates use RACF commands, SMF records, site REXX/CLIST tooling and products such as
IBM Security zSecure to analyse security posture. Gibson’s ZSEC and ENUM surfaces are training
simulators: they help students learn which questions to ask, but they do not replace live RACF
database analysis, SMF collection or zSecure reporting.


<!-- page 227 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
### Compact J.6 security-tool reference
ZSEC: run ZSEC or ZSEC <topic> from TSO READY or ISPF option 6. Use it to review simulated
posture reports for privilege, UID0, SURROGAT, APF, ICSF, SETROPTS, EVENTS and ALERTS. Labs:
ZS-1 and ZS-2.
ENUM: run ENUM SEC, ENUM APF or ENUM ALL from TSO READY or ISPF option 6. Use it for first-
pass security enumeration and follow-up prioritisation. Labs: EN-1, EN-2 and EN-3.
SEARCHRX: run SEARCHRX from TSO READY or ISPF option 6. Use it to organise WARNING,
dataset, BPX and SURROGAT leads into sections. Lab: SR-1.
ZREXX: external/future security-audit REXX package only in this build. No built-in Gibson ZREXX
command handler was found, so ZREXX is documented as conceptual/future integration rather
than a runnable lab.
### Appendix K. Implementation
### Completeness Notes
The final codebase audit also rechecked Gibson features that are easy to miss because they appear
in command dispatchers, tests or compatibility layers rather than in a single chapter file. The table
below records the main surfaces that were reviewed and either confirmed as already covered or
added to the reference proof package.
### Surface Status Why It Matters
ACF2 Added in this pass Alternative ESM model: logonids, UID strings,
rules and resource rules.
### SMPE Classified/referenced Maintenance workflows can expose software
inventory and exception handling.
NETACCESS/SERVAUTH Verified in command inventory Network zone controls shape who can reach
services.
RACDCERT/PTKTDATA/PassTicket Verified in command inventory Certificate, ring and passticket controls are
authentication-critical.
IKJTSO/PASSWORDPREPROMPT Verified in command inventory TSO logon prompting can affect enumeration
and authentication behaviour.
SECURITY RARE / reports Verified in command inventory Defensive reporting and frequency review
support audit triage.
IND$FILE, TRANSMIT, RECEIVE Verified in command inventory File-transfer paths matter for data movement
and evidence handling.
 Chapter 7. ISPF and Editor Workflows
 Code Interpreters
 Chapter 8. SDSF, JES, JCL, and NJE
 Chapter 9. Master Console and OPERLOG
 Chapter 10. CICS and Banking Lab


<!-- page 228 -->

### Gibson Mainframe Simulator Technical Manual - final1805
### Source-backed manual generated from code inventories - Phase 2
 Chapter 11. Db2 and SQL Simulation
 Chapter 12. OMVS/USS and Transfer Bridges
 Chapter 13. FTP, TCP/IP and Network Enumeration
 Chapter 14. REST API, Dashboard, and Web Interfaces
Source validated from Gibson command handlers and training tests; safe runtime validation is
recommended in a disposable simulator instance.
### Validation status
Reset the training state or remove the created profile/permit if continuing into a clean class run.
### Cleanup
Ask students to write the defensive validation first; that usually clarifies the finding.
### Instructor note
If the finding is vague, add the command, resource, user/group and observed field.
### Troubleshooting
Require students to provide a verification command for the fix, not just a recommendation.
### Defensive takeaway
Real mainframe findings must be reproducible, bounded, authorised and actionable for RACF,
system, database or network owners.
### On a real z/OS system
The output should be a concise finding that names the exact resource, command evidence and
recommended fix.
### What the output tells us
Choose one finding from Labs 24-28.
Write: Title, Evidence, Impact, Likelihood, Recommendation, Defensive Validation.
### Lab steps
Start from TSO READY. If you are in ISPF, use =6 before entering RACF/TSO commands. Use a
disposable Gibson lab state because these exercises intentionally create insecure training objects.
### Starting state
Use the previous labs as evidence sources. The command is the reporting workflow: evidence,
impact, likelihood, remediation and validation.
### What the commands do
### This final lab turns tool output into a finding. ENUM, SEARCHRX, SYS0WN, FTP/JES and SQL
evidence are only useful when they become clear risk statements and defensive actions.
### Why this lab matters
Start from TSO READY. If you are currently inside ISPF, use =6 first. Do not run these commands
from ISPF 3.4, the ISPF editor, FTP or CICS.
### Command context