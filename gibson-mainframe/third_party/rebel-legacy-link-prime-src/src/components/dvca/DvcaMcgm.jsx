import React, { useState } from 'react';

const S = {
  mono: "'Courier New', monospace",
  green: '#33FF33',
  bright: '#AAFFAA',
  blue: '#3399FF',
  yellow: '#FFFF00',
  red: '#FF3333',
  grey: '#668866',
  cyan: '#00FFFF',
};

// ASCII art splash for Mel's Cargo (MCGM screen)
const MCGM_LOGO = [
  "         __  __      _     ____                    ",
  "        |  \\/  | ___| |   / ___|__ _ _ __ __ _  ___",
  "        | |\\/| |/ _ \\ |  | |   / _` | '__/ _` |/ _ \\",
  "        | |  | |  __/ |  | |__| (_| | | | (_| | (_) |",
  "        |_|  |_|\\___|_|   \\____\\__,_|_|  \\__, |\\___/",
  "                                          |___/      ",
  "",
  "         ================================================",
  "         |   DAMN VULNERABLE CICS APPLICATION (DVCA)   |",
  "         |      Mel's Cargo - Office Supply Store       |",
  "         ================================================",
  "",
  "                   Transaction: MCGM",
  "",
  "         PF1  - Help         PF3  - Quit",
  "         PF5  - Main Menu    PA3  - Secret",
  "",
  "         PRESS PF5 TO ENTER MEL'S CARGO MAIN MENU",
];

export default function DvcaMcgm({ onNavigate, hackFields }) {
  const [message, setMessage] = useState('');

  const handleKey = (e) => {
    if (e.key === 'F5') onNavigate('MCMM');
    if (e.key === 'F3') onNavigate('CESF');
    if (e.key === 'F1') setMessage('HELP: PRESS PF5 TO ENTER MAIN MENU, PA3 FOR SECRET');
    // PA3 is not a real keyboard key — simulate with PA3 button
  };

  return (
    <div
      onKeyDown={handleKey}
      tabIndex={0}
      style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto', outline: 'none' }}
    >
      {/* Transaction ID top left */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ color: S.blue }}>MCGM</span>
        <span style={{ color: S.grey, fontSize: '11px' }}>DVCA - KICKS/VS 1.5</span>
      </div>

      {/* Logo */}
      <div style={{ marginTop: '8px' }}>
        {MCGM_LOGO.map((line, i) => (
          <div key={i} style={{
            color: i < 6 ? S.yellow : i === 7 || i === 9 ? S.cyan : i === 8 ? S.bright : S.blue,
            lineHeight: '1.4',
            whiteSpace: 'pre',
          }}>{line}</div>
        ))}
      </div>

      {/* Message */}
      {message && (
        <div style={{ marginTop: '8px', color: S.yellow }}>{message}</div>
      )}

      {/* Buttons */}
      <div style={{ marginTop: '16px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        <button onClick={() => onNavigate('MCMM')} style={btnStyle(S.bright)}>PF5 - MAIN MENU</button>
        <button onClick={() => setMessage('HELP: PRESS PF5 TO ENTER MAIN MENU, PA3 FOR SECRET')} style={btnStyle(S.blue)}>PF1 - HELP</button>
        <button onClick={() => onNavigate('CESF')} style={btnStyle(S.grey)}>PF3 - QUIT</button>
        {hackFields?.master && (
          <button
            onClick={() => onNavigate('SCRT')}
            style={btnStyle(S.red)}
            title="PA3 - Only accessible with hack3270 AID injection"
          >
            PA3 - SECRET ⚠ [AID INJECT]
          </button>
        )}
      </div>

      <div style={{ marginTop: '8px', color: S.grey, fontSize: '11px' }}>
        {hackFields?.master
          ? '⚠ HACK3270 ACTIVE — PA3 AID INJECTION AVAILABLE'
          : 'PA3 IS NOT A STANDARD KEYBOARD KEY — USE HACK3270 TO INJECT AID'}
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