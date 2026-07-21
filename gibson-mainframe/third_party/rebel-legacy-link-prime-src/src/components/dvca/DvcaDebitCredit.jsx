import React, { useState, useEffect, useRef } from 'react';
import { base44 } from '@/api/base44Client';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };
const iStyle = (w, num = false) => ({
  background: 'transparent', border: 'none', borderBottom: `1px solid #3399FF`,
  color: '#3399FF', fontFamily: S.mono, fontSize: '13px', outline: 'none', width: `${w}ch`, padding: 0,
});

export default function DvcaDebitCredit({ operatorId, onNavigate, hackFields = {}, onApiLeak, onLog, onStatUpdate }) {
  const [f, setF] = useState({ account_number: '', tran_type: 'CR', amount: '', pin: '', description: '' });
  const [msg, setMsg] = useState('ENTER ACCOUNT, TYPE (CR/DR), AMOUNT AND PIN');
  const [msgType, setMsgType] = useState('normal');
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchLog, setBatchLog] = useState([]);
  const batchRef = useRef(false);
  const sf = (k, v) => setF(x => ({ ...x, [k]: v }));

  // BATCH PIN brute-force engine
  useEffect(() => {
    if (!hackFields.master || !hackFields.batch_pin_enabled) {
      batchRef.current = false;
      setBatchRunning(false);
      return;
    }
    if (!f.account_number.trim()) return;
    batchRef.current = true;
    setBatchRunning(true);
    setBatchLog([]);
    let pin = 0;
    const interval = setInterval(async () => {
      if (!batchRef.current) { clearInterval(interval); return; }
      const pinStr = String(pin).padStart(4, '0');
      // Simulate PIN check — in real DVCA PIN is stored unencrypted
      const res = await base44.entities.Account.filter({ account_number: f.account_number.trim() });
      // Simulate: correct PIN is last 4 of account or hardcoded '1234'
      const correctPin = res.length > 0 ? (res[0].account_number || '').slice(-4) : '1234';
      const hit = pinStr === correctPin || pinStr === '1234';
      setBatchLog(prev => [
        ...prev.slice(-19),
        { pin: pinStr, hit },
      ]);
      if (onStatUpdate) onStatUpdate('pins_attempted', 1);
      if (hit) {
        if (onStatUpdate) onStatUpdate('pins_found', 1);
        if (onLog) onLog({ type: 'error', text: `[DRCA BATCH PIN] FOUND PIN: ${pinStr} for account ${f.account_number} — NO LOCKOUT (VULN #3)` });
        if (onApiLeak) onApiLeak(`BATCH PIN FOUND: account=${f.account_number} PIN=${pinStr} (no lockout protection)`);
        batchRef.current = false;
        setBatchRunning(false);
        clearInterval(interval);
        setMsg(`⚠ PIN FOUND: ${pinStr} — ACCOUNT ${f.account_number} COMPROMISED`);
        setMsgType('error');
        return;
      }
      pin++;
      if (pin > 9999) {
        clearInterval(interval);
        batchRef.current = false;
        setBatchRunning(false);
        setMsg('BATCH COMPLETE — PIN NOT FOUND IN RANGE 0000-9999');
        setMsgType('normal');
      }
    }, 80);
    return () => { batchRef.current = false; clearInterval(interval); };
  }, [hackFields.master, hackFields.batch_pin_enabled, f.account_number]);

  const handlePost = async () => {
    if (!f.account_number.trim()) { setMsg('ACCOUNT NUMBER REQUIRED'); setMsgType('error'); return; }
    if (!f.amount || isNaN(parseFloat(f.amount)) || parseFloat(f.amount) <= 0) { setMsg('VALID AMOUNT REQUIRED'); setMsgType('error'); return; }
    // PIN check — VULN: stored/compared plaintext, no lockout
    if (f.pin) {
      const res = await base44.entities.Account.filter({ account_number: f.account_number.trim() });
      if (res.length === 0) { setMsg('ACCOUNT NOT FOUND'); setMsgType('error'); return; }
      const correctPin = res[0].account_number.slice(-4);
      if (f.pin !== correctPin && f.pin !== '1234') {
        setMsg(`DRCA204 — INCORRECT PIN — ATTEMPT NOT LOCKED OUT (VULN #3)`);
        setMsgType('error');
        if (onLog) onLog({ type: 'warn', text: `[DRCA] Wrong PIN for ${f.account_number} — no lockout` });
        return;
      }
    }
    const res = await base44.entities.Account.filter({ account_number: f.account_number.trim() });
    if (res.length === 0) { setMsg('ACCOUNT NOT FOUND'); setMsgType('error'); return; }
    const acct = res[0];
    const amt = parseFloat(f.amount);
    const newBal = f.tran_type === 'CR' ? acct.balance + amt : acct.balance - amt;
    const today = (() => { const d = new Date(); return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`; })();
    await base44.entities.Transaction.create({
      account_number: f.account_number.trim(), tran_type: f.tran_type,
      amount: amt, description: f.description, operator_id: operatorId,
      post_date: today, balance_after: newBal,
    });
    await base44.entities.Account.update(acct.id, { balance: newBal, last_update_date: today, operator_id: operatorId });
    setMsg(`${f.tran_type === 'CR' ? 'CREDIT' : 'DEBIT'} POSTED — NEW BALANCE: ${acct.currency || 'GBP'} ${newBal.toFixed(2)}`);
    setMsgType('success');
    if (onApiLeak) onApiLeak(`POST /api/drca → {account:"${f.account_number}", balance:${newBal}, pin:"${f.pin||'not_provided'}"} — PIN in plaintext`);
    if (onLog) onLog({ type: 'info', text: `[DRCA] ${f.tran_type} £${amt} on account ${f.account_number} — PIN in request payload` });
    sf('amount', ''); sf('pin', ''); sf('description', '');
  };

  const handleKey = (e) => {
    if (e.key === 'F3') onNavigate('DVCA_MENU');
    if (e.key === 'F5') handlePost();
  };

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — CREDIT / DEBIT ACCOUNT &nbsp;&nbsp;&nbsp; DRCA</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>

      {hackFields.master && hackFields.batch_pin_enabled && (
        <div style={{ color: '#FF9933', fontSize: '11px', border: '1px solid #553300', padding: '3px 6px', marginBottom: '6px' }}>
          ⚠ BATCH PIN MODE ACTIVE — BRUTE-FORCING ACCOUNT: {f.account_number || '(enter account above)'}
          {batchRunning && <span style={{ color: S.red }}> — RUNNING...</span>}
        </div>
      )}

      {[
        ['ACCOUNT NUMBER', 'account_number', 10, true],
        ['AMOUNT', 'amount', 13, false],
        ['DESCRIPTION', 'description', 40, false],
      ].map(([label, key, w, num]) => (
        <div key={key} style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
          <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{label.padEnd(18)} :</span>
          <input value={f[key]} onChange={e => sf(key, num ? e.target.value.replace(/\D/g,'').slice(0,w) : e.target.value.toUpperCase().slice(0,w))}
            maxLength={w} autoFocus={key === 'account_number'} style={iStyle(w)} />
        </div>
      ))}

      {/* PIN field — always visible (VULN: visible in cleartext) */}
      <div style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
        <span style={{ color: hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.bright, width: '20ch', display: 'inline-block' }}>
          {'PIN'.padEnd(18)} :
          {hackFields.master && hackFields.enable_hidden_fields && (
            <span style={{ color: '#FF3333', fontSize: '10px', marginLeft: '4px' }}>[HIDDEN]</span>
          )}
        </span>
        <input
          type={hackFields.master && hackFields.enable_hidden_fields ? 'text' : 'password'}
          value={f.pin} onChange={e => sf('pin', e.target.value.replace(/\D/g,'').slice(0,4))}
          maxLength={4}
          style={{ ...iStyle(4), borderBottomColor: hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.blue, color: hackFields.master && hackFields.enable_hidden_fields ? '#FF9933' : S.blue }}
        />
        <span style={{ color: S.grey, fontSize: '11px', marginLeft: '8px' }}>
          {hackFields.master && hackFields.enable_hidden_fields ? '⚠ PIN VISIBLE (HACK3270)' : '4 DIGITS'}
        </span>
      </div>

      {/* Tran type */}
      <div style={{ display: 'flex', gap: '4px', alignItems: 'center', lineHeight: '2.0' }}>
        <span style={{ color: S.bright, width: '20ch', display: 'inline-block' }}>{'TRANSACTION TYPE'.padEnd(18)} :</span>
        <select value={f.tran_type} onChange={e => sf('tran_type', e.target.value)}
          style={{ background: '#001100', border: 'none', borderBottom: `1px solid ${S.blue}`, color: S.blue, fontFamily: S.mono, fontSize: '13px', outline: 'none' }}>
          <option value="CR">CR - CREDIT</option>
          <option value="DR">DR - DEBIT</option>
        </select>
      </div>

      <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
        <button onClick={handlePost} style={{ background: '#001100', border: `1px solid ${S.green}`, color: S.green, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF5 POST</button>
        <button onClick={() => onNavigate('DVCA_MENU')} style={{ background: '#111', border: '1px solid #668866', color: S.grey, fontFamily: S.mono, fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>PF3 MENU</button>
      </div>

      {/* Batch PIN log */}
      {hackFields.master && hackFields.batch_pin_enabled && batchLog.length > 0 && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ color: '#FF9933', fontSize: '11px', marginBottom: '2px' }}>BATCH PIN LOG:</div>
          <div style={{ background: '#0a0000', border: '1px solid #553300', padding: '3px', maxHeight: '80px', overflowY: 'auto', fontSize: '11px', fontFamily: S.mono }}>
            {batchLog.map((e, i) => (
              <div key={i} style={{ color: e.hit ? S.red : '#446644' }}>
                PIN: {e.pin} — {e.hit ? '✓ HIT! CORRECT PIN' : 'FAIL'}
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: '8px', color: msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green, fontWeight: 'bold' }}>==&gt; {msg}</div>
      <div style={{ color: S.grey, fontSize: '11px', marginTop: '4px' }}>PF5 = POST &nbsp;&nbsp; PF3 = MENU &nbsp;&nbsp; ENTER = EXECUTE</div>
    </div>
  );
}