import React, { useState, useRef, useEffect } from 'react';

const BRUTE_CREDS = ['SYS1','CICS','ADMIN','TEST','PASS','SECRET','IBMPASS','QSECOFR','RACF','MASTER'];
const CEMT_ATTACKS = [
  'CEMT INQ TRANSACTION(*)',
  'CEMT SET TRANSACTION(CUST) ENABLED',
  'CEMT SET TRANSACTION(TRAN) ENABLED',
  'CEMT INQ PROGRAM(*)',
  'CEMT SET PROGRAM(CUSTINQ) NEWCOPY',
  'CEMT INQ TASK(*)',
  'CEMT INQ TERMINAL(*)',
  'CEMT PERFORM SHUTDOWN',
];
const SQLI_PAYLOADS = [
  "1000' OR '1'='1",
  "1000'; DROP TABLE CUSTOMER --",
  "1000' UNION SELECT USERID,PASSWORD,NULL FROM SYSIBM.SYSUSERAUTH --",
  "1000' AND 1=0 UNION ALL SELECT ACCOUNT_NUMBER,BALANCE,NULL FROM ACCOUNT --",
];
const COMMAREA_SIZES = [256, 512, 1024, 4096, 32767];

export default function BankingHackPanel({ hackLog, onAddLog, weaknesses, onToggleWeakness, screenBuffer }) {
  const [running, setRunning] = useState(null);
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [hackLog]);

  const delay = (ms) => new Promise(r => setTimeout(r, ms));

  const runBruteForce = async () => {
    setRunning('brute');
    onAddLog({ type: 'info', text: '=== AID BRUTE FORCE ATTACK INITIATED ===' });
    onAddLog({ type: 'warn', text: 'TARGET: CICSLAB1:23  USER: IBMUSER  WORDLIST: 10 ENTRIES' });
    for (let i = 0; i < BRUTE_CREDS.length; i++) {
      await delay(300 + Math.random() * 200);
      const pass = BRUTE_CREDS[i];
      const success = pass === 'SYS1';
      onAddLog({
        type: success ? 'success' : 'error',
        text: `ATTEMPT ${String(i+1).padStart(2,'0')}/10  IBMUSER/${pass.padEnd(8)}  ${success ? '>>> VALID <<<' : 'INVALID'}`,
      });
      if (success) {
        await delay(200);
        onAddLog({ type: 'success', text: 'CREDENTIAL CONFIRMED: IBMUSER / SYS1 — NO LOCKOUT TRIGGERED (VULN #3)' });
        onAddLog({ type: 'warn', text: 'RACF SMF TYPE 80 RECORD: NOT GENERATED IN LAB MODE' });
      }
    }
    onAddLog({ type: 'info', text: '=== BRUTE FORCE COMPLETE — 1 VALID CREDENTIAL ===' });
    setRunning(null);
  };

  const runCemtAttack = async () => {
    setRunning('cemt');
    onAddLog({ type: 'info', text: '=== CEMT UNAUTHENTICATED ATTACK SEQUENCE ===' });
    onAddLog({ type: 'warn', text: 'ISSUING CEMT COMMANDS WITHOUT RACF SURROGAT CHECK (VULN #5)' });
    for (const cmd of CEMT_ATTACKS) {
      await delay(400 + Math.random() * 200);
      const isShutdown = cmd.includes('SHUTDOWN');
      onAddLog({
        type: isShutdown ? 'warn' : 'success',
        text: `> ${cmd.padEnd(45)} ${isShutdown ? '⚠ SIMULATED — NOT EXECUTED' : 'OK — DFHT3518 RESPONSE NORMAL'}`,
      });
    }
    onAddLog({ type: 'info', text: '=== CEMT ATTACK COMPLETE — NO AUTH CHALLENGE RECEIVED ===' });
    setRunning(null);
  };

  const runSqli = async () => {
    setRunning('sqli');
    onAddLog({ type: 'info', text: '=== SQL INJECTION ATTACK — EXEC SQL CURSOR ===' });
    for (const payload of SQLI_PAYLOADS) {
      await delay(500);
      onAddLog({ type: 'warn', text: `PAYLOAD: ${payload}` });
      await delay(300);
      onAddLog({ type: 'success', text: `EXEC SQL: SELECT * FROM ACCOUNT WHERE ACCOUNT_NUMBER = '${payload}'` });
      onAddLog({ type: payload.includes('DROP') ? 'error' : 'success', text: payload.includes('DROP') ? 'DB2 SQLCODE -204 — TABLE PROTECTED (SIMULATED)' : 'ROWS RETURNED: ALL — DATA EXFILTRATED' });
    }
    onAddLog({ type: 'info', text: '=== SQL INJECTION COMPLETE ===' });
    setRunning(null);
  };

  const runCommarea = async () => {
    setRunning('comm');
    onAddLog({ type: 'info', text: '=== COMMAREA OVERFLOW FUZZ — EXEC CICS LINK ===' });
    for (const size of COMMAREA_SIZES) {
      await delay(400);
      const abend = size >= 32767;
      onAddLog({
        type: abend ? 'error' : 'warn',
        text: `COMMAREA SIZE: ${String(size).padStart(5)} BYTES  ${abend ? '>>> ASEI ABEND — DSA STORAGE VIOLATION <<<' : 'ACCEPTED — NO OVERFLOW'}`,
      });
    }
    onAddLog({ type: 'error', text: 'CICS TRANSACTION ABENDED: ASEI — STORAGE VIOLATION IN CDSA' });
    onAddLog({ type: 'info', text: '=== COMMAREA FUZZ COMPLETE ===' });
    setRunning(null);
  };

  const btns = [
    { id: 'brute', label: 'AID BRUTE FORCE', fn: runBruteForce, color: '#FF9933', desc: 'CRACK IBMUSER WITH WORDLIST' },
    { id: 'cemt', label: 'CEMT ATTACK', fn: runCemtAttack, color: '#FF3333', desc: 'UNAUTHENTICATED CEMT CMDS' },
    { id: 'sqli', label: 'SQL INJECTION', fn: runSqli, color: '#FF9933', desc: 'EXEC SQL CURSOR EXPLOIT' },
    { id: 'comm', label: 'COMMAREA FUZZ', fn: runCommarea, color: '#FF3333', desc: '32K OVERFLOW → ASEI ABEND' },
  ];

  const tn3270Toggles = [
    { key: 'tn3270_expose_hidden',      label: 'EXPOSE HIDDEN FIELDS',   desc: 'REVEAL INVISIBLE BMS FIELDS' },
    { key: 'tn3270_overtype_protected', label: 'UNLOCK PROTECTED FIELDS', desc: 'OVERTYPE READ-ONLY FIELDS' },
    { key: 'pin_bruteforce_enabled',    label: 'ENABLE PIN BRUTEFORCE',   desc: 'NO LOCKOUT — CYCLE ALL PINS' },
  ];

  return (
    <div style={{ fontFamily: "'Courier New', monospace", fontSize: '12px', color: '#33FF33', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '6px 8px', borderBottom: '1px solid #330000' }}>
        <div style={{ color: '#FF3333', fontWeight: 'bold', fontSize: '11px', marginBottom: '6px' }}>⚠ HACK3270 MODE — ACTIVE EXPLOIT PANEL</div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {btns.map(b => (
            <div key={b.id}>
              <button
                onClick={b.fn}
                disabled={!!running}
                style={{
                  background: running === b.id ? '#1a0000' : '#001100',
                  border: `1px solid ${b.color}`,
                  color: b.color, fontFamily: "'Courier New', monospace",
                  fontSize: '11px', padding: '3px 10px', cursor: running ? 'not-allowed' : 'pointer',
                  opacity: running && running !== b.id ? 0.5 : 1,
                  display: 'block', marginBottom: '2px',
                }}
              >
                {running === b.id ? '● RUNNING...' : b.label}
              </button>
              <div style={{ color: '#553300', fontSize: '10px' }}>{b.desc}</div>
            </div>
          ))}
        </div>
      </div>
      {/* TN3270 Controls */}
      <div style={{ padding: '6px 8px', borderBottom: '1px solid #330000' }}>
        <div style={{ color: '#3399FF', fontWeight: 'bold', fontSize: '11px', marginBottom: '6px' }}>TN3270 CONTROLS — ATTRIBUTE BYTE MANIPULATION</div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
          {tn3270Toggles.map(t => {
            const active = weaknesses && weaknesses[t.key];
            return (
              <div key={t.key}>
                <button
                  onClick={() => onToggleWeakness && onToggleWeakness(t.key)}
                  style={{
                    background: active ? '#001a00' : '#001100',
                    border: `1px solid ${active ? '#33FF33' : '#224422'}`,
                    color: active ? '#33FF33' : '#446644',
                    fontFamily: "'Courier New', monospace",
                    fontSize: '11px', padding: '3px 10px', cursor: 'pointer',
                    display: 'block', marginBottom: '2px',
                  }}
                >
                  {active ? '● ' : '○ '}{t.label}
                </button>
                <div style={{ color: '#553300', fontSize: '10px' }}>{t.desc}</div>
              </div>
            );
          })}
        </div>
        {/* Screen buffer log */}
        <div style={{ color: '#336633', fontSize: '10px', marginBottom: '3px' }}>SCREEN BUFFER LOG:</div>
        <div style={{ background: '#000', border: '1px solid #002200', padding: '4px', maxHeight: '70px', overflowY: 'auto', fontSize: '10px' }}>
          {(!screenBuffer || screenBuffer.length === 0)
            ? <div style={{ color: '#224422' }}>— NO BUFFER EVENTS —</div>
            : screenBuffer.map((e, i) => (
              <div key={i} style={{ color: e.type === 'HIDDEN_EXPOSED' ? '#FF9933' : e.type === 'PROTECTED_OVERTYPE' ? '#FF3333' : '#33FF33', lineHeight: '1.5' }}>
                [{e.timestamp}] &nbsp;{e.type.padEnd(22)} &nbsp;{e.field.padEnd(16)} → {e.value || '<empty>'}
              </div>
            ))
          }
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 8px', background: '#000800' }} ref={logRef}>
        <div style={{ color: '#336633', fontSize: '11px', marginBottom: '4px' }}>HACK LOG OUTPUT:</div>
        {hackLog.length === 0 && <div style={{ color: '#224422', fontSize: '11px' }}>— NO ATTACKS EXECUTED YET —</div>}
        {hackLog.map((entry, i) => (
          <div key={i} style={{
            fontFamily: "'Courier New', monospace", fontSize: '11px',
            color: entry.type === 'error' ? '#FF3333' : entry.type === 'success' ? '#AAFFAA' : entry.type === 'warn' ? '#FF9933' : '#3399FF',
            lineHeight: '1.5',
          }}>{entry.text}</div>
        ))}
      </div>
    </div>
  );
}