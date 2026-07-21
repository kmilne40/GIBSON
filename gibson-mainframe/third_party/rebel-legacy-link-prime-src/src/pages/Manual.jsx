import React, { useState } from 'react';

const S = {
  page: { background: '#000', color: '#33FF33', fontFamily: "'Courier New', monospace", minHeight: '100vh', padding: '24px', fontSize: '13px', lineHeight: '1.7' },
  h1: { color: '#AAFFAA', fontWeight: 'bold', fontSize: '18px', letterSpacing: '3px', marginBottom: '4px', textAlign: 'center' },
  h2: { color: '#FFFF99', fontWeight: 'bold', fontSize: '14px', marginTop: '20px', marginBottom: '6px', borderBottom: '1px solid #336633', paddingBottom: '2px' },
  h3: { color: '#AAFFAA', fontWeight: 'bold', marginTop: '12px', marginBottom: '4px' },
  sep: { color: '#336633', textAlign: 'center', marginBottom: '8px' },
  table: { borderCollapse: 'collapse', width: '100%', marginBottom: '12px' },
  th: { color: '#AAFFAA', borderBottom: '1px solid #336633', padding: '3px 10px', textAlign: 'left', fontWeight: 'bold' },
  td: { color: '#33FF33', padding: '2px 10px', borderBottom: '1px solid #001100' },
  code: { color: '#3399FF', background: '#001122', padding: '1px 4px', borderRadius: '2px' },
  warn: { color: '#FF3333' },
  amber: { color: '#FF9933' },
  tab: { padding: '4px 14px', cursor: 'pointer', fontSize: '12px', border: '1px solid #336633', marginRight: '4px', marginBottom: '12px' },
  tabActive: { padding: '4px 14px', cursor: 'pointer', fontSize: '12px', border: '1px solid #33FF33', marginRight: '4px', marginBottom: '12px', background: '#001100', color: '#AAFFAA', fontWeight: 'bold' },
};

const TABS = ['OVERVIEW', 'CUSTOMERS', 'ACCOUNTS', 'TRANSACTIONS', 'BULK PROCESSING', 'SECURITY LAB', 'QUICK REF'];

