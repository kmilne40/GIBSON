import React, { useState, useEffect, useRef } from 'react';
import TerminalShell from '@/components/terminal/TerminalShell';
import StatusBar from '@/components/terminal/StatusBar';
import PFKeyBar from '@/components/terminal/PFKeyBar';
import CobolOverlay from '@/components/terminal/CobolOverlay';
import HelpOverlay from '@/components/terminal/HelpOverlay';
import LoginScreen from '@/components/screens/LoginScreen';
import MainMenu from '@/components/screens/MainMenu';
import CustomerScreen from '@/components/screens/CustomerScreen';
import AccountScreen from '@/components/screens/AccountScreen';
import TransactionScreen from '@/components/screens/TransactionScreen';
import AdminPanel from '@/components/screens/AdminPanel';
import CeciScreen from '@/components/screens/CeciScreen';
import CemtScreen from '@/components/screens/CemtScreen';
import RestApiTester from '@/components/screens/RestApiTester';
import Tn3270View from '@/components/screens/Tn3270View';
import BulkProcessingScreen from '@/components/screens/BulkProcessingScreen';
import CicsMenu from './CicsMenu';
import CedaViewer from './CedaViewer';
import CedfDebugger from './CedfDebugger';
import BmsMapViewer from './BmsMapViewer';
import SecurityWeaknessSettings from './SecurityWeaknessSettings';
import CicsSystemLog from '@/components/CicsSystemLog';
import CicsLogonScreen from '@/components/screens/CicsLogonScreen';
import BankingLab from '@/components/BankingLab';
import DvcaTerminal from './DvcaTerminal';

const DEFAULT_WEAKNESSES = {
  tls_disabled: true, default_creds: true, no_lockout: true,
  ceci_noauth: true, cemt_noauth: true, field_protection: true,
  sql_injection: false, commarea_overflow: false,
  tn3270_expose_hidden: false,
  tn3270_overtype_protected: false,
  pin_bruteforce_enabled: false,
};

