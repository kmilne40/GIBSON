import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };
const iStyle = (w) => ({
  background: 'transparent', border: 'none', borderBottom: `1px solid #3399FF`,
  color: '#3399FF', fontFamily: S.mono, fontSize: '13px', outline: 'none',
  width: `${w}ch`, padding: 0, textTransform: 'uppercase',
});

const EMPTY = { surname: '', forename: '', dob: '', ni_number: '', address1: '', address2: '', address3: '', postcode: '', customer_type: 'P', sort_code: '' };

export default function DvcaCreateCust({ operatorId, onNavigate, hackFields = {}, onApiLeak, onLog }) {
  const [f, setF] = useState(EMPTY);
  const [msg, setMsg] = useState('ENTER CUSTOMER DETAILS — ALL FIELDS REQUIRED');
  const [msgType, setMsgType] = useState('normal');
  const sf = (k, v) => setF(x => ({ ...x, [k]: v }));

  const today = () => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; };
  const genId = () => String(Math.floor(10000000 + Math.random() * 89999999));

  const handleCreate = async () => {
    if (!f.surname.trim() || !f.forename.trim()) { setMsg('SURNAME AND FORENAME ARE REQUIRED'); setMsgType('error'); return; }
    const custId = genId();
    await base44.entities.Customer.create({
      customer_id: custId, surname: f.surname, forename: f.forename,
      dob: f.dob, ni_number: f.ni_number, address1: f.address1, address2: f.address2,
      address3: f.address3, postcode: f.postcode, customer_type: f.customer_type,
      sort_code: f.sort_code, status: 'A', open_date: today(), operator_id: operatorId,
    });
    setMsg(`CUSTOMER CREATED — ID: ${custId}`);
    setMsgType('success');
    if (onApiLeak) onApiLeak(`POST /api/customers → {customer_id:"${custId}", ni:"${f.ni_number}"} — NI in response (VULN)`);
    if (onLog) onLog({ type: 'warn', text: `[CUSA] Created customer ${custId} — NI stored unencrypted` });
    setF(EMPTY);
  };

  const handleKey = (e) => {
    if (e.key === 'F3') onNavigate('DVCA_MENU');
    if (e.key === 'F5') handleCreate();
  };

  const row = (label, key, w, numeric = false) => (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
      <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
      <input value={f[key]} onChange={e => sf(key, numeric ? e.target.value.replace(/\D/g,'').slice(0,w) : e.target.value.toUpperCase().slice(0,w))}
        maxLength={w} style={iStyle(w)} />
    </div>
  );

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — CREATE NEW CUSTOMER &nbsp;&nbsp;&nbsp; CUSA</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>
      {row('SURNAME', 'surname', 30)}
      {row('FORENAME', 'forename', 20)}
      {row('DATE OF BIRTH', 'dob', 8)}
      {row('NI NUMBER', 'ni_number', 12)}
      {row('ADDRESS LINE 1', 'address1', 40)}
      {row('ADDRESS LINE 2', 'address2', 40)}
      {row('ADDRESS LINE 3', 'address3', 40)}
      {row('POSTCODE', 'postcode', 8)}
      {row('SORT CODE', 'sort_code', 6, true)}
      <div style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
        <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{'CUSTOMER TYPE'.padEnd(18)} :</span>
        <select value={f.customer_type} onChange={e => sf('customer_type', e.target.value)}
          style={{ background: '#001100', border: 'none', borderBottom: `1px solid ${S.blue}`, color: S.blue, fontFamily: S.mono, fontSize: '13px', outline: 'none' }}>
          <option value="P">P - PERSONAL</option>
          <option value="C">C - CORPORATE</option>
        </select>
      </div>
      <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
        <button onClick={handleCreate} style={{ background: '#001100', border: `1px solid ${S.green}`, color: S.green, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF5 CREATE</button>
        <button onClick={() => { setF(EMPTY); setMsg('SCREEN CLEARED'); setMsgType('normal'); }}
          style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>CLEAR</button>
        <button onClick={() => onNavigate('DVCA_MENU')} style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF3 MENU</button>
      </div>
      <div style={{ marginTop: '8px', color: msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green, fontWeight: 'bold' }}>==&gt; {msg}</div>
    </div>
  );
}