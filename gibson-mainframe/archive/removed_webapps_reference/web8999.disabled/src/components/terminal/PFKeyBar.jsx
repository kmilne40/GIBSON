import React from 'react';

export default function PFKeyBar({ keys }) {
  // keys: array of { pf, label, active }
  const defaultKeys = [
    { pf: 'PF1', label: 'HELP' },
    { pf: 'PF3', label: 'END' },
    { pf: 'PF5', label: 'ADD' },
    { pf: 'PF6', label: 'UPD' },
    { pf: 'PF7', label: 'UP' },
    { pf: 'PF8', label: 'DN/INQ' },
    { pf: 'PF9', label: 'NEXT' },
    { pf: 'PF12', label: 'CODE' },
  ];

  const displayKeys = keys || defaultKeys;

  return (
    <div style={{
      position: 'absolute',
      bottom: 0,
      left: 0,
      right: 0,
      height: '28px',
      background: '#000000',
      borderTop: '1px solid #005500',
      display: 'flex',
      alignItems: 'center',
      paddingLeft: '4px',
      fontFamily: "'Courier New', Courier, monospace",
      fontSize: '12px',
      flexWrap: 'nowrap',
      overflow: 'hidden',
    }}>
      {displayKeys.map((k, i) => (
        <span key={i} style={{ marginRight: '6px', whiteSpace: 'nowrap' }}>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>{k.pf}</span>
          <span style={{ color: '#33FF33' }}>={k.label}</span>
        </span>
      ))}
    </div>
  );
}