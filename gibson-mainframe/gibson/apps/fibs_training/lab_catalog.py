from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LabPayload:
    name: str
    value: str
    description: str


@dataclass(frozen=True)
class LabDefinition:
    slug: str
    title: str
    category: str
    severity: str
    summary: str
    learner_level: str
    estimated_time: str
    learning_objectives: list[str]
    prerequisites: list[str]
    mainframe_context: str
    api_paths: list[str]
    architecture_nodes: list[str]
    architecture_edges: list[tuple[str, str]]
    attack_steps: list[str]
    payloads: list[LabPayload]
    secure_comparison: list[str]
    backend_mapping: dict[str, str]
    evidence_targets: list[str]
    hints: list[str]
    solution: dict[str, str]
    remediation: list[str]
    knowledge_checks: list[dict[str, str]]
    references: list[str] = field(default_factory=list)
    beginner_explanation: str = ""
    why_it_matters: str = ""
    attacker_goal: str = ""
    defender_view: str = ""
    glossary: dict[str, str] = field(default_factory=dict)
    instructor_notes: list[str] = field(default_factory=list)


def _base_nodes(extra: list[str] | None = None) -> list[str]:
    nodes = [
        "Browser / curl",
        "FIBS WEB9080",
        "z/OS Connect-style API provider",
        "Native CICS JSON web service",
        "CICS transaction",
        "COBOL/service program",
        "Db2 SQL",
        "Db2 tables",
        "Audit/Event Bus",
        "SMF",
        "Master Console",
        "zSecure/SYSVIEW",
    ]
    if extra:
        nodes.extend(extra)
    return nodes


def _base_edges() -> list[tuple[str, str]]:
    return [
        ("Browser / curl", "FIBS WEB9080"),
        ("FIBS WEB9080", "z/OS Connect-style API provider"),
        ("z/OS Connect-style API provider", "CICS transaction"),
        ("FIBS WEB9080", "Native CICS JSON web service"),
        ("Native CICS JSON web service", "CICS transaction"),
        ("CICS transaction", "COBOL/service program"),
        ("COBOL/service program", "Db2 SQL"),
        ("Db2 SQL", "Db2 tables"),
        ("Db2 tables", "Audit/Event Bus"),
        ("Audit/Event Bus", "SMF"),
        ("SMF", "Master Console"),
        ("Master Console", "zSecure/SYSVIEW"),
    ]


def _kc(api: str, mainframe: str, evidence: str) -> list[dict[str, str]]:
    return [
        {"question": "Which API or HTTP input starts this lab scenario?", "answer": api},
        {"question": "Which mainframe backend component should be visible in the trace?", "answer": mainframe},
        {"question": "Which evidence source should a defender review?", "answer": evidence},
    ]


LABS: dict[str, LabDefinition] = {}


def _add(lab: LabDefinition) -> None:
    LABS[lab.slug] = lab


_add(LabDefinition(
    slug="sqli",
    title="SQL Injection",
    category="API and Db2",
    severity="High",
    summary="Exploit unsafe teller search input to change the simulated Db2 query shape and expand returned account rows.",
    learner_level="Intermediate",
    estimated_time="25 minutes",
    learning_objectives=[
        "Compare normal and unsafe teller search requests.",
        "Identify how user input can alter a simulated Db2 SELECT.",
        "Map SQLi evidence to WEB9080, CICS, Db2, SMF102 and Master Console alerts.",
        "Explain how parameterized query construction stops the attack.",
    ],
    prerequisites=["Login as teller/cics", "Open /teller/search", "Understand basic SQL WHERE clauses"],
    mainframe_context=(
        "The browser calls FIBS WEB9080. The teaching model shows both a z/OS Connect-style API provider path "
        "and a native CICS JSON web-service path before the request reaches the CBSA teller search service. "
        "The vulnerable path simulates concatenated SQL against CBSA.CUSTOMER and CBSA.ACCOUNT."
    ),
    api_paths=["GET /webapi/teller/search?type=all&q=...", "POST /webapi/labs/sqli/run"],
    architecture_nodes=_base_nodes(),
    architecture_edges=_base_edges(),
    attack_steps=[
        "Run a normal teller search for customer 1001.",
        "Run the payload 1001' OR '1'='1 and compare the row count.",
        "Inspect the simulated SQL and Db2 tables in the evidence panel.",
        "Review SMF102 and Master Console evidence, then run secure comparison.",
    ],
    payloads=[
        LabPayload("Normal customer search", "1001", "Returns rows for a single customer/account relationship."),
        LabPayload("Boolean true", "1001' OR '1'='1", "Expands the rowset in vulnerable mode."),
        LabPayload("Boolean false", "1001' AND '1'='2", "Returns an empty/false rowset."),
        LabPayload("UNION metadata", "1001' UNION SELECT ...", "Returns controlled metadata rows in the simulator."),
        LabPayload("Verbose quote", "'", "Triggers a controlled verbose error path when enabled."),
    ],
    secure_comparison=["Input is treated as data.", "No rowset expansion occurs.", "Generic error/correlation ID is returned for malformed input."],
    backend_mapping={
        "API facade": "FIBS WEB9080 /webapi/teller/search",
        "z/OS Connect-style API": "FIBS-TELLER-SEARCH",
        "Native CICS API": "URIMAP=/fibs/teller/search PIPELINE=FIBSPIPE WEBSERVICE=FIBSJSON",
        "CICS transaction": "OMEN / INQCUST / INQACC",
        "Program": "TELLER_SEARCH / INQCUST / INQACC",
        "Db2 plan/package": "PLAN=FIBSWEB COLLID=CBSA",
        "SQL": "SELECT * FROM CBSA.ACCOUNT WHERE CUSTOMER_ID = '<q>' OR ACCOUNT_NUMBER = '<q>'",
        "Db2 tables": "CBSA.CUSTOMER, CBSA.ACCOUNT, CBSA.SQLI_EVENTS, CBSA.VULN_EVENTS, CBSA.WEB_AUDIT",
        "SMF": "SIMULATED SMF102 Db2 audit/trace; SIMULATED SMF110 CICS monitoring",
        "Console": "GIBSQLI01W SQLI TRAINING PAYLOAD DETECTED",
    },
    evidence_targets=["WEB9080 audit", "CBSA.SQLI_EVENTS", "CBSA.VULN_EVENTS", "SIMULATED SMF102", "Master Console GIBSQLI01W"],
    hints=[
        "Compare a normal customer number with the same value followed by a quote.",
        "Look for a boolean expression that changes the WHERE clause.",
        "The secure fix is not string filtering; it is safe parameter binding and authorization boundaries.",
    ],
    solution={
        "payload": "1001' OR '1'='1",
        "why": "The vulnerable simulator treats the payload as part of the SQL predicate and returns a broader rowset.",
        "expected_vulnerable": "Multiple account rows and SQLI evidence are returned.",
        "expected_secure": "The input is treated as a literal search string and does not expand rows.",
        "remediation": "Use prepared statements, strict input typing, least-privilege Db2 access and central API validation.",
    },
    remediation=["Parameterize search queries.", "Use typed search fields rather than concatenated SQL.", "Alert on SQL metacharacters and rowset anomalies.", "Store evidence in WEB_AUDIT/SQLI_EVENTS."],
    knowledge_checks=_kc("/webapi/teller/search?q=payload", "Db2 SQL via CICS/CBSA", "SIMULATED SMF102 and GIBSQLI01W"),
    references=["OWASP SQL Injection Testing", "IBM z/OS Connect API provider", "CICS JSON web services"],
))

