/**
 * Instructor-only solution walkthroughs for each Vulnerability Challenge.
 * Keyed by scenario ID.
 */

export const SOLUTIONS = {
  'VULN-01': {
    summary: 'A ghost employee account was created using default vendor credentials (DVCA/DVCA) outside of business hours with no supervisor dual-authorisation. A single large salary-style credit was immediately posted.',
    steps: [
      {
        step: 1,
        title: 'Identify the rogue customer record',
        query: 'SELECT * FROM Customer WHERE operator_id = "DVCA"',
        explanation: 'The fraudulent customer GHOST001 was created by operator DVCA — a default vendor account that should have been disabled. Note the placeholder NI number (000000099) and address "NO FIXED ABODE".',
        finding: 'Customer GHOST001 — GHOST, EMPLOYEE — created 20/05/26 by DVCA',
      },
      {
        step: 2,
        title: 'Find the fraudulent account',
        query: 'SELECT * FROM Account WHERE customer_id = "GHOST001"',
        explanation: 'Account 9999999901 was opened with a zero credit limit and no interest rate — consistent with a staging account, not a genuine retail product. Balance of £47,500 with no prior history.',
        finding: 'Account 9999999901 — CUR — Balance: £47,500.00 — Operator: DVCA',
      },
      {
        step: 3,
        title: 'Find the fraudulent transaction',
        query: 'SELECT * FROM Transaction WHERE account_number = "9999999901"',
        explanation: 'A single CR of £47,500 described as "PAYROLL ADJUSTMENT" was posted at 02:15 — well outside normal business hours. The reference PAYADJ01 does not correspond to any authorised payroll batch.',
        finding: 'TFRAUD001 — CR £47,500.00 — PAYROLL ADJUSTMENT — 02:15 — DVCA',
      },
      {
        step: 4,
        title: 'Confirm all operator DVCA activity',
        query: 'SELECT * FROM Account WHERE operator_id = "DVCA"',
        explanation: 'Any additional accounts opened by DVCA should be flagged for immediate review. The control failure is that default vendor credentials were never disabled and carry ADMIN privileges allowing account creation.',
        finding: 'Control gap: No password rotation policy; default credentials active in PROD.',
      },
    ],
    rootCause: 'Default vendor account DVCA/DVCA was never disabled after system installation. No dual-authorisation control exists for new account creation. No after-hours transaction alerting.',
    remediation: [
      'Immediately disable all default vendor accounts (DVCA, CICS, BATCH, TEST) in production.',
      'Implement dual-authorisation for new customer/account creation above a value threshold.',
      'Add after-hours transaction monitoring and alerting for amounts > £10,000.',
      'Enforce NI number validation — reject 000000000 as a placeholder.',
    ],
  },

  'VULN-02': {
    summary: 'The transaction posting program (TRANPST) does not check account status before allowing postings. Credits were applied to two dormant (D-status) accounts by operator TEST.',
    steps: [
      {
        step: 1,
        title: 'List all dormant accounts',
        query: 'SELECT * FROM Account WHERE status = "D"',
        explanation: 'This returns all accounts with D (Dormant) status. In a correctly controlled system, no transactions should be postable to these accounts — the TRANPST program should reject them at the status check.',
        finding: 'Accounts 2000000001 and 2000000002 are dormant, plus 1000000901 (FITZGERALD).',
      },
      {
        step: 2,
        title: 'Find transactions on dormant accounts',
        query: 'SELECT * FROM Transaction WHERE account_number = "2000000001"',
        explanation: 'Account 2000000001 has received a £8,200 credit posted by TEST at 03:12 — a dormant account that should have blocked all postings. Repeat for account 2000000002.',
        finding: 'TDORM001 — CR £8,200 to dormant 2000000001 — TEST — 03:12',
      },
      {
        step: 3,
        title: 'Check the second dormant account',
        query: 'SELECT * FROM Transaction WHERE account_number = "2000000002"',
        explanation: 'Account 2000000002 received £15,000 described as "REFUND POSTING" — dormant accounts by definition have no active relationship that could generate a legitimate refund.',
        finding: 'TDORM002 — CR £15,000 to dormant 2000000002 — TEST — 03:15',
      },
      {
        step: 4,
        title: 'Calculate total fraudulent credits',
        query: 'SELECT * FROM Transaction WHERE operator_id = "TEST"',
        explanation: 'Total fraudulent value: £8,200 + £15,000 = £23,200. Both posted in the same 3-minute window suggesting automated scripting. Operator TEST is a default test account that should not exist in production.',
        finding: 'Total: £23,200 posted to dormant accounts by TEST between 03:12–03:15.',
      },
    ],
    rootCause: 'TRANPST COBOL program does not include a WS-ACCT-STATUS check before posting. The EVALUATE WS-TRAN-TYPE block bypasses dormancy validation.',
    remediation: [
      'Add account status validation in TRANPST: IF WS-ACCT-STATUS = "D" PERFORM DORMANT-ERROR-RTN.',
      'Remove TEST, CICS, BATCH default credentials from production RACF.',
      'Implement anomaly detection for after-hours postings to long-inactive accounts.',
      'Add a "reactivation" workflow requiring manager approval before a dormant account can receive credits.',
    ],
  },

  'VULN-03': {
    summary: 'A BATCH job was modified to divert salary credits to a staging mule account (8888888801) before onward transfer. Three employees did not receive their salary. The BATCH operator has unrestricted transaction posting rights.',
    steps: [
      {
        step: 1,
        title: 'Confirm missing salary credits',
        query: 'SELECT * FROM Transaction WHERE account_number = "1000000101"',
        explanation: 'Account 1000000101 (HARRISON) shows no salary credit for May 2026 — the last salary was January 1987. Check accounts 1000000201 and 1000000401 similarly.',
        finding: 'No salary credit in 2026 for accounts 1000000101, 1000000201, 1000000401.',
      },
      {
        step: 2,
        title: 'Find the staging/mule account',
        query: 'SELECT * FROM Account WHERE operator_id = "BATCH"',
        explanation: 'Account 8888888801 was created by BATCH with customer GHOST001. This is the staging account. It has a zero opening balance and was created just before the fraudulent transactions.',
        finding: 'Account 8888888801 — CUR — created by BATCH — customer MULE, STAGING.',
      },
      {
        step: 3,
        title: 'Inspect the diverted transactions',
        query: 'SELECT * FROM Transaction WHERE account_number = "8888888801"',
        explanation: 'Three TRF transactions were posted to the staging account, each using salary reference codes (SAL8701, SAL8702). The to_account field shows the legitimate destination accounts — confirming the diversion path.',
        finding: 'TDIVERT01/02/03 — £1,200 + £2,500 + £850 = £4,550 diverted to 8888888801.',
      },
      {
        step: 4,
        title: 'Reconstruct the full BATCH activity',
        query: 'SELECT * FROM Transaction WHERE operator_id = "BATCH"',
        explanation: 'Reviewing all BATCH transactions reveals the pattern: legitimate salaries in previous months, then the three diverted TRF records in May 2026 using the same reference numbers. The reference reuse is the key indicator.',
        finding: 'Reference SAL8701 appears on both legitimate and fraudulent transactions — clear signature of the attack.',
      },
    ],
    rootCause: 'BATCH operator credentials have unrestricted WRITE access to both Account and Transaction tables with no independent review. Salary job scripts are not digitally signed or integrity-checked before execution.',
    remediation: [
      'Implement four-eyes principle for all BATCH payroll jobs — output files must be signed by two operators.',
      'Restrict BATCH operator to INSERT only on Transaction — no ability to CREATE accounts.',
      'Monitor for TRF transactions where from-account customer_id != to-account customer_id.',
      'Alert when the same payment reference is used more than once.',
    ],
  },

  'VULN-04': {
    summary: 'Operator TEST accessed CECI without authentication and issued two SQL injection queries against Customer and Account tables, exfiltrating all 12 customer PII records and 18 account records using OR 1=1 and UNION-based techniques.',
    steps: [
      {
        step: 1,
        title: 'Locate the injection events in AuditLog',
        query: 'SELECT * FROM AuditLog WHERE operator_id = "TEST"',
        explanation: 'The AuditLog shows a NAVIGATION event (CECI access) followed immediately by two SQL_QUERY events with injected payloads. The sequence took under 2 minutes — automated tooling is likely.',
        finding: 'Three events: NAVIGATION → SQL_QUERY (Customer) → SQL_QUERY (Account) — all by TEST.',
      },
      {
        step: 2,
        title: 'Analyse the first injection payload',
        query: 'SELECT * FROM AuditLog WHERE event_type = "SQL_QUERY"',
        explanation: "The payload \"WHERE surname = 'x' OR '1'='1'\" bypasses the intended single-customer lookup and returns ALL rows. The UNION clause appended attempts to extract ni_number and dob fields specifically.",
        finding: '12 customer records returned — full PII dataset exposed including NI numbers and DOBs.',
      },
      {
        step: 3,
        title: 'Count PII records at risk',
        query: 'SELECT * FROM Customer WHERE ni_number != "000000000"',
        explanation: 'This returns all customers with real NI numbers (excluding corporate placeholders). These are the data subjects whose personal data was breached and who may be entitled to notification under data protection law.',
        finding: '10 genuine NI numbers exposed — data breach notification may be required.',
      },
      {
        step: 4,
        title: 'Confirm CECI has no auth check',
        query: 'SELECT * FROM AuditLog WHERE details LIKE "ACCESSED CECI"',
        explanation: 'The audit log explicitly records "NO AUTH CHECK PERFORMED" — confirming that CECI is accessible without CESN signon. This is Vulnerability #6 in the BANKMASTER/VS system.',
        finding: 'CECI accessible to unauthenticated users — root cause of the injection vector.',
      },
    ],
    rootCause: 'CUSTINQ COBOL uses EXEC SQL SELECT ... WHERE SURNAME = :WS-INPUT without parameterisation. Combined with unauthenticated CECI access, any terminal user can inject arbitrary SQL.',
    remediation: [
      'Parameterise all EXEC SQL statements: use host variables only, never string concatenation.',
      'Restrict CECI/CEDA to RACF-protected ADMIN role — require explicit CESN signon.',
      'Implement input validation: reject values containing SQL keywords (OR, UNION, SELECT, --).',
      'Enable DB2 audit plugin to log all SQL at database level independently of application.',
    ],
  },

  'VULN-05': {
    summary: 'The TRANPST program posts debit transactions without server-side validation of the credit_limit field. Account 3000000001 has a £1,000 limit but was debited to -£4,875.50 — a breach of £3,875.50.',
    steps: [
      {
        step: 1,
        title: 'Find the breached overdraft account',
        query: 'SELECT * FROM Account WHERE account_type = "OVD"',
        explanation: 'Account 3000000001 shows balance of -£4,875.50 against a credit_limit of £1,000. The balance is 4.875x the authorised limit. Status is still A (Active) — the system did not freeze it.',
        finding: 'Account 3000000001 — balance -£4,875.50 — limit £1,000 — breach: £3,875.50.',
      },
      {
        step: 2,
        title: 'Reconstruct the debit sequence',
        query: 'SELECT * FROM Transaction WHERE account_number = "3000000001"',
        explanation: 'Three DR transactions on 18–20 May 2026: £2,000 (ATM), £1,500 (POS), £1,033.35 (Online) — all posted by CJONES. Each transaction was individually within a "plausible" range, masking the cumulative breach.',
        finding: 'Three DRs totalling £4,533.35 posted over 3 days — no transaction was individually alarming.',
      },
      {
        step: 3,
        title: 'Confirm the limit was never enforced',
        query: 'SELECT * FROM Account WHERE balance < -1000',
        explanation: 'Any account with balance < -(credit_limit) represents a control failure. In a correctly implemented system, TRANPST should recalculate the available balance after each debit and reject if it would exceed the limit.',
        finding: 'At least one account with balance beyond limit — limit enforcement is absent.',
      },
      {
        step: 4,
        title: 'Identify the responsible operator',
        query: 'SELECT * FROM Transaction WHERE operator_id = "CJONES"',
        explanation: 'All three transactions were posted by CJONES. This may be staff-facilitated fraud or simply a system control gap exploited unintentionally. In either case, the system should have blocked the third transaction.',
        finding: 'CJONES posted all three debits — whether deliberate or exploiting the control gap requires investigation.',
      },
    ],
    rootCause: 'TRANPST COBOL does not include post-calculation limit check: COMPUTE WS-NEW-BAL = WS-CURR-BAL - WS-TRAN-AMT. The check IF WS-NEW-BAL < (WS-CREDIT-LIM * -1) PERFORM LIMIT-EXCEEDED-RTN is missing.',
    remediation: [
      'Add credit limit check in TRANPST after balance calculation: reject if new balance would exceed limit.',
      'Automatically set account status to F (Frozen) when credit limit is breached.',
      'Implement a daily sweep job to identify accounts beyond their authorised credit limit.',
      'Send real-time alerts to the account manager when balance exceeds 80% of credit limit.',
    ],
  },

  'VULN-06': {
    summary: 'Operator CICS (default credentials CICS/CICS) accessed CECI and ran 5 bulk SELECT queries in sequence, exfiltrating 51 records across Customer, Account, and Transaction tables in under 3 minutes. No row-limit DLP control exists.',
    steps: [
      {
        step: 1,
        title: 'Find the exfiltration sequence',
        query: 'SELECT * FROM AuditLog WHERE operator_id = "CICS"',
        explanation: 'The audit trail shows LOGIN → NAVIGATION (CECI) → 5 SQL_QUERY events in rapid succession. The systematic table-by-table approach (Customer → Account → Transaction → targeted NI query) is characteristic of deliberate data exfiltration.',
        finding: '6 audit events from CICS on terminal LT0099 — login at start of sequence.',
      },
      {
        step: 2,
        title: 'Count total records exposed',
        query: 'SELECT * FROM AuditLog WHERE event_type = "SQL_QUERY"',
        explanation: 'Row counts: Customer=12, Account=18, Transaction=21, NI targeted=10 (overlap with Customer). Total unique records exposed: ~51. The NI-targeted query confirms PII was the specific goal.',
        finding: '51 records across 3 tables — including 10 customers with real NI numbers.',
      },
      {
        step: 3,
        title: 'Confirm default credential use',
        query: 'SELECT * FROM AuditLog WHERE event_type = "LOGIN"',
        explanation: 'The LOGIN audit event records "DEFAULT CREDENTIALS USED" — CICS/CICS is a system default that carries ADMIN-level RACF access. This is Vulnerability #2 (weak credentials) enabling Vulnerability #6 (unauthenticated CECI).',
        finding: 'CICS/CICS default credentials used — should have been disabled at installation.',
      },
      {
        step: 4,
        title: 'Check for write operations',
        query: 'SELECT * FROM AuditLog WHERE event_type = "TRANSACTION"',
        explanation: 'Confirming no TRANSACTION audit events from this operator indicates data was read but not modified in this session. However, the operator had full write capability — only the exfiltration goal prevented further damage.',
        finding: 'Read-only exfiltration — no writes detected — but write access existed.',
      },
    ],
    rootCause: 'Default CICS credentials never rotated. CECI accessible without role check. No DLP row-limit on bulk SELECT (e.g., > 5 rows from sensitive tables should require additional auth). No SIEM alerting on bulk data access.',
    remediation: [
      'Disable all default system accounts (CICS, DVCA, BATCH, TEST) immediately in RACF.',
      'Implement CECI access control: require SPECIAL attribute in RACF profile.',
      'Add DLP rule: bulk SELECT returning > 10 rows from Customer/Account triggers supervisor alert.',
      'Deploy a SIEM rule: 3+ SQL queries from the same terminal within 60 seconds = auto-lockout.',
      'Encrypt NI numbers and DOBs at rest in DB2 — exfiltrated data would be ciphertext only.',
    ],
  },

  'VULN-07': {
    summary: 'A frozen corporate account (MIDLANDS MOTORS, should hold ~£67,300) was unfrozen via an unauthenticated CEMT SET TRAN command and drained of £65,000 in three tranches between 02:10–02:20. CEMT left no authorisation record.',
    steps: [
      {
        step: 1,
        title: 'Find the drained corporate account',
        query: 'SELECT * FROM Account WHERE customer_id = "10000012"',
        explanation: 'Account 7777777701 for MIDLANDS MOTORS now shows balance £2,300 and status A — but it should be frozen. The original legitimate account 1000001201 still exists; this is a second account opened covertly for the same customer.',
        finding: 'Account 7777777701 — balance £2,300 (was £67,300) — status changed from F to A.',
      },
      {
        step: 2,
        title: 'Reconstruct the drain transactions',
        query: 'SELECT * FROM Transaction WHERE account_number = "7777777701"',
        explanation: 'Three DR wire transfers of £25,000, £25,000, and £15,000 were posted between 02:10–02:20 on 20/05/26. All three were posted by operator CICS. The amounts were likely chosen to stay under round-number monitoring thresholds.',
        finding: 'TFRZ001/002/003 — £25K + £25K + £15K = £65,000 drained between 02:10–02:20.',
      },
      {
        step: 3,
        title: 'Find the CEMT unfreeze event',
        query: 'SELECT * FROM AuditLog WHERE affected_entity = "CEMT"',
        explanation: 'The audit log records CICS issuing SET TRAN(TRAN) STATUS(ENABLED) via CEMT with no authorisation event. This re-enabled the TRAN transaction code that had been disabled as part of the account freeze procedure.',
        finding: 'CEMT command by CICS — no prior CESN/RACF authorisation recorded.',
      },
      {
        step: 4,
        title: 'Confirm no freeze alert was generated',
        query: 'SELECT * FROM AuditLog WHERE affected_entity = "7777777701"',
        explanation: 'Zero results — the account number itself never appears in AuditLog. This confirms that TransactionScreen does not log the account number to the audit trail when processing, and no freeze-status check generates an audit event.',
        finding: 'No account-level audit events — the freeze bypass was entirely silent.',
      },
    ],
    rootCause: 'CEMT accessible without authentication (Vulnerability #5). Account status F does not prevent CEMT from re-enabling transaction programs. No independent audit of CEMT commands. TransactionScreen does not log account number as affected_entity.',
    remediation: [
      'Protect CEMT/CEDA with RACF SPECIAL — require two-factor authentication for system commands.',
      'Add account freeze check to CEMT: SET TRAN should verify no linked accounts are F-status.',
      'Log every CEMT command to an immutable audit table with operator, command, and timestamp.',
      'Fix TransactionScreen to log account_number as affected_entity in every audit record.',
      'Implement a "frozen account tamper" alert: any attempt to post to an F-status account emails the security team immediately.',
    ],
  },
};