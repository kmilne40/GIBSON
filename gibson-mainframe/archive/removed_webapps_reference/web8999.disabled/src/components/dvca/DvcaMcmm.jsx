import React, { useState } from 'react';

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

export default function DvcaMcmm({ onNavigate, hackFields }) {
  const [select, setSelect] = useState('');
  const [message, setMessage] = useState('');

  const handleEnter = () => {
    const val = select.trim();
    if (val === '1') { onNavigate('MCOR'); return; }
    if (val === '2') { onNavigate('MCAD'); return; }
    if (val === '3') { onNavigate('MCHI'); return; }
    if (val === '99') { setMessage('99 - DELETE HISTORY: USE OPTION 3 THEN CLEAR HISTORY FROM THERE'); return; }
    if (val === '') { setMessage('PLEASE ENTER A SELECTION'); return; }
    setMessage(`INVALID SELECTION: ${val} - ENTER 1, 2, OR 3`);
    setSelect('');
  };

  const handleKey = (e) => {
    if (e.key === 'Enter') handleEnter();
    if (e.key === 'F1') onNavigate('HELP');
    if (e.key === 'F3') onNavigate('CESF');
    if (e.key === 'F5') setMessage('PF5 - PAGE NOT AVAILABLE');
  };

  return (
    <div
      onKeyDown={handleKey}
      tabIndex={0}
      style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto', outline: 'none' }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ color: S.blue }}>MCMM</span>
        <span style={{ color: S.yellow, fontWeight: 'bold' }}>Mels Cargo Main Menu</span>
        <span style={{ color: S.blue }}>MCMM</span>
      </div>
      <div style={{ color: S.blue, marginBottom: '8px' }}>{'='.repeat(47).padStart(55)}</div>

      {/* Menu options */}
      <div style={{ marginLeft: '4ch', lineHeight: '2.2' }}>
        <div>
          <span style={{ color: S.neutral, fontWeight: 'bold' }}>1</span>
          <span style={{ color: S.blue }}>)  Office Supplies Price List</span>
        </div>
        <div>
          <span style={{ color: S.neutral, fontWeight: 'bold' }}>2</span>
          <span style={{ color: S.blue }}>)  Shipping Address</span>
        </div>
        <div>
          <span style={{ color: S.neutral, fontWeight: 'bold' }}>3</span>
          <span style={{ color: S.blue }}>)  Order History</span>
        </div>

        {/* Hidden option 99 — only visible with hack3270 hidden fields exposed */}
        {hackFields?.master && hackFields?.enable_hidden_fields ? (
          <div>
            <span style={{ color: S.red, fontWeight: 'bold' }}>99</span>
            <span style={{ color: S.red }}>)  DELETE ALL HISTORY RECORDS </span>
            <span style={{ color: '#FF9933', fontSize: '10px' }}>[HIDDEN FIELD — EXPOSED BY HACK3270]</span>
          </div>
        ) : (
          <div style={{ color: '#111111', userSelect: 'none' }}>
            {/* Invisible field — hack3270 can expose this */}
            99)  DELETE ALL HISTORY RECORDS
          </div>
        )}
      </div>

      {/* Decorative cargo box ANSI art (simplified) */}
      <div style={{ marginTop: '10px', marginLeft: '52ch', color: S.red, fontSize: '11px', lineHeight: '1.2' }}>
        <div>::::::::::::::::::::::::::</div>
        <div>::  <span style={{ color: S.yellow }}>##</span>  :::<span style={{ color: S.yellow }}>##</span>  :::<span style={{ color: S.yellow }}>##</span>  ::</div>
        <div>::::::::::::::::::::::::::</div>
        <div>:: <span style={{ color: S.bright }}>MEL'S</span> ::<span style={{ color: S.bright }}>CARGO</span>::</div>
        <div>::::::::::::::::::::::::::</div>
      </div>

      {/* Selection input */}
      <div style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ color: S.bright, fontWeight: 'bold' }}>Selection ==&gt;</span>
        <input
          type="text"
          value={select}
          onChange={e => setSelect(e.target.value.slice(0, 4))}
          maxLength={4}
          autoFocus
          style={{
            width: '6ch', background: 'transparent', border: 'none',
            borderBottom: `1px solid ${S.blue}`, color: S.blue,
            fontFamily: S.mono, fontSize: '13px', outline: 'none',
          }}
        />
        <button onClick={handleEnter} style={btnStyle(S.bright)}>ENTER</button>
      </div>

      {/* PF key bar */}
      <div style={{ marginTop: '8px', color: S.blue, fontSize: '11px' }}>
        PF1 - Help &nbsp;&nbsp; PF5 - This &nbsp;&nbsp; PF3 - Quit
      </div>

      {/* Message line */}
      {message && (
        <div style={{ marginTop: '4px', color: S.red, fontWeight: 'bold' }}>{message}</div>
      )}

      {/* Quick buttons */}
      <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button onClick={() => { setSelect('1'); }} style={btnStyle(S.bright)}>1 - PRICE LIST</button>
        <button onClick={() => { setSelect('2'); }} style={btnStyle(S.blue)}>2 - ADDRESS</button>
        <button onClick={() => { setSelect('3'); }} style={btnStyle(S.blue)}>3 - HISTORY</button>
        {hackFields?.master && (
          <button onClick={() => onNavigate('SCRT')} style={btnStyle(S.red)}>PA3 - SECRET [AID]</button>
        )}
        <button onClick={() => onNavigate('CESF')} style={btnStyle(S.grey)}>PF3 - QUIT</button>
      </div>
    </div>
  );
}

function btnStyle(color) {
  return {
    background: '#001100', border: `1px solid ${color}`,
    color, fontFamily: "'Courier New', monospace",
    fontSize: '11px', padding: '2px 10px', cursor: 'pointer',
  };
}