import React, { useState } from 'react';

const S = {
  root: { flex: 1, fontFamily: "'Courier New', monospace", fontSize: '13px', color: '#33FF33', display: 'flex', flexDirection: 'column', height: '100%' },
  hdr: { color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', marginBottom: '2px', padding: '6px 8px 0' },
  sep: { color: '#33FF33', margin: '0 8px 6px' },
  body: { flex: 1, overflowY: 'auto', padding: '0 8px 8px' },
};

const SCREENS = {
  LOGON: ({ fields, setFields, onLogin, msg }) => {
    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;
    return (
      <div style={{ padding: '20px 8px' }}>
        <div style={{ textAlign: 'center', color: '#AAFFAA', fontWeight: 'bold', fontSize: '15px', letterSpacing: '3px', marginBottom: '4px' }}>
          SIGHBERBANK PLC
        </div>
        <div style={{ textAlign: 'center', color: '#33FF33', marginBottom: '2px' }}>BANKING LAB — CICS/VS APPLID: CICSLAB1</div>
        <div style={{ textAlign: 'center', color: '#668866', marginBottom: '16px', fontSize: '11px' }}>DATE: {dateStr}  ·  TN3270 PORT: 23  ·  TERMINAL: LT0042</div>
        <div style={{ color: '#FF9933', border: '1px solid #553300', padding: '6px 12px', marginBottom: '16px', fontSize: '11px' }}>
          ⚠  AUTHORISED USE ONLY  ·  ALL SESSIONS ARE MONITORED AND LOGGED  ·  DFHCE3520
        </div>
        <div style={{ marginLeft: '8ch' }}>
          {[
            { label: 'USERID   ==>', key: 'userid', w: 8 },
            { label: 'PASSWORD ==>', key: 'password', w: 8, type: 'password' },
          ].map(({ label, key, w, type = 'text' }) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '14ch' }}>{label}</span>
              <input
                type={type}
                value={fields[key]}
                onChange={e => setFields(f => ({ ...f, [key]: e.target.value.toUpperCase().slice(0, w) }))}
                onKeyDown={e => e.key === 'Enter' && onLogin()}
                maxLength={w}
                style={{ background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF', color: '#3399FF', fontFamily: "'Courier New', monospace", fontSize: '13px', outline: 'none', width: `${w}ch` }}
                autoFocus={key === 'userid'}
              />
            </div>
          ))}
          <button onClick={onLogin} style={{ background: '#001100', border: '1px solid #33FF33', color: '#33FF33', fontFamily: "'Courier New', monospace", fontSize: '12px', padding: '3px 14px', cursor: 'pointer', marginTop: '8px' }}>
            ENTER — LOGON
          </button>
        </div>
        {msg && <div style={{ color: msg.type === 'error' ? '#FF3333' : '#AAFFAA', marginTop: '16px', marginLeft: '8px', fontWeight: 'bold' }}>==&gt; {msg.text}</div>}
        <div style={{ marginTop: '20px', marginLeft: '8px', color: '#668866', fontSize: '11px' }}>
          <div>DEFAULT CREDENTIALS (VULN #2 — HARDCODED):  IBMUSER / SYS1</div>
          <div style={{ marginTop: '2px' }}>OTHER ACCOUNTS:  CICSUSER / CICS  ·  ADMIN / ADMIN  ·  TEST / TEST</div>
        </div>
      </div>
    );
  },

  MENU: ({ operatorId, onNavigate }) => {
    const [sel, setSel] = React.useState('');
    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;
    const handleKey = (e) => {
      if (e.key === 'Enter') {
        const v = sel.trim().toUpperCase();
        if (v === '1' || v === 'INQY') onNavigate('INQY');
        else if (v === '2' || v === 'TRAN') onNavigate('TRAN');
        else if (v === '3' || v === 'ADMN') onNavigate('ADMN');
        else if (v === '4' || v === 'LOGO') onNavigate('LOGO');
        setSel('');
      }
      if (e.key === 'F3') onNavigate('LOGO');
    };
    return (
      <div onKeyDown={handleKey} style={{ padding: '6px 8px' }}>
        <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '2px', display: 'flex', justifyContent: 'space-between' }}>
          <span>BANKMASTER/VS — BANKING LAB MENU</span><span>DATE: {dateStr}</span>
        </div>
        <div style={{ color: '#33FF33', marginBottom: '8px' }}>{'─'.repeat(60)}</div>
        <div style={{ textAlign: 'center', color: '#AAFFAA', fontWeight: 'bold', marginBottom: '12px', letterSpacing: '2px' }}>OPERATOR: {operatorId}</div>
        <div style={{ marginLeft: '6ch', lineHeight: '2.2', color: '#33FF33' }}>
          <div><span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  1  INQY</span>  —  ACCOUNT INQUIRY</div>
          <div><span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>  2  TRAN</span>  —  TRANSACTION HISTORY</div>
          <div><span style={{ color: '#FF3333', fontWeight: 'bold' }}>  3  ADMN</span>  —  <span style={{ color: '#FF3333' }}>ADMIN PANEL ⚠ NO AUTH CHECK (VULN)</span></div>
          <div style={{ height: '0.4em' }} />
          <div><span style={{ color: '#668866' }}>  4  LOGO</span>  —  LOGOFF</div>
        </div>
        <div style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '8px' }}>
          <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>SELECTION ==&gt;</span>
          <input
            value={sel}
            onChange={e => setSel(e.target.value.toUpperCase().slice(0, 8))}
            maxLength={8}
            autoFocus
            style={{ background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF', color: '#3399FF', fontFamily: "'Courier New', monospace", fontSize: '13px', outline: 'none', width: '8ch' }}
          />
        </div>
      </div>
    );
  },

  INQY: ({ accounts, customers, onNavigate }) => {
    const [accNo, setAccNo] = React.useState('');
    const [result, setResult] = React.useState(null);
    const [msg, setMsg] = React.useState('');
    const lookup = () => {
      const acc = accounts.find(a => a.account_number === accNo.trim());
      if (!acc) { setResult(null); setMsg('NOTFND — ACCOUNT NOT ON FILE'); return; }
      const cust = customers.find(c => c.customer_id === acc.customer_id);
      setResult({ acc, cust });
      setMsg('');
    };
    return (
      <div style={{ padding: '6px 8px' }}>
        <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '6px' }}>ACCOUNT INQUIRY — INQY</div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '10px' }}>
          <span style={{ color: '#AAFFAA' }}>ACCOUNT-NUMBER ==&gt;</span>
          <input value={accNo} onChange={e => setAccNo(e.target.value.replace(/\D/g,'').slice(0,10))}
            onKeyDown={e => e.key === 'Enter' && lookup()}
            maxLength={10} autoFocus
            style={{ background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF', color: '#3399FF', fontFamily: "'Courier New', monospace", fontSize: '13px', outline: 'none', width: '10ch' }}
          />
          <button onClick={lookup} style={{ background: '#001100', border: '1px solid #33FF33', color: '#33FF33', fontFamily: "'Courier New', monospace", fontSize: '11px', padding: '2px 10px', cursor: 'pointer' }}>ENTER</button>
        </div>
        {msg && <div style={{ color: '#FF3333', marginBottom: '8px' }}>==&gt; {msg}</div>}
        {result && (
          <div style={{ border: '1px solid #336633', padding: '8px', background: '#000800' }}>
            {[
              ['ACCOUNT NUMBER', result.acc.account_number],
              ['CUSTOMER ID', result.acc.customer_id],
              ['ACCOUNT TYPE', result.acc.account_type],
              ['CURRENCY', result.acc.currency],
              ['BALANCE', `GBP ${result.acc.balance?.toFixed(2)}`],
              ['STATUS', result.acc.status],
              result.cust && ['CUSTOMER NAME', `${result.cust.forename} ${result.cust.surname}`],
            ].filter(Boolean).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', gap: '8px', marginBottom: '3px', fontSize: '12px' }}>
                <span style={{ color: '#AAFFAA', width: '18ch', fontWeight: 'bold' }}>{k}</span>
                <span style={{ color: '#3399FF' }}>{v}</span>
              </div>
            ))}
          </div>
        )}
        <button onClick={() => onNavigate('MENU')} style={{ marginTop: '12px', background: '#001100', border: '1px solid #668866', color: '#668866', fontFamily: "'Courier New', monospace", fontSize: '11px', padding: '2px 10px', cursor: 'pointer' }}>PF3 BACK</button>
      </div>
    );
  },

  ADMN: ({ onNavigate, customers, accounts }) => (
    <div style={{ padding: '6px 8px' }}>
      <div style={{ color: '#FF3333', fontWeight: 'bold', marginBottom: '4px' }}>⚠ ADMIN PANEL — UNAUTHENTICATED ACCESS (VULN)</div>
      <div style={{ color: '#FF9933', fontSize: '11px', border: '1px solid #553300', padding: '4px 8px', marginBottom: '10px' }}>
        THIS PANEL IS ACCESSIBLE WITHOUT SECONDARY AUTHENTICATION — CVE SIMULATION
      </div>
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>SYSTEM SUMMARY</div>
      <div style={{ color: '#33FF33', fontSize: '12px', lineHeight: '1.8' }}>
        <div>TOTAL CUSTOMERS : <span style={{ color: '#3399FF' }}>{customers.length}</span></div>
        <div>TOTAL ACCOUNTS  : <span style={{ color: '#3399FF' }}>{accounts.length}</span></div>
        <div>CICS REGION     : <span style={{ color: '#3399FF' }}>CICSLAB1</span></div>
        <div>TLS STATUS      : <span style={{ color: '#FF3333' }}>DISABLED (VULN #1)</span></div>
        <div>LOCKOUT POLICY  : <span style={{ color: '#FF3333' }}>NONE (VULN #3)</span></div>
      </div>
      <button onClick={() => onNavigate('MENU')} style={{ marginTop: '12px', background: '#001100', border: '1px solid #668866', color: '#668866', fontFamily: "'Courier New', monospace", fontSize: '11px', padding: '2px 10px', cursor: 'pointer' }}>PF3 BACK</button>
    </div>
  ),

  TRAN: ({ transactions, onNavigate }) => (
    <div style={{ padding: '6px 8px' }}>
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '6px' }}>TRANSACTION HISTORY — LAB SIMULATION</div>
      {transactions.length === 0 && <div style={{ color: '#668866' }}>NO TRANSACTIONS RECORDED IN LAB SESSION</div>}
      {transactions.map((t, i) => (
        <div key={i} style={{ borderBottom: '1px solid #002200', padding: '4px 0', fontSize: '12px', color: '#33FF33', fontFamily: "'Courier New', monospace" }}>
          <span style={{ color: '#668866' }}>{t.time}</span>  <span style={{ color: '#3399FF' }}>{t.acct}</span>  <span style={{ color: t.type === 'CR' ? '#AAFFAA' : '#FF3333' }}>{t.type}</span>  GBP {t.amount.toFixed(2)}  <span style={{ color: '#AAFFAA' }}>{t.desc}</span>
        </div>
      ))}
      <button onClick={() => onNavigate('MENU')} style={{ marginTop: '12px', background: '#001100', border: '1px solid #668866', color: '#668866', fontFamily: "'Courier New', monospace", fontSize: '11px', padding: '2px 10px', cursor: 'pointer' }}>PF3 BACK</button>
    </div>
  ),

  LOGO: ({ operatorId, onLogoff }) => (
    <div style={{ padding: '40px 8px', textAlign: 'center' }}>
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', fontSize: '15px', letterSpacing: '3px', marginBottom: '12px' }}>SIGHBERBANK PLC</div>
      <div style={{ color: '#33FF33', marginBottom: '6px' }}>OPERATOR {operatorId} HAS BEEN SIGNED OFF</div>
      <div style={{ color: '#668866', fontSize: '11px', marginBottom: '20px' }}>ALL LAB SESSION DATA HAS BEEN LOGGED</div>
      <button onClick={onLogoff} style={{ background: '#001100', border: '1px solid #33FF33', color: '#33FF33', fontFamily: "'Courier New', monospace", fontSize: '12px', padding: '4px 18px', cursor: 'pointer' }}>
        RE-LOGON
      </button>
    </div>
  ),
};

export default function BankingScreen({ screen, fields, setFields, onLogin, onNavigate, onLogoff, operatorId, accounts, customers, transactions, msg }) {
  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;
  const ScreenComp = SCREENS[screen];

  return (
    <div style={S.root}>
      {screen !== 'LOGON' && (
        <>
          <div style={S.hdr}>
            <span>BANKMASTER/VS — BANKING LAB</span>
            <span>CICSLAB1</span>
            <span>DATE: {dateStr}</span>
          </div>
          <div style={S.sep}>{'─'.repeat(62)}</div>
        </>
      )}
      <div style={S.body}>
        {ScreenComp ? (
          <ScreenComp
            fields={fields} setFields={setFields}
            onLogin={onLogin} onNavigate={onNavigate} onLogoff={onLogoff}
            operatorId={operatorId} accounts={accounts} customers={customers}
            transactions={transactions} msg={msg}
          />
        ) : (
          <div style={{ color: '#FF3333', padding: '8px' }}>UNKNOWN SCREEN: {screen}</div>
        )}
      </div>
    </div>
  );
}