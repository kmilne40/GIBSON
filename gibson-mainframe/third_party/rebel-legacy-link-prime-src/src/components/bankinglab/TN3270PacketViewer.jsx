import React, { useState } from 'react';

// Simulated TN3270 packet captures — plaintext EBCDIC credentials visible
const PACKETS = [
  {
    id: 'PKT-001',
    direction: 'CLIENT→SERVER',
    timestamp: '14:32:01.004',
    type: 'TN3270 DATA',
    length: 64,
    hex: 'FF EF 00 01 00 00 C9 C2 D4 E4 E2 C5 D9 40 40 40 40 40 E2 E8 E2 F1 40 40 40 40 40 40 40 40 40 40',
    ebcdic: 'IBMUSER  SYS1            ',
    note: '⚠ PLAINTEXT CREDENTIALS IN TN3270 LOGON STREAM (VULN #1)',
    highlight: true,
  },
  {
    id: 'PKT-002',
    direction: 'SERVER→CLIENT',
    timestamp: '14:32:01.112',
    type: 'TN3270 DATA',
    length: 128,
    hex: 'FF EF 00 01 F1 C2 11 40 40 1D 60 C2 C1 D5 D2 D4 C1 E2 E3 C5 D9 2F E5 E2 40 40 40 40 40 40 40 40',
    ebcdic: 'BANKMASTER/VS  CICSLAB1  SIGNON OK',
    note: 'LOGON ACCEPTED — SESSION ESTABLISHED',
    highlight: false,
  },
  {
    id: 'PKT-003',
    direction: 'CLIENT→SERVER',
    timestamp: '14:32:04.889',
    type: 'TN3270 DATA',
    length: 32,
    hex: 'FF EF 00 01 C3 E4 E2 E3 40 40 40 40 40 40 40 40',
    ebcdic: 'CUST            ',
    note: 'TRANSACTION CODE ENTRY — VISIBLE IN STREAM',
    highlight: false,
  },
  {
    id: 'PKT-004',
    direction: 'CLIENT→SERVER',
    timestamp: '14:32:09.441',
    type: 'TN3270 DATA',
    length: 48,
    hex: 'FF EF 00 01 F1 F0 F0 F0 F0 F0 F0 F0 F1 40 40 40 40 40 40 40 40 40 40 40',
    ebcdic: '10000001                ',
    note: 'CUSTOMER ID FIELD — PII EXPOSED IN TRANSIT',
    highlight: true,
  },
  {
    id: 'PKT-005',
    direction: 'SERVER→CLIENT',
    timestamp: '14:32:09.558',
    type: 'TN3270 DATA',
    length: 256,
    hex: 'FF EF 00 01 C8 C1 D9 D9 C9 E2 D6 D5 40 E6 C9 D3 D3 C9 C1 D4 40 40 40 E2 D6 D9 E3 40 C3 D6 C4 C5',
    ebcdic: 'HARRISON WILLIAM    SORT CODE: 20-45-14  BAL: £24521.00',
    note: '⚠ FULL CUSTOMER RECORD RETURNED IN PLAINTEXT (VULN #1)',
    highlight: true,
  },
  {
    id: 'PKT-006',
    direction: 'CLIENT→SERVER',
    timestamp: '14:32:15.001',
    type: 'TN3270 AID',
    length: 3,
    hex: '7D 40 40',
    ebcdic: 'ENTER KEY (AID=0x7D)',
    note: 'AID KEY PRESS — OBSERVABLE VIA WIRESHARK tcp.port==23',
    highlight: false,
  },
];

export default function TN3270PacketViewer() {
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState('ALL');

  const filtered = filter === 'ALL' ? PACKETS : filter === 'VULN' ? PACKETS.filter(p => p.highlight) : PACKETS.filter(p => p.direction.startsWith(filter === 'C→S' ? 'CLIENT' : 'SERVER'));

  return (
    <div style={{ fontFamily: "'Courier New', monospace", fontSize: '12px', color: '#33FF33', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '4px 8px', borderBottom: '1px solid #002200' }}>
        <div style={{ color: '#FF9933', fontWeight: 'bold', fontSize: '11px', marginBottom: '4px' }}>
          TN3270 PACKET CAPTURE — PORT 23 — PLAINTEXT EBCDIC STREAM
        </div>
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {['ALL','VULN','C→S','S→C'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              style={{
                background: filter === f ? '#002200' : '#000800',
                border: `1px solid ${filter === f ? '#AAFFAA' : '#336633'}`,
                color: filter === f ? '#FFFF99' : '#668866',
                fontFamily: "'Courier New', monospace", fontSize: '10px',
                padding: '1px 8px', cursor: 'pointer',
              }}>{f}</button>
          ))}
          <span style={{ color: '#668866', fontSize: '10px', alignSelf: 'center', marginLeft: '6px' }}>
            WIRESHARK FILTER: tcp.port == 23
          </span>
        </div>
      </div>

      {/* Packet list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
        {filtered.map(pkt => (
          <div key={pkt.id}
            onClick={() => setSelected(selected?.id === pkt.id ? null : pkt)}
            style={{
              border: `1px solid ${selected?.id === pkt.id ? '#AAFFAA' : pkt.highlight ? '#553300' : '#002200'}`,
              background: selected?.id === pkt.id ? '#001800' : pkt.highlight ? '#0a0500' : '#000800',
              padding: '4px 6px', marginBottom: '4px', cursor: 'pointer',
            }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'baseline', flexWrap: 'wrap' }}>
              <span style={{ color: '#668866', fontSize: '10px' }}>{pkt.timestamp}</span>
              <span style={{ color: '#3399FF', fontSize: '10px', fontWeight: 'bold' }}>{pkt.id}</span>
              <span style={{ color: pkt.direction.startsWith('CLIENT') ? '#FF9933' : '#33FF33', fontSize: '10px' }}>{pkt.direction}</span>
              <span style={{ color: '#AAFFAA', fontSize: '10px' }}>{pkt.type}</span>
              <span style={{ color: '#668866', fontSize: '10px' }}>{pkt.length}B</span>
              {pkt.highlight && <span style={{ color: '#FF3333', fontSize: '10px', fontWeight: 'bold' }}>⚠ VULN</span>}
            </div>
            <div style={{ color: pkt.highlight ? '#FF9933' : '#668866', fontSize: '10px', marginTop: '2px' }}>{pkt.note}</div>

            {selected?.id === pkt.id && (
              <div style={{ marginTop: '8px', borderTop: '1px solid #002200', paddingTop: '6px' }}>
                <div style={{ color: '#FFFF99', fontSize: '10px', fontWeight: 'bold', marginBottom: '4px' }}>HEX DUMP:</div>
                <div style={{ color: '#3399FF', fontSize: '11px', fontFamily: "'Courier New', monospace", wordBreak: 'break-all', marginBottom: '6px' }}>
                  {pkt.hex}
                </div>
                <div style={{ color: '#FFFF99', fontSize: '10px', fontWeight: 'bold', marginBottom: '4px' }}>EBCDIC DECODE:</div>
                <div style={{ color: '#AAFFAA', fontSize: '12px', fontFamily: "'Courier New', monospace", background: '#000000', padding: '4px', border: '1px solid #001100' }}>
                  {pkt.ebcdic}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{ padding: '4px 8px', borderTop: '1px solid #002200', color: '#336633', fontSize: '10px' }}>
        TOTAL PACKETS: {filtered.length}  ·  CLICK PACKET TO EXPAND HEX DUMP  ·  ⚠ = VULNERABILITY EVIDENCE
      </div>
    </div>
  );
}