_add(LabDefinition(
    slug="idor",
    title="IDOR / BOLA",
    category="API Authorization",
    severity="High",
    summary="Tamper with an account identifier that exists in Db2 but should not be visible to the logged-in customer.",
    learner_level="Intermediate",
    estimated_time="20 minutes",
    learning_objectives=["Recognize object-level authorization failures.", "Separate valid Db2 records from authorized API access.", "Find SMF80-style evidence for authorization failures."],
    prerequisites=["Login as a customer", "Know at least two account numbers"],
    mainframe_context="The API layer requests a real account row from CBSA.ACCOUNT. The defect is not that Db2 returns data; it is that the API/CICS service fails to verify customer-account ownership before returning it.",
    api_paths=["GET /accounts/{account_id}", "GET /webapi/accounts/{account_id}"],
    architecture_nodes=_base_nodes(["Authorization check"]),
    architecture_edges=_base_edges()+[("FIBS WEB9080", "Authorization check"),("Authorization check","CICS transaction")],
    attack_steps=["Open your own account.", "Change the account number in the URL.", "Compare vulnerable and secure behaviour.", "Review SMF80/API authorization evidence."],
    payloads=[LabPayload("Other account", "00000103", "Attempts to view another customer's account."), LabPayload("Own account", "00000101", "Baseline authorized request.")],
    secure_comparison=["Ownership check is enforced.", "Cross-customer access returns 403.", "Authorization denial is audited."],
    backend_mapping={"API facade":"FIBS WEB9080 /accounts/{account_id}","CICS transaction":"INQACC / ACCT","Program":"INQACC","Db2 tables":"CBSA.ACCOUNT, CBSA.WEB_USERS","SMF":"SIMULATED SMF80 authorization event","Console":"GIBAPI401W API AUTHZ TRAINING EVENT"},
    evidence_targets=["WEB9080 audit", "SIMULATED SMF80", "Master Console GIBAPI401W"],
    hints=["The account number is the object identifier.", "A valid object is not the same as an authorized object.", "Look for customer_id ownership checks."],
    solution={"payload":"/accounts/00000103","why":"The vulnerable path returns an account by object ID without ownership validation.","expected_vulnerable":"Other customer's account detail is returned.","expected_secure":"Access denied and SMF80-style evidence generated.","remediation":"Enforce object-level authorization on every account lookup."},
    remediation=["Authorize by server-side customer/account linkage.", "Do not trust hidden fields or browser state.", "Log denied object access."],
    knowledge_checks=_kc("/accounts/{account_id}", "CBSA.ACCOUNT ownership check", "SIMULATED SMF80 / GIBAPI401W"),
))

_add(LabDefinition(
    slug="mass-assignment",
    title="Mass Assignment",
    category="Object Property Authorization",
    severity="High",
    summary="Submit unexpected profile fields such as role, isAdmin, status or overdraftLimit and observe unsafe object binding.",
    learner_level="Intermediate",
    estimated_time="20 minutes",
    learning_objectives=["Identify unsafe object binding.", "Understand field allowlists.", "Map role tampering to GACF/WEB_USERS evidence."],
    prerequisites=["Login as customer", "Open profile update"],
    mainframe_context="The web/API layer maps request properties into a CBSA customer or web-user update. In a mainframe environment this can flow into CICS UPDCUST/CUSTUPD logic and Db2 WEB_USERS or CUSTOMER tables.",
    api_paths=["POST /profile", "POST /webapi/profile"],
    architecture_nodes=_base_nodes(["GACF.DB / WEB_USERS"]),
    architecture_edges=_base_edges()+[("COBOL/service program","GACF.DB / WEB_USERS")],
    attack_steps=["Submit a normal profile update.", "Add role=admin or isAdmin=true.", "Observe vulnerable update/evidence.", "Compare secure allowlist behaviour."],
    payloads=[LabPayload("Role tamper", "name=Alice&role=admin&isAdmin=true", "Attempts to set privileged fields."), LabPayload("Limit tamper", "overdraftLimit=999999", "Attempts to change banking limits.")],
    secure_comparison=["Only allowlisted fields are accepted.", "Privileged fields are ignored or rejected.", "Role is loaded from GACF/WEB_USERS server side."],
    backend_mapping={"API facade":"FIBS WEB9080 /profile","CICS transaction":"UPDCUST","Program":"CUSTUPD","Db2 tables":"CBSA.CUSTOMER, CBSA.WEB_USERS","SMF":"SIMULATED SMF80 role/property authorization event","Console":"GIBAPI403I MASS ASSIGNMENT BLOCKED/DETECTED"},
    evidence_targets=["WEB9080 audit", "CBSA.VULN_EVENTS", "SIMULATED SMF80"],
    hints=["Look for fields the UI never displays.", "Server-side role should not come from request JSON/form fields.", "Use an allowlist rather than a denylist."],
    solution={"payload":"role=admin&isAdmin=true","why":"The vulnerable path binds request fields into privileged properties.","expected_vulnerable":"Privileged property appears in audit/evidence.","expected_secure":"Privileged field rejected or ignored.","remediation":"Use explicit DTOs and server-side authorization for sensitive properties."},
    remediation=["Use property allowlists.", "Separate profile DTOs from persistence models.", "Log privileged-field attempts."],
    knowledge_checks=_kc("POST /profile", "UPDCUST/CUSTUPD and WEB_USERS", "WEB9080 audit and SMF80"),
))

