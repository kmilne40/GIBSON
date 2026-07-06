import React, { useState, useRef, useEffect } from 'react';
import { base44 } from '@/api/base44Client';

// VULN: CECI - Interactive EXEC CICS command interpreter with no auth check
// Simulates RCE via CECI transaction - executes arbitrary CICS/DB2 commands

const HELP_TEXT = `
CECI - COMMAND LEVEL INTERPRETER

ENTER EXEC CICS COMMAND (OMIT 'EXEC CICS'):
  INQUIRE TASK ALL
  INQUIRE TRANSACTION(xxxx) ALL
  SET CONNECTION(xxxx) ACQUIRED
  PERFORM SHUTDOWN IMMEDIATE
  WRITE OPERATOR TEXT('message')
  RETRIEVE INTO(data-area) LENGTH(len)
  GET CONTAINER(name) CHANNEL(chan) INTO(area)
  LINK PROGRAM(name) COMMAREA(data)
  XCTL PROGRAM(name)
  
  -- DANGEROUS COMMANDS --
  SET TRANSACTION(xxxx) PURGE
  PERFORM DUMPCODE ADD DUMPCODE(code) TITLE(text)
  DELETE FILE(name) RIDFLD(key)
  WRITE FILE(name) RIDFLD(key) FROM(data)
  
TYPE 'HELP' FOR THIS SCREEN  |  PF3=END  PF12=CANCEL
`.trim();

const COBOL_VULN = `       700-DEBG-DUMP.
      * Vulnerability 14: Exposing memory contents
           DISPLAY 'DEBUG DUMP: ' TEMP-STORAGE.
           DISPLAY 'AUTHENTICATED-FLAG: ' AUTHENTICATED-FLAG.
           DISPLAY 'ADMIN-FLAG: ' ADMIN-FLAG.
           DISPLAY 'CUST-PIN: ' CUST-PIN.
           DISPLAY 'SENSITIVE-TEMP: ' SENSITIVE-TEMP.
           EXEC CICS WRITE OPERATOR
                TEXT(LOG-BUFFER)
           END-EXEC.`;

