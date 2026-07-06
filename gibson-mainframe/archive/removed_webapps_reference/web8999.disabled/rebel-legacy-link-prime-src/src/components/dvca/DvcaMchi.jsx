import React, { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';

const S = {
  mono: "'Courier New', monospace",
  green: '#33FF33',
  bright: '#AAFFAA',
  blue: '#3399FF',
  yellow: '#FFFF00',
  red: '#FF3333',
  grey: '#668866',
};

// Sample history records
const STATIC_HISTORY = [
  { key: '00001', date: '09/17/22', name: 'Ballpoint Pens (box of 12)',       price: '$4.99',   shipping: '$2.99',  comment: 'Office Supply' },
  { key: '00002', date: '09/17/22', name: 'A4 Paper (500 sheets)',            price: '$6.99',   shipping: '$5.99',  comment: 'Office Supply' },
  { key: '00003', date: '09/18/22', name: 'Stapler - Heavy Duty',             price: '$18.50',  shipping: '$4.99',  comment: 'Office Supply' },
  { key: '00004', date: '09/19/22', name: 'Sticky Notes 3x3 (24 pads)',       price: '$12.99',  shipping: '$3.99',  comment: 'Office Supply' },
  { key: '00005', date: '09/20/22', name: 'Ergonomic Office Chair',           price: '$249.99', shipping: '$24.99', comment: 'Furniture' },
];

export default function DvcaMchi({ operatorId, onNavigate, hackFields, onLog }) {
  const [history, setHistory] = useState(STATIC_HISTORY);
  const [message, setMessage] = useState('ORDER HISTORY — PF7/PF8 TO SCROLL');
  const [msgType, setMsgType] = useState('normal');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 5;

  // Check for hidden delete command (option 99 from main menu — exposed by hack3270)
  const hiddenExposed = hackFields?.master && hackFields?.enable_hidden_fields;

  const handleClearAll = () => {
    // VULN: Option 99 deletes all history records without confirmation
    if (!hiddenExposed) {
      setMessage('INVREQ — OPTION 99 NOT AVAILABLE FROM THIS SCREEN');
      setMsgType('error');
      return;
    }
    const count = history.length;
    setHistory([]);
    setMessage(`DELETED ${count} RECORDS FROM HISTORY (OPTION 99 — NO CONFIRMATION REQUIRED)`);
    setMsgType('error');
    if (onLog) onLog({ type: 'warn', text: `⚠ VULN: ALL ${count} HISTORY RECORDS DELETED VIA HIDDEN OPTION 99 — NO AUTH/CONFIRM` });
  };

  const handleKey = (e) => {
    if (e.key === 'F7') { e.preventDefault(); setPage(p => Math.max(0, p - 1)); }
    if (e.key === 'F8') { e.preventDefault(); setPage(p => Math.min(Math.ceil(history.length / PAGE_SIZE) - 1, p + 1)); }
    if (e.key === 'F5' || e.key === 'F3') onNavigate('MCMM');
  };

  const pageRecords = history.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.max(1, Math.ceil(history.length / PAGE_SIZE));
  const msgColor = msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green;

  return (
    <div
      onKeyDown={handleKey}
      tabIndex={0}
      style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto', outline: 'none' }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ color: S.blue }}>MCHI</span>
        <span style={{ color: S.yellow, fontWeight: 'bold' }}>Mels Cargo — Order History</span>
        <span style={{ color: S.blue }}>MCHI</span>
      </div>
      <div style={{ color: S.blue, marginBottom: '8px' }}>{'─'.repeat(79)}</div>

      {/* Column headers */}
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '4px', fontSize: '12px' }}>
        {'KEY  '.padEnd(6)}{'DATE    '.padEnd(10)}{'PRODUCT NAME'.padEnd(36)}{'PRICE    '.padEnd(11)}{'SHIPPING '.padEnd(11)}COMMENT
      </div>
      <div style={{ color: S.blue, marginBottom: '4px' }}>{'─'.repeat(79)}</div>

      {/* Records */}
      {history.length === 0 ? (
        <div style={{ color: S.grey, margin: '10px 0' }}>
          NO HISTORY RECORDS FOUND
          {hiddenExposed && <span style={{ color: S.red }}> — ALL RECORDS DELETED VIA OPTION 99</span>}
        </div>
      ) : (
        pageRecords.map(rec => (
          <div key={rec.key} style={{ color: S.green, lineHeight: '1.8', fontSize: '12px', whiteSpace: 'nowrap', overflow: 'hidden' }}>
            <span style={{ color: S.grey }}>{rec.key} </span>
            <span style={{ color: S.neutral }}>{rec.date.padEnd(10)}</span>
            <span style={{ color: S.green }}>{rec.name.slice(0, 34).padEnd(36)}</span>
            <span style={{ color: S.bright }}>{rec.price.padEnd(11)}</span>
            <span style={{ color: S.blue }}>{rec.shipping.padEnd(11)}</span>
            <span style={{ color: S.grey }}>{rec.comment}</span>
          </div>
        ))
      )}

      <div style={{ color: S.blue, margin: '6px 0' }}>{'─'.repeat(79)}</div>

      {/* Pagination info */}
      <div style={{ color: S.grey, fontSize: '11px', marginBottom: '4px' }}>
        PAGE {page + 1} OF {totalPages} &nbsp;&nbsp; TOTAL RECORDS: {history.length}
      </div>

      {/* Message */}
      <div style={{ color: msgColor, fontWeight: 'bold', minHeight: '1.4em' }}>{message}</div>

      {/* PF keys */}
      <div style={{ color: S.blue, fontSize: '11px', marginTop: '4px' }}>
        PF1 - Help &nbsp;&nbsp; PF3/PF5 - Main Menu &nbsp;&nbsp; PF7 - Prev &nbsp;&nbsp; PF8 - Next
      </div>

      {/* Buttons */}
      <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={btnStyle(S.blue, page === 0)}>PF7 PREV</button>
        <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} style={btnStyle(S.blue, page >= totalPages - 1)}>PF8 NEXT</button>
        <button onClick={() => onNavigate('MCMM')} style={btnStyle(S.grey)}>PF5 MENU</button>
        {hiddenExposed && (
          <button onClick={handleClearAll} style={btnStyle(S.red)}>
            OPTION 99 — DELETE ALL RECORDS ⚠
          </button>
        )}
      </div>

      {!hackFields?.master && (
        <div style={{ marginTop: '8px', color: '#224422', fontSize: '11px' }}>
          HINT: Enable HACK3270 hidden fields to expose Option 99 (delete all records — no confirmation)
        </div>
      )}
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