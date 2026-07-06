import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const EMPTY = { account_number: '', customer_id: '', account_type: 'CUR', sort_code: '', open_date: '', currency: 'GBP', balance: '', credit_limit: '', interest_rate: '', status: 'A', operator_id: '', last_update_date: '' };

const SQL_PATTERNS = /('|--|;|OR\s+1=1|OR\s+'1'='1|UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO|DELETE\s+FROM|SELECT\s+\*)/i;
const hasSQLi = (val) => SQL_PATTERNS.test(val);
const OVERFLOW_LIMIT = 20;

export default function AccountScreen({ operatorId, onBack, weaknesses = {} }) {
  const [fields, setFields] = useState(EMPTY);
  const [message, setMessage] = useState('ACCOUNT MAINTENANCE  -  ENTER ACCOUNT-NUMBER AND SELECT ACTION');
  const [msgType, setMsgType] = useState('normal');
  const [abend, setAbend] = useState(null);

  const today = () => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; };

  const setF = (k, v) => {
    // VULN: COMMAREA overflow on certain fields
    if (weaknesses.commarea_overflow && ['account_number', 'currency', 'sort_code'].includes(k) && v.length > OVERFLOW_LIMIT) {
      setAbend({ code: 'ASRA', msg: `DFHAC2236 ABEND ASRA — DATA OVERFLOW IN FIELD ${k.toUpperCase()} — INPUT LENGTH ${v.length} EXCEEDS COMMAREA BOUNDARY +${OVERFLOW_LIMIT}` });
      return;
    }
    setFields(f => ({ ...f, [k]: v }));
  };

  const setMsg = (msg, type = 'normal') => { setMessage(msg); setMsgType(type); };

  const handleInquire = async () => {
    if (!fields.account_number.trim()) { setMsg('INVREQ - ACCOUNT-NUMBER REQUIRED FOR INQUIRY', 'error'); return; }
    // VULN: SQL injection on account inquiry
    if (weaknesses.sql_injection && hasSQLi(fields.account_number)) {
      const all = await base44.entities.Account.list();
      setMsg(`⚠ SQL INJECTION — DSNT408I SQLCODE=-204 — UNQUALIFIED QUERY RETURNED ${all.length} ROWS (ALL ACCOUNTS EXPOSED)`, 'error');
      if (all.length > 0) setFields({ ...EMPTY, ...all[0], balance: String(all[0].balance), credit_limit: String(all[0].credit_limit), interest_rate: String(all[0].interest_rate) });
      return;
    }
    const res = await base44.entities.Account.filter({ account_number: fields.account_number.trim() });
    if (res.length === 0) { setMsg('NOTFND - ACCOUNT NOT ON FILE', 'error'); return; }
    setFields({ ...EMPTY, ...res[0], balance: String(res[0].balance), credit_limit: String(res[0].credit_limit), interest_rate: String(res[0].interest_rate) });
    setMsg('NORMAL - ACCOUNT RECORD RETRIEVED SUCCESSFULLY', 'success');
  };

  const handleOpen = async () => {
    if (!fields.account_number.trim() || !fields.customer_id.trim()) { setMsg('INVREQ - ACCOUNT-NUMBER AND CUSTOMER-ID REQUIRED', 'error'); return; }
    const existing = await base44.entities.Account.filter({ account_number: fields.account_number.trim() });
    if (existing.length > 0) { setMsg('DUPKEY - ACCOUNT NUMBER ALREADY EXISTS', 'error'); return; }
    const custCheck = await base44.entities.Customer.filter({ customer_id: fields.customer_id.trim() });
    if (custCheck.length === 0) { setMsg('NOTFND - CUSTOMER ID NOT ON FILE - CANNOT OPEN ACCOUNT', 'error'); return; }
    await base44.entities.Account.create({ ...fields, balance: parseFloat(fields.balance) || 0, credit_limit: parseFloat(fields.credit_limit) || 0, interest_rate: parseFloat(fields.interest_rate) || 0, operator_id: operatorId, open_date: today(), last_update_date: today() });
    setMsg('NORMAL - ACCOUNT OPENED SUCCESSFULLY', 'success');
  };

  const handleModify = async () => {
    if (!fields.account_number.trim()) { setMsg('INVREQ - ACCOUNT-NUMBER REQUIRED FOR MODIFY', 'error'); return; }
    const res = await base44.entities.Account.filter({ account_number: fields.account_number.trim() });
    if (res.length === 0) { setMsg('NOTFND - ACCOUNT NOT FOUND - CANNOT MODIFY', 'error'); return; }
    await base44.entities.Account.update(res[0].id, { ...fields, balance: parseFloat(fields.balance) || 0, credit_limit: parseFloat(fields.credit_limit) || 0, interest_rate: parseFloat(fields.interest_rate) || 0, operator_id: operatorId, last_update_date: today() });
    setMsg('NORMAL - ACCOUNT RECORD UPDATED SUCCESSFULLY', 'success');
  };

  const handleNext = async () => {
    if (!fields.customer_id.trim()) { setMsg('INVREQ - CUSTOMER-ID REQUIRED FOR NEXT ACCOUNT', 'error'); return; }
    const res = await base44.entities.Account.filter({ customer_id: fields.customer_id.trim() });
    if (res.length === 0) { setMsg('NOTFND - NO ACCOUNTS FOUND FOR CUSTOMER', 'error'); return; }
    const currentIdx = res.findIndex(a => a.account_number === fields.account_number.trim());
    const next = res[(currentIdx + 1) % res.length];
    setFields({ ...EMPTY, ...next, balance: String(next.balance), credit_limit: String(next.credit_limit), interest_rate: String(next.interest_rate) });
    setMsg(`NORMAL - ACCOUNT ${next.account_number} RETRIEVED (${currentIdx + 2} OF ${res.length})`, 'success');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'F1') onBack('HELP_ACCT');
    if (e.key === 'F3') onBack('MENU');
    if (e.key === 'F5') { e.preventDefault(); handleOpen(); }
    if (e.key === 'F6') { e.preventDefault(); handleModify(); }
    if (e.key === 'F8') { e.preventDefault(); handleInquire(); }
    if (e.key === 'F9') { e.preventDefault(); handleNext(); }
    if (e.key === 'F12') onBack('CODE_ACCT');
    if (e.key === 'Escape') { setFields(EMPTY); setMsg('SCREEN CLEARED - READY FOR INPUT'); }
  };

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;
  const msgColor = msgType === 'error' ? '#FF3333' : msgType === 'success' ? '#AAFFAA' : '#33FF33';

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

  const iStyle = (w) => ({
    background: 'transparent', border: 'none',
    borderBottom: '1px solid #3399FF',
    color: '#3399FF', fontFamily: "'Courier New', monospace",
    fontSize: '13px', outline: 'none', textTransform: 'uppercase',
    padding: 0, width: `${w}ch`,
  });

  const numStyle = (w) => ({ ...iStyle(w), textTransform: 'none' });

  const fmtBalance = (v) => {
    const n = parseFloat(v);
    if (isNaN(n)) return '             ';
    return (n < 0 ? '-' : ' ') + Math.abs(n).toFixed(2).padStart(12);
  };

  return (
    <div onKeyDown={handleKeyDown} style={{ flex: 1, padding: '6px 8px', fontFamily: "'Courier New', monospace", fontSize: '13px', paddingBottom: '60px', overflowY: 'auto' }}>
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span>BANKMASTER/VS - ACCOUNT MAINTENANCE & INQUIRY</span>
        <span>ACCTMNT</span>
        <span>DATE: {dateStr}</span>
      </div>
      <div style={{ color: '#33FF33', marginBottom: '6px' }}>{'─'.repeat(79)}</div>

      {/* Vulnerability indicator */}
      {(weaknesses.sql_injection || weaknesses.commarea_overflow || weaknesses.field_protection) && (
        <div style={{ color: '#553300', fontSize: '10px', marginBottom: '4px' }}>
          ACTIVE VULNS:{weaknesses.sql_injection ? ' ⚠ SQLI' : ''}{weaknesses.commarea_overflow ? ' ⚠ OVERFLOW' : ''}{weaknesses.field_protection ? ' ⚠ FLDPROT' : ''}
        </div>
      )}

      {/* Account identity */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>ACCOUNT-NUMBER :</span>
        {/* VULN: SQLi — allow special chars; field_protection — allow editing after load */}
        <input value={fields.account_number} onChange={e => { const v = weaknesses.sql_injection ? e.target.value.slice(0,30) : e.target.value.replace(/\D/g,'').slice(0,10); setF('account_number', v); }} maxLength={weaknesses.sql_injection ? 30 : 10} style={{ ...iStyle(weaknesses.sql_injection ? 30 : 10), borderColor: weaknesses.field_protection ? '#FF9933' : '#3399FF', color: weaknesses.field_protection ? '#FF9933' : '#3399FF' }} autoComplete="off" />
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '14ch' }}>CUSTOMER-ID :</span>
        <input value={fields.customer_id} onChange={e => setF('customer_id', e.target.value.replace(/\D/g,'').slice(0,8))} maxLength={8} style={iStyle(8)} autoComplete="off" />
      </div>

      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>ACCOUNT-TYPE   :</span>
        <input value={fields.account_type} onChange={e => setF('account_type', e.target.value.toUpperCase().slice(0,3))} maxLength={3} style={iStyle(3)} autoComplete="off" />
        <span style={{ color: '#668866', marginLeft: '2px' }}>SAV/CUR/OVD/LON</span>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '16px', width: '14ch' }}>SORT-CODE   :</span>
        <input value={fields.sort_code} onChange={e => setF('sort_code', e.target.value.replace(/\D/g,'').slice(0,6))} maxLength={6} style={iStyle(6)} autoComplete="off" />
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>CURRENCY :</span>
        <input value={fields.currency} onChange={e => setF('currency', e.target.value.toUpperCase().slice(0,3))} maxLength={3} style={iStyle(3)} autoComplete="off" />
        <span style={{ color: '#668866', marginLeft: '2px' }}>GBP/USD/EUR</span>
      </div>

      <div style={{ color: '#33FF33', margin: '4px 0' }}>{'─'.repeat(79)}</div>

      {/* Financials */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>CURRENT BALANCE:</span>
        <span style={{ color: parseFloat(fields.balance) < 0 ? '#FF3333' : '#AAFFAA', fontWeight: 'bold', width: '16ch', textAlign: 'right' }}>
          {fmtBalance(fields.balance)}
        </span>
        <input value={fields.balance} onChange={e => setF('balance', e.target.value)} maxLength={14} style={{ ...numStyle(14), marginLeft: '4px' }} autoComplete="off" />
      </div>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>CREDIT LIMIT   :</span>
        <input value={fields.credit_limit} onChange={e => setF('credit_limit', e.target.value)} maxLength={12} style={numStyle(12)} autoComplete="off" />
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '16px', width: '14ch' }}>INT RATE    :</span>
        <input value={fields.interest_rate} onChange={e => setF('interest_rate', e.target.value)} maxLength={6} style={numStyle(6)} autoComplete="off" />
        <span style={{ color: '#668866', marginLeft: '2px' }}>% P.A.</span>
      </div>

      <div style={{ color: '#33FF33', margin: '4px 0' }}>{'─'.repeat(79)}</div>

      {/* Status and dates */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>ACCOUNT STATUS :</span>
        <input value={fields.status} onChange={e => setF('status', e.target.value.toUpperCase().slice(0,1))} maxLength={1} style={iStyle(1)} autoComplete="off" />
        <span style={{ color: '#668866', marginLeft: '2px' }}>A=ACTIVE D=DORMANT F=FROZEN</span>
      </div>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '18ch' }}>OPEN DATE      :</span>
        {/* VULN: field_protection bypass — OPEN DATE becomes editable */}
        {weaknesses.field_protection
          ? <input value={fields.open_date || ''} onChange={e => setFields(f => ({ ...f, open_date: e.target.value.slice(0,8) }))} maxLength={8} style={{ background: 'transparent', border: 'none', borderBottom: '1px solid #FF9933', color: '#FF9933', fontFamily: "'Courier New', monospace", fontSize: '13px', outline: 'none', padding: 0, width: '10ch' }} autoComplete="off" />
          : <span style={{ color: '#33FF33' }}>{fields.open_date || '        '}</span>
        }
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '16px', width: '14ch' }}>LAST UPD    :</span>
        <span style={{ color: '#33FF33' }}>{fields.last_update_date || '        '}</span>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>OPERATOR :</span>
        <span style={{ color: '#33FF33' }}>{fields.operator_id || '        '}</span>
      </div>

      <div style={{ color: '#33FF33', margin: '4px 0' }}>{'─'.repeat(79)}</div>

      <div style={{ color: msgColor, fontWeight: 'bold', marginTop: '4px', minHeight: '1.4em' }}>==&gt; {message}</div>
      <div style={{ color: '#668866', fontSize: '12px', marginTop: '4px' }}>
        PF5=OPEN  PF6=MODIFY  PF8=INQUIRE  PF9=NEXT ACCT  PF3=MENU  PF1=HELP  PF12=CODE  ESC=CLEAR
      </div>
      <div style={{ display: 'flex', gap: '6px', marginTop: '6px', flexWrap: 'wrap' }}>
        {[
          { label: 'PF5 OPEN', fn: handleOpen },
          { label: 'PF6 MODIFY', fn: handleModify },
          { label: 'PF8 INQUIRE', fn: handleInquire },
          { label: 'PF9 NEXT ACCT', fn: handleNext },
          { label: 'PF3 MENU', fn: () => onBack('MENU') },
          { label: 'ESC CLEAR', fn: () => { setFields(EMPTY); setMsg('SCREEN CLEARED'); } },
        ].map(({ label, fn }) => (
          <button key={label} onClick={fn} style={{
            background: '#001100', border: '1px solid #336633',
            color: '#33FF33', fontFamily: 'inherit', fontSize: '12px',
            padding: '2px 8px', cursor: 'pointer',
          }}>{label}</button>
        ))}
      </div>
    </div>
  );
}