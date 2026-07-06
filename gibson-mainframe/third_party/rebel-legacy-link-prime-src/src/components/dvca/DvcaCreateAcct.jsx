import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };
const iStyle = (w) => ({
  background: 'transparent', border: 'none', borderBottom: `1px solid #3399FF`,
  color: '#3399FF', fontFamily: S.mono, fontSize: '13px', outline: 'none', width: `${w}ch`, padding: 0,
});

const EMPTY = { customer_id: '', account_type: 'CUR', currency: 'GBP', sort_code: '', credit_limit: '0', interest_rate: '0.0000' };

export default function DvcaCreateAcct({ operatorId, onNavigate, hackFields = {}, onApiLeak, onLog }) {
  const [f, setF] = useState(EMPTY);
  const [msg, setMsg] = useState('ENTER ACCOUNT DETAILS AND PRESS PF5 TO CREATE');
  const [msgType, setMsgType] = useState('normal');
  const sf = (k, v) => setF(x => ({ ...x, [k]: v }));
  const today = () => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; };
  const genAcct = () => String(Math.floor(1000000000 + Math.random() * 8999999999));

  const handleCreate = async () => {
    if (!f.customer_id.trim()) { setMsg('CUSTOMER ID IS REQUIRED'); setMsgType('error'); return; }
    const custRes = await base44.entities.Customer.filter({ customer_id: f.customer_id.trim() });
    if (custRes.length === 0) { setMsg('CUSTOMER NOT FOUND'); setMsgType('error'); return; }
    const acctNo = genAcct();
    await base44.entities.Account.create({
      account_number: acctNo, customer_id: f.customer_id.trim(),
      account_type: f.account_type, currency: f.currency, sort_code: f.sort_code,
      balance: 0, credit_limit: parseFloat(f.credit_limit) || 0,
      interest_rate: parseFloat(f.interest_rate) || 0,
      status: 'A', open_date: today(), operator_id: operatorId, last_update_date: today(),
    });
    setMsg(`ACCOUNT CREATED — NO: ${acctNo}`);
    setMsgType('success');
    if (onApiLeak) onApiLeak(`POST /api/accounts → {account_number:"${acctNo}", customer_id:"${f.customer_id}", balance:0, credit_limit:${f.credit_limit}}`);
    if (onLog) onLog({ type: 'warn', text: `[ACCA] Account ${acctNo} created for customer ${f.customer_id}` });
    setF(EMPTY);
  };

  const handleKey = (e) => {
    if (e.key === 'F3') onNavigate('DVCA_MENU');
    if (e.key === 'F5') handleCreate();
  };

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — CREATE NEW ACCOUNT &nbsp;&nbsp;&nbsp; ACCA</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>

      {[
        ['CUSTOMER ID', 'customer_id', 8, true],
        ['SORT CODE', 'sort_code', 6, true],
        ['CREDIT LIMIT', 'credit_limit', 12, false],
        ['INTEREST RATE', 'interest_rate', 8, false],
      ].map(([label, key, w, num]) => (
        <div key={key} style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
          <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
          <input value={f[key]} onChange={e => sf(key, num ? e.target.value.replace(/\D/g,'').slice(0,w) : e.target.value.slice(0,w))}
            maxLength={w} style={iStyle(w)} />
        </div>
      ))}

      {[
        ['ACCOUNT TYPE', 'account_type', [['CUR','CURRENT'],['SAV','SAVINGS'],['OVD','OVERDRAFT'],['LON','LOAN']]],
        ['CURRENCY', 'currency', [['GBP','GBP'],['USD','USD'],['EUR','EUR']]],
      ].map(([label, key, opts]) => (
        <div key={key} style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
          <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
          <select value={f[key]} onChange={e => sf(key, e.target.value)}
            style={{ background: '#001100', border: 'none', borderBottom: `1px solid ${S.blue}`, color: S.blue, fontFamily: S.mono, fontSize: '13px', outline: 'none' }}>
            {opts.map(([v, l]) => <option key={v} value={v}>{v} - {l}</option>)}
          </select>
        </div>
      ))}

      <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
        <button onClick={handleCreate} style={{ background: '#001100', border: `1px solid ${S.green}`, color: S.green, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF5 CREATE</button>
        <button onClick={() => { setF(EMPTY); setMsg('SCREEN CLEARED'); }} style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>CLEAR</button>
        <button onClick={() => onNavigate('DVCA_MENU')} style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF3 MENU</button>
      </div>
      <div style={{ marginTop: '8px', color: msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green, fontWeight: 'bold' }}>==&gt; {msg}</div>
    </div>
  );
}