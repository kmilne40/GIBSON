import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const EMPTY = { customer_id: '', surname: '', forename: '', dob: '', sort_code: '', ni_number: '', address1: '', address2: '', address3: '', postcode: '', status: 'A', customer_type: 'P', open_date: '', operator_id: '', last_update_date: '' };

// Detect SQL injection patterns
const SQL_PATTERNS = /('|--|;|OR\s+1=1|OR\s+'1'='1|UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO|DELETE\s+FROM|SELECT\s+\*)/i;
const hasSQLi = (val) => SQL_PATTERNS.test(val);
const OVERFLOW_LIMIT = 50;

export default function CustomerScreen({ operatorId, onBack, weaknesses = {} }) {
  const [fields, setFields] = useState(EMPTY);
  const [message, setMessage] = useState('CUSTOMER MASTER MAINTENANCE  -  ENTER CUSTOMER-ID AND SELECT ACTION');
  const [msgType, setMsgType] = useState('normal');
  const [focusField, setFocusField] = useState('customer_id');
  const [abend, setAbend] = useState(null);

  const today = () => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; };

  const setF = (k, v) => {
    // VULN: COMMAREA overflow — any field > OVERFLOW_LIMIT chars triggers ABEND
    if (weaknesses.commarea_overflow && v.length > OVERFLOW_LIMIT) {
      setAbend({ code: 'ASRA', msg: `DFHAC2236 ABEND ASRA — DATA BUFFER OVERRUN IN FIELD ${k.toUpperCase()} — OFFSET +${OVERFLOW_LIMIT} — COMMAREA EXCEEDED` });
      return;
    }
    setFields(f => ({ ...f, [k]: v }));
  };

  const setMsg = (msg, type = 'normal') => { setMessage(msg); setMsgType(type); };

  const handleInquire = async () => {
    if (!fields.customer_id.trim()) { setMsg('INVREQ - CUSTOMER-ID REQUIRED FOR INQUIRY', 'error'); return; }
    // VULN: SQL injection on inquiry
    if (weaknesses.sql_injection && hasSQLi(fields.customer_id)) {
      const all = await base44.entities.Customer.list();
      setMsg(`⚠ SQL INJECTION — DSNT408I SQLCODE=-204 — QUERY RETURNED ${all.length} ROWS (ALL RECORDS EXPOSED)`, 'error');
      if (all.length > 0) setFields({ ...EMPTY, ...all[0] });
      return;
    }
    const res = await base44.entities.Customer.filter({ customer_id: fields.customer_id.trim() });
    if (res.length === 0) { setMsg('NOTFND - CUSTOMER ID NOT ON FILE', 'error'); return; }
    setFields({ ...EMPTY, ...res[0] });
    setMsg('NORMAL - CUSTOMER RECORD RETRIEVED SUCCESSFULLY', 'success');
  };

  const handleAdd = async () => {
    if (!fields.customer_id.trim() || !fields.surname.trim() || !fields.forename.trim()) {
      setMsg('INVREQ - CUSTOMER-ID, SURNAME AND FORENAME ARE REQUIRED', 'error'); return;
    }
    // VULN: SQLi in text fields during add
    if (weaknesses.sql_injection && (hasSQLi(fields.surname) || hasSQLi(fields.forename))) {
      setMsg('⚠ SQL INJECTION DETECTED IN INPUT — DSNT408I SQLCODE=-104 — DB2 STATEMENT ERROR', 'error'); return;
    }
    const existing = await base44.entities.Customer.filter({ customer_id: fields.customer_id.trim() });
    if (existing.length > 0) { setMsg('DUPKEY - CUSTOMER ID ALREADY EXISTS ON FILE', 'error'); return; }
    await base44.entities.Customer.create({ ...fields, operator_id: operatorId, open_date: today(), last_update_date: today() });
    setMsg('NORMAL - CUSTOMER RECORD ADDED SUCCESSFULLY', 'success');
  };

  const handleUpdate = async () => {
    if (!fields.customer_id.trim()) { setMsg('INVREQ - CUSTOMER-ID REQUIRED FOR UPDATE', 'error'); return; }
    // VULN: SQLi in text fields during update
    if (weaknesses.sql_injection && (hasSQLi(fields.surname) || hasSQLi(fields.forename) || hasSQLi(fields.address1))) {
      setMsg('⚠ SQL INJECTION DETECTED — DSNT418I SQLSTATE=42704 — INVALID SQL STATEMENT', 'error'); return;
    }
    const res = await base44.entities.Customer.filter({ customer_id: fields.customer_id.trim() });
    if (res.length === 0) { setMsg('NOTFND - CUSTOMER NOT FOUND - CANNOT UPDATE', 'error'); return; }
    await base44.entities.Customer.update(res[0].id, { ...fields, operator_id: operatorId, last_update_date: today() });
    setMsg('NORMAL - CUSTOMER RECORD UPDATED SUCCESSFULLY', 'success');
  };

  const handleDelete = async () => {
    if (!fields.customer_id.trim()) { setMsg('INVREQ - CUSTOMER-ID REQUIRED FOR DELETE', 'error'); return; }
    const res = await base44.entities.Customer.filter({ customer_id: fields.customer_id.trim() });
    if (res.length === 0) { setMsg('NOTFND - CUSTOMER NOT FOUND - CANNOT DELETE', 'error'); return; }
    await base44.entities.Customer.update(res[0].id, { status: 'D', operator_id: operatorId, last_update_date: today() });
    setFields(f => ({ ...f, status: 'D' }));
    setMsg('NORMAL - CUSTOMER STATUS SET TO DELETED (LOGICAL DELETE)', 'success');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'F1') { if (onBack) onBack('HELP_CUST'); }
    if (e.key === 'F3') { if (onBack) onBack('MENU'); }
    if (e.key === 'F5') { e.preventDefault(); handleAdd(); }
    if (e.key === 'F6') { e.preventDefault(); handleUpdate(); }
    if (e.key === 'F7') { e.preventDefault(); handleDelete(); }
    if (e.key === 'F8') { e.preventDefault(); handleInquire(); }
    if (e.key === 'F12') { if (onBack) onBack('CODE_CUST'); }
    if (e.key === 'Escape') { setFields(EMPTY); setMsg('SCREEN CLEARED - READY FOR INPUT'); }
  };

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  const iStyle = (active) => ({
    background: 'transparent', border: 'none',
    borderBottom: `1px solid ${active ? '#3399FF' : '#336633'}`,
    color: '#3399FF', fontFamily: "'Courier New', monospace",
    fontSize: '13px', outline: 'none', textTransform: 'uppercase',
    padding: 0,
  });

  const field = (key, w, up = true, num = false) => (
    <input
      type="text"
      value={fields[key] || ''}
      onChange={e => setF(key, (up ? e.target.value.toUpperCase() : e.target.value).slice(0, w))}
      onFocus={() => setFocusField(key)}
      maxLength={w}
      style={{ ...iStyle(focusField === key), width: `${w}ch` }}
      autoComplete="off" spellCheck="false"
    />
  );

  const msgColor = msgType === 'error' ? '#FF3333' : msgType === 'success' ? '#AAFFAA' : '#33FF33';

  // ABEND overlay
  if (abend) {
    return (
      <div style={{ flex: 1, padding: '20px', fontFamily: "'Courier New', monospace", fontSize: '13px', background: '#000' }}>
        <div style={{ color: '#FF3333', fontWeight: 'bold', fontSize: '15px', marginBottom: '8px' }}>
          *** CICS ABEND — TRANSACTION TERMINATED ***
        </div>
        <div style={{ color: '#FF9933', marginBottom: '4px' }}>ABEND CODE : {abend.code}</div>
        <div style={{ color: '#AAFFAA', marginBottom: '12px', wordBreak: 'break-all' }}>{abend.msg}</div>
        <div style={{ color: '#668866', fontSize: '11px', marginBottom: '16px' }}>
          DFHAP0001  CICS IS UNABLE TO RECOVER  —  TRANSACTION DUMPED TO SYS1.DUMPxx<br/>
          PSW AT TIME OF ABEND:  00000000  80000000  07F3A2B4<br/>
          REGISTER CONTENTS SAVED TO DUMP DATASET
        </div>
        <button onClick={() => { setAbend(null); setFields(EMPTY); setMsg('ABEND CLEARED — SCREEN RESET', 'error'); }}
          style={{ background: '#001100', border: '1px solid #FF3333', color: '#FF3333', fontFamily: 'inherit', fontSize: '12px', padding: '4px 12px', cursor: 'pointer' }}>
          ENTER — CLEAR ABEND
        </button>
      </div>
    );
  }

  return (
    <div onKeyDown={handleKeyDown} style={{ flex: 1, padding: '6px 8px', fontFamily: "'Courier New', monospace", fontSize: '13px', overflowY: 'auto', paddingBottom: '60px' }}>
      {/* Header */}
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span>BANKMASTER/VS - CUSTOMER MASTER MAINTENANCE</span>
        <span>CUSTMNT</span>
        <span>DATE: {dateStr}</span>
      </div>
      <div style={{ color: '#33FF33', marginBottom: '6px' }}>{'─'.repeat(79)}</div>

      {/* Vulnerability indicator */}
      {(weaknesses.sql_injection || weaknesses.commarea_overflow || weaknesses.field_protection) && (
        <div style={{ color: '#553300', fontSize: '10px', marginBottom: '4px' }}>
          ACTIVE VULNS:{weaknesses.sql_injection ? ' ⚠ SQLI' : ''}{weaknesses.commarea_overflow ? ' ⚠ OVERFLOW' : ''}{weaknesses.field_protection ? ' ⚠ FLDPROT' : ''}
        </div>
      )}

      {/* Row 1: Customer ID */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '16ch' }}>CUSTOMER-ID  :</span>
        {/* VULN: field_protection bypass — normally read-only after load, now editable */}
        {weaknesses.field_protection
          ? <input type="text" value={fields.customer_id || ''} onChange={e => setFields(f => ({ ...f, customer_id: e.target.value.toUpperCase().slice(0, 8) }))} onFocus={() => setFocusField('customer_id')} maxLength={8} style={{ ...iStyle(focusField === 'customer_id'), width: '8ch', borderBottom: '1px solid #FF9933', color: '#FF9933' }} autoComplete="off" spellCheck="false" />
          : field('customer_id', 8)
        }
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>STATUS    :</span>
        {field('status', 1)}
        <span style={{ color: '#668866', marginLeft: '4px' }}>(A/I/D)</span>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>CUST TYPE :</span>
        {field('customer_type', 1)}
        <span style={{ color: '#668866', marginLeft: '4px' }}>(P/C)</span>
      </div>

      {/* Row 2: Name */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '16ch' }}>SURNAME      :</span>
        {field('surname', 30)}
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>FORENAME  :</span>
        {field('forename', 20)}
      </div>

      {/* Row 3: DOB, Sort, NI */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '16ch' }}>DATE-OF-BIRTH:</span>
        {/* VULN: field_protection bypass — DOB becomes editable */}
        {weaknesses.field_protection
          ? <input type="text" value={fields.dob || ''} onChange={e => setFields(f => ({ ...f, dob: e.target.value.slice(0, 8) }))} onFocus={() => setFocusField('dob')} maxLength={8} style={{ background: 'transparent', border: 'none', borderBottom: '1px solid #FF9933', color: '#FF9933', fontFamily: "'Courier New', monospace", fontSize: '13px', outline: 'none', padding: 0, width: '8ch' }} autoComplete="off" />
          : field('dob', 8)
        }
        <span style={{ color: '#668866', marginLeft: '2px' }}>DD/MM/YY</span>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>SORT-CODE :</span>
        {field('sort_code', 6)}
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>NI NUMBER :</span>
        {field('ni_number', 9)}
      </div>

      <div style={{ color: '#33FF33', margin: '4px 0' }}>{'─'.repeat(79)}</div>

      {/* Address block */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '16ch' }}>ADDRESS LINE 1:</span>
        {field('address1', 30)}
      </div>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '16ch' }}>ADDRESS LINE 2:</span>
        {field('address2', 30)}
      </div>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '16ch' }}>ADDRESS LINE 3:</span>
        {field('address3', 30)}
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>POSTCODE  :</span>
        {field('postcode', 8)}
      </div>

      <div style={{ color: '#33FF33', margin: '4px 0' }}>{'─'.repeat(79)}</div>

      {/* System fields */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '4px', alignItems: 'center' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '16ch' }}>OPEN DATE    :</span>
        <span style={{ color: '#33FF33' }}>{fields.open_date || '        '}</span>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>LAST UPD  :</span>
        <span style={{ color: '#33FF33' }}>{fields.last_update_date || '        '}</span>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', marginLeft: '8px', width: '12ch' }}>OPERATOR  :</span>
        <span style={{ color: '#33FF33' }}>{fields.operator_id || '        '}</span>
      </div>

      <div style={{ color: '#33FF33', margin: '4px 0' }}>{'─'.repeat(79)}</div>

      {/* Message line */}
      <div style={{ color: msgColor, fontWeight: 'bold', marginTop: '4px', minHeight: '1.4em' }}>
        ==&gt; {message}
      </div>

      {/* Action hints */}
      <div style={{ color: '#668866', fontSize: '12px', marginTop: '4px' }}>
        PF5=ADD  PF6=UPDATE  PF7=DELETE  PF8=INQUIRE  PF3=MENU  PF1=HELP  PF12=CODE  ESC=CLEAR
      </div>

      {/* Action buttons (clickable for mouse users) */}
      <div style={{ display: 'flex', gap: '6px', marginTop: '6px', flexWrap: 'wrap' }}>
        {[
          { label: 'PF5 ADD', fn: handleAdd, color: '#33FF33' },
          { label: 'PF6 UPDATE', fn: handleUpdate, color: '#33FF33' },
          { label: 'PF7 DELETE', fn: handleDelete, color: '#FF9933' },
          { label: 'PF8 INQUIRE', fn: handleInquire, color: '#33FF33' },
          { label: 'PF3 MENU', fn: () => onBack('MENU'), color: '#AAFFAA' },
          { label: 'ESC CLEAR', fn: () => { setFields(EMPTY); setMsg('SCREEN CLEARED'); }, color: '#33FF33' },
        ].map(({ label, fn, color }) => (
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