_add(LabDefinition(
    slug="weak-auth",
    title="Weak Authentication",
    category="Authentication",
    severity="High",
    summary="Exercise a controlled weak login/token path and compare it to GACF-backed verification.",
    learner_level="Foundation",
    estimated_time="20 minutes",
    learning_objectives=["Explain weak authentication patterns.", "Understand GACF/RACF-style decision points.", "Identify SMF80 authentication evidence."],
    prerequisites=["Know seeded users", "Understand vulnerable vs secure mode"],
    mainframe_context="FIBS uses a local GACF.DB/WEB_USERS model to simulate enterprise identity controls. A real z/OS estate would centralize authentication/authorization through SAF/RACF-like controls.",
    api_paths=["POST /login", "POST /webapi/auth/token"],
    architecture_nodes=_base_nodes(["GACF.DB", "SAF/RACF decision"]),
    architecture_edges=_base_edges()+[("FIBS WEB9080","GACF.DB"),("GACF.DB","SAF/RACF decision"),("SAF/RACF decision","SMF")],
    attack_steps=["Run a normal login/token request.", "Run the weak-auth lab path.", "Inspect GACF lookup and SMF80 events.", "Compare secure mode."],
    payloads=[LabPayload("Weak auth flag", "username=alice&weak_auth=1", "Controlled lab bypass."), LabPayload("Normal", "username=alice&password=training1", "Baseline verification.")],
    secure_comparison=["Password/token is verified.", "Weak flags are ignored.", "Failed attempts generate audit evidence."],
    backend_mapping={"API facade":"FIBS WEB9080 /login /webapi/auth/token","Identity store":"GACF.DB / CBSA.WEB_USERS","SMF":"SIMULATED SMF80 authentication event","Console":"GIBAUTH01I/GIBAUTH02W"},
    evidence_targets=["WEB9080 audit", "SIMULATED SMF80", "Master Console auth alert"],
    hints=["Authentication is about proving identity, not selecting a username.", "Look for optional flags or predictable tokens.", "Check SMF80-style evidence."],
    solution={"payload":"weak_auth=1","why":"The vulnerable path accepts a lab bypass flag.","expected_vulnerable":"Login/token accepted with weak controls.","expected_secure":"Password/token verification required.","remediation":"Centralize auth, remove lab bypasses, rate-limit and log failures."},
    remediation=["Require verified credentials.", "Remove username-only paths.", "Monitor authentication failures and token anomalies."],
    knowledge_checks=_kc("/login or /webapi/auth/token", "GACF.DB / SAF-like decision", "SIMULATED SMF80"),
))

_add(LabDefinition(
    slug="verbose-errors",
    title="Verbose Errors",
    category="Information Disclosure",
    severity="Medium",
    summary="Trigger a controlled backend error and compare raw Db2/CICS detail leakage with safe correlation-ID handling.",
    learner_level="Foundation",
    estimated_time="15 minutes",
    learning_objectives=["Identify dangerous backend error details.", "Explain safe correlation IDs.", "Map leaked SQLCODE/TRAN/PROGRAM detail to defender logs."],
    prerequisites=["Open teller search or lab workbench"],
    mainframe_context="Verbose errors can reveal SQLCODEs, Db2 plans, package names, CICS transactions and program names. Those details belong in logs and trace evidence, not the browser response.",
    api_paths=["GET /webapi/teller/search?q='", "POST /webapi/labs/verbose-errors/run"],
    architecture_nodes=_base_nodes(),
    architecture_edges=_base_edges(),
    attack_steps=["Run a malformed quote payload.", "Inspect vulnerable raw backend details.", "Compare secure response containing only a correlation ID.", "Review full detail in audit/trace."],
    payloads=[LabPayload("Bare quote", "'", "Triggers controlled SQLCODE detail."), LabPayload("Bad field", "unknownField", "Simulates invalid backend field." )],
    secure_comparison=["Browser sees generic error.", "Full detail remains in server logs/evidence.", "Correlation ID links user-facing error to backend trace."],
    backend_mapping={"API facade":"FIBS WEB9080 vulnerable search/query","CICS transaction":"OMEN / INQCUST","Program":"INQCUST","Db2 plan":"FIBSWEB","Leaked values":"SQLCODE, SQLSTATE, TABLE, PLAN, TRAN, PROGRAM","SMF":"SIMULATED SMF102/110"},
    evidence_targets=["WEB9080 audit", "Trace timeline", "SIMULATED SMF102", "Master Console warning"],
    hints=["A single quote is often enough to trigger backend parsing errors.", "The safe response should include a correlation ID, not SQLCODE detail.", "Look for PLAN/TABLE/TRAN in the vulnerable result."],
    solution={"payload":"'","why":"Malformed input reaches the simulated backend error path.","expected_vulnerable":"SQLCODE/table/plan/program details shown.","expected_secure":"Generic error plus correlation ID.","remediation":"Centralize exception handling; log detail server-side only."},
    remediation=["Use generic errors.", "Return correlation IDs.", "Log backend details to CSMT/SYSVIEW/zSecure evidence only."],
    knowledge_checks=_kc("Malformed query/search", "Db2/CICS error handling", "Trace + Master Console"),
))

_add(LabDefinition(
    slug="business-logic",
    title="Business Logic",
    category="Transaction Integrity",
    severity="High",
    summary="Abuse transfer/payment rules such as negative amounts, overdraft bypass or source/destination tampering.",
    learner_level="Intermediate",
    estimated_time="25 minutes",
    learning_objectives=["Recognize logic flaws not found by simple input validation.", "Read before/after ledger state.", "Map payment flow to PROCTRAN and CICS/Db2 evidence."],
    prerequisites=["Login as customer or teller", "Understand account balances"],
    mainframe_context="Payment/transfer requests update CBSA.ACCOUNT and write CBSA.PROCTRAN. The lab shows why CICS/COBOL business rules must validate amounts, ownership and overdraft decisions server side.",
    api_paths=["POST /transfer", "POST /webapi/transfer"],
    architecture_nodes=_base_nodes(["PROCTRAN ledger"]),
    architecture_edges=_base_edges()+[("COBOL/service program","PROCTRAN ledger")],
    attack_steps=["Run a normal transfer.", "Run a negative amount or overdraft-bypass lab payload.", "Inspect before/after balances and PROCTRAN.", "Compare secure rejection."],
    payloads=[LabPayload("Negative transfer", "amount=-100.00&lab_business_logic=1", "Attempts to credit by debiting a negative value."), LabPayload("Overdraft bypass", "amount=999999.00&lab_business_logic=1", "Attempts to bypass available funds.")],
    secure_comparison=["Amount must be positive.", "Source ownership and available funds enforced.", "PROCTRAN only records valid business transactions."],
    backend_mapping={"API facade":"FIBS WEB9080 /transfer","CICS transaction":"PAYM / XFER","Program":"PAYMENT / TRANSFER","Db2 tables":"CBSA.ACCOUNT, CBSA.PROCTRAN","SQL":"UPDATE CBSA.ACCOUNT; INSERT CBSA.PROCTRAN","SMF":"SIMULATED SMF101 accounting and SMF110 CICS"},
    evidence_targets=["CBSA.PROCTRAN", "WEB9080 audit", "SIMULATED SMF101", "SIMULATED SMF110", "Master Console high-value alert"],
    hints=["The payload may be syntactically valid but economically impossible.", "Compare actual and available balances before/after.", "Look for PROCTRAN entries."],
    solution={"payload":"amount=-100.00&lab_business_logic=1","why":"The vulnerable logic applies transfer arithmetic without enforcing positive amount and ownership rules.","expected_vulnerable":"Ledger/balance changes or a training event records the attempted flaw.","expected_secure":"Request rejected before ledger update.","remediation":"Validate business invariants in the service/CICS layer, not just the UI."},
    remediation=["Use invariant checks.", "Validate ownership and funds server-side.", "Alert on anomalous transaction amounts."],
    knowledge_checks=_kc("POST /transfer", "PAYM/XFER and PROCTRAN", "SMF101/SMF110"),
))

