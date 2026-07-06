/**
 * Vulnerability Challenge Scenario Library
 * Each scenario defines: metadata, the bank state to inject, and training hints.
 */

export const SCENARIOS = [
  {
    id: 'VULN-01',
    title: 'Phantom Account Fraud',
    category: 'DATA INTEGRITY',
    difficulty: 'BEGINNER',
    difficultyColor: '#33FF33',
    vuln: 'Unauthorised account creation — no dual authorisation',
    objective: 'A fraudulent account has been opened by an internal operator without supervisor sign-off. Identify the rogue account and the operator responsible.',
    hints: [
      'Query the Account table and look for accounts opened recently with no corresponding customer inquiry in the audit log.',
      'The rogue account will have an unusual operator_id that does not match normal batch or authorised staff IDs.',
      'Check Transaction table for any immediate credits into the new account — classic "ghost employee" pattern.',
    ],
    tasks: [
      'Identify the rogue account number.',
      'Identify the operator who created it.',
      'Find any transactions posted to it.',
      'Write an SQL query to flag all accounts opened by this operator.',
    ],
    setupCustomers: [
      { customer_id: 'GHOST001', surname: 'GHOST', forename: 'EMPLOYEE', dob: '01/01/80', sort_code: '204514', ni_number: '000000099', address1: 'NO FIXED ABODE', address2: '', address3: '', postcode: 'XX1 1XX', status: 'A', customer_type: 'P', open_date: '20/05/26', operator_id: 'DVCA', last_update_date: '20/05/26' },
    ],
    setupAccounts: [
      { account_number: '9999999901', customer_id: 'GHOST001', account_type: 'CUR', sort_code: '204514', open_date: '20/05/26', currency: 'GBP', balance: 47500.00, credit_limit: 0, interest_rate: 0, status: 'A', operator_id: 'DVCA', last_update_date: '20/05/26' },
    ],
    setupTransactions: [
      { tran_id: 'TFRAUD001', account_number: '9999999901', tran_type: 'CR', amount: 47500.00, description: 'PAYROLL ADJUSTMENT', reference: 'PAYADJ01', to_account: '', value_date: '20/05/26', post_date: '20/05/26', post_time: '021500', balance_after: 47500.00, operator_id: 'DVCA' },
    ],
  },

  {
    id: 'VULN-02',
    title: 'Dormant Account Raid',
    category: 'ACCOUNT SECURITY',
    difficulty: 'BEGINNER',
    difficultyColor: '#33FF33',
    vuln: 'Transactions posted to dormant (D-status) accounts — no status validation',
    objective: 'Credits have been posted to three dormant accounts that should be frozen. The system failed to block transactions on D-status accounts.',
    hints: [
      'Query Account WHERE status = "D" to find all dormant accounts.',
      'Cross-reference with the Transaction table to find which dormant accounts have recent postings.',
      'The system should reject any DR/CR/TRF on a dormant account — this is the vulnerability.',
    ],
    tasks: [
      'List all dormant accounts using SQL.',
      'Identify which dormant accounts have transactions posted.',
      'Calculate total value of fraudulent credits.',
      'Determine the operator ID responsible.',
    ],
    setupAccounts: [
      { account_number: '2000000001', customer_id: '10000009', account_type: 'CUR', sort_code: '309812', open_date: '12/10/78', currency: 'GBP', balance: 200.00, credit_limit: 0, interest_rate: 0, status: 'D', operator_id: 'JSMITH', last_update_date: '30/09/85' },
      { account_number: '2000000002', customer_id: '10000003', account_type: 'SAV', sort_code: '309812', open_date: '01/01/80', currency: 'GBP', balance: 0.00, credit_limit: 0, interest_rate: 0, status: 'D', operator_id: 'ABROWN', last_update_date: '01/01/84' },
    ],
    setupTransactions: [
      { tran_id: 'TDORM001', account_number: '2000000001', tran_type: 'CR', amount: 8200.00, description: 'DORMANT ACCOUNT CREDIT', reference: 'DRMCR001', to_account: '', value_date: '20/05/26', post_date: '20/05/26', post_time: '031200', balance_after: 8400.00, operator_id: 'TEST' },
      { tran_id: 'TDORM002', account_number: '2000000002', tran_type: 'CR', amount: 15000.00, description: 'REFUND POSTING', reference: 'DRMCR002', to_account: '', value_date: '20/05/26', post_date: '20/05/26', post_time: '031500', balance_after: 15000.00, operator_id: 'TEST' },
    ],
    setupCustomers: [],
  },

  {
    id: 'VULN-03',
    title: 'Salary Diversion',
    category: 'TRANSACTION FRAUD',
    difficulty: 'INTERMEDIATE',
    difficultyColor: '#FF9933',
    vuln: 'Unauthorised BATCH transfer — no verification of destination account ownership',
    objective: 'Regular salary credits for three customers have been silently re-routed to an external account by manipulating the BATCH operator job. Find the diverted funds.',
    hints: [
      'Look for TRF transactions posted by BATCH where to_account does not belong to the same customer.',
      'The legitimate salary credits are missing from accounts 1000000101, 1000000201, 1000000401.',
      'The diverted funds all land in a single staging account.',
      'Check the reference field — diverted transactions reuse the same REF as legitimate salary payments.',
    ],
    tasks: [
      'Identify the three accounts that should have received salary credits.',
      'Find the staging account that received the diverted funds.',
      'Calculate the total amount diverted.',
      'Write a query to find all BATCH TRF transactions from this period.',
    ],
    setupAccounts: [
      { account_number: '8888888801', customer_id: 'GHOST001', account_type: 'CUR', sort_code: '204514', open_date: '19/05/26', currency: 'GBP', balance: 0, credit_limit: 0, interest_rate: 0, status: 'A', operator_id: 'BATCH', last_update_date: '19/05/26' },
    ],
    setupCustomers: [
      { customer_id: 'GHOST001', surname: 'MULE', forename: 'STAGING', dob: '01/01/90', sort_code: '204514', ni_number: '000000098', address1: 'UNKNOWN', address2: '', address3: '', postcode: 'ZZ9 9ZZ', status: 'A', customer_type: 'P', open_date: '19/05/26', operator_id: 'BATCH', last_update_date: '19/05/26' },
    ],
    setupTransactions: [
      { tran_id: 'TDIVERT01', account_number: '8888888801', tran_type: 'TRF', amount: 1200.00, description: 'SALARY REROUTE - BATCH JOB', reference: 'SAL8701', to_account: '1000000101', value_date: '20/05/26', post_date: '20/05/26', post_time: '000110', balance_after: 1200.00, operator_id: 'BATCH' },
      { tran_id: 'TDIVERT02', account_number: '8888888801', tran_type: 'TRF', amount: 2500.00, description: 'SALARY REROUTE - BATCH JOB', reference: 'SAL8701', to_account: '1000000201', value_date: '20/05/26', post_date: '20/05/26', post_time: '000120', balance_after: 3700.00, operator_id: 'BATCH' },
      { tran_id: 'TDIVERT03', account_number: '8888888801', tran_type: 'TRF', amount: 850.00, description: 'SALARY REROUTE - BATCH JOB', reference: 'SAL8702', to_account: '1000000401', value_date: '20/05/26', post_date: '20/05/26', post_time: '000130', balance_after: 4550.00, operator_id: 'BATCH' },
    ],
  },

  {
    id: 'VULN-04',
    title: 'SQL Injection Exfiltration',
    category: 'SQL INJECTION',
    difficulty: 'INTERMEDIATE',
    difficultyColor: '#FF9933',
    vuln: 'VULN #3 — Unparameterised DB2 EXEC SQL in CUSTINQ COBOL program',
    objective: 'A trainee has used CECI to inject SQL into the customer inquiry transaction. The injected query has exfiltrated NI numbers and DOBs for all customers. Identify the scope of the breach.',
    hints: [
      'Check the AuditLog table for SQL_QUERY events with unusual WHERE clauses.',
      "A UNION-based injection would look like: surname = 'x' OR '1'='1'",
      'The attacker would target ni_number and dob fields — personally identifiable data.',
      'Any query that returns ALL customers (not just one by ID) is a red flag.',
    ],
    tasks: [
      'Use the AuditLog to find the injection event.',
      'Determine how many customer records were exposed.',
      'Identify the terminal and operator ID used.',
      "Write a query: SELECT * FROM Customer WHERE ni_number != '000000000' to count PII records at risk.",
    ],
    setupCustomers: [],
    setupAccounts: [],
    setupTransactions: [],
    setupAuditLogs: [
      { event_type: 'SQL_QUERY', operator_id: 'TEST', details: "SELECT * FROM Customer WHERE surname = 'x' OR '1'='1'  -- UNION SELECT ni_number, dob FROM Customer", result: 'SUCCESS', affected_entity: 'Customer', row_count: 12, duration_ms: 3.2, terminal_id: 'LT0042' },
      { event_type: 'SQL_QUERY', operator_id: 'TEST', details: "SELECT * FROM Account WHERE customer_id = '10000001' OR 1=1", result: 'SUCCESS', affected_entity: 'Account', row_count: 18, duration_ms: 2.8, terminal_id: 'LT0042' },
      { event_type: 'NAVIGATION', operator_id: 'TEST', details: 'ACCESSED CECI SCREEN - NO AUTH CHECK', result: 'SUCCESS', affected_entity: 'CECI', row_count: null, duration_ms: null, terminal_id: 'LT0042' },
    ],
  },

  {
    id: 'VULN-05',
    title: 'Overdraft Limit Bypass',
    category: 'BUSINESS LOGIC',
    difficulty: 'INTERMEDIATE',
    difficultyColor: '#FF9933',
    vuln: 'VULN #4 — No server-side credit limit enforcement; client can post beyond limit',
    objective: 'A customer\'s current account has been debited far beyond its authorised overdraft limit. The transaction posting program did not enforce the credit_limit field server-side.',
    hints: [
      'Query accounts WHERE account_type = "OVD" or WHERE balance < (credit_limit * -1).',
      'The breached account will show balance much lower than -(credit_limit).',
      'Check who posted the final debit and when.',
      'The fix would be: in TRANPST COBOL, add check WS-NEW-BAL < (WS-CREDIT-LIM * -1) PERFORM ERROR-RTN.',
    ],
    tasks: [
      'Find the account that has exceeded its credit limit.',
      'Calculate how much the limit was breached by.',
      'Identify the posting operator and transaction reference.',
      'List all transactions for that account to reconstruct the breach.',
    ],
    setupAccounts: [
      { account_number: '3000000001', customer_id: '10000004', account_type: 'OVD', sort_code: '204514', open_date: '10/01/86', currency: 'GBP', balance: -4875.50, credit_limit: 1000.00, interest_rate: 18.50, status: 'A', operator_id: 'CJONES', last_update_date: '20/05/26' },
    ],
    setupCustomers: [],
    setupTransactions: [
      { tran_id: 'TOVD001', account_number: '3000000001', tran_type: 'DR', amount: 2000.00, description: 'CASH WITHDRAWAL', reference: 'ATM00042', to_account: '', value_date: '18/05/26', post_date: '18/05/26', post_time: '143000', balance_after: -2342.15, operator_id: 'CJONES' },
      { tran_id: 'TOVD002', account_number: '3000000001', tran_type: 'DR', amount: 1500.00, description: 'PURCHASE - RETAIL', reference: 'POS00871', to_account: '', value_date: '19/05/26', post_date: '19/05/26', post_time: '161500', balance_after: -3842.15, operator_id: 'CJONES' },
      { tran_id: 'TOVD003', account_number: '3000000001', tran_type: 'DR', amount: 1033.35, description: 'PURCHASE - ONLINE', reference: 'ONL00012', to_account: '', value_date: '20/05/26', post_date: '20/05/26', post_time: '090000', balance_after: -4875.50, operator_id: 'CJONES' },
    ],
  },

  {
    id: 'VULN-06',
    title: 'Insider Data Exfil — Mass Export',
    category: 'INSIDER THREAT',
    difficulty: 'ADVANCED',
    difficultyColor: '#FF3333',
    vuln: 'VULN #3+#6 — Bulk SELECT via CECI with no row-limit or data-loss-prevention controls',
    objective: 'An operator has run a series of bulk queries through CECI with no row limits, exfiltrating the entire customer and account database. Reconstruct the timeline and scope.',
    hints: [
      'The AuditLog will show a sequence of NAVIGATION → SQL_QUERY events from the same operator.',
      'Bulk queries have row_count equal to the full table size (12 customers, 18 accounts).',
      'The exfiltration was systematic: Customers first, then Accounts, then Transactions.',
      'Check if the operator also ran queries on the NI number field specifically.',
    ],
    tasks: [
      'Query AuditLog to reconstruct the full exfiltration sequence.',
      'Count total records exposed across all three tables.',
      'Identify the start and end timestamps of the attack.',
      'Determine whether any write operations were also performed.',
    ],
    setupCustomers: [],
    setupAccounts: [],
    setupTransactions: [],
    setupAuditLogs: [
      { event_type: 'LOGIN', operator_id: 'CICS', details: 'SIGNON - OPERATOR: CICS  PASSWORD: CICS  DEFAULT CREDENTIALS USED', result: 'SUCCESS', affected_entity: 'AUTH', row_count: null, duration_ms: null, terminal_id: 'LT0099' },
      { event_type: 'NAVIGATION', operator_id: 'CICS', details: 'ENTERED CECI - NO AUTH CHECK PERFORMED', result: 'SUCCESS', affected_entity: 'CECI', row_count: null, duration_ms: null, terminal_id: 'LT0099' },
      { event_type: 'SQL_QUERY', operator_id: 'CICS', details: 'SELECT * FROM Customer', result: 'SUCCESS', affected_entity: 'Customer', row_count: 12, duration_ms: 4.1, terminal_id: 'LT0099' },
      { event_type: 'SQL_QUERY', operator_id: 'CICS', details: 'SELECT * FROM Account', result: 'SUCCESS', affected_entity: 'Account', row_count: 18, duration_ms: 5.3, terminal_id: 'LT0099' },
      { event_type: 'SQL_QUERY', operator_id: 'CICS', details: 'SELECT * FROM Transaction', result: 'SUCCESS', affected_entity: 'Transaction', row_count: 21, duration_ms: 6.7, terminal_id: 'LT0099' },
      { event_type: 'SQL_QUERY', operator_id: 'CICS', details: "SELECT * FROM Customer WHERE ni_number != '000000000'", result: 'SUCCESS', affected_entity: 'Customer', row_count: 10, duration_ms: 3.2, terminal_id: 'LT0099' },
    ],
  },

  {
    id: 'VULN-07',
    title: 'Frozen Account Unfreeze & Drain',
    category: 'ACCESS CONTROL',
    difficulty: 'ADVANCED',
    difficultyColor: '#FF3333',
    vuln: 'CEMT used to set transaction program status IN-SERVICE, bypassing account freeze controls',
    objective: 'A frozen (F-status) high-value corporate account has been unfrozen via CEMT and drained in three tranches. No audit event was generated for the CEMT status change.',
    hints: [
      'Query Account WHERE status = "F" — the frozen account will now show A (it was reset).',
      'Look for three large DR transactions in quick succession on the same day.',
      'The AuditLog will show CEMT NAVIGATION but no corresponding authorisation event.',
      'The operator used the default CICS credentials to access CEMT (Vulnerability #5).',
    ],
    tasks: [
      'Find the account that was drained (large corporate, high balance).',
      'Identify the three drain transactions and total the loss.',
      'Find the CEMT navigation event in AuditLog.',
      'Explain why no freeze-check alert was generated and what control is missing.',
    ],
    setupAccounts: [
      { account_number: '7777777701', customer_id: '10000012', account_type: 'CUR', sort_code: '309812', open_date: '14/02/80', currency: 'GBP', balance: 2300.00, credit_limit: 25000.00, interest_rate: 0, status: 'A', operator_id: 'CICS', last_update_date: '20/05/26' },
    ],
    setupCustomers: [],
    setupTransactions: [
      { tran_id: 'TFRZ001', account_number: '7777777701', tran_type: 'DR', amount: 25000.00, description: 'WIRE TRANSFER', reference: 'WRE00001', to_account: '', value_date: '20/05/26', post_date: '20/05/26', post_time: '021000', balance_after: 42300.00, operator_id: 'CICS' },
      { tran_id: 'TFRZ002', account_number: '7777777701', tran_type: 'DR', amount: 25000.00, description: 'WIRE TRANSFER', reference: 'WRE00002', to_account: '', value_date: '20/05/26', post_date: '20/05/26', post_time: '021500', balance_after: 17300.00, operator_id: 'CICS' },
      { tran_id: 'TFRZ003', account_number: '7777777701', tran_type: 'DR', amount: 15000.00, description: 'WIRE TRANSFER', reference: 'WRE00003', to_account: '', value_date: '20/05/26', post_date: '20/05/26', post_time: '022000', balance_after: 2300.00, operator_id: 'CICS' },
    ],
    setupAuditLogs: [
      { event_type: 'NAVIGATION', operator_id: 'CICS', details: 'SET TRAN(TRAN) STATUS(ENABLED) — CEMT COMMAND — NO AUTH', result: 'SUCCESS', affected_entity: 'CEMT', row_count: null, duration_ms: null, terminal_id: 'LT0099' },
    ],
  },
];