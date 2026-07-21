import React, { useState } from 'react';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };

// HACK3270 transaction — shows BMS map field analysis
const BMS_MAPS = [
  {
    name: 'CSTMINQ — CUSTOMER INQUIRY MAP',
    fields: [
      { name: 'CUSTNO', attr: '0x00', type: 'Input', len: 8, protection: 'Unprotected', hidden: false, numeric: true },
      { name: 'CUSTNM', attr: '0x20', type: 'Output', len: 40, protection: 'Protected', hidden: false, numeric: false },
      { name: 'DOFBTH', attr: '0x0C', type: 'Hidden', len: 8, protection: 'Protected', hidden: true, numeric: false },
      { name: 'NINO  ', attr: '0x0C', type: 'Hidden', len: 12, protection: 'Protected', hidden: true, numeric: false },
      { name: 'SRTCDE', attr: '0x20', type: 'Output', len: 6, protection: 'Protected', hidden: false, numeric: true },
      { name: 'STATUS', attr: '0x20', type: 'Output', len: 1, protection: 'Protected', hidden: false, numeric: false },
    ],
  },
  {
    name: 'ACCTINQ — ACCOUNT INQUIRY MAP',
    fields: [
      { name: 'ACCTNO', attr: '0x00', type: 'Input', len: 10, protection: 'Unprotected', hidden: false, numeric: true },
      { name: 'BALANC', attr: '0x20', type: 'Output', len: 12, protection: 'Protected', hidden: false, numeric: true },
      { name: 'CRDLMT', attr: '0x0C', type: 'Hidden', len: 12, protection: 'Protected', hidden: true, numeric: true },
      { name: 'INTRAT', attr: '0x0C', type: 'Hidden', len: 8, protection: 'Protected', hidden: true, numeric: true },
      { name: 'STATUS', attr: '0x20', type: 'Output', len: 1, protection: 'Protected', hidden: false, numeric: false },
    ],
  },
  {
    name: 'DRCAINQ — DEBIT/CREDIT/PIN MAP',
    fields: [
      { name: 'ACCTNO', attr: '0x00', type: 'Input', len: 10, protection: 'Unprotected', hidden: false, numeric: true },
      { name: 'AMOUNT', attr: '0x02', type: 'Input', len: 12, protection: 'Unprotected', hidden: false, numeric: true },
      { name: 'PINNUM', attr: '0x4C', type: 'Hidden/MDT', len: 4, protection: 'Protected', hidden: true, numeric: true },
      { name: 'TRNTYP', attr: '0x00', type: 'Input', len: 2, protection: 'Unprotected', hidden: false, numeric: false },
      { name: 'ERRMSG', attr: '0x24', type: 'Output', len: 50, protection: 'Protected', hidden: false, numeric: false },
    ],
  },
  {
    name: 'XFERINQ — TRANSFER MAP',
    fields: [
      { name: 'FRMACT', attr: '0x00', type: 'Input', len: 10, protection: 'Unprotected', hidden: false, numeric: true },
      { name: 'TOACT ', attr: '0x00', type: 'Input', len: 10, protection: 'Unprotected', hidden: false, numeric: true },
      { name: 'AMOUNT', attr: '0x02', type: 'Input', len: 12, protection: 'Unprotected', hidden: false, numeric: true },
      { name: 'PINNUM', attr: '0x4C', type: 'Hidden/MDT', len: 4, protection: 'Protected', hidden: true, numeric: true },
      { name: 'CSRFTK', attr: '0x0C', type: 'Hidden', len: 0, protection: 'NOT IMPLEMENTED', hidden: true, numeric: false },
    ],
  },
];

