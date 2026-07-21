import React, { useState, useEffect, useRef } from 'react';
import { base44 } from '@/api/base44Client';
import BankingScreen from './bankinglab/BankingScreen';
import BankingHackPanel from './bankinglab/BankingHackPanel';
import CICSLabGuide from './bankinglab/CICSLabGuide';
import TN3270PacketViewer from './bankinglab/TN3270PacketViewer';
import FunctionKeys from './bankinglab/FunctionKeys';
import Tn3270ExploitPanel from './bankinglab/Tn3270ExploitPanel';

const DEMO_CUSTOMERS = [
  { customer_id: '10000001', forename: 'WILLIAM', surname: 'HARRISON', sort_code: '20-45-14', status: 'A' },
  { customer_id: '10000002', forename: 'MARGARET', surname: 'THATCHER', sort_code: '30-98-12', status: 'A' },
  { customer_id: '10000003', forename: 'DOROTHY', surname: 'BLACKWELL', sort_code: '20-45-14', status: 'A' },
];
const DEMO_ACCOUNTS = [
  { account_number: '1000000001', customer_id: '10000001', account_type: 'CUR', currency: 'GBP', balance: 24521.00, status: 'A' },
  { account_number: '1000000002', customer_id: '10000002', account_type: 'SAV', currency: 'GBP', balance: 98250.50, status: 'A' },
  { account_number: '1000000003', customer_id: '10000003', account_type: 'CUR', currency: 'GBP', balance: 1842.75, status: 'A' },
];

const TABS = [
  { id: 'guide', label: 'LAB GUIDE' },
  { id: 'hack',  label: 'HACK PANEL ⚠' },
  { id: 'tn32',  label: 'TN3270 PACKETS' },
  { id: 'xpl',   label: 'TN3270 EXPLOIT 🔴' },
];

