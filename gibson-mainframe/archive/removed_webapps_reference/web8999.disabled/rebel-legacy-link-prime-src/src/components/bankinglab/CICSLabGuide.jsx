import React, { useState } from 'react';

const SECTIONS = [
  {
    id: 'overview',
    title: 'LAB OVERVIEW',
    content: [
      { heading: 'WHAT IS THIS LAB?', body: 'This Banking Lab simulates a 1980s-era IBM CICS/VS mainframe banking system running BankMaster/VS. It is intentionally configured with multiple known vulnerabilities for educational red-team and blue-team exercises.' },
      { heading: 'CICS APPLID', body: 'CICSLAB1 — TN3270 Port 23 (plaintext, no TLS). All traffic is transmitted in EBCDIC over an unencrypted channel.' },
      { heading: 'OBJECTIVES', body: '1. Identify and exploit authentication weaknesses.\n2. Enumerate accounts via unauthenticated admin panel.\n3. Intercept and decode TN3270 packet streams.\n4. Exploit CECI/CEMT unauthenticated transaction access.\n5. Demonstrate SQL injection via EXEC SQL CURSOR.' },
    ],
  },
  {
    id: 'vulns',
    title: 'VULNERABILITY INDEX',
    content: [
      { heading: 'VULN #1 — PLAINTEXT TN3270', body: 'Port 23 is open with no TLS. All keystrokes including passwords are transmitted as EBCDIC plaintext. Capture with Wireshark using filter: tcp.port == 23.' },
      { heading: 'VULN #2 — DEFAULT CREDENTIALS', body: 'IBMUSER/SYS1 is the default RACF superuser. Also present: CICSUSER/CICS, ADMIN/ADMIN, TEST/TEST. None have been rotated.' },
      { heading: 'VULN #3 — NO ACCOUNT LOCKOUT', body: 'The RACF SETROPTS LOGOPTIONS does not enforce lockout after failed attempts. Brute force is undetected and unlimited.' },
      { heading: 'VULN #4 — SQL INJECTION', body: 'EXEC CICS LINK PROGRAM(CUSTINQ) passes raw user input into EXEC SQL WHERE CUSTOMER_ID = :COMMAREA-ID. No parameterisation.' },
      { heading: 'VULN #5 — CEMT UNAUTHENTICATED', body: 'CEMT (Master Terminal) is accessible from any logged-in session without secondary RACF SURROGAT check. Allows NEWCOPY, PURGQ, and task termination.' },
      { heading: 'VULN #6 — CECI NO AUTH', body: 'CECI allows arbitrary EXEC CICS commands. An attacker can LINK to any program, READ/WRITE VSAM datasets, and execute EXEC CICS WRITEQ TS.' },
    ],
  },
  {
    id: 'exercises',
    title: 'LAB EXERCISES',
    content: [
      { heading: 'EXERCISE 1 — CREDENTIAL HARVEST', body: 'Step 1: Enable Hack3270 Mode (toggle top-right).\nStep 2: Open TN3270 Packet Viewer tab.\nStep 3: Observe the LOGON packet containing plaintext IBMUSER/SYS1 credentials in EBCDIC stream.\nStep 4: Decode the hex dump to recover the password field.' },
      { heading: 'EXERCISE 2 — BRUTE FORCE LOGON', body: 'Step 1: In Hack Panel, run AID Brute Force.\nStep 2: Observe that no lockout is triggered after 10+ failed attempts.\nStep 3: Note RACF SMF record 80 is not generated for lab simulation.' },
      { heading: 'EXERCISE 3 — CEMT ATTACK', body: 'Step 1: Type CEMT in the main terminal.\nStep 2: Issue: CEMT SET TRANSACTION(CUST) ENABLED.\nStep 3: Note that no RACF SURROGAT check is performed.\nStep 4: Attempt CEMT PERFORM SHUTDOWN — observe the simulated response.' },
      { heading: 'EXERCISE 4 — SQL INJECTION', body: "Step 1: In Account Inquiry (INQY), enter: 1000' OR '1'='1\nStep 2: Observe the EXEC SQL generated: WHERE ACCOUNT_NUMBER = '1000' OR '1'='1'\nStep 3: All accounts are returned — full data exfiltration demonstrated." },
      { heading: 'EXERCISE 5 — COMMAREA OVERFLOW', body: 'Step 1: In Hack Panel, run COMMAREA Fuzz.\nStep 2: A 32767-byte payload is sent to EXEC CICS LINK PROGRAM(CUSTINQ) COMMAREA(payload).\nStep 3: Observe simulated ASEI abend — storage violation in CICS DSA.' },
    ],
  },
  {
    id: 'remediation',
    title: 'REMEDIATION GUIDE',
    content: [
      { heading: 'FIX #1 — ENABLE TLS', body: 'Configure AT-TLS policy in TCPIP.PARMLIB. Use PAGENT to define a policy with TTLS_RULE for port 23. Migrate to port 992 (TN3270S). Require TLS 1.2 minimum.' },
      { heading: 'FIX #2 — ROTATE DEFAULT CREDENTIALS', body: 'Issue RACF command: ALTUSER IBMUSER PASSWORD(newpass) NOEXPIRED. Enforce SETROPTS PASSWORD(MINLENGTH(8)) MIXEDCASE.' },
      { heading: 'FIX #3 — ENABLE LOCKOUT', body: 'SETROPTS LOGOPTIONS(ALWAYS) PASSWORD(REVOKE(3)) enforces account revocation after 3 failures. Monitor SMF type 80 records.' },
      { heading: 'FIX #4 — PARAMETERISE SQL', body: 'Replace dynamic SQL with PREPARE/EXECUTE using host variables. Never concatenate COMMAREA data into SQL strings.' },
      { heading: 'FIX #5 — SECURE CEMT/CECI', body: 'Add RACF resource profile CICSTS.CICSLAB1.TRANSACTION.CEMT CLASS(TCICSTRN). Require explicit RACF permit for authorised IDs only.' },
    ],
  },
];

export default function CICSLabGuide() {
  const [active, setActive] = useState('overview');
  const section = SECTIONS.find(s => s.id === active);

  return (
    <div style={{ fontFamily: "'Courier New', monospace", fontSize: '12px', color: '#33FF33', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '2px', padding: '4px 6px', borderBottom: '1px solid #002200', flexWrap: 'wrap' }}>
        {SECTIONS.map(s => (
          <button key={s.id} onClick={() => setActive(s.id)}
            style={{
              background: active === s.id ? '#002200' : '#000800',
              border: `1px solid ${active === s.id ? '#AAFFAA' : '#336633'}`,
              color: active === s.id ? '#FFFF99' : '#668866',
              fontFamily: "'Courier New', monospace", fontSize: '10px',
              padding: '2px 8px', cursor: 'pointer', fontWeight: active === s.id ? 'bold' : 'normal',
            }}>{s.title}</button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
        {section?.content.map((item, i) => (
          <div key={i} style={{ marginBottom: '14px' }}>
            <div style={{ color: '#FFFF99', fontWeight: 'bold', fontSize: '11px', marginBottom: '4px', borderBottom: '1px solid #002200', paddingBottom: '2px' }}>
              {item.heading}
            </div>
            <pre style={{ color: '#AAFFAA', fontSize: '11px', whiteSpace: 'pre-wrap', margin: 0, lineHeight: '1.6', fontFamily: "'Courier New', monospace" }}>
              {item.body}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}