export default function DvcaHack3270Inspector({ operatorId, onNavigate, hackFields = {} }) {
  const [selectedMap, setSelectedMap] = useState(0);
  const [highlightHidden, setHighlightHidden] = useState(false);

  const map = BMS_MAPS[selectedMap];

  const fieldColor = (f) => {
    if (f.hidden && highlightHidden) return '#FF9933';
    if (f.hidden) return '#553300';
    if (f.protection === 'NOT IMPLEMENTED') return '#FF3333';
    if (f.protection === 'Unprotected') return S.bright;
    return S.green;
  };

  const handleKey = (e) => {
    if (e.key === 'F3') onNavigate('DVCA_MENU');
  };

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: '#FF9933', fontWeight: 'bold', marginBottom: '2px' }}>PIBS — HACK3270 FIELD INSPECTOR &nbsp;&nbsp;&nbsp; HACK3270</div>
      <div style={{ color: S.green, marginBottom: '6px' }}>{'─'.repeat(70)}</div>

      <div style={{ color: S.grey, fontSize: '11px', marginBottom: '8px' }}>
        ⚠ TRAINING TOOL — SHOWS BMS MAP ATTRIBUTE BYTE ANALYSIS — IDENTIFIES HIDDEN/PROTECTED FIELDS
      </div>

      {/* Map selector */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '10px', flexWrap: 'wrap' }}>
        {BMS_MAPS.map((m, i) => (
          <button key={i} onClick={() => setSelectedMap(i)}
            style={{
              background: selectedMap === i ? '#002200' : '#111',
              border: `1px solid ${selectedMap === i ? S.green : '#336633'}`,
              color: selectedMap === i ? S.bright : S.grey,
              fontFamily: S.mono, fontSize: '11px', padding: '2px 8px', cursor: 'pointer',
            }}>
            {m.name.split(' — ')[0]}
          </button>
        ))}
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: highlightHidden ? '#FF9933' : S.grey, fontSize: '11px', cursor: 'pointer', marginLeft: '10px' }}>
          <input type="checkbox" checked={highlightHidden} onChange={() => setHighlightHidden(h => !h)} />
          Highlight Hidden Fields
        </label>
      </div>

      <div style={{ color: '#FF9933', fontWeight: 'bold', marginBottom: '6px' }}>{map.name}</div>

      {/* Field table */}
      <div style={{ borderTop: '1px solid #336633', paddingTop: '4px' }}>
        <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>
          {'FIELD'.padEnd(10)}{'ATTR'.padEnd(8)}{'TYPE'.padEnd(14)}{'LEN'.padEnd(6)}{'PROTECTION'.padEnd(20)}{'NOTES'}
        </div>
        {map.fields.map((f, i) => (
          <div key={i} style={{ color: fieldColor(f), lineHeight: '1.9', fontSize: '12px' }}>
            {f.name.padEnd(10)}
            {f.attr.padEnd(8)}
            {f.type.padEnd(14)}
            {String(f.len).padEnd(6)}
            {f.protection.padEnd(20)}
            {f.hidden ? <span style={{ color: '#FF9933' }}>⚠ HIDDEN FIELD — EXPLOIT WITH ENABLE HIDDEN FIELDS</span> : ''}
            {f.protection === 'NOT IMPLEMENTED' ? <span style={{ color: S.red }}>⚠ CSRF TOKEN NOT PRESENT — VULNERABLE TO CSRF</span> : ''}
            {f.name.trim() === 'PINNUM' ? <span style={{ color: S.red }}>⚠ PIN STORED IN PLAINTEXT — BATCH BRUTE-FORCE POSSIBLE</span> : ''}
          </div>
        ))}
      </div>

      <div style={{ marginTop: '10px', color: S.grey, fontSize: '11px', borderTop: '1px solid #224422', paddingTop: '4px' }}>
        VULNERABILITIES IDENTIFIED:
        {['Hidden fields contain PII (NI, DOB, PIN) without encryption',
          'PIN transmitted in plaintext in DRCA/XFER transactions',
          'No CSRF token implemented in XFER map',
          'No account lockout on PIN failures (brute-force via DRCA)',
          'Credit limit and interest rate exposed in unmasked fields',
        ].map((v, i) => (
          <div key={i} style={{ color: S.red, marginLeft: '2ch' }}> {i+1}. {v}</div>
        ))}
      </div>

      <div style={{ marginTop: '8px', color: S.grey, fontSize: '11px' }}>PF3 = MENU</div>
    </div>
  );
}