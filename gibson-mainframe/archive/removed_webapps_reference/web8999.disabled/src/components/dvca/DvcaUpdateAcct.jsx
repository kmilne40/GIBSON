import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };
const iStyle = (w, disabled = false) => ({
  background: disabled ? '#002200' : 'transparent', border: 'none',
  borderBottom: `1px solid ${disabled ? '#336633' : '#3399FF'}`,
  color: disabled ? S.bright : S.blue, fontFamily: S.mono, fontSize: '13px', outline: 'none',
  width: `${w}ch`, padding: 0,
});

export default function DvcaUpdateAcct({ operatorId, onNavigate, hackFields = {}, onLog }) {
  const [acctNo, setAcctNo] = useState('');
  const [loaded, setLoaded] = useState(null);
  const [fields, setFields] = useState({});
  const [msg, setMsg] = useState('ENTER ACCOUNT NUMBER AND PRESS ENTER TO LOAD');
  const [msgType, setMsgType] = useState('normal');

  const handleLoad = async () => {
    if (!acctNo.trim()) { setMsg('ACCOUNT NUMBER REQUIRED'); setMsgType('error'); return; }
    const res = await base44.entities.Account.filter({ account_number: acctNo.trim() });
    if (res.length === 0) { setMsg('ACCOUNT NOT FOUND'); setMsgType('error'); return; }
    const a = res[0];
    setLoaded(a);
    setFields({ credit_limit: String(a.credit_limit), interest_rate: String(a.interest_rate), status: a.status });
    setMsg('ACCOUNT LOADED — MODIFY FIELDS AND PRESS PF5 TO UPDATE');
    setMsgType('normal');
  };

  const handleUpdate = async () => {
    if (!loaded) return;
    const today = (() => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; })();
    await base44.entities.Account.update(loaded.id, {
      credit_limit: parseFloat(fields.credit_limit) || 0,
      interest_rate: parseFloat(fields.interest_rate) || 0,
      status: fields.status, last_update_date: today, operator_id: operatorId,
    });
    setMsg('ACCOUNT UPDATED SUCCESSFULLY');
    setMsgType('success');
    if (onLog) onLog({ type: 'warn', text: `[ACCU] Account ${loaded.account_number} updated by ${operatorId}` });
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !loaded) handleLoad();
    if (e.key === 'F5') handleUpdate();
    if (e.key === 'F3') onNavigate('DVCA_MENU');
  };

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — UPDATE ACCOUNT INFORMATION &nbsp;&nbsp;&nbsp; ACCU</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', lineHeight: '2.0', marginBottom: '8px' }}>
        <span style={{ color: S.bright, width: '20ch' }}>ACCOUNT NUMBER  :</span>
        <input value={acctNo} onChange={e => setAcctNo(e.target.value.replace(/\D/g,'').slice(0,10))}
          maxLength={10} autoFocus style={iStyle(12)} />
        <button onClick={handleLoad} style={{ background: '#111', border: '1px solid #668866', color: S.green, fontFamily: S.mono, fontSize: '11px', padding: '1px 8px', cursor: 'pointer' }}>ENTER</button>
      </div>

      {loaded && (
        <div>
          {/* Read-only fields */}
          {[
            ['ACCOUNT TYPE', loaded.account_type],
            ['CURRENCY', loaded.currency],
            ['SORT CODE', loaded.sort_code],
            ['CURRENT BALANCE', `${loaded.currency} ${Number(loaded.balance).toFixed(2)}`],
            ['OPEN DATE', loaded.open_date],
          ].map(([label, value]) => (
            <div key={label} style={{ display: 'flex', gap: '4px', lineHeight: '1.9' }}>
              <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
              <span style={{ color: S.bright }}>{value}</span>
            </div>
          ))}
          <div style={{ color: S.green, margin: '4px 0' }}>{'─'.repeat(50)}</div>
          {/* Editable fields */}
          {[['CREDIT LIMIT', 'credit_limit', 12], ['INTEREST RATE', 'interest_rate', 8]].map(([label, key, w]) => (
            <div key={key} style={{ display: 'flex', gap: '4px', lineHeight: '1.9' }}>
              <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
              <input value={fields[key] || ''} onChange={e => setFields(x => ({ ...x, [key]: e.target.value.slice(0, w) }))} maxLength={w} style={iStyle(w)} />
            </div>
          ))}
          <div style={{ display: 'flex', gap: '4px', lineHeight: '1.9', alignItems: 'center' }}>
            <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{'STATUS'.padEnd(18)} :</span>
            <select value={fields.status || 'A'} onChange={e => setFields(x => ({ ...x, status: e.target.value }))}
              style={{ background: '#001100', border: 'none', borderBottom: `1px solid ${S.blue}`, color: S.blue, fontFamily: S.mono, fontSize: '13px', outline: 'none' }}>
              <option value="A">A - ACTIVE</option>
              <option value="D">D - DORMANT</option>
              <option value="F">F - FROZEN</option>
            </select>
          </div>
        </div>
      )}

      <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
        {loaded && <button onClick={handleUpdate} style={{ background: '#001100', border: `1px solid ${S.green}`, color: S.green, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF5 UPDATE</button>}
        <button onClick={() => onNavigate('DVCA_MENU')} style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF3 MENU</button>
      </div>
      <div style={{ marginTop: '8px', color: msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green, fontWeight: 'bold' }}>==&gt; {msg}</div>
    </div>
  );
}