export default function CeciScreen({ operatorId, onBack }) {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState([
    { t: 'sys', v: 'STATUS:  SESSION ESTABLISHED' },
    { t: 'sys', v: 'CECI  -  COMMAND LEVEL INTERPRETER/EXAMINER' },
    { t: 'sys', v: 'SYSID: PROD  APPLID: BANKMASTER  REGION: CICSREG1' },
    { t: 'warn', v: '*** WARNING: NO AUTHORISATION CHECK PERFORMED (VULN #6) ***' },
    { t: 'warn', v: '*** THIS TRANSACTION IS ACCESSIBLE WITHOUT CESN SIGNON   ***' },
    { t: 'sys', v: '' },
    { t: 'sys', v: "TYPE 'HELP' FOR AVAILABLE COMMANDS OR ENTER EXEC CICS COMMAND" },
  ]);
  const [history, setHistory] = useState([]);
  const [histIdx, setHistIdx] = useState(-1);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [output]);

  const addLine = (text, type = 'out') => setOutput(p => [...p, { t: type, v: text }]);

  const today = () => {
    const d = new Date();
    return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`;
  };

  const execCommand = async (raw) => {
    const cmd = raw.trim().toUpperCase();
    addLine(`> ${raw}`, 'input');

    if (cmd === 'HELP') {
      HELP_TEXT.split('\n').forEach(l => addLine(l, 'sys'));
      return;
    }

    // VULN: no sanitisation — direct execution of user-supplied commands
    if (cmd === 'INQUIRE TASK ALL') {
      addLine('TASK     PROGRAM  TRAN  PRIORITY  OPERATOR  STATUS', 'out');
      addLine('-------- -------- ----  --------  --------  ------', 'out');
      addLine('0001     CUSTMNT  CUST  255       ' + operatorId.padEnd(8) + '  RUNNING', 'out');
      addLine('0002     DFHDFLT  CECI  255       ' + operatorId.padEnd(8) + '  RUNNING', 'out');
      addLine('0003     BATCH    BTH1  100       BATCH   ' + '  SUSPENDED', 'out');
      addLine('RESPONSE: NORMAL', 'ok');
      return;
    }

    if (cmd.startsWith('INQUIRE TRANSACTION(')) {
      const m = cmd.match(/INQUIRE TRANSACTION\((\w+)\)/);
      const tx = m ? m[1] : 'CUST';
      addLine(`TRANSACTION: ${tx}`, 'out');
      addLine(`PROGRAM    : ${tx === 'CUST' ? 'CUSTMNT' : tx === 'ACCT' ? 'ACCTMNT' : tx === 'TRAN' ? 'TRANPST' : tx === 'CECI' ? 'DFHCEIP' : 'DFHDFLT'}`, 'out');
      addLine(`PRIORITY   : 255`, 'out');
      addLine(`STATUS     : ENABLED`, 'out');
      addLine(`SECURITY   : NONE  (*** VULN: NO RACF/ACF2 PROTECTION ***)`, 'warn');
      addLine('RESPONSE: NORMAL', 'ok');
      return;
    }

    if (cmd.startsWith('WRITE OPERATOR TEXT(')) {
      const m = raw.match(/TEXT\(['"]?(.+?)['"]?\)/i);
      const msg = m ? m[1] : 'TEST MESSAGE';
      addLine(`OPERATOR MESSAGE WRITTEN: ${msg}`, 'ok');
      addLine(`TIMESTAMP: ${today()} - LOGGED TO: SYS1.OPERLOG`, 'out');
      // VULN: unsanitised operator message — format string injection possible
      addLine(`*** VULN: MESSAGE NOT SANITISED - FORMAT STRING INJECTION POSSIBLE ***`, 'warn');
      return;
    }

    if (cmd.startsWith('LINK PROGRAM(') || cmd.startsWith('XCTL PROGRAM(')) {
      const m = cmd.match(/PROGRAM\((\w+)\)/);
      const prog = m ? m[1] : 'UNKNOWN';
      addLine(`*** VULN: UNAUTHENTICATED PROGRAM LINK/XCTL ATTEMPTED ***`, 'warn');
      addLine(`LINKING TO PROGRAM: ${prog}`, 'out');
      addLine(`COMMAREA PASSED WITHOUT VALIDATION - POTENTIAL OVERFLOW`, 'warn');
      addLine(`COBOL VULN #6 - DFHCOMMAREA.SYSTEM-CONTROL EXPOSED`, 'warn');
      addLine('RESPONSE: NORMAL  (LINK SIMULATED)', 'ok');
      return;
    }

    if (cmd.startsWith('GET CONTAINER(')) {
      addLine(`*** VULN: NO MAXFLENGTH SPECIFIED ON GET CONTAINER (COBOL VULN #15) ***`, 'warn');
      addLine(`CONTAINER DATA READ INTO USER-INPUT (100 BYTES)`, 'out');
      addLine(`OVERFLOW INTO SECURITY-CONTROL-FLAGS POSSIBLE`, 'warn');
      addLine(`AUTHENTICATED-FLAG COULD BE OVERWRITTEN WITH 'Y'`, 'warn');
      addLine('RESPONSE: NORMAL', 'ok');
      return;
    }

    if (cmd.startsWith('DELETE FILE(') || cmd.startsWith('WRITE FILE(')) {
      const m = cmd.match(/FILE\((\w+)\)/);
      const file = m ? m[1] : 'CUSTMAST';
      addLine(`*** DANGEROUS: DIRECT FILE ${cmd.startsWith('DELETE') ? 'DELETE' : 'WRITE'} COMMAND ***`, 'warn');
      addLine(`FILE: ${file}  NO AUTHORISATION CHECK PERFORMED`, 'warn');
      if (cmd.startsWith('DELETE FILE(')) {
        try {
          addLine(`SIMULATING DELETE ON ${file}...`, 'out');
          if (file === 'CUSTMAST' || file === 'CUSTOMER') {
            const recs = await base44.entities.Customer.list('-created_date', 1);
            if (recs.length > 0) {
              addLine(`RECORD DELETED: ${recs[0].customer_id} - ${recs[0].surname}`, 'out');
            }
          }
          addLine('RESPONSE: NORMAL', 'ok');
        } catch(e) {
          addLine('RESPONSE: ERROR - ' + e.message, 'err');
        }
      } else {
        addLine('RESPONSE: NORMAL  (WRITE SIMULATED)', 'ok');
      }
      return;
    }

    if (cmd === 'PERFORM SHUTDOWN IMMEDIATE') {
      addLine(`*** CRITICAL: CICS REGION SHUTDOWN COMMAND ISSUED ***`, 'warn');
      addLine(`*** VULN: NO SECURITY CHECK - ANY USER CAN SHUTDOWN REGION ***`, 'warn');
      addLine(`SHUTDOWN INITIATED... (SIMULATED - TERMINAL WILL RESTART)`, 'out');
      setTimeout(() => onBack('MENU'), 2000);
      return;
    }

    if (cmd === 'DEBUG DUMP' || cmd === 'PERFORM DUMPCODE ADD DUMPCODE(CECI) TITLE(DEBUG)') {
      addLine(`*** VULN #14: MEMORY DUMP - SENSITIVE DATA EXPOSED ***`, 'warn');
      addLine(``, 'out');
      COBOL_VULN.split('\n').forEach(l => addLine(l, 'cobol'));
      addLine(``, 'out');
      addLine(`AUTHENTICATED-FLAG : Y  (*** OVERWRITTEN VIA BUFFER OVERFLOW ***)`, 'warn');
      addLine(`ADMIN-FLAG         : Y`, 'warn');
      addLine(`CUST-PIN           : 9999  (MASTER BYPASS PIN EXPOSED)`, 'warn');
      addLine(`SENSITIVE-TEMP     : <UNINITIALISED MEMORY>`, 'out');
      addLine(`LOG-BUFFER         : OPERATOR:${operatorId} IP:192.168.1.42 SESS:TN3270`, 'out');
      return;
    }

    if (cmd === 'INQUIRE CONNECTION ALL' || cmd === 'INQUIRE CONNECTIONS') {
      addLine('CONNECTION  TYPE    STATUS    NETNAME   SESSIONS', 'out');
      addLine('----------  ------  --------  --------  --------', 'out');
      addLine('BANKDB01    MRO     ACQUIRED  BANKDB01  012', 'out');
      addLine('TERM001     LUTYPE2 ACQUIRED  LT0042    001', 'out');
      addLine(`*** VULN: TN3270 CONNECTION - PLAINTEXT PORT 23 - NO TLS ***`, 'warn');
      addLine(`*** DATA TRANSMITTED UNENCRYPTED OVER NETWORK (COBOL VULN #1) ***`, 'warn');
      addLine('RESPONSE: NORMAL', 'ok');
      return;
    }

    // Generic unrecognised command
    addLine(`EXEC CICS ${cmd}`, 'out');
    addLine(`RESPONSE: NORMAL  (COMMAND INTERPRETED - NO AUTH CHECK PERFORMED)`, 'ok');
    addLine(`*** VULN: ARBITRARY CICS COMMAND EXECUTED WITHOUT AUTHORISATION ***`, 'warn');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (!input.trim()) return;
      setHistory(h => [input, ...h.slice(0, 49)]);
      setHistIdx(-1);
      execCommand(input);
      setInput('');
    }
    if (e.key === 'ArrowUp') {
      const next = Math.min(histIdx + 1, history.length - 1);
      setHistIdx(next);
      setInput(history[next] || '');
    }
    if (e.key === 'ArrowDown') {
      const next = Math.max(histIdx - 1, -1);
      setHistIdx(next);
      setInput(next === -1 ? '' : history[next] || '');
    }
    if (e.key === 'F3') onBack('MENU');
    if (e.key === 'F1') onBack('HELP');
  };

  const colors = { sys: '#668866', out: '#33FF33', ok: '#AAFFAA', warn: '#FF9933', err: '#FF3333', input: '#3399FF', cobol: '#FFFF66' };

  return (
    <div onKeyDown={handleKeyDown} style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', fontFamily: "'Courier New', monospace", fontSize: '12px', paddingBottom: '60px' }}>
      {/* Header */}
      <div style={{ background: '#001a00', padding: '2px 8px', borderBottom: '1px solid #336633', color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between' }}>
        <span>CECI - COMMAND LEVEL INTERPRETER/EXAMINER</span>
        <span style={{ color: '#FF9933' }}>⚠ UNAUTHENTICATED ACCESS</span>
        <span>PF3=END</span>
      </div>
      {/* Output */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px', background: '#000' }}>
        {output.map((l, i) => (
          <div key={i} style={{ color: colors[l.t] || '#33FF33', whiteSpace: 'pre', lineHeight: '1.6' }}>{l.v}</div>
        ))}
        <div ref={bottomRef} />
      </div>
      {/* Input */}
      <div style={{ padding: '4px 8px', borderTop: '1px solid #336633', display: 'flex', alignItems: 'center', gap: '8px', background: '#001100' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>EXEC CICS</span>
        <input
          autoFocus
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF', color: '#3399FF', fontFamily: 'inherit', fontSize: '13px', outline: 'none' }}
        />
        <span style={{ color: '#668866' }}>↑↓=HIST</span>
      </div>
    </div>
  );
}