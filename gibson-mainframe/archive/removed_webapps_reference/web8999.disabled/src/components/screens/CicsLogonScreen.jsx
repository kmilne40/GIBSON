import React, { useState } from 'react';

export default function CicsLogonScreen({ operatorId, onLoginSuccess, onBack }) {
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('ENTER CICS APPLID CREDENTIALS TO CONTINUE');
  const [msgType, setMsgType] = useState('normal');
  const [attempts, setAttempts] = useState(0);

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  const msgColor = msgType === 'error' ? '#FF3333' : msgType === 'success' ? '#AAFFAA' : '#33FF33';

  const handleLogon = () => {
    if (userId.toUpperCase() === 'IBMUSER' && password === 'SYS1') {
      setMessage('SIGNON SUCCESSFUL - CONNECTING TO CICS APPLID...');
      setMsgType('success');
      setTimeout(() => onLoginSuccess(), 600);
    } else {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);
      setPassword('');
      if (newAttempts >= 3) {
        setMessage(`DFHAC2006 ${userId.toUpperCase() || 'UNKNOWN'} INVALID CREDENTIALS - ${newAttempts} FAILED ATTEMPT(S) - TERMINAL MAY BE LOCKED`);
      } else {
        setMessage(`DFHAC2006 ${userId.toUpperCase() || 'UNKNOWN'} YOUR USERID OR PASSWORD IS INVALID`);
      }
      setMsgType('error');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); handleLogon(); }
    if (e.key === 'F3') { e.preventDefault(); onBack(); }
  };

  const iStyle = (w, isPass = false) => ({
    background: 'transparent', border: 'none',
    borderBottom: '1px solid #3399FF',
    color: '#3399FF', fontFamily: "'Courier New', monospace",
    fontSize: '14px', outline: 'none',
    textTransform: isPass ? 'none' : 'uppercase',
    padding: 0, width: `${w}ch`,
    letterSpacing: isPass ? '0.2em' : 'normal',
  });

  return (
    <div
      onKeyDown={handleKeyDown}
      style={{ flex: 1, padding: '8px', fontFamily: "'Courier New', monospace", fontSize: '14px', color: '#33FF33', paddingBottom: '60px' }}
    >
      {/* Header */}
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span>BANKMASTER/VS</span>
        <span>DFHCE3520</span>
        <span>DATE: {dateStr}</span>
      </div>
      <div style={{ color: '#33FF33', marginBottom: '16px' }}>{'─'.repeat(79)}</div>

      {/* Title */}
      <div style={{ textAlign: 'center', color: '#AAFFAA', fontWeight: 'bold', fontSize: '15px', letterSpacing: '2px', marginBottom: '4px' }}>
        SIGHBERBANK PLC
      </div>
      <div style={{ textAlign: 'center', color: '#AAFFAA', fontWeight: 'bold', marginBottom: '2px' }}>
        CICS TRANSACTION SERVER  -  APPLID: CICS
      </div>
      <div style={{ textAlign: 'center', color: '#668866', fontSize: '12px', marginBottom: '2px' }}>
        IBM CICS/VS  REL 2.1.1  REGION: CICSREG1
      </div>
      <div style={{ textAlign: 'center', color: '#33FF33', marginBottom: '20px' }}>
        {'─'.repeat(50)}
      </div>

      {/* Logon form */}
      <div style={{ marginLeft: '12ch', lineHeight: '2.2' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '14ch' }}>OPERATOR ID  :</span>
          <input
            type="text"
            value={userId}
            onChange={e => setUserId(e.target.value.toUpperCase().slice(0, 8))}
            maxLength={8}
            autoFocus
            style={iStyle(8)}
            autoComplete="off"
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '14ch' }}>PASSWORD     :</span>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value.slice(0, 8))}
            maxLength={8}
            style={iStyle(8, true)}
            autoComplete="off"
          />
        </div>
      </div>

      <div style={{ color: '#33FF33', margin: '12px 0 4px 0' }}>{'─'.repeat(79)}</div>

      {/* Status message */}
      <div style={{ color: msgColor, fontWeight: 'bold', minHeight: '1.6em', marginBottom: '4px' }}>
        ==&gt; {message}
      </div>

      {/* Hints */}
      <div style={{ color: '#668866', fontSize: '12px', marginTop: '4px' }}>
        ENTER=SIGNON  PF3=RETURN TO MAIN MENU
      </div>

      {/* Buttons */}
      <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
        <button
          onClick={handleLogon}
          style={{ background: '#001100', border: '1px solid #AAFFAA', color: '#AAFFAA', fontFamily: 'inherit', fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>
          ENTER SIGNON
        </button>
        <button
          onClick={onBack}
          style={{ background: '#001100', border: '1px solid #668866', color: '#668866', fontFamily: 'inherit', fontSize: '12px', padding: '2px 10px', cursor: 'pointer' }}>
          PF3 RETURN
        </button>
      </div>

      {/* Security notice */}
      <div style={{ marginTop: '20px', color: '#333300', fontSize: '11px', borderTop: '1px solid #221100', paddingTop: '6px' }}>
        *** THIS SYSTEM IS RESTRICTED TO AUTHORISED PERSONNEL ONLY ***<br/>
        *** UNAUTHORISED ACCESS IS A CRIMINAL OFFENCE UNDER THE COMPUTER MISUSE ACT 1990 ***
      </div>
    </div>
  );
}