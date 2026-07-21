import React, { useEffect, useState } from 'react';

export default function StatusBar({ transactionId, operatorId, message, messageType = 'normal' }) {
  const [time, setTime] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      const ss = String(now.getSeconds()).padStart(2, '0');
      setTime(`${hh}:${mm}:${ss}`);
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, []);

  const msgColor = messageType === 'error' ? '#FF3333' : messageType === 'success' ? '#AAFFAA' : '#33FF33';

  const leftSide = `TRANS: ${(transactionId || 'NONE').padEnd(8)} OPER: ${(operatorId || 'UNKNOWN').padEnd(8)}`;
  const msgPad = message ? message.substring(0, 45) : 'READY';
  const rightSide = `TIME: ${time}`;
  const spacer = ' '.repeat(Math.max(1, 80 - leftSide.length - msgPad.length - rightSide.length));

  return (
    <div style={{
      position: 'absolute',
      bottom: '28px',
      left: 0,
      right: 0,
      height: '1.2em',
      background: '#001100',
      borderTop: '1px solid #33FF33',
      display: 'flex',
      alignItems: 'center',
      paddingLeft: '8px',
      paddingRight: '8px',
      fontFamily: "'Courier New', Courier, monospace",
      fontSize: '13px',
    }}>
      <span style={{ color: '#33FF33', whiteSpace: 'pre' }}>{leftSide}</span>
      <span style={{ color: msgColor, flex: 1, textAlign: 'center', fontWeight: 'bold' }}>{msgPad}</span>
      <span style={{ color: '#33FF33', whiteSpace: 'pre' }}>{rightSide}</span>
    </div>
  );
}