import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };

export default function DvcaCustAccts({ operatorId, onNavigate, hackFields = {}, onApiLeak, onLog }) {
  const [custId, setCustId] = useState('');
  const [results, setResults] = useState([]);
  const [msg, setMsg] = useState('ENTER CUSTOMER NUMBER TO LIST ALL ACCOUNTS');
  const [msgType, setMsgType] = useState('normal');

  const handleSearch = async () => {
    if (!custId.trim()) { setMsg('CUSTOMER NUMBER IS REQUIRED'); setMsgType('error'); return; }
    const res = await base44.entities.Account.filter({ customer_id: custId.trim() });
    if (res.length === 0) { setMsg('NO ACCOUNTS FOUND FOR CUSTOMER'); setMsgType('error'); setResults([]); return; }
    setResults(res);
    setMsg(`${res.length} ACCOUNT(S) FOUND FOR CUSTOMER ${custId}`);
    setMsgType('success');
    if (onApiLeak) onApiLeak(`GET /api/customers/${custId}/accounts → [${res.map(a=>a.account_number).join(',')}] all balances exposed`);
    if (onLog) onLog({ type: 'info', text: `[CUST*] Listed ${res.length} accounts for ${custId}` });
  };

  const handleKey = (e) => {
    if (e.key === 'Enter') handleSearch();
    if (e.key === 'F3') onNavigate('DVCA_MENU');
  };

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — DISPLAY ALL ACCOUNTS FOR CUSTOMER &nbsp;&nbsp;&nbsp; CUST*</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '10px' }}>
        <span style={{ color: S.bright, fontWeight: 'bold', width: '20ch' }}>CUSTOMER NUMBER :</span>
        <input value={custId} onChange={e => setCustId(e.target.value.replace(/\D/g,'').slice(0,8))}
          maxLength={8} autoFocus
          style={{ background: 'transparent', border: 'none', borderBottom: `1px solid ${S.blue}`, color: S.blue, fontFamily: S.mono, fontSize: '13px', outline: 'none', width: '10ch' }} />
        <button onClick={handleSearch} style={{ background: '#111', border: '1px solid #668866', color: S.green, fontFamily: S.mono, fontSize: '11px', padding: '1px 8px', cursor: 'pointer' }}>ENTER</button>
      </div>

      {results.length > 0 && (
        <div>
          {/* Table header */}
          <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '3px', borderBottom: '1px solid #336633', paddingBottom: '2px' }}>
            {'ACCT NUMBER'.padEnd(14)}{'TYPE'.padEnd(8)}{'CURRENCY'.padEnd(10)}{'BALANCE'.padEnd(16)}{'STATUS'.padEnd(10)}SORT CODE
          </div>
          {results.map((a, i) => (
            <div key={i} style={{ color: S.green, lineHeight: '1.7' }}>
              {a.account_number.padEnd(14)}
              {a.account_type.padEnd(8)}
              {(a.currency||'GBP').padEnd(10)}
              <span style={{ color: hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.green }}>
                {Number(a.balance).toFixed(2).padEnd(16)}
              </span>
              {(a.status==='A'?'ACTIVE':a.status==='D'?'DORMANT':'FROZEN').padEnd(10)}
              {a.sort_code||''}
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