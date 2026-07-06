import React, { useState } from 'react';

export default function MainMenu({ operatorId, onNavigate }) {
  const [selection, setSelection] = useState('');

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      const val = selection.trim().toUpperCase();
      if (val === '1' || val === 'CUST') onNavigate('CUST');
      else if (val === '2' || val === 'ACCT') onNavigate('ACCT');
      else if (val === '3' || val === 'TRAN') onNavigate('TRAN');
      else if (val === '5' || val === 'LOGO') onNavigate('LOGO');
      else if (val === 'ADMN') onNavigate('ADMN');
      // VULN: Admin/system transactions accessible without auth check
      else if (val === 'CECI') onNavigate('CECI');
      else if (val === 'CEMT' || val === 'CEDA') onNavigate('CEMT');
      else if (val === 'REST' || val === '6') onNavigate('REST');
      else if (val === 'TN32' || val === '7') onNavigate('TN32');
      else if (val === 'BULK' || val === '4') onNavigate('BULK');
      else if (val === 'CICS' || val === '8') onNavigate('CICS');
      else if (val === 'BLAB' || val === '9') onNavigate('BLAB');
      else if (val === 'DVCA') onNavigate('DVCA');
      else if (/^LOGON\s+APPLID\s*\(\s*CICS\s*\)$/i.test(val.trim())) onNavigate('CICS_LOGON');
      setSelection('');
    }
    if (e.key === 'F3') onNavigate('LOGO');
    if (e.key === 'F1') onNavigate('HELP');
  };

  return (
    <div
      onKeyDown={handleKeyDown}
      style={{ flex: 1, position: 'relative', overflow: 'hidden', padding: '8px', fontFamily: "'Courier New', monospace" }}
    >
      {/* Header */}
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '2px' }}>
        {'BANKMASTER/VS'.padEnd(30)}{'BKGMENU'.padEnd(20)}{'DATE: ' + dateStr}
      </div>
      <div style={{ color: '#33FF33', marginBottom: '8px' }}>
        {'─'.repeat(79)}
      </div>

      {/* Title */}
      <div style={{ textAlign: 'center', color: '#AAFFAA', fontWeight: 'bold', fontSize: '15px', letterSpacing: '2px', marginBottom: '4px' }}>
        SIGHBERBANK PLC
      </div>
      <div style={{ textAlign: 'center', color: '#AAFFAA', fontWeight: 'bold', marginBottom: '2px' }}>
        BANKMASTER/VS  -  MAIN TRANSACTION MENU
      </div>
      <div style={{ textAlign: 'center', color: '#33FF33', marginBottom: '16px' }}>
        {'─'.repeat(50)}
      </div>

      {/* Menu items */}
      <div style={{ marginLeft: '10ch', lineHeight: '2.0', color: '#33FF33' }}>
        <div>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  1   CUST</span>
          <span>   -   CUSTOMER MASTER MAINTENANCE</span>
        </div>
        <div>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  2   ACCT</span>
          <span>   -   ACCOUNT INQUIRY & MAINTENANCE</span>
        </div>
        <div>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  3   TRAN</span>
          <span>   -   TRANSACTION POSTING</span>
        </div>
        <div>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  4   BULK</span>
          <span>   -   BULK PROCESSING CENTRE  </span>
          <span style={{ color: '#668866' }}>(MORTGAGE / PAYMENTS / CARD APPROVALS)</span>
        </div>
        <div style={{ height: '0.4em' }} />
        <div style={{ color: '#668866' }}>{'─'.repeat(55)}</div>
        <div>
          <span style={{ color: '#FF9933', fontWeight: 'bold' }}>  6   REST</span>
          <span style={{ color: '#FF9933' }}>   -   REST API SECURITY TESTER</span>
          <span style={{ color: '#553300' }}>        [SECURITY LAB]</span>
        </div>
        <div>
          <span style={{ color: '#FF9933', fontWeight: 'bold' }}>  7   TN32</span>
          <span style={{ color: '#FF9933' }}>   -   TN3270 PACKET ANALYSER (PLAINTEXT STREAM)</span>
        </div>
        <div style={{ height: '0.4em' }} />
        <div style={{ color: '#668866' }}>{'─'.repeat(55)}</div>
        <div>
          <span style={{ color: '#FF3333', fontWeight: 'bold' }}>      CECI</span>
          <span style={{ color: '#FF3333' }}>   -   COMMAND INTERPRETER  </span>
          <span style={{ color: '#553300' }}>⚠ NO AUTH (VULN #6)</span>
        </div>
        <div>
          <span style={{ color: '#FF3333', fontWeight: 'bold' }}>      CEMT</span>
          <span style={{ color: '#FF3333' }}>   -   MASTER TERMINAL      </span>
          <span style={{ color: '#553300' }}>⚠ NO AUTH (VULN #5)</span>
        </div>
        <div style={{ height: '0.4em' }} />
        <div>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  8   CICS</span>
          <span style={{ color: '#AAFFAA' }}>   -   CICS TRANSACTION SERVICES  </span>
          <span style={{ color: '#446644' }}>(CEDA/CEDF/BMS/SECURITY LAB)</span>
        </div>
        <div>
          <span style={{ color: '#FF9933', fontWeight: 'bold' }}>  9   BLAB</span>
          <span style={{ color: '#FF9933' }}>   -   BANKING LAB  </span>
          <span style={{ color: '#553300' }}>(INTERACTIVE VULNERABILITY SIMULATION)</span>
        </div>
        <div>
          <span style={{ color: '#FF3333', fontWeight: 'bold' }}>      DVCA</span>
          <span style={{ color: '#FF3333' }}>   -   DAMN VULNERABLE CICS APPLICATION  </span>
          <span style={{ color: '#553300' }}>⚠ PIBS/HACK3270 TRAINING</span>
        </div>
        <div style={{ height: '0.4em' }} />
        <div>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  5   LOGO</span>
          <span>   -   SIGN OFF TERMINAL</span>
        </div>
        <div style={{ height: '0.4em' }} />
        <div style={{ color: '#668866' }}>{'─'.repeat(55)}</div>
        <div>
          <span style={{ color: '#668866' }}>      TYPE  </span>
          <span style={{ color: '#3399FF', fontWeight: 'bold' }}>LOGON APPLID(CICS)</span>
          <span style={{ color: '#668866' }}>   TO ACCESS CICS APPLID DIRECTLY</span>
        </div>
      </div>

      {/* Selection field */}
      <div style={{ marginTop: '24px', display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '8px' }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>SELECTION ==&gt;</span>
        <input
          type="text"
          value={selection}
          onChange={e => setSelection(e.target.value.toUpperCase().slice(0,24))}
          maxLength={24}
          autoFocus
          style={{
            width: '24ch', background: 'transparent', border: 'none',
            borderBottom: '1px solid #3399FF', color: '#3399FF',
            fontFamily: "'Courier New', monospace", fontSize: '14px',
            outline: 'none', textTransform: 'uppercase',
          }}
        />
        <span style={{ color: '#33FF33' }}>OR TYPE TRANSACTION CODE DIRECTLY</span>
      </div>

      {/* Operator info */}
      <div style={{ position: 'absolute', bottom: '60px', left: '8px', right: '8px', color: '#33FF33', fontSize: '12px', borderTop: '1px solid #004400', paddingTop: '4px' }}>
        OPERATOR: {operatorId}{'   '}TERMINAL: LT0042{'   '}REGION: CICSREG1{'   '}DATE: {dateStr}
      </div>
    </div>
  );
}