_add(LabDefinition(
    slug="method-override",
    title="Method Override",
    category="API Routing",
    severity="Medium",
    summary="Abuse X-HTTP-Method-Override to route a request to an unsafe maintenance-style action.",
    learner_level="Intermediate",
    estimated_time="15 minutes",
    learning_objectives=["Understand method override risks.", "Map gateway method decisions to CICS routing.", "Review destructive-action evidence."],
    prerequisites=["Know HTTP methods and headers"],
    mainframe_context="API gateways sometimes translate web methods to backend actions. A native CICS web-service route or z/OS Connect operation must not honor unexpected method override headers for sensitive actions.",
    api_paths=["POST /webapi/accounts/{id} with X-HTTP-Method-Override: DELETE"],
    architecture_nodes=_base_nodes(["API method router"]),
    architecture_edges=_base_edges()+[("FIBS WEB9080","API method router"),("API method router","CICS transaction")],
    attack_steps=["Send a normal POST.", "Add X-HTTP-Method-Override: DELETE.", "Observe vulnerable routing decision.", "Compare secure block."],
    payloads=[LabPayload("Override DELETE", "X-HTTP-Method-Override: DELETE", "Attempts to force destructive method routing."), LabPayload("Normal POST", "POST", "Baseline safe method." )],
    secure_comparison=["Override ignored or rejected.", "Destructive routes require explicit server authorization.", "Event logged as method override attempt."],
    backend_mapping={"API facade":"FIBS WEB9080 method router","CICS transaction":"MAINT / ACCT","Program":"ACCOUNT_MAINT","Db2 tables":"CBSA.ACCOUNT","SMF":"SIMULATED SMF80/102","Console":"GIBAPI405W"},
    evidence_targets=["WEB9080 audit", "SIMULATED SMF102", "GIBAPI405W"],
    hints=["Look at headers, not only the URL.", "Would the UI normally expose DELETE?", "Secure mode should reject the override before CICS/Db2."],
    solution={"payload":"X-HTTP-Method-Override: DELETE","why":"The vulnerable route trusts a client-controlled override header.","expected_vulnerable":"Maintenance-style action/event is reached.","expected_secure":"Override is rejected.","remediation":"Disable override headers or strictly allowlist them on safe routes."},
    remediation=["Reject override headers by default.", "Require explicit authz for destructive actions.", "Alert on method override usage."],
    knowledge_checks=_kc("X-HTTP-Method-Override", "API router to CICS MAINT/ACCT", "GIBAPI405W / SMF102"),
))

_add(LabDefinition(
    slug="excessive-data",
    title="Excessive Data Exposure",
    category="API Response Design",
    severity="Medium",
    summary="Return backend-only fields such as role, internal status, risk score, Db2 table and CICS program details.",
    learner_level="Foundation",
    estimated_time="15 minutes",
    learning_objectives=["Identify fields the UI does not need.", "Explain response filtering.", "Understand why mainframe records often contain rich internal metadata."],
    prerequisites=["Login as customer or teller"],
    mainframe_context="Mainframe data structures often carry operational fields beyond what a mobile/web UI requires. The API must shape responses deliberately rather than dumping backend rows.",
    api_paths=["GET /webapi/debug/customer/{customer_id}", "POST /webapi/labs/excessive-data/run"],
    architecture_nodes=_base_nodes(["Response filter"]),
    architecture_edges=_base_edges()+[("Db2 tables","Response filter"),("Response filter","FIBS WEB9080")],
    attack_steps=["Request a normal customer profile.", "Request the debug/excessive endpoint.", "Compare returned fields.", "Run secure comparison with redaction."],
    payloads=[LabPayload("Debug customer", "1001", "Returns controlled internal fields in vulnerable mode."), LabPayload("Normal profile", "profile", "Only UI-required fields." )],
    secure_comparison=["Only necessary fields returned.", "Internal status, role, risk and backend identifiers are redacted.", "Raw Db2 rows remain server side."],
    backend_mapping={"API facade":"FIBS WEB9080 /webapi/debug/customer/{id}","Db2 tables":"CBSA.CUSTOMER, CBSA.ACCOUNT, CBSA.WEB_USERS","Internal fields":"risk_score, internal_status, role, racf_group, cics_program, db2_table","SMF":"SIMULATED SMF101/80"},
    evidence_targets=["WEB9080 audit", "Trace event", "Master Console information event"],
    hints=["Ask whether each returned field is needed by the page.", "Backend identifiers help attackers chain attacks.", "Secure mode should shape the response."],
    solution={"payload":"GET /webapi/debug/customer/1001","why":"The vulnerable endpoint returns backend/internal fields directly.","expected_vulnerable":"Extra operational/security fields exposed.","expected_secure":"Redacted response.","remediation":"Use response DTOs and field-level authorization."},
    remediation=["Use explicit response models.", "Redact internal fields.", "Monitor debug endpoint usage."],
    knowledge_checks=_kc("/webapi/debug/customer/{id}", "Db2 row shaping / response filter", "WEB9080 audit"),
))

