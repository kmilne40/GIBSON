import React, { useState, useCallback } from 'react';
import Hack3270Toolbar from '@/components/dvca/Hack3270Toolbar';
import DvcaMcgm from '@/components/dvca/DvcaMcgm';
import DvcaMcmm from '@/components/dvca/DvcaMcmm';
import DvcaMcor from '@/components/dvca/DvcaMcor';
import DvcaMcad from '@/components/dvca/DvcaMcad';
import DvcaMchi from '@/components/dvca/DvcaMchi';
import DvcaScrt from '@/components/dvca/DvcaScrt';

// DVCA = Damn Vulnerable CICS Application — "Mel's Cargo" storefront
// Transactions:
//   MCGM  = splash/landing (MCSTART program)
//   MCMM  = main menu (MCMMENU program) — options 1,2,3 + hidden 99
//   MCOR  = office supplies price list (MCORDERS) — FSET vuln + hidden purchasable field
//   MCAD  = shipping address (MCADDRSS)  — PIN brute force vuln (1337, no lockout)
//   MCHI  = order history (MCHISTRY)     — option 99 deletes all records
//   SCRT  = secret screen (SECRET)       — only via PA3 AID injection

const DEFAULT_HACK = {
  master: false,
  disable_field_protection: false,
  enable_hidden_fields: false,
  remove_numeric_only: false,
  start_field: false,
  start_field_extended: false,
  modify_field: false,
  inject_cust_id: false,
  inject_acct_no: false,
  inject_pin: false,
  inject_enter: false,
  inject_pf3: false,
  inject_clear: false,
  batch_pin_enabled: false,
};

const DEFAULT_STATS = {
  screens: 0,
  hidden_exposed: 0,
  protected_overtyped: 0,
  pins_attempted: 0,
  pins_found: 0,
  api_intercepted: 0,
  fields_injected: 0,
};

export default function DvcaTerminal({ operatorId, onBack }) {
  const [dvcaScreen, setDvcaScreen] = useState('MCGM');
  const [hackFields, setHackFields] = useState(DEFAULT_HACK);
  const [activeTab, setActiveTab] = useState('Hack Field Attributes');
  const [injectLog, setInjectLog] = useState([]);
  const [apiLeakLog, setApiLeakLog] = useState([]);
  const [stats, setStats] = useState(DEFAULT_STATS);

  const addLog = useCallback((entry) => {
    setInjectLog(prev => [...prev.slice(-99), { ...entry, text: `[${new Date().toLocaleTimeString()}] ${entry.text}` }]);
  }, []);

  const addApiLeak = useCallback((text) => {
    setApiLeakLog(prev => [...prev.slice(-49), `[${new Date().toLocaleTimeString()}] ${text}`]);
    setStats(s => ({ ...s, api_intercepted: s.api_intercepted + 1 }));
  }, []);

  const updateStat = useCallback((key, delta) => {
    setStats(s => ({ ...s, [key]: (s[key] || 0) + delta }));
  }, []);

  const handleNavigate = (dest) => {
    if (dest === 'MENU' || dest === 'CESF') {
      onBack('MENU');
      return;
    }
    setDvcaScreen(dest);
    setStats(s => ({ ...s, screens: s.screens + 1 }));
    addLog({ type: 'info', text: `XCTL: ${dvcaScreen} → ${dest}` });
  };

  const sharedProps = {
    operatorId,
    onNavigate: handleNavigate,
    hackFields,
    onApiLeak: addApiLeak,
    onLog: addLog,
    onStatUpdate: updateStat,
  };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: '#000', fontFamily: "'Courier New', monospace",
      overflow: 'hidden',
    }}>
      {/* hack3270 toolbar (top) */}
      <div style={{ flexShrink: 0 }}>
        <Hack3270Toolbar
          hackFields={hackFields}
          onHackFieldsChange={setHackFields}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          injectLog={injectLog}
          apiLeakLog={apiLeakLog}
          stats={stats}
        />
      </div>

      {/* x3270 window chrome — Mel's Cargo */}
      <div style={{
        flexShrink: 0,
        background: '#c0c0c0',
        borderTop: '1px solid #808080',
        borderBottom: '2px solid #404040',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '1px 6px',
        fontSize: '11px',
        fontFamily: 'Tahoma, Arial, sans-serif',
        color: '#000',
      }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <span style={{ cursor: 'pointer', padding: '1px 6px', border: '1px solid #808080', background: '#d4d0c8' }}>File</span>
          <span style={{ cursor: 'pointer', padding: '1px 6px', border: '1px solid #808080', background: '#d4d0c8' }}>Options</span>
        </div>
        <span style={{ fontWeight: 'bold', fontSize: '12px' }}>
          x3270-gibson 127.0.0.1:9999 — {dvcaScreen}
          {hackFields?.master && ' [HACK3270 ACTIVE]'}
        </span>
        <button
          onClick={() => onBack('MENU')}
          style={{ background: '#d4d0c8', border: '1px solid #808080', cursor: 'pointer', fontSize: '10px', padding: '1px 8px', fontFamily: 'Tahoma, Arial, sans-serif' }}
        >
          ✕
        </button>
      </div>

      {/* Terminal area */}
      <div style={{
        flex: 1, background: '#000000', overflow: 'hidden', display: 'flex', flexDirection: 'column',
        minHeight: 0,
      }}>
        {dvcaScreen === 'MCGM' && <DvcaMcgm {...sharedProps} />}
        {dvcaScreen === 'MCMM' && <DvcaMcmm {...sharedProps} />}
        {dvcaScreen === 'MCOR' && <DvcaMcor {...sharedProps} />}
        {dvcaScreen === 'MCAD' && <DvcaMcad {...sharedProps} />}
        {dvcaScreen === 'MCHI' && <DvcaMchi {...sharedProps} />}
        {dvcaScreen === 'SCRT' && <DvcaScrt {...sharedProps} />}
      </div>
    </div>
  );
}