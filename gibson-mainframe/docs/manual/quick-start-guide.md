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
### R 05,GIBSON
### R 06,SKIP
In Gibson, these replies teach the discipline of responding to operator prompts before assuming the
system is ready. CLPA represents the controlled IPL path used by the simulator, U and Y are
confirmation-style replies in the lab flow, R 04,1234 is the default MFA PIN reply for the
training build, R 05 sets the simulated system hostname, and R 06,SKIP declines the optional
DVCA/CBSA/OMEN training PIN. `gibsonctl.sh start`/`restart` answer all six replies automatically
in non-interactive use (via `--ipl-prestart-console`); this sequence is what you would type by
hand if running the console interactively instead. On a real z/OS system, operator replies are
controlled actions and should be visible through console/automation evidence.
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