_add(LabDefinition(
    slug="jwt",
    title="JWT Security",
    category="Identity and API Authorization",
    severity="High",
    summary="Manipulate JWT headers and claims to demonstrate algorithm, key, issuer, audience, expiry and role validation failures.",
    learner_level="Advanced",
    estimated_time="30 minutes",
    learning_objectives=["Decode JWT structure.", "Explain signature, issuer, audience and expiry validation.", "Show how token flaws can expose CICS/Db2-backed APIs."],
    prerequisites=["Understand bearer tokens", "Open /labs/oauth for OIDC context if needed"],
    mainframe_context="JWT validation happens before the API call reaches CBSA/CICS/Db2. If the identity layer trusts forged claims, a request can be incorrectly authorized to mainframe-backed data and transactions.",
    api_paths=["POST /webapi/labs/jwt/forge", "POST /webapi/auth/introspect"],
    architecture_nodes=_base_nodes(["JWT validator", "GACF.DB / WEB_USERS"]),
    architecture_edges=[("Browser / curl","FIBS WEB9080"),("FIBS WEB9080","JWT validator"),("JWT validator","GACF.DB / WEB_USERS"),("JWT validator","CICS transaction"),("JWT validator","SMF"),("SMF","Master Console")],
    attack_steps=["Run a normal token validation.", "Run alg=none or role-tamper lab.", "Inspect claims and SMF80 evidence.", "Compare secure rejection."],
    payloads=[LabPayload("alg=none", "lab=alg_none&sub=alice&role=admin", "Unsigned token accepted only in vulnerable lab."), LabPayload("Role tamper", "lab=role_tamper&role=admin", "Attempts to trust role claim."), LabPayload("Wrong audience", "lab=wrong_aud", "Audience validation failure."), LabPayload("kid confusion", "lab=kid_confusion", "Controlled key-selection weakness without filesystem access." )],
    secure_comparison=["Algorithm allowlist enforced.", "Signature, iss, aud and exp verified.", "Role comes from GACF/WEB_USERS server-side."],
    backend_mapping={"API facade":"FIBS WEB9080 JWT lab","Identity":"JWT validator + GACF.DB / WEB_USERS","Downstream":"CBSA API/CICS/Db2 only after token acceptance","SMF":"SIMULATED SMF80 security event","Console":"GIBAUTH02W JWT TRAINING TOKEN"},
    evidence_targets=["WEB9080 audit", "Trace event", "SIMULATED SMF80", "Master Console GIBAUTH"],
    hints=["Decode the header first.", "Claims are not trustworthy without a verified signature and expected issuer/audience.", "Role claims should be mapped to server-side authorization."],
    solution={"payload":"alg=none with role=admin","why":"The vulnerable lab accepts an unsigned or weakly validated token.","expected_vulnerable":"Token accepted and SMF80 warning emitted.","expected_secure":"Token rejected before CBSA/CICS/Db2 access.","remediation":"Enforce algorithm allowlist, validate signature/iss/aud/exp and load roles server side."},
    remediation=["Use strict JWT validation.", "Reject alg=none.", "Whitelist kid values without filesystem reads.", "Do not trust role claims for privilege."],
    knowledge_checks=_kc("/webapi/labs/jwt/forge", "JWT validator before CBSA/CICS", "SIMULATED SMF80 / GIBAUTH"),
))

_add(LabDefinition(
    slug="oauth",
    title="OAuth/OIDC Security",
    category="Identity Federation",
    severity="High",
    summary="Exercise local OAuth/OIDC weaknesses such as missing PKCE, missing state, loose redirect_uri, scope abuse and refresh-token reuse.",
    learner_level="Advanced",
    estimated_time="35 minutes",
    learning_objectives=["Trace Authorization Code + PKCE flow.", "Explain state, nonce and exact redirect validation.", "Map identity failures to API/mainframe access decisions."],
    prerequisites=["Understand HTTP redirects and tokens", "Review JWT lab"],
    mainframe_context="OAuth/OIDC controls protect the API boundary before z/OS Connect-style or CICS-native APIs access CBSA data. The simulator keeps all identity flows local and emits SMF80-style evidence for suspicious auth events.",
    api_paths=["GET /.well-known/openid-configuration", "GET /oauth/authorize", "POST /oauth/token", "POST /webapi/labs/oauth/authorize"],
    architecture_nodes=_base_nodes(["OAuth authorization server", "OIDC claims", "JWKS"]),
    architecture_edges=[("Browser / curl","OAuth authorization server"),("OAuth authorization server","OIDC claims"),("OAuth authorization server","JWKS"),("OAuth authorization server","FIBS WEB9080"),("FIBS WEB9080","CICS transaction"),("OAuth authorization server","SMF"),("SMF","Master Console")],
    attack_steps=["Open discovery/JWKS.", "Run a normal authorization-code style request.", "Run loose redirect or missing PKCE lab.", "Compare secure rejection and evidence."],
    payloads=[LabPayload("Loose redirect", "redirect_uri=http://evil.example/callback", "Accepted only in vulnerable lab."), LabPayload("Missing state", "state=", "CSRF-style auth-flow weakness."), LabPayload("Missing PKCE", "code_verifier=", "Code interception weakness."), LabPayload("Scope abuse", "scope=openid admin", "Attempts to escalate API scope."), LabPayload("Refresh reuse", "reuse_refresh_token=1", "Reuse accepted only in vulnerable lab." )],
    secure_comparison=["Exact redirect URI required.", "state and nonce required.", "PKCE verifier/challenge enforced.", "Scopes constrained to registered client/user.", "Refresh reuse detected."],
    backend_mapping={"API facade":"FIBS WEB9080 OAuth/OIDC endpoints","Identity":"Local OAuth authorization server, JWKS, OIDC claims","Client":"fibs-web","Downstream":"CBSA API only after token acceptance","SMF":"SIMULATED SMF80 security event","Console":"GIBAUTH03W OAUTH TRAINING EVENT"},
    evidence_targets=["WEB9080 audit", "Trace event", "SIMULATED SMF80", "Master Console GIBAUTH"],
    hints=["Start with redirect_uri and state.", "Public clients need PKCE.", "The secure comparison should reject before a token is issued."],
    solution={"payload":"redirect_uri=http://evil.example/callback&scope=openid admin","why":"The vulnerable lab accepts loose redirect/scope values.","expected_vulnerable":"Authorization/token step accepted with warning evidence.","expected_secure":"Request rejected due to redirect/state/PKCE/scope controls.","remediation":"Use exact redirect matching, PKCE, state/nonce and strict scope registration."},
    remediation=["Require PKCE for browser/public flows.", "Validate state and nonce.", "Exact-match redirect_uri.", "Constrain scopes and rotate refresh tokens."],
    knowledge_checks=_kc("/oauth/authorize and /oauth/token", "OAuth server before CBSA/CICS", "SIMULATED SMF80 / GIBAUTH"),
))