export default function BankingLab({ operatorId, onBack, weaknesses = {}, onToggleWeakness }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [bankScreen, setBankScreen] = useState('LOGON');
  const [bankUser, setBankUser] = useState('');
  const [logonFields, setLogonFields] = useState({ userid: '', password: '' });
  const [logonMsg, setLogonMsg] = useState(null);
  const [hackMode, setHackMode] = useState(false);
  const [hackLog, setHackLog] = useState([]);
  const [activeTab, setActiveTab] = useState('guide');
  const [transactions, setTransactions] = useState([]);
  const screenBuffer = useRef([]);

  const handleBufferUpdate = (entry) => {
    screenBuffer.current = [...screenBuffer.current.slice(-9), entry];
  };

  useEffect(() => {
    base44.auth.me().then(u => setCurrentUser(u)).catch(() => {});
  }, []);

  const addHackLog = (entry) => setHackLog(prev => [...prev, entry]);

  const handleBankingLogin = () => {
    const { userid, password } = logonFields;
    const VALID = { IBMUSER: 'SYS1', CICSUSER: 'CICS', ADMIN: 'ADMIN', TEST: 'TEST' };
    if (!userid) { setLogonMsg({ type: 'error', text: 'INVREQ — USERID IS REQUIRED' }); return; }
    if (VALID[userid] && VALID[userid] === password) {
      setBankUser(userid);
      setBankScreen('MENU');
      setLogonMsg(null);
      if (hackMode) addHackLog({ type: 'success', text: `LOGON CAPTURED: ${userid}/${password} — PLAINTEXT EBCDIC (VULN #1)` });
    } else if (VALID[userid] && VALID[userid] !== password) {
      setLogonMsg({ type: 'error', text: 'DFHCE3520 — PASSWORD INCORRECT — NO LOCKOUT (VULN #3)' });
      if (hackMode) addHackLog({ type: 'warn', text: `FAILED ATTEMPT: ${userid}/${password} — NO LOCKOUT TRIGGERED` });
    } else {
      setLogonMsg({ type: 'error', text: 'DFHCE3520 — USERID NOT FOUND' });
    }
  };

  const handleBankNavigate = (dest) => {
    if (dest === 'LOGO') { setBankScreen('LOGO'); return; }
    setBankScreen(dest);
  };

  const handleLogoff = () => {
    setBankScreen('LOGON');
    setBankUser('');
    setLogonFields({ userid: '', password: '' });
    setLogonMsg(null);
  };

  const pfKeys = [
    { pf: 'PF3', label: 'MAIN MENU' },
    { pf: 'PF12', label: 'LAB EXIT' },
  ];

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column', height: '100%',
      fontFamily: "'Courier New', monospace", color: '#33FF33',
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '4px 8px', background: '#000800', borderBottom: '1px solid #002200',
        flexWrap: 'wrap', gap: '6px',
      }}>
        <span style={{ color: '#AAFFAA', fontWeight: 'bold', fontSize: '12px' }}>
          BANKING LAB — CICSLAB1
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Hack mode toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '11px' }}>
            <span style={{ color: hackMode ? '#FF3333' : '#668866', fontWeight: hackMode ? 'bold' : 'normal' }}>
              {hackMode ? '⚠ HACK3270 ON' : 'HACK3270 OFF'}
            </span>
            <div
              onClick={() => setHackMode(h => !h)}
              style={{
                width: '36px', height: '16px', borderRadius: '8px',
                background: hackMode ? '#4a0000' : '#001100',
                border: `1px solid ${hackMode ? '#FF3333' : '#336633'}`,
                position: 'relative', cursor: 'pointer',
              }}>
              <div style={{
                position: 'absolute', top: '2px',
                left: hackMode ? '20px' : '2px',
                width: '10px', height: '10px', borderRadius: '50%',
                background: hackMode ? '#FF3333' : '#336633',
                transition: 'left 0.15s',
              }} />
            </div>
          </label>
          <button
            onClick={() => onBack('MENU')}
            style={{ background: '#001100', border: '1px solid #668866', color: '#668866', fontFamily: "'Courier New', monospace", fontSize: '11px', padding: '2px 10px', cursor: 'pointer' }}
          >
            PF12 EXIT LAB
          </button>
        </div>
      </div>

      {/* Main layout: terminal left, panel right */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Banking terminal */}
        <div style={{ flex: '0 0 42%', borderRight: '1px solid #002200', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <BankingScreen
              screen={bankScreen}
              fields={logonFields}
              setFields={setLogonFields}
              onLogin={handleBankingLogin}
              onNavigate={handleBankNavigate}
              onLogoff={handleLogoff}
              operatorId={bankUser}
              accounts={DEMO_ACCOUNTS}
              customers={DEMO_CUSTOMERS}
              transactions={transactions}
              msg={logonMsg}
            />
          </div>
          <FunctionKeys keys={pfKeys} onKey={(pf) => { if (pf === 'PF12') onBack('MENU'); }} />
        </div>

        {/* Right panel with tabs */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Tab bar */}
        <div style={{ display: 'flex', gap: '2px', padding: '4px 6px', borderBottom: '1px solid #002200', background: '#000800' }}>
          {TABS.filter(t => (t.id !== 'hack' && t.id !== 'xpl') || hackMode).map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                style={{
                  background: activeTab === t.id ? '#002200' : '#000800',
                  border: `1px solid ${activeTab === t.id ? '#AAFFAA' : '#336633'}`,
                  color: activeTab === t.id ? '#FFFF99' : t.id === 'hack' ? '#FF9933' : '#668866',
                  fontFamily: "'Courier New', monospace", fontSize: '11px',
                  padding: '2px 10px', cursor: 'pointer', fontWeight: activeTab === t.id ? 'bold' : 'normal',
                }}>{t.label}</button>
            ))}
            {!hackMode && (
              <span style={{ color: '#224422', fontSize: '10px', alignSelf: 'center', marginLeft: '6px' }}>
                ENABLE HACK3270 TO UNLOCK HACK PANEL
              </span>
            )}
          </div>

          {/* Tab content */}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            {activeTab === 'guide' && <CICSLabGuide />}
            {activeTab === 'hack' && hackMode && (
              <BankingHackPanel
                hackLog={hackLog}
                onAddLog={addHackLog}
                weaknesses={weaknesses}
                onToggleWeakness={onToggleWeakness}
                screenBuffer={screenBuffer.current}
              />
            )}
            {activeTab === 'tn32' && <TN3270PacketViewer />}
            {activeTab === 'xpl' && hackMode && (
              <Tn3270ExploitPanel operatorId={operatorId} onBufferUpdate={handleBufferUpdate} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}