export default function Terminal() {
  const [screen, setScreen] = useState('LOGIN'); // LOGIN | MENU | CUST | ACCT | TRAN | LOGO | CECI | CEMT | REST | TN32 | BULK | CICS | CEDA | CEDF | BMSV | SWKN | SLOG
  const [operatorId, setOperatorId] = useState('');
  const [weaknesses, setWeaknesses] = useState(DEFAULT_WEAKNESSES);
  const [statusMsg, setStatusMsg] = useState('BANKMASTER/VS  IBM CICS/VS 2.1.1  SYSTEM READY');
  const [statusType, setStatusType] = useState('normal');
  const [showCobol, setShowCobol] = useState(false);
  const [cobolTrans, setCobolTrans] = useState('CUST');
  const [showHelp, setShowHelp] = useState(false);
  const [helpScreen, setHelpScreen] = useState('MENU');
  const shellRef = useRef(null);

  useEffect(() => {
    if (shellRef.current) shellRef.current.focus();
  }, [screen]);

  const handleLogin = (id, password, role) => {
    setOperatorId(id);
    setScreen('MENU');
    // VULN #2: Detect default/weak credentials and warn (but still allow in)
    const weakCreds = ['DVCA','CICS','TEST','BATCH'];
    if (weakCreds.includes(id.toUpperCase()) || password === id || !password) {
      setStatusMsg(`SIGNON OK - ${id}  *** WEAK/DEFAULT CREDENTIALS DETECTED ***`);
      setStatusType('error');
    } else {
      setStatusMsg(`SIGNON SUCCESSFUL - WELCOME ${id}`);
      setStatusType('success');
    }
  };

  const handleNavigate = (dest) => {
    if (dest === 'MENU') {
      setScreen('MENU');
      setStatusMsg('MAIN MENU - SELECT TRANSACTION OR TYPE CODE');
      setStatusType('normal');
    } else if (dest === 'CUST') {
      setScreen('CUST');
      setStatusMsg('CUSTMNT - CUSTOMER MASTER MAINTENANCE');
      setStatusType('normal');
    } else if (dest === 'ACCT') {
      setScreen('ACCT');
      setStatusMsg('ACCTMNT - ACCOUNT MAINTENANCE');
      setStatusType('normal');
    } else if (dest === 'TRAN') {
      setScreen('TRAN');
      setStatusMsg('TRANPST - TRANSACTION POSTING');
      setStatusType('normal');
    } else if (dest === 'ADMN') {
      setScreen('ADMN');
    } else if (dest === 'CECI') {
      setScreen('CECI');
      setStatusMsg('CECI - COMMAND INTERPRETER - NO AUTH CHECK (VULN #6/RCE)');
      setStatusType('error');
    } else if (dest === 'CEMT') {
      setScreen('CEMT');
      setStatusMsg('CEMT/CEDA - MASTER TERMINAL - UNAUTHENTICATED ACCESS (VULN #5)');
      setStatusType('error');
    } else if (dest === 'REST') {
      setScreen('REST');
      setStatusMsg('REST API SECURITY TESTER - BANKMASTER/VS API GATEWAY');
      setStatusType('normal');
    } else if (dest === 'TN32') {
      setScreen('TN32');
      setStatusMsg('TN3270 PACKET ANALYSER - PLAINTEXT STREAM PORT 23 (VULN #1)');
      setStatusType('error');
    } else if (dest === 'BULK') {
      setScreen('BULK');
      setStatusMsg('BLKPRC - BULK PROCESSING CENTRE - MORTGAGE / PAYMENTS / CARD APPROVALS');
      setStatusType('normal');
    } else if (dest === 'CICS_LOGON') {
      setScreen('CICS_LOGON');
      setStatusMsg('DFHCE3520 - CICS APPLID LOGON - ENTER CREDENTIALS');
      setStatusType('normal');
    } else if (dest === 'CICS') {
      setScreen('CICS');
      setStatusMsg('CICS TRANSACTION SERVICES — CONTROL MENU — CICSREG1');
      setStatusType('normal');
    } else if (dest === 'CEDA') {
      setScreen('CEDA');
      setStatusMsg('CEDA — RESOURCE DEFINITION ONLINE — CICSREG1');
      setStatusType('normal');
    } else if (dest === 'CEDF') {
      setScreen('CEDF');
      setStatusMsg('CEDF — EXECUTION DIAGNOSTIC FACILITY — STEP-THROUGH DEBUGGER');
      setStatusType('normal');
    } else if (dest === 'BMSV') {
      setScreen('BMSV');
      setStatusMsg('BMSVIEW — BMS MAP STRUCTURE ANALYSER');
      setStatusType('normal');
    } else if (dest === 'SWKN') {
      setScreen('SWKN');
      setStatusMsg('SWKN — SECURITY WEAKNESS INJECTOR — LIVE VULNERABILITY CONTROL');
      setStatusType('error');
    } else if (dest === 'SLOG') {
      setScreen('SLOG');
      setStatusMsg('CICS SYSTEM LOG — DFH/ICH/IEA MESSAGE JOURNAL');
      setStatusType('normal');
    } else if (dest === 'BLAB') {
      setScreen('BLAB');
      setStatusMsg('BANKING LAB — CICSLAB1 — INTERACTIVE VULNERABILITY SIMULATION');
      setStatusType('normal');
    } else if (dest === 'DVCA') {
      setScreen('DVCA');
      setStatusMsg('DVCA — DAMN VULNERABLE CICS APPLICATION — PIBS GIBSON BANKING');
      setStatusType('error');
    } else if (dest === 'LOGO') {
      setScreen('LOGO');
    } else if (dest === 'CODE_CUST') {
      setCobolTrans('CUST'); setShowCobol(true);
    } else if (dest === 'CODE_ACCT') {
      setCobolTrans('ACCT'); setShowCobol(true);
    } else if (dest === 'CODE_TRAN') {
      setCobolTrans('TRAN'); setShowCobol(true);
    } else if (dest === 'HELP_CUST') {
      setHelpScreen('CUST'); setShowHelp(true);
    } else if (dest === 'HELP_ACCT') {
      setHelpScreen('ACCT'); setShowHelp(true);
    } else if (dest === 'HELP_TRAN') {
      setHelpScreen('TRAN'); setShowHelp(true);
    } else if (dest === 'HELP') {
      setHelpScreen('MENU'); setShowHelp(true);
    }
  };

  const handleGlobalKey = (e) => {
    if (showCobol || showHelp) {
      if (e.key === 'F3' || e.key === 'F1') {
        setShowCobol(false);
        setShowHelp(false);
      }
      return;
    }
    if (e.key === 'F12') {
      const transMap = { CUST: 'CUST', ACCT: 'ACCT', TRAN: 'TRAN', MENU: 'CUST', CECI: 'TRAN', CEMT: 'CUST', REST: 'ACCT', TN32: 'TRAN' };
      setCobolTrans(transMap[screen] || 'CUST');
      setShowCobol(true);
    }
    if (e.key === 'F1') {
      const helpMap = { CUST: 'CUST', ACCT: 'ACCT', TRAN: 'TRAN', MENU: 'MENU' };
      setHelpScreen(helpMap[screen] || 'MENU');
      setShowHelp(true);
    }
  };

  // PF keys per screen
  const pfKeys = {
    LOGIN: [{ pf: 'ENTER', label: 'SIGNON' }],
    MENU: [{ pf: 'PF1', label: 'HELP' }, { pf: 'PF3', label: 'SIGNOFF' }, { pf: 'PF12', label: 'CODE' }],
    CUST: [{ pf: 'PF1', label: 'HELP' }, { pf: 'PF3', label: 'MENU' }, { pf: 'PF5', label: 'ADD' }, { pf: 'PF6', label: 'UPD' }, { pf: 'PF7', label: 'DEL' }, { pf: 'PF8', label: 'INQ' }, { pf: 'PF12', label: 'CODE' }],
    ACCT: [{ pf: 'PF1', label: 'HELP' }, { pf: 'PF3', label: 'MENU' }, { pf: 'PF5', label: 'OPEN' }, { pf: 'PF6', label: 'MOD' }, { pf: 'PF8', label: 'INQ' }, { pf: 'PF9', label: 'NEXT' }, { pf: 'PF12', label: 'CODE' }],
    TRAN: [{ pf: 'PF1', label: 'HELP' }, { pf: 'PF3', label: 'MENU' }, { pf: 'PF5', label: 'POST' }, { pf: 'PF8', label: 'HIST' }, { pf: 'PF12', label: 'CODE' }],
    CECI: [{ pf: 'PF3', label: 'END' }, { pf: 'PF12', label: 'CANCEL' }],
    CEMT: [{ pf: 'PF3', label: 'MENU' }],
    REST: [{ pf: 'PF3', label: 'MENU' }],
    TN32: [{ pf: 'PF3', label: 'MENU' }],
    BULK: [{ pf: 'PF3', label: 'MENU' }, { pf: 'PF5', label: 'SUBMIT' }, { pf: 'PF6', label: 'REFER' }, { pf: 'PF7', label: 'DECLINE' }],
    CICS: [{ pf: 'PF3', label: 'MENU' }],
    CEDA: [{ pf: 'PF3', label: 'CICS' }, { pf: 'PF12', label: 'MENU' }],
    CEDF: [{ pf: 'PF3', label: 'CICS' }, { pf: 'PF1', label: 'STEP' }, { pf: 'PF2', label: 'RUN' }],
    BMSV: [{ pf: 'PF3', label: 'CICS' }, { pf: 'PF12', label: 'MENU' }],
    SWKN: [{ pf: 'PF3', label: 'CICS' }, { pf: 'PF12', label: 'MENU' }],
    SLOG: [{ pf: 'PF3', label: 'CICS' }],
    BLAB: [{ pf: 'PF12', label: 'EXIT LAB' }],
    DVCA: [{ pf: 'PF3', label: 'MENU' }, { pf: 'PF12', label: 'SIGNOFF' }],
    ADMN: [],
  };

  if (screen === 'LOGO') {
    return (
      <div style={{ background: '#000', color: '#33FF33', fontFamily: "'Courier New', monospace", height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>
        <div style={{ color: '#AAFFAA', fontWeight: 'bold', fontSize: '16px', letterSpacing: '4px', marginBottom: '16px' }}>SIGHBERBANK PLC</div>
        <div style={{ marginBottom: '8px' }}>OPERATOR {operatorId} HAS BEEN SIGNED OFF</div>
        <div style={{ marginBottom: '8px', color: '#33FF33' }}>THIS TERMINAL IS NOW AVAILABLE</div>
        <div style={{ color: '#668866', fontSize: '12px', marginBottom: '24px' }}>ALL TRANSACTIONS HAVE BEEN LOGGED</div>
        <button
          onClick={() => { setOperatorId(''); setScreen('LOGIN'); setStatusMsg('BANKMASTER/VS  SYSTEM READY'); }}
          style={{ background: '#001100', border: '1px solid #33FF33', color: '#33FF33', fontFamily: 'inherit', fontSize: '13px', padding: '6px 20px', cursor: 'pointer' }}
        >
          SIGN ON NEW OPERATOR
        </button>
      </div>
    );
  }

  if (screen === 'ADMN') {
    return <AdminPanel operatorId={operatorId} onBack={() => setScreen('MENU')} />;
  }

  return (
    <TerminalShell onKeyDown={handleGlobalKey}>
      <div ref={shellRef} style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', position: 'relative' }}>
        {/* Main content area */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', marginBottom: screen === 'DVCA' ? '28px' : '52px' }}>
          {screen === 'LOGIN' && <LoginScreen onLogin={handleLogin} weaknesses={weaknesses} />}
          {screen === 'MENU' && <MainMenu operatorId={operatorId} onNavigate={handleNavigate} />}
          {screen === 'CUST' && <CustomerScreen operatorId={operatorId} onBack={handleNavigate} weaknesses={weaknesses} />}
          {screen === 'ACCT' && <AccountScreen operatorId={operatorId} onBack={handleNavigate} weaknesses={weaknesses} />}
          {screen === 'TRAN' && <TransactionScreen operatorId={operatorId} onBack={handleNavigate} weaknesses={weaknesses} />}
          {screen === 'CECI' && <CeciScreen operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'CEMT' && <CemtScreen operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'REST' && <RestApiTester operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'TN32' && <Tn3270View operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'BULK' && <BulkProcessingScreen operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'CICS_LOGON' && <CicsLogonScreen operatorId={operatorId} onLoginSuccess={() => handleNavigate('CICS')} onBack={() => handleNavigate('MENU')} />}
          {screen === 'CICS' && <CicsMenu operatorId={operatorId} onNavigate={handleNavigate} />}
          {screen === 'CEDA' && <CedaViewer operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'CEDF' && <CedfDebugger operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'BMSV' && <BmsMapViewer operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'SWKN' && <SecurityWeaknessSettings operatorId={operatorId} onBack={handleNavigate} weaknesses={weaknesses} setWeaknesses={setWeaknesses} />}
          {screen === 'SLOG' && <CicsSystemLog operatorId={operatorId} onBack={handleNavigate} />}
          {screen === 'BLAB' && <BankingLab operatorId={operatorId} onBack={handleNavigate} weaknesses={weaknesses} onToggleWeakness={(name) => setWeaknesses(w => ({ ...w, [name]: !w[name] }))} />}
          {screen === 'DVCA' && <DvcaTerminal operatorId={operatorId} onBack={handleNavigate} />}
        </div>

        {/* Overlays */}
        {showCobol && <CobolOverlay transactionCode={cobolTrans} onClose={() => setShowCobol(false)} />}
        {showHelp && <HelpOverlay screen={helpScreen} onClose={() => setShowHelp(false)} />}

        {/* Status bar and PF key bar */}
        {screen !== 'LOGIN' && screen !== 'ADMN' && (
          <StatusBar
            transactionId={screen}
            operatorId={operatorId}
            message={statusMsg}
            messageType={statusType}
          />
        )}
        <PFKeyBar keys={pfKeys[screen] || pfKeys.MENU} />

        {/* Admin shortcut (hidden) */}
        {screen === 'MENU' && (
          <div style={{ position: 'absolute', bottom: '28px', right: '8px', fontSize: '10px', display: 'flex', gap: '10px' }}>
            <a href="/scenarios" style={{ color: '#336633', textDecoration: 'none' }}>[LAB]</a>
            <span style={{ color: '#224422', cursor: 'pointer' }} onClick={() => setScreen('ADMN')}>[ADMN]</span>
          </div>
        )}
      </div>
    </TerminalShell>
  );
}