# --- Operation CICS Academy enrichment -------------------------------------
_BEGINNER_DEFAULTS = {
    "sqli": ("SQL injection happens when user input changes the structure of a database query instead of being treated as data.", "It can expose or change data across customer/account tables and leaves Db2 audit evidence."),
    "idor": ("IDOR/BOLA happens when an API returns an object by ID without proving the logged-in user is allowed to access that object.", "Db2 may return a valid row, but the API/CICS service must still enforce ownership."),
    "mass-assignment": ("Mass assignment happens when the server accepts extra request fields and writes them into sensitive properties.", "Attackers can try to set role, admin or limit fields that the UI never intended to expose."),
    "weak-auth": ("Weak authentication accepts a user or token without strong proof of identity.", "A mainframe-backed application must not let API flags bypass GACF/RACF-style controls."),
    "verbose-errors": ("Verbose errors reveal backend implementation details such as SQLCODE, table names, plans or CICS programs.", "Attackers use these details to build better payloads and map the estate."),
    "business-logic": ("Business logic flaws abuse valid functions in invalid ways, such as negative transfers or overdraft bypass.", "The API, CICS program and Db2 update path must enforce business rules server-side."),
    "method-override": ("Method override flaws let headers such as X-HTTP-Method-Override change the intended operation.", "A gateway or API facade can accidentally route a safe request to a destructive backend action."),
    "excessive-data": ("Excessive data exposure happens when APIs return internal fields the UI does not need.", "Mainframe records often contain operational, security and routing data that must be filtered."),
    "jwt": ("JWT security failures occur when tokens are not strictly validated for signature, algorithm, issuer, audience and expiry.", "Forged claims can grant access to CICS/Db2-backed APIs before the mainframe even sees the request."),
    "oauth": ("OAuth/OIDC flaws happen when redirect, state, PKCE, scope or refresh-token checks are weak.", "A weak identity flow can issue tokens that unlock protected banking APIs."),
}
_GLOSSARY = {
    "API": "A programmatic interface used by the browser or curl to call banking functions.",
    "z/OS Connect": "A REST API facade pattern for exposing z/OS applications and data.",
    "CICS transaction": "A named unit of work such as OMEN, INQACC or BOFL that runs application logic.",
    "COBOL program": "The business program behind a CICS transaction.",
    "Db2 table": "The backend relational table holding customer, account, audit or transaction data.",
    "SMF": "System Management Facilities-style evidence; Gibson marks these records as SIMULATED.",
    "CSMT": "CICS message log where operational/security messages can be reviewed.",
}


def _enrich_labs() -> None:
    for slug, lab in list(LABS.items()):
        exp, why = _BEGINNER_DEFAULTS.get(slug, (lab.summary, "It matters because API flaws can reach CICS, Db2 and identity controls."))
        object.__setattr__(lab, "beginner_explanation", lab.beginner_explanation or exp)
        object.__setattr__(lab, "why_it_matters", lab.why_it_matters or why)
        object.__setattr__(lab, "attacker_goal", lab.attacker_goal or "Change the request so the vulnerable path produces a result that secure mode should block.")
        object.__setattr__(lab, "defender_view", lab.defender_view or "Use validation, authorization, monitoring and simulated SMF/Master Console evidence to detect and contain the issue.")
        object.__setattr__(lab, "glossary", lab.glossary or dict(_GLOSSARY))
        object.__setattr__(lab, "instructor_notes", lab.instructor_notes or ["Start with the normal request before showing the vulnerable payload.", "Ask learners to identify which layer should have blocked the attack.", "Review the evidence ID, trace timeline and simulated SMF/CSMT records."])


