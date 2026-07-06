import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };
const iStyle = (w) => ({
  background: 'transparent', border: 'none', borderBottom: `1px solid #3399FF`,
  color: '#3399FF', fontFamily: S.mono, fontSize: '13px', outline: 'none', width: `${w}ch`, padding: 0,
});

const EMPTY = { from_account: '', to_account: '', amount: '', reference: '', pin: '' };

export default function DvcaXfer({ operatorId, onNavigate, hackFields = {}, onApiLeak, onLog }) {
  const [f, setF] = useState(EMPTY);
  const [msg, setMsg] = useState('ENTER FROM/TO ACCOUNTS, AMOUNT AND PRESS PF5');
  const [msgType, setMsgType] = useState('normal');
  const sf = (k, v) => setF(x => ({ ...x, [k]: v }));

  const today = () => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; };

  const handleTransfer = async () => {
    if (!f.from_account.trim() || !f.to_account.trim()) { setMsg('FROM AND TO ACCOUNTS REQUIRED'); setMsgType('error'); return; }
    if (!f.amount || parseFloat(f.amount) <= 0) { setMsg('VALID AMOUNT REQUIRED'); setMsgType('error'); return; }
    const [fromRes, toRes] = await Promise.all([
      base44.entities.Account.filter({ account_number: f.from_account.trim() }),
      base44.entities.Account.filter({ account_number: f.to_account.trim() }),
    ]);
    if (fromRes.length === 0) { setMsg('FROM ACCOUNT NOT FOUND'); setMsgType('error'); return; }
    if (toRes.length === 0) { setMsg('TO ACCOUNT NOT FOUND'); setMsgType('error'); return; }
    const from = fromRes[0];
    const to = toRes[0];
    const amt = parseFloat(f.amount);
    const newFromBal = from.balance - amt;
    const newToBal = to.balance + amt;
    const postDate = today();
    await Promise.all([
      base44.entities.Transaction.create({
        account_number: f.from_account.trim(), tran_type: 'TRF', amount: amt,
        description: `TRANSFER TO ${f.to_account.trim()}`, reference: f.reference,
        to_account: f.to_account.trim(), post_date: postDate, balance_after: newFromBal, operator_id: operatorId,
      }),
      base44.entities.Transaction.create({
        account_number: f.to_account.trim(), tran_type: 'CR', amount: amt,
        description: `TRANSFER FROM ${f.from_account.trim()}`, reference: f.reference,
        post_date: postDate, balance_after: newToBal, operator_id: operatorId,
      }),
      base44.entities.Account.update(from.id, { balance: newFromBal, last_update_date: postDate, operator_id: operatorId }),
      base44.entities.Account.update(to.id, { balance: newToBal, last_update_date: postDate, operator_id: operatorId }),
    ]);
    setMsg(`TRANSFER COMPLETE — FROM: ${from.currency||'GBP'} ${newFromBal.toFixed(2)} &nbsp; TO: ${to.currency||'GBP'} ${newToBal.toFixed(2)}`);
    setMsgType('success');
    if (onApiLeak) onApiLeak(`POST /api/xfer → {from:"${f.from_account}", to:"${f.to_account}", amt:${amt}, pin:"${f.pin||'none'}"} — no CSRF token`);
    if (onLog) onLog({ type: 'warn', text: `[XFER] £${amt} transferred ${f.from_account} → ${f.to_account} — no CSRF/2FA` });
    setF(EMPTY);
  };

  const handleKey = (e) => {
    if (e.key === 'F3') onNavigate('DVCA_MENU');
    if (e.key === 'F5') handleTransfer();
  };

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — TRANSFER FUNDS BETWEEN ACCOUNTS &nbsp;&nbsp;&nbsp; XFER</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>

      {[
        ['FROM ACCOUNT', 'from_account', 10, true],
        ['TO ACCOUNT', 'to_account', 10, true],
        ['AMOUNT', 'amount', 13, false],
        ['REFERENCE', 'reference', 16, false],
      ].map(([label, key, w, num]) => (
        <div key={key} style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
          <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
          <input value={f[key]} onChange={e => sf(key, num ? e.target.value.replace(/\D/g,'').slice(0,w) : e.target.value.toUpperCase().slice(0,w))}
            maxLength={w} autoFocus={key === 'from_account'} style={iStyle(w)} />
        </div>
      ))}

      {/* PIN */}
      <div style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
        <span style={{ color: hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.bright, width: '20ch', display: 'inline-block' }}>
          {'AUTHORISATION PIN'.padEnd(18)} :
        </span>
        <input type={hackFields.master && hackFields.enable_hidden_fields ? 'text' : 'password'}
          value={f.pin} onChange={e => sf('pin', e.target.value.replace(/\D/g,'').slice(0,4))}
          maxLength={4}
          style={{ ...iStyle(4), borderBottomColor: hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.blue, color: hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.blue }}
        />
        {hackFields.master && hackFields.enable_hidden_fields && (
          <span style={{ color: S.red, fontSize: '10px', marginLeft: '6px' }}>⚠ PIN EXPOSED BY HACK3270</span>
        )}
      </div>

      <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
        <button onClick={handleTransfer} style={{ background: '#001100', border: `1px solid ${S.green}`, color: S.green, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF5 TRANSFER</button>
        <button onClick={() => { setF(EMPTY); setMsg('SCREEN CLEARED'); }} style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>CLEAR</button>
        <button onClick={() => onNavigate('DVCA_MENU')} style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF3 MENU</button>
      </div>
      <div style={{ marginTop: '8px', color: msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green, fontWeight: 'bold' }}>==&gt; {msg}</div>
      <div style={{ color: S.grey, fontSize: '11px', marginTop: '4px' }}>PF5 = TRANSFER &nbsp;&nbsp; PF3 = MENU</div>
    </div>
  );
}