import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };
const iStyle = (w, ro) => ({
  background: ro ? '#003300' : 'transparent',
  border: 'none', borderBottom: `1px solid ${ro ? '#336633' : '#3399FF'}`,
  color: ro ? '#AAFFAA' : '#3399FF',
  fontFamily: S.mono, fontSize: '13px', outline: 'none',
  width: `${w}ch`, padding: 0, textTransform: 'uppercase',
  cursor: ro ? 'default' : 'text',
});

export default function DvcaCust({ operatorId, onNavigate, hackFields = {}, onApiLeak, onLog }) {
  const [custId, setCustId] = useState('');
  const [result, setResult] = useState(null);
  const [msg, setMsg] = useState('ENTER CUSTOMER NUMBER AND PRESS ENTER');
  const [msgType, setMsgType] = useState('normal');

  const handleSearch = async () => {
    if (!custId.trim()) { setMsg('CUSTOMER NUMBER IS REQUIRED'); setMsgType('error'); return; }
    const res = await base44.entities.Customer.filter({ customer_id: custId.trim() });
    if (res.length === 0) { setMsg('CUSTOMER NOT FOUND'); setMsgType('error'); setResult(null); return; }
    const c = res[0];
    setResult(c);
    setMsg('CUSTOMER RECORD DISPLAYED');
    setMsgType('success');
    // API leakage simulation
    if (onApiLeak) onApiLeak(`GET /api/customers/${custId} → {customer_id, name, ni_number:"${c.ni_number||'XX 12 34 56 A'}", dob:"${c.dob||'**/**/**'}", sort_code:"${c.sort_code}"}`);
    if (onLog) onLog({ type: 'info', text: `[CUST] Displayed customer ${custId} — NI/DOB in response (VULN #API-1)` });
  };

  const handleKey = (e) => {
    if (e.key === 'Enter') handleSearch();
    if (e.key === 'F3') onNavigate('DVCA_MENU');
    if (e.key === 'F12') onNavigate('CESF');
  };

  const fieldColor = hackFields.master && hackFields.disable_field_protection ? '#FF9933' : S.blue;

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — DISPLAY CUSTOMER INFORMATION &nbsp;&nbsp;&nbsp; CUST</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>

      {hackFields.master && (hackFields.disable_field_protection || hackFields.enable_hidden_fields) && (
        <div style={{ color: '#FF9933', fontSize: '10px', marginBottom: '6px', border: '1px solid #553300', padding: '2px 6px' }}>
          ⚠ hack3270: {hackFields.disable_field_protection ? 'FIELD PROTECTION DISABLED ' : ''}{hackFields.enable_hidden_fields ? 'HIDDEN FIELDS VISIBLE' : ''}
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '10px' }}>
        <span style={{ color: S.bright, fontWeight: 'bold', width: '20ch' }}>CUSTOMER NUMBER :</span>
        <input value={custId} onChange={e => setCustId(e.target.value.replace(/\D/g,'').slice(0,8))}
          maxLength={8} autoFocus style={{ ...iStyle(10, false), borderBottomColor: fieldColor, color: fieldColor }} />
        <button onClick={handleSearch} style={{ background: '#111', border: '1px solid #668866', color: S.green, fontFamily: S.mono, fontSize: '11px', padding: '1px 8px', cursor: 'pointer' }}>ENTER</button>
      </div>

      {result && (
        <div style={{ lineHeight: '1.9' }}>
          {[
            ['NAME', `${result.forename} ${result.surname}`],
            ['ADDRESS 1', result.address1 || ''],
            ['ADDRESS 2', result.address2 || ''],
            ['ADDRESS 3', result.address3 || ''],
            ['POSTCODE', result.postcode || ''],
            ['DATE OF BIRTH', result.dob || ''],
            ['NI NUMBER', hackFields.master && hackFields.enable_hidden_fields ? (result.ni_number || 'AB 12 34 56 C') : '** ** ** ** *'],
            ['SORT CODE', result.sort_code || ''],
            ['STATUS', result.status === 'A' ? 'ACTIVE' : result.status === 'I' ? 'INACTIVE' : 'DELETED'],
            ['CUSTOMER TYPE', result.customer_type === 'P' ? 'PERSONAL' : 'CORPORATE'],
            ['OPEN DATE', result.open_date || ''],
            ['OPERATOR', result.operator_id || operatorId],
          ].map(([label, value]) => (
            <div key={label} style={{ display: 'flex', gap: '4px' }}>
              <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
              <span style={{ color: label === 'NI NUMBER' && hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.green }}>
                {value}
                {label === 'NI NUMBER' && hackFields.master && hackFields.enable_hidden_fields && (
                  <span style={{ color: '#FF3333', fontSize: '10px', marginLeft: '8px' }}>[HIDDEN FIELD EXPOSED]</span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: '10px', color: msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green, fontWeight: 'bold' }}>
        ==&gt; {msg}
      </div>
      <div style={{ color: S.grey, fontSize: '11px', marginTop: '4px' }}>
        PF3 = MENU &nbsp;&nbsp; PF12 = SIGNOFF &nbsp;&nbsp; ENTER = SEARCH
      </div>
    </div>
  );
}