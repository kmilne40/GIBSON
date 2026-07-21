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

// SECRET screen — only accessible via PA3 (AID injection with hack3270)
// Vulnerability: COBOL program handles AID PA3 which is not on standard keyboard
const SECRET_TEXT = [
  "  *** SECRET MENU — TRANSACTION: SCRT ***",
  "",
  "  You found the secret menu!",
  "  This screen is only accessible via PA3",
  "  which is NOT available on a standard keyboard.",
  "",
  "  VULNERABILITY: COBOL programs can handle any",
  "  AID byte including PA1, PA2, PA3 which normal",
  "  users cannot press without a tool like BIRP.",
  "",
  "  Using a TN3270 tool or HACK3270 you can inject",
  "  raw AID bytes and reach unreachable screens.",
  "",
  "  This screen demonstrates:",
  "  - Hidden application flow via PA3 AID",
  "  - COBOL programs that respond to non-keyboard keys",
  "  - Secret functionality in production CICS apps",
  "",
  "  VULN REFERENCE: CWE-288 — Authentication Bypass",
  "  Using an Alternate Path or Channel",
  "",
  "  PF5 = Return to Main Menu",
  "  PA1 = Easter Egg (press button below)",
];

const EASTER_EGG = [
  "  ╔══════════════════════════════════════╗",
  "  ║  YOU FOUND THE EASTER EGG!           ║",
  "  ║                                      ║",
  "  ║  'There are only two hard things     ║",
  "  ║   in computer science: cache         ║",
  "  ║   invalidation, naming things,       ║",
  "  ║   and off-by-one errors.'            ║",
  "  ║                                      ║",
  "  ║  — Philip Young, Soldier of FORTRAN  ║",
  "  ╚══════════════════════════════════════╝",
];

export default function DvcaScrt({ onNavigate, onLog }) {
  const [showEgg, setShowEgg] = useState(false);

  const handleKey = (e) => {
    if (e.key === 'F5' || e.key === 'F3') onNavigate('MCMM');
  };

  const handlePA1 = () => {
    setShowEgg(true);
    if (onLog) onLog({ type: 'success', text: 'EASTER EGG TRIGGERED: PA1 AID on SECRET screen' });
  };

  return (
    <div
      onKeyDown={handleKey}
      tabIndex={0}
      style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto', outline: 'none' }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ color: S.blue }}>SCRT</span>
        <span style={{ color: S.red, fontWeight: 'bold' }}>⚠ SECRET SCREEN — PA3 AID INJECTION REQUIRED</span>
        <span style={{ color: S.blue }}>SCRT</span>
      </div>
      <div style={{ color: S.red, marginBottom: '8px' }}>{'═'.repeat(79)}</div>

      {/* Secret content */}
      <div>
        {SECRET_TEXT.map((line, i) => (
          <div key={i} style={{
            color: line.includes('VULN') || line.includes('CWE') ? S.red
              : line.includes('PA3') || line.includes('PA1') || line.includes('PA2') ? S.yellow
              : line.startsWith('  *') ? S.bright
              : S.green,
            lineHeight: '1.6',
            whiteSpace: 'pre',
          }}>{line || ' '}</div>
        ))}
      </div>

      {/* Easter egg */}
      {showEgg && (
        <div style={{ marginTop: '10px' }}>
          {EASTER_EGG.map((line, i) => (
            <div key={i} style={{ color: S.cyan, lineHeight: '1.5', whiteSpace: 'pre' }}>{line}</div>
          ))}
        </div>
      )}

      <div style={{ color: S.red, margin: '8px 0' }}>{'═'.repeat(79)}</div>

      {/* Buttons */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button onClick={() => onNavigate('MCMM')} style={btnStyle(S.grey)}>PF5 MAIN MENU</button>
        <button onClick={handlePA1} style={btnStyle(S.yellow)}>PA1 — EASTER EGG</button>
      </div>

      <div style={{ marginTop: '6px', color: S.grey, fontSize: '11px' }}>
        This screen was reached via PA3 AID injection — not accessible from normal keyboard
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