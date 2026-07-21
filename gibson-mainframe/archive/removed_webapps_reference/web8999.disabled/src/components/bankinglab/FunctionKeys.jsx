import React from 'react';

const KEYS = [
  { pf: 'PF1', label: 'HELP' },
  { pf: 'PF3', label: 'BACK' },
  { pf: 'PF5', label: 'SUBMIT' },
  { pf: 'PF12', label: 'CANCEL' },
];

export default function FunctionKeys({ keys = KEYS, onKey }) {
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: '6px',
      padding: '4px 8px', borderTop: '1px solid #002200',
      background: '#000800', fontFamily: "'Courier New', monospace",
    }}>
      {keys.map(({ pf, label }) => (
        <button
          key={pf}
          onClick={() => onKey && onKey(pf)}
          style={{
            background: '#001100', border: '1px solid #336633',
            color: '#33FF33', fontFamily: "'Courier New', monospace",
            fontSize: '11px', padding: '2px 8px', cursor: 'pointer',
          }}
        >
          <span style={{ color: '#FFFF99' }}>{pf}</span>
          <span style={{ color: '#668866', marginLeft: '3px' }}>{label}</span>
        </button>
      ))}
    </div>
  );
}