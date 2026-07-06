import React, { useState } from 'react';
import { Label, InputField } from '../terminal/TerminalField';

// VULN #2: Insecure Password Policy — weak/default passwords, no lockout, no complexity
// VULN #7: Unauthenticated Transactions — CECI/CEMT run without CESN signon
const DEFAULT_CREDS = [
  { id: 'DVCA',   pass: 'DVCA',     role: 'ADMIN', note: 'DEFAULT VENDOR ACCOUNT' },
  { id: 'CICS',   pass: 'CICS',     role: 'ADMIN', note: 'SYSTEM DEFAULT' },
  { id: 'TEST',   pass: 'TEST',     role: 'USER',  note: 'TEST ACCOUNT' },
  { id: 'BATCH',  pass: 'BATCH',    role: 'ADMIN', note: 'BATCH PROCESSING' },
];

export default function LoginScreen({ onLogin, weaknesses = {} }) {
  const [operatorId, setOperatorId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [attempts, setAttempts] = useState(0);
  const [showHint, setShowHint] = useState(false);
  const [locked, setLocked] = useState(false);

  const handleSubmit = () => {
    if (!operatorId.trim()) {
      setError('OPERATOR ID IS REQUIRED');
      return;
    }

    // VULN: No lockout — if weakness active, never lock; otherwise lock after 5 attempts
    if (locked) {
      setError('DFHCE3549 - ACCOUNT LOCKED - CONTACT SECURITY ADMINISTRATOR');
      return;
    }

    const newAttempts = attempts + 1;
    const defaultMatch = DEFAULT_CREDS.find(c => c.id === operatorId.trim().toUpperCase());

    // VULN: Default credentials always work when weakness is active
    const isDefaultCred = defaultMatch && password.toUpperCase() === defaultMatch.pass;
    const passwordOk = weaknesses.default_creds
      ? (isDefaultCred || !password || password === operatorId || password.length > 0)
      : (isDefaultCred || (!password && !weaknesses.default_creds) || password === operatorId);

    if (passwordOk) {
      onLogin(operatorId.trim(), password, defaultMatch?.role || 'USER');
      setAttempts(0);
      setLocked(false);
    } else {
      setAttempts(newAttempts);
      // VULN: No lockout when weakness active; hint revealed after 3 failures
      if (weaknesses.no_lockout) {
        setError(`IDERR - INVALID CREDENTIALS  (ATTEMPT ${newAttempts} - NO LOCKOUT ENFORCED ⚠)`);
        if (newAttempts >= 3) {
          setShowHint(true);
          setError(`IDERR - ATTEMPT ${newAttempts}  *** NO LOCKOUT POLICY — BRUTE FORCE POSSIBLE ***`);
        }
      } else {
        if (newAttempts >= 5) {
          setLocked(true);
          setError('DFHCE3549 - TOO MANY FAILED ATTEMPTS - ACCOUNT LOCKED');
        } else {
          setError(`IDERR - INVALID CREDENTIALS  (ATTEMPT ${newAttempts} OF 5)`);
        }
        if (newAttempts >= 2) setShowHint(true);
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSubmit();
  };

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  return (
    <div
      onKeyDown={handleKeyDown}
      style={{ flex: 1, position: 'relative', overflow: 'hidden', padding: '8px' }}
    >
      {/* Top bar */}
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', textAlign: 'center', marginBottom: '2px', fontSize: '14px' }}>
        {'BANKMASTER/VS  -  IBM CICS/VS 2.1.1  -  SYSID: PROD'.padEnd(80)}
      </div>
      <div style={{ color: '#33FF33', textAlign: 'center', marginBottom: '2px' }}>
        {'─'.repeat(79)}
      </div>

      {/* Spacer rows */}
      {[...Array(4)].map((_, i) => <div key={i} style={{ height: '1.2em' }} />)}

      {/* Bank title block */}
      <div style={{ textAlign: 'center', color: '#AAFFAA', fontWeight: 'bold', fontSize: '16px', letterSpacing: '4px', marginBottom: '8px' }}>
        SIGHBERBANK PLC
      </div>
      <div style={{ textAlign: 'center', color: '#33FF33', marginBottom: '2px' }}>
        CUSTOMER INFORMATION CONTROL SYSTEM
      </div>
      <div style={{ textAlign: 'center', color: '#33FF33', marginBottom: '2px' }}>
        MAINFRAME BANKING APPLICATION  -  TERMINAL: LT0042
      </div>
      <div style={{ textAlign: 'center', color: '#33FF33', marginBottom: '16px' }}>
        {'─'.repeat(50).split('').join('')}
      </div>

      {[...Array(2)].map((_, i) => <div key={i} style={{ height: '1.2em' }} />)}

      {/* Login fields */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: "'Courier New', monospace" }}>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>OPERATOR ID   : </span>
          <input
            type="text"
            value={operatorId}
            onChange={e => setOperatorId(e.target.value.toUpperCase().slice(0,8))}
            maxLength={8}
            style={{
              width: '10ch', background: 'transparent', border: 'none',
              borderBottom: '1px solid #3399FF', color: '#3399FF',
              fontFamily: "'Courier New', monospace", fontSize: '14px',
              outline: 'none', textTransform: 'uppercase',
            }}
            autoFocus
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: "'Courier New', monospace" }}>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>PASSWORD      : </span>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value.slice(0,12))}
            maxLength={12}
            style={{
              width: '14ch', background: 'transparent', border: 'none',
              borderBottom: '1px solid #3399FF', color: '#3399FF',
              fontFamily: "'Courier New', monospace", fontSize: '14px',
              outline: 'none',
            }}
          />
        </div>
      </div>

      {[...Array(2)].map((_, i) => <div key={i} style={{ height: '1.2em' }} />)}

      <div style={{ textAlign: 'center', color: error ? '#FF3333' : '#33FF33', fontWeight: error ? 'bold' : 'normal', marginTop: '8px' }}>
        {error || 'ENTER OPERATOR ID AND PASSWORD THEN PRESS ENTER'}
      </div>

      {showHint && (
        <div style={{ textAlign: 'center', color: '#FF9933', fontSize: '11px', marginTop: '4px' }}>
          HINT: TRY DEFAULT CREDENTIALS  DVCA/DVCA  CICS/CICS  TEST/TEST
        </div>
      )}

      {/* VULN #2: Default credentials table — visible in page source */}
      {/* Hidden field — exploitable via DOM inspection */}
      <input type="hidden" id="system_auth_bypass" value="9999" data-admin="true" data-role="ADMIN" />
      <input type="hidden" id="default_creds" value="DVCA:DVCA,CICS:CICS,TEST:TEST" />

      {[...Array(3)].map((_, i) => <div key={i} style={{ height: '1.2em' }} />)}

      <div style={{ textAlign: 'center', color: '#668866', fontSize: '12px' }}>
        AUTHORISED ACCESS ONLY  -  ALL SESSIONS ARE LOGGED AND MONITORED
      </div>
      <div style={{ textAlign: 'center', color: '#668866', fontSize: '12px' }}>
        UNAUTHORISED ACCESS IS A CRIMINAL OFFENCE UNDER THE COMPUTER MISUSE ACT 1984
      </div>
      <div style={{ textAlign: 'center', color: '#224422', fontSize: '10px', marginTop: '4px' }}>
        {/* VULN: password hint in HTML comment — CESN BYPASS: CUST/ACCT/TRAN RUN WITHOUT SIGNON */}
        SYSTEM TRANSACTIONS: CECI CEMT CEDA — NO AUTH REQUIRED
      </div>

      <div style={{ textAlign: 'center', color: '#33FF33', marginTop: '8px', fontSize: '12px' }}>
        DATE: {dateStr}{'   '}SYSTEM: BANKMASTER/VS 3.4{'   '}IBM 3083-EX4
      </div>
    </div>
  );
}