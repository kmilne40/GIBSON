import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';
import TransactionHistory from './TransactionHistory';
import { logAudit } from '@/lib/auditLogger';

const EMPTY = { account_number: '', tran_type: 'CR', amount: '', description: '', reference: '', to_account: '', value_date: '' };

const SQL_PATTERNS = /('|--|;|OR\s+1=1|OR\s+'1'='1|UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO|DELETE\s+FROM|SELECT\s+\*)/i;
const hasSQLi = (val) => SQL_PATTERNS.test(val);

export default function TransactionScreen({ operatorId, onBack, weaknesses = {} }) {
  const [fields, setFields] = useState(EMPTY);
  const [message, setMessage] = useState('TRANSACTION POSTING  -  ENTER ACCOUNT-NUMBER AND TRANSACTION DETAILS');
  const [msgType, setMsgType] = useState('normal');
  const [showHistory, setShowHistory] = useState(false);
  const [abend, setAbend] = useState(null);

  const today = () => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; };
  const timeNow = () => { const d = new Date(); return `${String(d.getHours()).padStart(2,'0')}${String(d.getMinutes()).padStart(2,'0')}${String(d.getSeconds()).padStart(2,'0')}`; };
  const setF = (k, v) => setFields(f => ({ ...f, [k]: v }));
  const setMsg = (msg, type = 'normal') => { setMessage(msg); setMsgType(type); };

  const padId = () => 'T' + String(Date.now()).slice(-11);

  const handlePost = async () => {
    // VULN: SQL injection in account_number or reference
    if (weaknesses.sql_injection && (hasSQLi(fields.account_number) || hasSQLi(fields.reference))) {
      setMsg('⚠ SQL INJECTION DETECTED — DSNT408I SQLCODE=-204  DSNT418I SQLSTATE=42704 — DB2 STATEMENT ERROR', 'error');
      return;
    }
    // VULN: COMMAREA overflow in description or reference
    if (weaknesses.commarea_overflow && (fields.description.length > 100 || fields.reference.length > 100)) {
      setAbend({ code: 'ASRA', msg: `DFHAC2236 ABEND ASRA — COMMAREA OVERFLOW IN FIELD ${fields.description.length > 100 ? 'DESCRIPTION' : 'REFERENCE'} — LENGTH ${Math.max(fields.description.length, fields.reference.length)} EXCEEDS BOUNDARY +100` });
      return;
    }
    if (!fields.account_number.trim()) { setMsg('INVREQ - ACCOUNT-NUMBER IS REQUIRED', 'error'); return; }
    if (!fields.amount || isNaN(parseFloat(fields.amount)) || parseFloat(fields.amount) <= 0) { setMsg('INVREQ - AMOUNT MUST BE A POSITIVE NUMERIC VALUE', 'error'); return; }
    if (!['CR','DR','TRF'].includes(fields.tran_type.trim().toUpperCase())) { setMsg('INVREQ - TRAN TYPE MUST BE CR, DR OR TRF', 'error'); return; }
    if (fields.tran_type === 'TRF' && !fields.to_account.trim()) { setMsg('INVREQ - TO-ACCOUNT REQUIRED FOR TRANSFER', 'error'); return; }

    // Fetch account
    const acctRes = await base44.entities.Account.filter({ account_number: fields.account_number.trim() });
    if (acctRes.length === 0) { setMsg('NOTFND - ACCOUNT NOT ON FILE', 'error'); return; }
    const account = acctRes[0];
    if (account.status === 'F') { setMsg('ACTIDERR - ACCOUNT IS FROZEN - TRANSACTIONS NOT PERMITTED', 'error'); return; }

    const amt = parseFloat(fields.amount);
    let newBalance = account.balance;
    if (fields.tran_type === 'CR') newBalance = account.balance + amt;
    else if (fields.tran_type === 'DR') newBalance = account.balance - amt;
    else if (fields.tran_type === 'TRF') newBalance = account.balance - amt;

    // Check credit limit
    if (newBalance < 0 && Math.abs(newBalance) > account.credit_limit) {
      setMsg('CREDLMT - TRANSACTION WOULD EXCEED CREDIT LIMIT - REFER TO MANAGER', 'error'); return;
    }

    const postDate = today();
    const postTime = timeNow();
    const tranId = padId();

    // Post transaction
    await base44.entities.Transaction.create({
      tran_id: tranId, account_number: fields.account_number.trim(),
      tran_type: fields.tran_type, amount: amt,
      description: fields.description, reference: fields.reference,
      to_account: fields.to_account, value_date: fields.value_date || postDate,
      post_date: postDate, post_time: postTime,
      balance_after: newBalance, operator_id: operatorId,
    });

    // Update account balance
    await base44.entities.Account.update(account.id, { balance: newBalance, last_update_date: postDate, operator_id: operatorId });

    // For transfer, credit the destination
    if (fields.tran_type === 'TRF') {
      const toRes = await base44.entities.Account.filter({ account_number: fields.to_account.trim() });
      if (toRes.length > 0) {
        const toAcct = toRes[0];
        const toNewBal = toAcct.balance + amt;
        await base44.entities.Transaction.create({
          tran_id: 'T' + String(Date.now()).slice(-11) + '1', account_number: fields.to_account.trim(),
          tran_type: 'CR', amount: amt,
          description: 'TRANSFER FROM ' + fields.account_number.trim(),
          reference: fields.reference, to_account: '', value_date: fields.value_date || postDate,
          post_date: postDate, post_time: postTime,
          balance_after: toNewBal, operator_id: operatorId,
        });
        await base44.entities.Account.update(toAcct.id, { balance: toNewBal, last_update_date: postDate, operator_id: operatorId });
      }
    }

    setMsg(`NORMAL - TRAN ${tranId} POSTED. BAL: ${newBalance < 0 ? '-' : ''}GBP ${Math.abs(newBalance).toFixed(2)}`, 'success');
    logAudit({
      event_type: 'TRANSACTION',
      operator_id: operatorId,
      details: `TRAN-ID: ${tranId}  TYPE: ${fields.tran_type}  ACCOUNT: ${fields.account_number.trim()}  AMOUNT: £${amt.toFixed(2)}  DESC: ${fields.description}  REF: ${fields.reference}${fields.tran_type === 'TRF' ? `  TO: ${fields.to_account.trim()}` : ''}  BAL-AFTER: £${newBalance.toFixed(2)}`,
      result: 'SUCCESS',
      affected_entity: fields.account_number.trim(),
      row_count: 1,
      duration_ms: null,
    });
    setFields(f => ({ ...EMPTY, account_number: f.account_number }));
  };

  const handleHistory = () => {
    if (!fields.account_number.trim()) { setMsg('INVREQ - ACCOUNT-NUMBER REQUIRED TO VIEW HISTORY', 'error'); return; }
    setShowHistory(true);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'F1') onBack('HELP_TRAN');
    if (e.key === 'F3') onBack('MENU');
    if (e.key === 'F5') { e.preventDefault(); handlePost(); }
    if (e.key === 'F8') { e.preventDefault(); handleHistory(); }
    if (e.key === 'F12') onBack('CODE_TRAN');
    if (e.key === 'Escape') { setFields(EMPTY); setMsg('SCREEN CLEARED - READY FOR INPUT'); }
  };

  if (showHistory) {
    return <TransactionHistory accountNumber={fields.account_number} operatorId={operatorId} onBack={() => setShowHistory(false)} onTopBack={onBack} />;
  }

  // ABEND overlay
  if (abend) {
    return (
      <div style={{ flex: 1, padding: '20px', fontFamily: "'Courier New', monospace", fontSize: '13px', background: '#000' }}>
        <div style={{ color: '#FF3333', fontWeight: 'bold', fontSize: '15px', marginBottom: '8px' }}>*** CICS ABEND — TRANSACTION TERMINATED ***</div>
        <div style={{ color: '#FF9933', marginBottom: '4px' }}>ABEND CODE : {abend.code}</div>
        <div style={{ color: '#AAFFAA', marginBottom: '12px', wordBreak: 'break-all' }}>{abend.msg}</div>
        <div style={{ color: '#668866', fontSize: '11px', marginBottom: '16px' }}>
          DFHAP0001  CICS IS UNABLE TO RECOVER  —  TRANSACTION DUMPED TO SYS1.DUMPxx<br/>
          PSW AT TIME OF ABEND:  00000000  80000000  07F3A2B4
        </div>
        <button onClick={() => { setAbend(null); setFields(EMPTY); setMsg('ABEND CLEARED — SCREEN RESET', 'error'); }}
          style={{ background: '#001100', border: '1px solid #FF3333', color: '#FF3333', fontFamily: 'inherit', fontSize: '12px', padding: '4px 12px', cursor: 'pointer' }}>
          ENTER — CLEAR ABEND
        </button>
      </div>
    );
  }

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;
  const msgColor = msgType === 'error' ? '#FF3333' : msgType === 'success' ? '#AAFFAA' : '#33FF33';

  const iStyle = (w, up = true) => ({
    background: 'transparent', border: 'none',
    borderBottom: '1px solid #3399FF',
    color: '#3399FF', fontFamily: "'Courier New', monospace",
    fontSize: '13px', outline: 'none',
    textTransform: up ? 'uppercase' : 'none',
    padding: 0, width: `${w}ch`,
  });

  return (
    <div onKeyDown={handleKeyDown} style={{ flex: 1, padding: '6px 8px', fontFamily: "'Courier New', monospace", fontSize: '13px', paddingBottom: '60px', overflowY: 'auto' }}>
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span>BANKMASTER/VS - TRANSACTION POSTING</span>
        <span>TRANPST</span>
        <span>DATE: {dateStr}</span>
      </div>
      <div style={{ color: '#33FF33', marginBottom: '6px' }}>{'─'.repeat(79)}</div>

      {/* Vulnerability indicator */}
      {(weaknesses.sql_injection || weaknesses.commarea_overflow) && (
        <div style={{ color: '#553300', fontSize: '10px', marginBottom: '4px' }}>
          ACTIVE VULNS:{weaknesses.sql_injection ? ' ⚠ SQLI' : ''}{weaknesses.commarea_overflow ? ' ⚠ OVERFLOW (DESC/REF >100 CHARS)' : ''}
        </div>
      )}

      {/* Account and type */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>ACCOUNT-NUMBER :</span>
        {/* VULN: SQL injection — allow special chars when vulnerability active */}
        <input value={fields.account_number} onChange={e => { const v = weaknesses.sql_injection ? e.target.value.slice(0,40) : e.target.value.replace(/\D/g,'').slice(0,10); setF('account_number', v); }} maxLength={weaknesses.sql_injection ? 40 : 10} style={iStyle(weaknesses.sql_injection ? 30 : 10)} autoComplete="off" />
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>TRAN TYPE  :</span>
        <input value={fields.tran_type} onChange={e => setF('tran_type', e.target.value.toUpperCase().slice(0,3))} maxLength={3} style={iStyle(3)} autoComplete="off" />
        <span style={{ color: '#668866', marginLeft: '2px' }}>CR/DR/TRF</span>
      </div>

      {/* Amount and reference */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>AMOUNT         :</span>
        <input value={fields.amount} onChange={e => setF('amount', e.target.value.replace(/[^0-9.]/g,'').slice(0,13))} maxLength={13} style={{ ...iStyle(13, false) }} autoComplete="off" />
        <span style={{ color: '#668866', marginLeft: '2px' }}>DO NOT ENTER CURRENCY SYMBOL</span>
      </div>

      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>REFERENCE      :</span>
        {/* VULN: SQL injection — allow long/special input; COMMAREA overflow — allow long input */}
        <input value={fields.reference} onChange={e => setF('reference', (weaknesses.sql_injection || weaknesses.commarea_overflow) ? e.target.value.toUpperCase().slice(0,120) : e.target.value.toUpperCase().slice(0,12))} maxLength={weaknesses.sql_injection || weaknesses.commarea_overflow ? 120 : 12} style={iStyle(weaknesses.sql_injection || weaknesses.commarea_overflow ? 30 : 12)} autoComplete="off" />
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '14ch' }}>VALUE DATE  :</span>
        <input value={fields.value_date} onChange={e => setF('value_date', e.target.value.slice(0,8))} maxLength={8} style={iStyle(8)} placeholder="DD/MM/YY" autoComplete="off" />
      </div>

      {/* Description */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>DESCRIPTION    :</span>
        {/* VULN: COMMAREA overflow — allow >100 chars to trigger ABEND */}
        <input value={fields.description} onChange={e => setF('description', weaknesses.commarea_overflow ? e.target.value.toUpperCase().slice(0,120) : e.target.value.toUpperCase().slice(0,40))} maxLength={weaknesses.commarea_overflow ? 120 : 40} style={iStyle(weaknesses.commarea_overflow ? 40 : 40)} autoComplete="off" />
      </div>

      {/* Transfer destination */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: fields.tran_type === 'TRF' ? '#AAFFAA' : '#446644', fontWeight: 'bold', width: '18ch' }}>TO-ACCOUNT     :</span>
        <input value={fields.to_account} onChange={e => setF('to_account', e.target.value.replace(/\D/g,'').slice(0,10))} maxLength={10} disabled={fields.tran_type !== 'TRF'} style={{ ...iStyle(10), opacity: fields.tran_type === 'TRF' ? 1 : 0.4 }} autoComplete="off" />
        <span style={{ color: '#668866', marginLeft: '2px' }}>REQUIRED FOR TRF TYPE ONLY</span>
      </div>

      <div style={{ color: '#33FF33', margin: '4px 0' }}>{'─'.repeat(79)}</div>
      <div style={{ color: msgColor, fontWeight: 'bold', marginTop: '4px', minHeight: '1.4em' }}>==&gt; {message}</div>
      <div style={{ color: '#668866', fontSize: '12px', marginTop: '4px' }}>
        PF5=POST TRANSACTION  PF8=VIEW HISTORY  PF3=MENU  PF1=HELP  PF12=CODE  ESC=CLEAR
      </div>
      <div style={{ display: 'flex', gap: '6px', marginTop: '6px', flexWrap: 'wrap' }}>
        {[
          { label: 'PF5 POST', fn: handlePost, color: '#AAFFAA' },
          { label: 'PF8 HISTORY', fn: handleHistory, color: '#33FF33' },
          { label: 'PF3 MENU', fn: () => onBack('MENU') },
          { label: 'ESC CLEAR', fn: () => { setFields(EMPTY); setMsg('SCREEN CLEARED'); } },
        ].map(({ label, fn, color = '#33FF33' }) => (
          <button key={label} onClick={fn} style={{
            background: '#001100', border: '1px solid #336633',
            color, fontFamily: 'inherit', fontSize: '12px',
            padding: '2px 8px', cursor: 'pointer',
          }}>{label}</button>
        ))}
      </div>
    </div>
  );
}