_add(LabDefinition(
    slug="cobol-buffer-overflow",
    title="COBOL/CICS Buffer Overflow",
    category="CICS / COBOL / Memory Safety",
    severity="Critical",
    summary="Simulate fixed-buffer overflow effects in a COBOL/CICS banking program without causing real memory corruption.",
    learner_level="Advanced",
    estimated_time="35 minutes",
    learning_objectives=["Explain fixed-size COBOL field risk.", "Understand adjacent flag overwrite simulations.", "Recognize ASRA/S0C4-style operational evidence.", "Apply safe CICS channel/container length handling."],
    prerequisites=["Review DVCA/hack3270 hidden fields", "Understand CICS transactions and COBOL working-storage"],
    mainframe_context="The lab models a CICS transaction BOFL/BANKBO running VULNERABLE-BANK-UPDATE. Oversized fields alter simulated adjacent flags or trigger a simulated ASRA/S0C4 abend. No real memory corruption is performed.",
    api_paths=["POST /webapi/labs/cobol-buffer-overflow/run", "CICS TRAN=BOFL PROGRAM=VULNERABLE-BANK-UPDATE"],
    architecture_nodes=_base_nodes(["COBOL overflow simulator", "CSMT"]),
    architecture_edges=_base_edges()+[("CICS transaction", "COBOL overflow simulator"),("COBOL overflow simulator", "SMF"),("COBOL overflow simulator", "CSMT")],
    attack_steps=["Run a normal payload.", "Run an auth flag overwrite payload.", "Run a crash payload.", "Review CSMT, SMF110 and Master Console evidence.", "Compare secure validation."],
    payloads=[LabPayload("Normal", "ALICE-TRANSFER-0001", "Baseline safe request."), LabPayload("Auth flag overwrite", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY", "Simulates adjacent AUTH/ADMIN flag overwrite."), LabPayload("Sort-code overflow", "123456789", "Simulates field-length overflow."), LabPayload("Crash payload", "1234567890ABCDEF", "Simulates ASRA/S0C4 abend."), LabPayload("Channel overflow", "USERDATA=" + ("A"*160), "Simulates oversized CICS channel/container input." )],
    secure_comparison=["Length checks reject oversized input.", "Flags remain server-controlled.", "MAXFLENGTH-style container validation blocks oversized payloads."],
    backend_mapping={"API facade":"FIBS WEB9080 /webapi/labs/cobol-buffer-overflow/run","CICS transaction":"BOFL / BANKBO","Program":"VULNERABLE-BANK-UPDATE / VULNBO","CICS channel":"BANKCHAN USERDATA container","Db2 tables":"CBSA.WEB_AUDIT, CBSA.VULN_EVENTS, CBSA.PROCTRAN","SMF":"SIMULATED SMF110 CICS exception; SIMULATED SMF80 auth event","Console":"DFHAC2206W/GIBBOF01W training alerts"},
    evidence_targets=["WEB9080 audit", "CBSA.VULN_EVENTS", "CSMT", "SIMULATED SMF110", "SIMULATED SMF80", "Master Console"],
    hints=["Look at field lengths and adjacent flags.", "A payload ending in Y can simulate flipping an authorization flag.", "Secure mode should reject the input before any flag changes."],
    solution={"payload":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY","why":"The vulnerable simulator treats excess bytes as if they overwrote adjacent control flags.","expected_vulnerable":"AUTHENTICATED-FLAG or ADMIN-FLAG becomes Y and SMF80/110 evidence is emitted.","expected_secure":"Length validation blocks the payload and records defensive evidence.","remediation":"Validate lengths, separate sensitive flags from input buffers, use SSRANGE, MAXFLENGTH and server-side authorization."},
    remediation=["Check input length before MOVE.", "Use safe CICS container length handling.", "Keep security flags away from user-controlled buffers.", "Do not expose debug dumps.", "Compile/test with bounds checking where appropriate."],
    knowledge_checks=_kc("/webapi/labs/cobol-buffer-overflow/run", "CICS BOFL/BANKBO and VULNERABLE-BANK-UPDATE", "SIMULATED SMF110 / CSMT / Master Console"),
    references=["COBOL fixed-size field training", "CICS channel/container safe handling"],
    beginner_explanation="A buffer overflow happens when more data is accepted than a fixed-size field was designed to hold. In this safe simulator, oversized input deterministically flips simulated flags or triggers a simulated abend instead of corrupting real memory.",
    why_it_matters="In CICS/COBOL systems, field-size mistakes can alter business decisions, bypass checks or cause operational outages such as ASRA/S0C4 abends.",
    attacker_goal="Send oversized data to change simulated authentication/admin/debug flags or trigger a controlled abend.",
    defender_view="Validate lengths before moving data, check CSMT/SMF evidence, and prevent debug/memory output from reaching users.",
    glossary=_GLOSSARY,
    instructor_notes=["Emphasize that Gibson does not perform real memory corruption.", "Show the COBOL source layout before running the exploit.", "Review the difference between auth bypass and crash payloads."],
))

_enrich_labs()


# --- Identity and Access labs (PassTicket + MFA) -------------------------
def _identity_lab(slug: str, title: str, summary: str, objectives: list[str], payloads: list[LabPayload]) -> LabDefinition:
    is_ptkt = slug.startswith("passticket")
    category = "Identity and Access / RACF PassTickets" if is_ptkt else "Identity and Access / MFA and Step-Up Authentication"
    sev = "High" if any(x in slug for x in ["bypass","overbroad","leakage","service-gap","fallback"]) else "Medium"
    nodes = _base_nodes(["RACF", "PTKTDATA", "IRRPTAUTH", "MFA Policy", "Identity Evidence"])
    edges = _base_edges() + [("FIBS WEB9080", "RACF"), ("RACF", "PTKTDATA"), ("RACF", "MFA Policy"), ("MFA Policy", "Identity Evidence"), ("PTKTDATA", "Identity Evidence")]
    backend = {
        "API facade": "FIBS WEB9080 Identity and Access Academy",
        "RACF": "RACF/PassTicket/MFA simulator state",
        "PTKTDATA": "TSO, TSOGIBS, CICS, DB2, WEBBANK",
        "IRRPTAUTH": "IRRPTAUTH.CICS.*, IRRPTAUTH.TSO.*, IRRPTAUTH.DB2.*",
        "CICS transaction": "CESN / GMVB where relevant",
        "Program": "IDENTITYLAB / PTKTLAB / MFALAB",
        "Db2 tables": "GIBSON.PTKT_PROFILES, GIBSON.PASSTICKETS, GIBSON.PTKT_AUDIT",
        "SMF": "SIMULATED SMF80 identity/security events",
        "Console": "GIBID001W high-severity identity event when relevant",
    }
    return LabDefinition(
        slug=slug,
        title=title,
        category=category,
        severity=sev,
        summary=summary,
        learner_level="Intermediate",
        estimated_time="20 minutes",
        learning_objectives=objectives,
        prerequisites=["Login to the Security Academy as teller/cics", "Review PTKTSTAT or MFA status where requested"],
        mainframe_context="This lab models z/OS/RACF identity behaviour in Gibson. It emits simulated SMF80, SDSF, zSecure, dashboard and master-console evidence where appropriate.",
        api_paths=[f"POST /webapi/labs/{slug}/run", f"POST /webapi/labs/{slug}/secure-compare"],
        architecture_nodes=nodes,
        architecture_edges=edges,
        attack_steps=["Run the vulnerable lab action.", "Inspect the request/response and backend evidence.", "Run secure comparison.", "Reset and repeat from the terminal command equivalent if desired."],
        payloads=payloads,
        secure_comparison=["Apply least privilege and service-specific policy.", "Generate structured identity evidence.", "Reset lab state after validation."],
        backend_mapping=backend,
        evidence_targets=["WEB9080 trace", "SIMULATED SMF80", "SDSF/OPERLOG", "zSecure-style finding", "Master Console/Dashboard for high severity"],
        hints=["Look for the RACF class/profile involved.", "Compare vulnerable and secure evidence.", "Use the terminal command equivalent to reinforce the browser lab."],
        solution={"payload": payloads[0].value if payloads else "", "why": summary, "expected_vulnerable": "Identity risk is demonstrated and evidence is generated.", "expected_secure": "Secure comparison enforces the intended control.", "remediation": "Constrain authority, enforce MFA where appropriate and audit high-risk identity events."},
        remediation=["Use strict APPL binding.", "Keep replay protection enabled.", "Narrow IRRPTAUTH permissions.", "Require MFA context for sensitive middle-tier generation.", "Audit and alert on bypass/fallback events."],
        knowledge_checks=[{"question":"Which evidence type should be reviewed?","answer":"SMF80/SDSF/zSecure identity evidence"},{"question":"Which RACF area is most relevant?","answer":"PTKTDATA/IRRPTAUTH or MFA policy, depending on the lab"}],
        references=["IBM z/OS Security Server RACF", "IBM Multi-Factor Authentication for z/OS", "Gibson Identity Academy"],
        beginner_explanation="The lab is a safe simulator exercise: no real PassTickets or MFA providers are contacted.",
        why_it_matters="Identity controls are a common bridge between web, CICS, TSO, Db2 and privileged administration.",
        attacker_goal="Find weak identity configuration that turns a valid login, token or fallback into broader access.",
        defender_view="Review RACF profiles, MFA policy, SMF80 evidence and high-severity console/dashboard alerts.",
        glossary={"PassTicket":"A short-lived RACF one-time password alternative bound to an application ID.", "PTKTDATA":"RACF class used to define PassTicket application data.", "IRRPTAUTH":"RACF profile family controlling who can generate PassTickets.", "MFA":"Multi-factor authentication; a second proof beyond a password.", "CICS transaction":"A named CICS unit of work that runs a program or service in the simulator."},
        instructor_notes=["Use terminal equivalents after the browser lab.", "Stress that this is a safe Gibson simulation.", "Ask learners to compare web, TSO, CICS and zSecure evidence for the same event."],
    )


def _add_identity_labs() -> None:
    labs = [
        ("passticket-concepts", "PassTicket Concepts and Discovery", "Inspect PTKTDATA, replay protection, APPL binding, IRRPTAUTH and audit concepts.", ["Identify PTKTDATA profiles.", "Explain replay and APPL binding.", "Locate evidence."], [LabPayload("Discovery", "PTKTSTAT", "Show live PassTicket profile state.")]),
        ("passticket-generate-validate", "Generate and Validate a PassTicket", "Generate a CICS PassTicket and validate it once.", ["Generate a token.", "Validate it.", "Review audit evidence."], [LabPayload("CICS ticket", "USER=IBMUSER&APPL=CICS", "Generate and validate APPL(CICS).")]),
        ("passticket-cics-cesn", "CICS CESN PassTicket Sign-on", "Use a CICS-bound PassTicket for CESN sign-on.", ["Bind token to CICS.", "Use CESN PTKT syntax.", "Review CICS/RACF evidence."], [LabPayload("CESN", "CESN USER(IBMUSER) PTKT(ticket) APPL(CICS)", "CICS sign-on equivalent.")]),
        ("passticket-gmvb-banking", "GMVB Banking PassTicket Sign-on", "Use PassTicket authentication against the GMVB banking training transaction.", ["Generate CICS token.", "Log on to GMVB.", "Review banking trace."], [LabPayload("GMVB", "GMVB LOGN IBMUSER PTKT ticket CICS", "GMVB logon equivalent.")]),
        ("passticket-tso-logon", "TSO PassTicket Logon", "Model TSO logon using PTKT(ticket) or PASSTICKET ticket.", ["Generate TSO token.", "Understand TSOGIBS strict mode.", "Review logon audit."], [LabPayload("TSO", "USER=IBMUSER&APPL=TSO", "TSO logon equivalent.")]),
        ("passticket-db2-evidence", "Db2 PassTicket Evidence", "Review PassTicket profile, issued ticket and audit rows through Db2-style evidence.", ["Query profiles.", "Query issued tickets.", "Query audit."], [LabPayload("Db2 evidence", "RUN SQL SELECT * FROM GIBSON.PTKT_AUDIT", "Evidence query.")]),
        ("passticket-replay-protection", "PassTicket Replay Protection", "Use one token twice and observe replay denial.", ["Demonstrate one-use behaviour.", "Explain replay protection.", "Compare insecure mode."], [LabPayload("Replay", "USE_TWICE=YES", "Attempt to reuse a ticket.")]),
        ("passticket-applid-mismatch", "PassTicket APPLID Mismatch", "Generate for one APPLID and attempt use against another.", ["Explain APPL binding.", "Observe mismatch denial.", "Compare loose binding."], [LabPayload("Mismatch", "GENERATE=CICS&USE=DB2", "Cross-APPL use attempt.")]),
        ("passticket-overbroad-irrptauth", "Overbroad IRRPTAUTH", "Show a middle-tier identity with excessive PassTicket generation authority.", ["Inspect IRRPTAUTH.", "Detect broad authority.", "Narrow permissions."], [LabPayload("WEBBANK", "REQUESTER=WEBBANK&APPL=CICS", "Middle-tier generation.")]),
        ("passticket-debug-leakage", "PassTicket Debug Leakage", "Demonstrate how debug logging can expose short-lived tokens inside controlled lab evidence.", ["Enable lab-only leakage.", "Find the leaked secret in evidence.", "Disable logging."], [LabPayload("Leak", "LABLEAK=YES", "Controlled evidence leakage.")]),
        ("passticket-expiry", "Expired PassTicket", "Simulate token expiry and failed validation.", ["Generate token.", "Advance simulator clock.", "Observe expiry denial."], [LabPayload("Expire", "VALIDSECS=1&SIMULATE_EXPIRE=YES", "Deterministic expiry.")]),
        ("passticket-hardening", "PassTicket Hardening", "Apply replay protection, strict APPL binding, narrow IRRPTAUTH and no secret logging.", ["Review weak settings.", "Apply hardening.", "Verify evidence."], [LabPayload("Harden", "HARDEN=YES", "Apply secure baseline.")]),
        ("mfa-concepts-zos", "MFA Concepts on z/OS", "Introduce Gibson's deterministic z/OS MFA policy model.", ["Explain MFA policy.", "Review services.", "Inspect evidence."], [LabPayload("MFA status", "SERVICE=TSO", "Display service MFA requirements.")]),
        ("mfa-tso-enforcement", "TSO MFA Enforcement", "Require MFA for TSO and compare password-only with password-plus-factor.", ["Require MFA.", "Deny missing factor.", "Allow valid factor."], [LabPayload("TSO MFA", "USER=RUARIV&SERVICE=TSO&TOKEN=222222", "Valid deterministic token.")]),
        ("mfa-cics-step-up", "CICS Step-Up Authentication", "Require a factor before a sensitive CICS transaction.", ["Identify sensitive transaction.", "Deny missing factor.", "Allow valid step-up."], [LabPayload("CICS step-up", "USER=TELLER&SERVICE=CICS&TRAN=GMVB.ADMIN&TOKEN=333333", "Step-up transaction.")]),
        ("mfa-service-gap-ftp", "MFA Service Gap: FTP", "Show risk when TSO requires MFA but FTP remains password-only.", ["Compare service policy.", "Detect gap.", "Apply consistent enforcement."], [LabPayload("FTP gap", "SERVICE=FTP&USER=RUARIV", "FTP without MFA.")]),
        ("mfa-fallback-breakglass", "Fallback and Break-Glass Misuse", "Detect overbroad fallback or break-glass use.", ["Use fallback.", "Generate alert.", "Restrict and monitor."], [LabPayload("Breakglass", "USER=IBMUSER&BREAKGLASS=YES", "Break-glass event.")]),
        ("mfa-shared-factor-seed", "Shared MFA Factor Seed", "Detect multiple users sharing a simulator MFA seed.", ["Find shared seed.", "Report finding.", "Assign unique factors."], [LabPayload("Shared seed", "USERS=RUARIV,TELLER&SEED=222222", "Shared factor seed.")]),
        ("mfa-passticket-bypass", "PassTicket Issued Without MFA Context", "Show a middle tier issuing a PassTicket after weak or non-MFA authentication.", ["Generate without MFA context.", "Detect bypass.", "Require MFA context."], [LabPayload("Bypass", "REQUESTER=WEBBANK&USER=RUARIV&APPL=CICS&MFA_CONTEXT=NO", "Trusted middle-tier risk.")]),
        ("mfa-fatigue-concept", "MFA Fatigue Concept", "Safe conceptual lab that models repeated prompts as events, without real push notifications.", ["Recognize prompt fatigue risk.", "Review events.", "Apply policy controls."], [LabPayload("Prompts", "PROMPTS=5", "Simulated repeated prompts.")]),
        ("mfa-audit-review", "MFA Audit Review", "Review MFA events across SMF/SDSF/zSecure/dashboard evidence.", ["Collect events.", "Correlate IDs.", "Report findings."], [LabPayload("Audit", "REVIEW=YES", "MFA evidence review.")]),
        ("mfa-hardening", "MFA Hardening", "Enforce MFA consistently, remove fallback misuse and require MFA context for PassTicket generation.", ["Apply policy.", "Verify enforcement.", "Review zSecure finding cleared."], [LabPayload("Harden MFA", "HARDEN=YES", "Secure MFA baseline.")]),
    ]
    for slug,title,summary,obj,payloads in labs:
        _add(_identity_lab(slug,title,summary,obj,payloads))

_add_identity_labs()


def list_labs() -> list[LabDefinition]:
    return list(LABS.values())


def get_lab(slug: str) -> LabDefinition | None:
    return LABS.get(slug)