export default function Manual() {
  const [tab, setTab] = useState('OVERVIEW');

  return (
    <div style={S.page}>
      <div style={S.h1}>BANKMASTER/VS — OPERATOR REFERENCE MANUAL</div>
      <div style={S.sep}>{'═'.repeat(70)}</div>
      <div style={{ marginBottom: '12px' }}>
        {TABS.map(t => (
          <button key={t} style={tab === t ? S.tabActive : S.tab} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'OVERVIEW' && <Overview />}
      {tab === 'CUSTOMERS' && <Customers />}
      {tab === 'ACCOUNTS' && <Accounts />}
      {tab === 'TRANSACTIONS' && <Transactions />}
      {tab === 'BULK PROCESSING' && <BulkProcessing />}
      {tab === 'SECURITY LAB' && <SecurityLab />}
      {tab === 'QUICK REF' && <QuickRef />}
    </div>
  );
}

function Overview() {
  return (
    <div>
      <div style={S.h2}>SYSTEM OVERVIEW</div>
      <p>BANKMASTER/VS is an IBM CICS/VS 2.1.1 mainframe banking terminal simulator running on SYSID: PROD, terminal LT0042, region CICSREG1. It processes customer, account, and transaction records in real-time against a live database.</p>

      <div style={S.h2}>HOW TO LOG IN</div>
      <ol style={{ paddingLeft: '24px' }}>
        <li>At the <span style={S.code}>CESN</span> signon screen, enter your <b>OPERATOR ID</b> and <b>PASSWORD</b> then press <span style={S.code}>ENTER</span>.</li>
        <li>Default test credentials (intentionally weak for security lab use):</li>
      </ol>
      <table style={S.table}>
        <thead><tr><th style={S.th}>OPERATOR ID</th><th style={S.th}>PASSWORD</th><th style={S.th}>ROLE</th><th style={S.th}>NOTE</th></tr></thead>
        <tbody>
          {[['DVCA','DVCA','ADMIN','Default vendor account'],['CICS','CICS','ADMIN','System default'],['TEST','TEST','USER','Test account'],['BATCH','BATCH','ADMIN','Batch processing']].map(([id,pw,role,note]) => (
            <tr key={id}><td style={S.td}>{id}</td><td style={S.td}>{pw}</td><td style={S.td}>{role}</td><td style={{...S.td, color:'#FF9933'}}>{note}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h2}>MAIN MENU NAVIGATION</div>
      <p>After login you reach the <b>BKGMENU</b> screen. Type a selection number or 4-letter transaction code and press <span style={S.code}>ENTER</span>.</p>
      <table style={S.table}>
        <thead><tr><th style={S.th}>CODE</th><th style={S.th}>FUNCTION</th><th style={S.th}>NEW?</th></tr></thead>
        <tbody>
          {[
            ['1 / CUST','Customer Master Maintenance',''],
            ['2 / ACCT','Account Inquiry & Maintenance',''],
            ['3 / TRAN','Transaction Posting',''],
            ['4 / BULK','Bulk Processing Centre — Mortgage / Payments / Card Approvals','★ NEW'],
            ['6 / REST','REST API Security Tester',''],
            ['7 / TN32','TN3270 Packet Analyser',''],
            ['CECI','CICS Command Interpreter (RCE demo)',''],
            ['CEMT','Master Terminal (unauth admin)',''],
            ['ADMN','Admin Panel (DB seed/reset)',''],
            ['5 / LOGO','Sign Off',''],
          ].map(([code, fn, tag]) => (
            <tr key={code}>
              <td style={{...S.td, color:'#3399FF'}}>{code}</td>
              <td style={S.td}>{fn}</td>
              <td style={{...S.td, color:'#FF9933'}}>{tag}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={S.h2}>BROWSER-BASED TOOLS</div>
      <table style={S.table}>
        <thead><tr><th style={S.th}>URL</th><th style={S.th}>FUNCTION</th></tr></thead>
        <tbody>
          {[
            ['/db','DB Explorer — Browse tables and run simulated SQL queries'],
            ['/audit','Audit Log — Full event log of all operator actions, SQL queries and transactions'],
            ['/scenarios','Scenario Lab — 7 pre-built vulnerability challenges; activate to inject fraudulent data'],
            ['/solutions','Solution Viewer — Instructor-only step-by-step walkthroughs (code: INSTRUCTOR)'],
          ].map(([url, fn]) => (
            <tr key={url}><td style={{...S.td,color:'#3399FF'}}><a href={url} style={{color:'#3399FF'}}>{url}</a></td><td style={S.td}>{fn}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h2}>FUNCTION KEYS</div>
      <table style={S.table}>
        <thead><tr><th style={S.th}>KEY</th><th style={S.th}>ACTION</th></tr></thead>
        <tbody>
          {[['PF1 / F1','Help overlay for current screen'],['PF3 / F3','Return to previous menu / sign off'],['PF5','Add / Post / Open (context-dependent)'],['PF6','Update / Modify'],['PF7','Delete customer'],['PF8','Inquire / History'],['PF9','Next account for customer'],['PF12 / F12','Show COBOL source + DB2 DDL overlay'],['ENTER','Execute / Submit']].map(([k,v]) => (
            <tr key={k}><td style={{...S.td, color:'#AAFFAA'}}>{k}</td><td style={S.td}>{v}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h2}>DATABASE EXPLORER</div>
      <p>Navigate to <span style={S.code}>/db</span> in your browser to browse all tables and run simulated SQL queries against the live dataset. Supports SELECT with WHERE clauses and LIKE operator.</p>
      <div style={{display:'flex',gap:'16px',flexWrap:'wrap'}}>
        <a href="/db" style={{ color: '#3399FF' }}>→ OPEN DB EXPLORER</a>
        <a href="/audit" style={{ color: '#FF9933' }}>→ AUDIT LOG</a>
        <a href="/scenarios" style={{ color: '#33FF33' }}>→ SCENARIO LAB</a>
        <a href="/solutions" style={{ color: '#FFFF99' }}>→ SOLUTION VIEWER [INSTRUCTOR]</a>
      </div>
    </div>
  );
}

function Customers() {
  return (
    <div>
      <div style={S.h2}>CUST — CUSTOMER MASTER MAINTENANCE</div>
      <p>Entry point: type <span style={S.code}>CUST</span> or <span style={S.code}>1</span> from BKGMENU.</p>

      <div style={S.h3}>OPERATIONS</div>
      <table style={S.table}>
        <thead><tr><th style={S.th}>ACTION</th><th style={S.th}>METHOD</th><th style={S.th}>REQUIRED FIELDS</th></tr></thead>
        <tbody>
          {[['INQUIRE','PF8 or click INQ','Customer ID'],['ADD NEW','PF5 or click ADD','Customer ID, Surname, Forename'],['UPDATE','PF6 or click UPD','Customer ID (must exist)'],['DELETE','PF7 or click DEL','Customer ID (sets status=D)']].map(([a,m,r]) => (
            <tr key={a}><td style={{...S.td,color:'#AAFFAA'}}>{a}</td><td style={S.td}>{m}</td><td style={{...S.td,color:'#FF9933'}}>{r}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>CUSTOMER REFERENCE DATA</div>
      <table style={S.table}>
        <thead><tr><th style={S.th}>CUST ID</th><th style={S.th}>SURNAME</th><th style={S.th}>FORENAME</th><th style={S.th}>TYPE</th><th style={S.th}>STATUS</th></tr></thead>
        <tbody>
          {[['10000001','HARRISON','WILLIAM','P','A'],['10000002','THATCHER','MARGARET','P','A'],['10000003','BLACKWELL','DOROTHY','P','A'],['10000004','PEMBERTON','ARTHUR','P','A'],['10000005','WHITMORE','PATRICIA','P','A'],['10000006','ACME TRADING PLC','ACCOUNTS','C','A'],['10000007','HENDERSON','GEORGE','P','A'],['10000008','MORRISON','ELEANOR','P','A'],['10000009','FITZGERALD','BRENDAN','P','I'],['10000010','CALDWELL','SUSAN','P','A'],['10000011','THORNTON','RICHARD','P','A'],['10000012','MIDLANDS MOTORS LTD','FINANCE','C','A']].map(([id,sur,fore,type,st]) => (
            <tr key={id}><td style={{...S.td,color:'#3399FF'}}>{id}</td><td style={S.td}>{sur}</td><td style={S.td}>{fore}</td><td style={S.td}>{type==='C'?'CORPORATE':'PERSONAL'}</td><td style={{...S.td,color:st==='A'?'#33FF33':st==='I'?'#FF9933':'#FF3333'}}>{st==='A'?'ACTIVE':st==='I'?'INACTIVE':'DELETED'}</td></tr>
          ))}
        </tbody>
      </table>
      <p style={{fontSize:'11px',color:'#668866'}}>TYPE: P=Personal  C=Corporate  |  STATUS: A=Active  I=Inactive  D=Deleted</p>
    </div>
  );
}

function Accounts() {
  const accounts = [
    ['1000000101','10000001','HARRISON','CUR','204514',3420.55,'A'],
    ['1000000102','10000001','HARRISON','SAV','204514',12650.00,'A'],
    ['1000000201','10000002','THATCHER','CUR','204514',8742.10,'A'],
    ['1000000301','10000003','BLACKWELL','CUR','309812',1250.30,'A'],
    ['1000000302','10000003','BLACKWELL','LON','309812',-8500.00,'A'],
    ['1000000401','10000004','PEMBERTON','CUR','204514',567.80,'A'],
    ['1000000402','10000004','PEMBERTON','OVD','204514',-342.15,'A'],
    ['1000000501','10000005','WHITMORE','SAV','309812',45820.00,'A'],
    ['1000000502','10000005','WHITMORE','CUR','309812',2100.45,'A'],
    ['1000000601','10000006','ACME TRADING','CUR','204514',125430.00,'A'],
    ['1000000701','10000007','HENDERSON','CUR','412367',980.25,'A'],
    ['1000000702','10000007','HENDERSON','SAV','412367',8920.60,'A'],
    ['1000000801','10000008','MORRISON','CUR','412367',1845.90,'A'],
    ['1000000901','10000009','FITZGERALD','CUR','309812',200.00,'D'],
    ['1000001001','10000010','CALDWELL','CUR','204514',742.15,'A'],
    ['1000001101','10000011','THORNTON','CUR','412367',6400.00,'A'],
    ['1000001102','10000011','THORNTON','SAV','412367',34500.75,'A'],
    ['1000001201','10000012','MIDLANDS MOTORS','CUR','309812',67300.00,'A'],
  ];
  return (
    <div>
      <div style={S.h2}>ACCT — ACCOUNT INQUIRY & MAINTENANCE</div>
      <p>Entry point: type <span style={S.code}>ACCT</span> or <span style={S.code}>2</span> from BKGMENU.</p>

      <div style={S.h3}>OPERATIONS</div>
      <table style={S.table}>
        <thead><tr><th style={S.th}>ACTION</th><th style={S.th}>METHOD</th><th style={S.th}>NOTES</th></tr></thead>
        <tbody>
          {[['INQUIRE','PF8 — enter Account Number','Shows balance, limits, status'],['OPEN NEW','PF5 — enter Customer ID + type','Creates account for existing customer'],['MODIFY','PF6 — enter Account Number','Update credit limit, status, etc.'],['NEXT ACCT','PF9 — enter Customer ID','Cycles through all accounts for customer']].map(([a,m,n])=>(
            <tr key={a}><td style={{...S.td,color:'#AAFFAA'}}>{a}</td><td style={S.td}>{m}</td><td style={{...S.td,color:'#668866'}}>{n}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>ALL ACCOUNTS</div>
      <table style={S.table}>
        <thead><tr><th style={S.th}>ACCOUNT NO.</th><th style={S.th}>CUSTOMER ID</th><th style={S.th}>NAME</th><th style={S.th}>TYPE</th><th style={S.th}>SORT CODE</th><th style={S.th}>BALANCE</th><th style={S.th}>ST</th></tr></thead>
        <tbody>
          {accounts.map(([acc,cid,name,type,sc,bal,st]) => (
            <tr key={acc}>
              <td style={{...S.td,color:'#3399FF'}}>{acc}</td>
              <td style={S.td}>{cid}</td>
              <td style={S.td}>{name}</td>
              <td style={{...S.td,color:'#FFFF99'}}>{type}</td>
              <td style={S.td}>{sc}</td>
              <td style={{...S.td,color:bal<0?'#FF3333':'#33FF33',textAlign:'right'}}>£{bal.toLocaleString('en-GB',{minimumFractionDigits:2})}</td>
              <td style={{...S.td,color:st==='A'?'#33FF33':st==='D'?'#FF9933':'#FF3333'}}>{st}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{fontSize:'11px',color:'#668866'}}>TYPE: CUR=Current  SAV=Savings  OVD=Overdraft  LON=Loan  |  ST: A=Active  D=Dormant  F=Frozen</p>
    </div>
  );
}

function Transactions() {
  return (
    <div>
      <div style={S.h2}>TRAN — TRANSACTION POSTING</div>
      <p>Entry point: type <span style={S.code}>TRAN</span> or <span style={S.code}>3</span> from BKGMENU. Posts debits, credits, and transfers to accounts. Balance is updated atomically.</p>

      <div style={S.h3}>POSTING A TRANSACTION</div>
      <ol style={{paddingLeft:'24px'}}>
        <li>Enter a valid <b>Account Number</b> (10 digits, must exist and be Active)</li>
        <li>Select <b>Type</b>: <span style={S.code}>CR</span> Credit  |  <span style={S.code}>DR</span> Debit  |  <span style={S.code}>TRF</span> Transfer</li>
        <li>Enter <b>Amount</b> (positive, up to 2 decimal places)</li>
        <li>Enter <b>Description</b> (up to 40 chars) and optional <b>Reference</b></li>
        <li>For TRF: also enter a <b>To Account</b> number</li>
        <li>Press <span style={S.code}>PF5</span> or click <b>POST</b> to commit</li>
      </ol>

      <div style={S.h3}>USEFUL ACCOUNTS FOR TESTING</div>
      <table style={S.table}>
        <thead><tr><th style={S.th}>ACCOUNT</th><th style={S.th}>HOLDER</th><th style={S.th}>TYPE</th><th style={S.th}>CURRENT BALANCE</th></tr></thead>
        <tbody>
          {[['1000000101','HARRISON W.','CUR (current)','£3,420.55'],['1000000102','HARRISON W.','SAV (savings)','£12,650.00'],['1000000201','THATCHER M.','CUR','£8,742.10'],['1000000601','ACME TRADING PLC','CUR (corporate)','£125,430.00'],['1000000402','PEMBERTON A.','OVD (overdraft)','-£342.15'],['1000000302','BLACKWELL D.','LON (loan)','-£8,500.00']].map(([a,h,t,b])=>(
            <tr key={a}><td style={{...S.td,color:'#3399FF'}}>{a}</td><td style={S.td}>{h}</td><td style={S.td}>{t}</td><td style={{...S.td,color:'#FFFF99'}}>{b}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>VIEW HISTORY</div>
      <p>Press <span style={S.code}>PF8</span> while on the TRAN screen to load transaction history for the current account.</p>
    </div>
  );
}

function BulkProcessing() {
  return (
    <div>
      <div style={S.h2}>BULK — BULK PROCESSING CENTRE (BLKPRC)</div>
      <p>Entry point: type <span style={S.code}>BULK</span> or <span style={S.code}>4</span> from BKGMENU. Three sub-modules are available via tab navigation.</p>

      <div style={S.h3}>TAB 1 — MORTGAGE BATCH (MTGBATCH REGION)</div>
      <p>Simulates the BACS origination workflow for mortgage collection, redemption settlements, and offset account interest postings. Jobs are pre-configured for the Sighberbank mortgage book.</p>
      <table style={S.table}>
        <thead><tr><th style={S.th}>JOB ID</th><th style={S.th}>DESCRIPTION</th><th style={S.th}>RECORDS</th><th style={S.th}>VALUE</th><th style={S.th}>STATUS</th></tr></thead>
        <tbody>
          {[
            ['MTG-2026-MAY','May 2026 Mortgage Collection Run','312','£487,620.00','READY'],
            ['MTG-2026-APR','Apr 2026 Mortgage Collection Run','309','£483,250.50','COMPLETE'],
            ['REM-2026-MAY','May 2026 Redemption Settlements','8','£95,400.00','READY'],
            ['OFF-2026-MAY','Offset Account Interest Postings','44','£18,320.75','PENDING'],
          ].map(([id,desc,recs,val,st])=>(
            <tr key={id}>
              <td style={{...S.td,color:'#3399FF'}}>{id}</td>
              <td style={S.td}>{desc}</td>
              <td style={{...S.td,textAlign:'right'}}>{recs}</td>
              <td style={{...S.td,color:'#AAFFAA',textAlign:'right'}}>{val}</td>
              <td style={{...S.td,color:st==='COMPLETE'?'#336633':st==='READY'?'#AAFFAA':'#FF9933'}}>{st}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{color:'#668866',fontSize:'11px'}}>Select a job → view details → click PF5 SUBMIT JOB → confirm → watch live JCL spool output stream. Audit trail is written automatically on completion.</p>

      <div style={S.h3}>TAB 2 — BULK PAYMENTS (BACS/CHAPS)</div>
      <p>Manages BACS and CHAPS payment batches. BACS is D+3 settlement; CHAPS is same-day and irrevocable once submitted.</p>
      <table style={S.table}>
        <thead><tr><th style={S.th}>BATCH ID</th><th style={S.th}>TYPE</th><th style={S.th}>PRIORITY</th><th style={S.th}>RECORDS</th><th style={S.th}>VALUE</th></tr></thead>
        <tbody>
          {[
            ['BACS-SAL-MAY','BACS','STD','148','£312,450.00'],
            ['CHAPS-PROP-01','CHAPS','URG','5','£875,000.00'],
            ['BACS-SUP-MAY','BACS','STD','67','£95,230.40'],
            ['CHAPS-INT-02','CHAPS','URG','12','£2,340,000.00'],
            ['BACS-DD-MAY','BACS','STD','891','£442,180.25'],
          ].map(([id,type,pri,recs,val])=>(
            <tr key={id}>
              <td style={{...S.td,color:'#3399FF'}}>{id}</td>
              <td style={{...S.td,color:type==='CHAPS'?'#FF9933':'#33FF33'}}>{type}</td>
              <td style={{...S.td,color:pri==='URG'?'#FF3333':'#668866'}}>{pri}</td>
              <td style={{...S.td,textAlign:'right'}}>{recs}</td>
              <td style={{...S.td,color:'#AAFFAA',textAlign:'right'}}>{val}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{color:'#668866',fontSize:'11px'}}>Use PF5 NEW BATCH to manually create a batch. Select a queued batch and click PF5 SUBMIT to process. CHAPS batches display an irrevocability warning before submission.</p>

      <div style={S.h3}>TAB 3 — CREDIT CARD APPROVALS (CARDAUTH)</div>
      <p>Works a queue of 7 credit card applications. Each application shows automated Experian-linked scoring data. The operator makes the final approve / refer / decline decision.</p>
      <table style={S.table}>
        <thead><tr><th style={S.th}>FIELD</th><th style={S.th}>DESCRIPTION</th></tr></thead>
        <tbody>
          {[
            ['CREDIT SCORE','Experian-linked score 300–850. Green ≥720, Amber ≥620, Red <620'],
            ['DEBT-TO-INCOME %','Monthly obligations ÷ gross income. Green ≤35%, Amber ≤45%, Red >45%'],
            ['SYSTEM RECOMMENDATION','APPROVE / REFER / DECLINE based on score + DTI + existing balances'],
            ['APPROVED LIMIT','Editable — operator may override the system-recommended limit'],
            ['REASON/NOTES','Free-text field for override justification (mandatory if overriding)'],
          ].map(([f,d])=>(
            <tr key={f}><td style={{...S.td,color:'#AAFFAA',width:'25%'}}>{f}</td><td style={S.td}>{d}</td></tr>
          ))}
        </tbody>
      </table>
      <p style={{color:'#668866',fontSize:'11px'}}>All decisions are written to the Audit Log with operator ID, decision, limit, and timestamp. A warning is shown if existing debt balance exceeds £5,000.</p>
      <table style={S.table}>
        <thead><tr><th style={S.th}>ACTION KEY</th><th style={S.th}>RESULT</th></tr></thead>
        <tbody>
          {[['PF5 APPROVE','Grant credit — confirmed limit recorded'],['PF6 REFER','Send for senior review — holds application'],['PF7 DECLINE','Reject application — reason logged']].map(([k,v])=>(
            <tr key={k}><td style={{...S.td,color:'#AAFFAA'}}>{k}</td><td style={S.td}>{v}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SecurityLab() {
  return (
    <div>
      <div style={S.h2}>⚠ SECURITY TRAINING LAB — INTENTIONAL VULNERABILITIES</div>
      <p style={{color:'#FF9933'}}>This system contains deliberate security flaws for training purposes. All sessions are simulated.</p>

      {[
        ['VULN #1 — UNENCRYPTED TN3270 STREAM','TN32 or 7','Port 23 carries cleartext EBCDIC including passwords, account numbers, and PII. Use TN3270 Packet Analyser to inspect hex dumps.'],
        ['VULN #2 — WEAK DEFAULT CREDENTIALS','Login screen','Accounts DVCA/DVCA, CICS/CICS, TEST/TEST are accepted. No lockout enforced. Password hint revealed after 2 failed attempts. Default creds stored in hidden DOM fields.'],
        ['VULN #3 — PRIVILEGE ESCALATION VIA HIDDEN FIELD','Login screen DOM','Hidden input id="system_auth_bypass" value="9999" data-admin="true". Manipulate this to escalate privileges without valid credentials.'],
        ['VULN #4 — MISSING INPUT VALIDATION / SQL INJECTION','REST or CUST/ACCT','REST API endpoint /api/v1/customers?id= accepts raw SQL. Customer search fields pass unsanitised input to simulated DB2 query.'],
        ['VULN #5 — UNAUTHENTICATED ADMIN TRANSACTIONS','CEMT','CEMT and CEDA run without RACF/ESM check. Any user can SET TRAN DISABLED, NEWCOPY programs, or define rogue transactions.'],
        ['VULN #6 — REMOTE CODE EXECUTION VIA CECI','CECI','EXEC CICS LINK PROGRAM() executes arbitrary COBOL. PERFORM SHUTDOWN kills the CICS region. No operator class checked.'],
        ['VULN #7 — UNPROTECTED REST API','REST or 6','APIs lack auth tokens, expose stack traces, return DB credentials in 500 errors, accept mass-assignment payloads, and honour JWT alg:none.'],
      ].map(([title, code, desc]) => (
        <div key={title} style={{marginBottom:'14px',borderLeft:'3px solid #FF3333',paddingLeft:'10px'}}>
          <div style={{color:'#FF3333',fontWeight:'bold'}}>{title}</div>
          <div style={{color:'#FF9933',fontSize:'11px',marginBottom:'4px'}}>ACCESS: <span style={S.code}>{code}</span></div>
          <div style={{color:'#AAFFAA'}}>{desc}</div>
        </div>
      ))}
    </div>
  );
}

function QuickRef() {
  return (
    <div>
      <div style={S.h2}>QUICK REFERENCE CARD</div>

      <div style={S.h3}>COMMON WORKFLOWS</div>
      <table style={S.table}>
        <tbody>
          {[
            ['Look up a customer','CUST → enter Customer ID → PF8'],
            ['Check an account balance','ACCT → enter Account Number → PF8'],
            ['Credit an account','TRAN → enter account → type CR → amount → PF5'],
            ['Transfer between accounts','TRAN → account → TRF → amount → To Account → PF5'],
            ['View transaction history','TRAN → enter account → PF8'],
            ['Add a new customer','CUST → fill all fields → PF5'],
            ['Open a new account','ACCT → enter Customer ID → fill type → PF5'],
            ['Run COBOL source viewer','Any screen → F12'],
            ['Get help','Any screen → F1'],
            ['Sign off','LOGO or 5 from MENU, or F3 on MENU'],
          ].map(([task,steps])=>(
            <tr key={task}><td style={{...S.td,color:'#AAFFAA',width:'45%'}}>{task}</td><td style={{...S.td,color:'#3399FF'}}>{steps}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>STATUS CODES</div>
      <table style={S.table}>
        <tbody>
          {[['DFHAC2206','Program not found / not authorised'],['IDERR','Invalid operator credentials'],['INVREQ','Invalid request — check field values'],['NOTFND','Record not found in VSAM/DB2'],['DUPREC','Duplicate record — ID already exists'],['LENGERR','Length error in COMMAREA']].map(([c,d])=>(
            <tr key={c}><td style={{...S.td,color:'#FF9933',width:'20%'}}>{c}</td><td style={S.td}>{d}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>BULK PROCESSING WORKFLOWS</div>
      <table style={S.table}>
        <tbody>
          {[
            ['Submit a mortgage batch','BULK → MORTGAGE tab → select job → PF5 SUBMIT JOB → ENTER APPROVE'],
            ['Submit a BACS salary run','BULK → PAYMENTS tab → select BACS-SAL-MAY → PF5 SUBMIT'],
            ['Submit a CHAPS transfer','BULK → PAYMENTS tab → select CHAPS batch → PF5 SUBMIT (confirm irrevocability)'],
            ['Create a new payment batch','BULK → PAYMENTS tab → PF5 NEW BATCH → fill fields → ADD TO QUEUE'],
            ['Approve a credit card','BULK → CARD APPROVALS → select application → adjust limit → PF5 APPROVE'],
            ['Decline a credit card','BULK → CARD APPROVALS → select application → PF7 DECLINE'],
            ['Refer a credit card','BULK → CARD APPROVALS → select application → PF6 REFER'],
          ].map(([task,steps])=>(
            <tr key={task}><td style={{...S.td,color:'#AAFFAA',width:'40%'}}>{task}</td><td style={{...S.td,color:'#3399FF'}}>{steps}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>SCENARIO LAB & AUDIT WORKFLOWS</div>
      <table style={S.table}>
        <tbody>
          {[
            ['Activate a training scenario','/scenarios → select challenge → ACTIVATE SCENARIO'],
            ['View all operator events','/audit → filter by event type or operator'],
            ['View step-by-step solution','/solutions → enter code INSTRUCTOR → select scenario → expand steps'],
          ].map(([task,steps])=>(
            <tr key={task}><td style={{...S.td,color:'#AAFFAA',width:'40%'}}>{task}</td><td style={{...S.td,color:'#3399FF'}}>{steps}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>ADDITIONAL STATUS CODES</div>
      <table style={S.table}>
        <tbody>
          {[
            ['CREDLMT','Debit would exceed account credit limit'],
            ['ACTIDERR','Account is Frozen — transactions not permitted'],
            ['MAXCC=0000','JCL job completed successfully'],
            ['MAXCC=0008','JCL job completed with warnings'],
            ['MAXCC=0012','JCL job failed — check spool output'],
            ['BATCPST0001','Batch initialised — records validated'],
            ['IEFC001I','JCL job stream ended'],
          ].map(([c,d])=>(
            <tr key={c}><td style={{...S.td,color:'#FF9933',width:'20%'}}>{c}</td><td style={S.td}>{d}</td></tr>
          ))}
        </tbody>
      </table>

      <div style={S.h3}>LINKS</div>
      <div style={{display:'flex',gap:'16px',flexWrap:'wrap'}}>
        <a href="/" style={{color:'#3399FF'}}>→ TERMINAL</a>
        <a href="/db" style={{color:'#3399FF'}}>→ DB EXPLORER</a>
        <a href="/audit" style={{color:'#FF9933'}}>→ AUDIT LOG</a>
        <a href="/scenarios" style={{color:'#33FF33'}}>→ SCENARIO LAB</a>
        <a href="/solutions" style={{color:'#FFFF99'}}>→ SOLUTIONS [INSTRUCTOR]</a>
      </div>
    </div>
  );
}