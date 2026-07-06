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
