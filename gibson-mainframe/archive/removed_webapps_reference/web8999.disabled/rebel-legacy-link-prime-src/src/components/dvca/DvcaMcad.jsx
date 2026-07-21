import React, { useState, useRef } from 'react';

const S = {
  mono: "'Courier New', monospace",
  green: '#33FF33',
  bright: '#AAFFAA',
  blue: '#3399FF',
  yellow: '#FFFF00',
  red: '#FF3333',
  grey: '#668866',
  neutral: '#AAAAAA',
};

// VULN: Supervisor PIN hardcoded as 1337 in COBOL source
const SUPERVISOR_PIN = 1337;

// Default address record
const DEFAULT_ADDRESS = {
  name: "Mel's Cargo Ltd",
  street: '42 Warehouse Row',
  city: 'Chicago',
  state: 'IL',
  zip: '60601',
  country: 'USA',
};

export default function DvcaMcad({ operatorId, onNavigate, hackFields, onApiLeak, onLog }) {
  const [address, setAddress] = useState(DEFAULT_ADDRESS);
  const [editMode, setEditMode] = useState(false);
  const [editFields, setEditFields] = useState({ ...DEFAULT_ADDRESS });
  const [pin, setPin] = useState('');
  const [pinDisplay, setPinDisplay] = useState('');
  const [message, setMessage] = useState('SHIPPING ADDRESS — ENTER SUPERVISOR PIN TO EDIT');
  const [msgType, setMsgType] = useState('normal');
  const [bruteRunning, setBruteRunning] = useState(false);
  const [bruteLog, setBruteLog] = useState([]);
  const [foundPin, setFoundPin] = useState(null);
  const bruteRef = useRef(null);

  const pinExposed = hackFields?.master && hackFields?.enable_hidden_fields;
  const protOff = hackFields?.master && hackFields?.disable_field_protection;

  const handlePinSubmit = () => {
    const entered = parseInt(pin, 10);
    if (entered === SUPERVISOR_PIN) {
      setEditMode(true);
      setEditFields({ ...address });
      setMessage('PIN ACCEPTED — EDIT MODE ENABLED');
      setMsgType('success');
      if (onLog) onLog({ type: 'success', text: `PIN ACCEPTED: ${pin} — ACCESS GRANTED TO EDIT ADDRESS` });
    } else {
      // VULN: No lockout, unlimited attempts
      setMessage(`INVALID PIN: ${pin} — TRY AGAIN (NO LOCKOUT VULN #3)`);
      setMsgType('error');
      if (onLog) onLog({ type: 'warn', text: `FAILED PIN ATTEMPT: ${pin} — NO LOCKOUT TRIGGERED` });
    }
    setPin('');
    setPinDisplay('');
  };

  const handleSave = () => {
    setAddress({ ...editFields });
    setEditMode(false);
    setMessage('ADDRESS UPDATED SUCCESSFULLY');
    setMsgType('success');
    if (onLog) onLog({ type: 'info', text: `ADDRESS RECORD UPDATED BY: ${operatorId || 'DVCA'}` });
  };

  const handleBrute = async () => {
    setBruteRunning(true);
    setBruteLog([]);
    setFoundPin(null);
    if (onLog) onLog({ type: 'warn', text: '=== PIN BRUTE FORCE STARTED — TARGET: MCAD SUPERVISOR PIN ===' });
    if (onApiLeak) onApiLeak('BRUTE FORCE ATTACK: MCAD supervisor PIN (4 digits, no lockout, VULN #3)');

    // Brute force 0000–1999 quickly, then slow near 1337
    const batchSize = 50;
    for (let i = 0; i <= 1337; i += batchSize) {
      await new Promise(r => setTimeout(r, 80));
      const end = Math.min(i + batchSize - 1, 1337);
      setBruteLog(prev => [...prev.slice(-20), {
        type: end >= 1337 ? 'success' : 'error',
        text: `TRYING ${String(i).padStart(4, '0')} - ${String(end).padStart(4, '0')}   ${end >= 1337 ? '>>> HIT <<<' : 'INVALID'}`,
      }]);
      if (end >= SUPERVISOR_PIN) {
        setFoundPin(SUPERVISOR_PIN);
        setBruteRunning(false);
        setPin(String(SUPERVISOR_PIN));
        setPinDisplay(String(SUPERVISOR_PIN));
        setMessage(`BRUTE FORCE SUCCESS: PIN = ${SUPERVISOR_PIN} — ${1337} ATTEMPTS — NO LOCKOUT (VULN #3)`);
        setMsgType('error');
        if (onLog) onLog({ type: 'success', text: `⚠ BRUTE FORCE FOUND PIN: ${SUPERVISOR_PIN} after 1337 attempts — NO LOCKOUT PROTECTION` });
        return;
      }
    }
    setBruteRunning(false);
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !editMode) handlePinSubmit();
    if (e.key === 'F5' || e.key === 'F3') onNavigate('MCMM');
  };

  const setEf = (k, v) => setEditFields(f => ({ ...f, [k]: v }));
  const msgColor = msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green;

  return (
    <div
      onKeyDown={handleKey}
      tabIndex={0}
      style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto', outline: 'none' }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ color: S.blue }}>MCAD</span>
        <span style={{ color: S.yellow, fontWeight: 'bold' }}>Mels Cargo — Shipping Address</span>
        <span style={{ color: S.blue }}>MCAD</span>
      </div>
      <div style={{ color: S.blue, marginBottom: '8px' }}>{'─'.repeat(79)}</div>

      {/* Address display */}
      <div style={{ lineHeight: '2.0', marginBottom: '8px' }}>
        {[['Name', 'name'], ['Street', 'street'], ['City', 'city'], ['State', 'state'], ['ZIP', 'zip'], ['Country', 'country']].map(([label, key]) => (
          <div key={key} style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            <span style={{ color: S.bright, width: '14ch' }}>{label.padEnd(12)} :</span>
            {editMode ? (
              <input
                value={editFields[key]}
                onChange={e => setEf(key, e.target.value.slice(0, 44))}
                maxLength={44}
                style={{
                  background: 'transparent', border: 'none',
                  borderBottom: `1px solid ${S.blue}`, color: S.blue,
                  fontFamily: S.mono, fontSize: '13px', outline: 'none', width: '44ch',
                }}
              />
            ) : (
              <span style={{ color: S.neutral }}>{address[key]}</span>
            )}
          </div>
        ))}

        {/* PIN field — VULN: PIN shown in plaintext when hidden fields exposed */}
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center', marginTop: '4px' }}>
          <span style={{ color: pinExposed ? '#FF9933' : '#111111', width: '14ch' }}>
            {pinExposed ? 'PIN [HIDDEN]  :' : '               '}
          </span>
          <span style={{ color: pinExposed ? S.red : '#111111' }}>
            {pinExposed ? (
              <>
                <span style={{ fontWeight: 'bold' }}>{SUPERVISOR_PIN}</span>
                <span style={{ color: '#FF9933', fontSize: '10px', marginLeft: '8px' }}>
                  ⚠ PLAINTEXT PIN EXPOSED BY HACK3270 HIDDEN FIELD REVEAL
                </span>
              </>
            ) : ''}
          </span>
        </div>
      </div>

      <div style={{ color: S.blue, margin: '4px 0' }}>{'─'.repeat(79)}</div>

      {/* PIN entry section */}
      {!editMode && (
        <div style={{ marginBottom: '8px' }}>
          <div style={{ color: S.grey, fontSize: '11px', marginBottom: '4px' }}>
            ENTER SUPERVISOR PIN TO EDIT ADDRESS (4 DIGITS):
            {!hackFields?.master && (
              <span style={{ color: '#224422' }}> &nbsp; [BRUTE FORCE: ENABLE HACK3270]</span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: S.bright }}>Supervisode Code:</span>
            <input
              type={protOff ? 'text' : 'password'}
              value={pinDisplay}
              onChange={e => {
                const v = e.target.value.replace(/\D/g, '').slice(0, 4);
                setPin(v);
                setPinDisplay(protOff ? v : v.replace(/./g, '*'));
              }}
              maxLength={4}
              placeholder="____"
              style={{
                width: '6ch', background: 'transparent', border: 'none',
                borderBottom: `1px solid ${S.blue}`, color: protOff ? S.yellow : S.blue,
                fontFamily: S.mono, fontSize: '13px', outline: 'none', letterSpacing: '4px',
              }}
            />
            {protOff && <span style={{ color: S.red, fontSize: '10px' }}>⚠ PIN VISIBLE (PROTECTION OFF)</span>}
            <button onClick={handlePinSubmit} style={btnStyle(S.bright)}>ENTER</button>
          </div>
        </div>
      )}

      {/* Edit mode controls */}
      {editMode && (
        <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
          <button onClick={handleSave} style={btnStyle(S.bright)}>PF5 SAVE ADDRESS</button>
          <button onClick={() => { setEditMode(false); setMessage('EDIT CANCELLED'); setMsgType('normal'); }} style={btnStyle(S.grey)}>CANCEL</button>
        </div>
      )}

      {/* Brute force section */}
      {hackFields?.master && !editMode && (
        <div style={{ marginBottom: '8px', border: '1px solid #330000', padding: '6px' }}>
          <div style={{ color: S.red, fontSize: '11px', fontWeight: 'bold', marginBottom: '4px' }}>
            ⚠ HACK3270 — PIN BRUTE FORCE (NO LOCKOUT VULN #3)
          </div>
          <div style={{ color: S.grey, fontSize: '10px', marginBottom: '4px' }}>
            4-digit PIN: 0000–9999 (10,000 combos) — SUPERVISOR-CODE PIC 9(4) VALUE 1337
          </div>
          <button
            onClick={handleBrute}
            disabled={bruteRunning}
            style={btnStyle(bruteRunning ? S.grey : S.red)}
          >
            {bruteRunning ? '● BRUTE FORCING...' : 'START BRUTE FORCE'}
          </button>
          {foundPin && (
            <span style={{ color: S.bright, marginLeft: '12px', fontWeight: 'bold' }}>
              FOUND: {foundPin}
            </span>
          )}
          {bruteLog.length > 0 && (
            <div style={{ marginTop: '4px', maxHeight: '80px', overflowY: 'auto', background: '#000', padding: '4px', fontSize: '10px' }}>
              {bruteLog.map((e, i) => (
                <div key={i} style={{ color: e.type === 'success' ? S.bright : '#553300' }}>{e.text}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Message */}
      <div style={{ color: msgColor, fontWeight: 'bold', minHeight: '1.4em' }}>{message}</div>

      {/* PF key guide */}
      <div style={{ color: S.blue, fontSize: '11px', marginTop: '4px' }}>
        PF1 - Help &nbsp;&nbsp; PF3/PF5 - Main Menu
      </div>
      <div style={{ marginTop: '6px', display: 'flex', gap: '8px' }}>
        <button onClick={() => onNavigate('MCMM')} style={btnStyle(S.grey)}>PF5 MENU</button>
      </div>
    </div>
  );
}

function btnStyle(color, disabled = false) {
  return {
    background: '#001100', border: `1px solid ${disabled ? '#224422' : color}`,
    color: disabled ? '#224422' : color,
    fontFamily: "'Courier New', monospace",
    fontSize: '11px', padding: '2px 10px',
    cursor: disabled ? 'not-allowed' : 'pointer',
  };
}