import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };
const iStyle = (w) => ({
  background: 'transparent', border: 'none', borderBottom: `1px solid #3399FF`,
  color: '#3399FF', fontFamily: S.mono, fontSize: '13px', outline: 'none',
  width: `${w}ch`, padding: 0, textTransform: 'uppercase',
});

export default function DvcaAcct({ operatorId, onNavigate, hackFields = {}, onApiLeak, onLog }) {
  const [acctNo, setAcctNo] = useState('');
  const [result, setResult] = useState(null);
  const [msg, setMsg] = useState('ENTER ACCOUNT NUMBER AND PRESS ENTER');
  const [msgType, setMsgType] = useState('normal');

  const handleSearch = async () => {
    if (!acctNo.trim()) { setMsg('ACCOUNT NUMBER IS REQUIRED'); setMsgType('error'); return; }
    const res = await base44.entities.Account.filter({ account_number: acctNo.trim() });
    if (res.length === 0) { setMsg('ACCOUNT NOT FOUND'); setMsgType('error'); setResult(null); return; }
    const a = res[0];
    setResult(a);
    setMsg('ACCOUNT RECORD DISPLAYED');
    setMsgType('success');
    if (onApiLeak) onApiLeak(`GET /api/accounts/${acctNo} → {balance:${a.balance}, credit_limit:${a.credit_limit}, interest_rate:${a.interest_rate}} UNMASKED`);
    if (onLog) onLog({ type: 'info', text: `[ACCT] Account ${acctNo} displayed — balance/credit unmasked in response` });
  };

  const handleKey = (e) => {
    if (e.key === 'Enter') handleSearch();
    if (e.key === 'F3') onNavigate('DVCA_MENU');
  };

  const balanceColor = result && hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.green;

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — DISPLAY ACCOUNT INFORMATION &nbsp;&nbsp;&nbsp; ACCT</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '10px' }}>
        <span style={{ color: S.bright, fontWeight: 'bold', width: '20ch' }}>ACCOUNT NUMBER  :</span>
        <input value={acctNo} onChange={e => setAcctNo(e.target.value.replace(/\D/g,'').slice(0,10))}
          maxLength={10} autoFocus style={iStyle(12)} />
        <button onClick={handleSearch} style={{ background: '#111', border: '1px solid #668866', color: S.green, fontFamily: S.mono, fontSize: '11px', padding: '1px 8px', cursor: 'pointer' }}>ENTER</button>
      </div>

      {result && (
        <div style={{ lineHeight: '1.9' }}>
          {[
            ['ACCOUNT NUMBER', result.account_number],
            ['CUSTOMER ID', result.customer_id],
            ['ACCOUNT TYPE', result.account_type === 'SAV' ? 'SAVINGS' : result.account_type === 'CUR' ? 'CURRENT' : result.account_type === 'OVD' ? 'OVERDRAFT' : 'LOAN'],
            ['SORT CODE', result.sort_code || ''],
            ['CURRENCY', result.currency || 'GBP'],
            ['BALANCE', `${result.currency || 'GBP'} ${Number(result.balance).toFixed(2)}`],
            ['CREDIT LIMIT', `${result.currency || 'GBP'} ${Number(result.credit_limit).toFixed(2)}`],
            ['INTEREST RATE', `${Number(result.interest_rate).toFixed(4)}%`],
            ['STATUS', result.status === 'A' ? 'ACTIVE' : result.status === 'D' ? 'DORMANT' : 'FROZEN'],
            ['OPEN DATE', result.open_date || ''],
            ['LAST UPDATE', result.last_update_date || ''],
          ].map(([label, value]) => (
            <div key={label} style={{ display: 'flex', gap: '4px' }}>
              <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
              <span style={{ color: ['BALANCE','CREDIT LIMIT','INTEREST RATE'].includes(label) ? balanceColor : S.green }}>
                {value}
                {['BALANCE','CREDIT LIMIT'].includes(label) && hackFields.master && hackFields.enable_hidden_fields && (
                  <span style={{ color: S.red, fontSize: '10px', marginLeft: '8px' }}>[UNMASKED - VULN]</span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: '10px', color: msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green, fontWeight: 'bold' }}>
        ==&gt; {msg}
      </div>
      <div style={{ color: S.grey, fontSize: '11px', marginTop: '4px' }}>PF3 = MENU &nbsp;&nbsp; ENTER = SEARCH</div>
    </div>
  );
}