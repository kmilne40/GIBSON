import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

// VULN: CEMT/CEDA - Master terminal & definition transactions exposed without auth
// Admin Transaction Access — CEMT, CEDA exposed without RACF/security check

const TRANSACTIONS = [
  { code: 'CUST', prog: 'CUSTMNT', status: 'ENABLED', security: 'NONE', desc: 'Customer Maintenance' },
  { code: 'ACCT', prog: 'ACCTMNT', status: 'ENABLED', security: 'NONE', desc: 'Account Maintenance' },
  { code: 'TRAN', prog: 'TRANPST', status: 'ENABLED', security: 'NONE', desc: 'Transaction Posting' },
  { code: 'CEMT', prog: 'DFHEMTP', status: 'ENABLED', security: 'NONE', desc: 'Master Terminal (*** NO AUTH ***)' },
  { code: 'CEDA', prog: 'DFHEDF',  status: 'ENABLED', security: 'NONE', desc: 'Resource Definition (*** NO AUTH ***)' },
  { code: 'CEDF', prog: 'DFHEDF',  status: 'ENABLED', security: 'NONE', desc: 'Execution Diagnostic Facility' },
  { code: 'CECI', prog: 'DFHCEIP', status: 'ENABLED', security: 'NONE', desc: 'Command Interpreter (*** RCE RISK ***)' },
  { code: 'CESN', prog: 'DFHSNP',  status: 'ENABLED', security: 'BYPASS', desc: 'Signon (BYPASS=transactions run w/o it)' },
];

export default function CemtScreen({ operatorId, onBack }) {
  const [tab, setTab] = useState('inquire');
  const [selectedTx, setSelectedTx] = useState(null);
  const [cmdInput, setCmdInput] = useState('');
  const [cmdOutput, setCmdOutput] = useState([]);
  const [programs, setPrograms] = useState([
    { name: 'CUSTMNT', status: 'ENABLED', length: '4096', dataloc: 'ANY' },
    { name: 'ACCTMNT', status: 'ENABLED', length: '5120', dataloc: 'ANY' },
    { name: 'TRANPST', status: 'ENABLED', length: '6144', dataloc: 'ANY' },
    { name: 'DFHDFLT', status: 'ENABLED', length: '2048', dataloc: 'ANY' },
    { name: 'DFHCEIP', status: 'ENABLED', length: '8192', dataloc: 'ANY' },
  ]);

  const execCemt = () => {
    const cmd = cmdInput.trim().toUpperCase();
    const lines = [`==> CEMT ${cmd}`];

    if (cmd.startsWith('INQ TASK')) {
      lines.push('  Tas(0001)  Tra(CUST)  Ope(' + operatorId + ')  Pri(255)  Sta(SU)');
      lines.push('  Tas(0002)  Tra(CEMT)  Ope(' + operatorId + ')  Pri(255)  Sta(RU)');
      lines.push('STATUS: NORMAL');
    } else if (cmd.startsWith('INQ TRAN')) {
      TRANSACTIONS.forEach(t => {
        lines.push(`  Tra(${t.code.padEnd(4)})  Pro(${t.prog.padEnd(8)})  Sta(${t.status.padEnd(8)})  Sec(${t.security})`);
      });
      lines.push('STATUS: NORMAL');
      lines.push('*** VULN: ALL TRANSACTIONS HAVE SECURITY=NONE ***');
    } else if (cmd.startsWith('SET TRAN(') && cmd.includes('DISABLED')) {
      const m = cmd.match(/SET TRAN\((\w+)\)/);
      if (m) lines.push(`Transaction ${m[1]} DISABLED - NO AUTH CHECK PERFORMED`);
      lines.push('STATUS: NORMAL');
    } else if (cmd.startsWith('INQ PROG')) {
      programs.forEach(p => {
        lines.push(`  Pro(${p.name.padEnd(8)})  Len(${p.length.padEnd(6)})  Sta(${p.status})  Dat(${p.dataloc})`);
      });
      lines.push('STATUS: NORMAL');
    } else if (cmd.startsWith('PERFORM SHUTDOWN')) {
      lines.push('*** CRITICAL VULN: CICS REGION SHUTDOWN WITHOUT AUTH ***');
      lines.push('SHUTDOWN IMMEDIATE ACCEPTED - REGION TERMINATING...');
      lines.push('*** IN REAL SYSTEM THIS WOULD KILL ALL SESSIONS ***');
    } else if (cmd === '') {
      lines.push('ENTER CEMT COMMAND (e.g. INQ TASK, INQ TRAN, INQ PROG)');
    } else {
      lines.push(`CEMT ${cmd} - ACCEPTED (NO AUTH CHECK)`);
      lines.push('STATUS: NORMAL');
    }

    setCmdOutput(prev => [...prev, ...lines.map(l => ({ v: l, w: l.includes('VULN') || l.includes('CRITICAL') || l.includes('***') }))]);
    setCmdInput('');
  };

  const th = { color: '#AAFFAA', fontWeight: 'bold', padding: '2px 8px', borderBottom: '1px solid #336633', textAlign: 'left', fontSize: '11px' };
  const td = (warn) => ({ color: warn ? '#FF9933' : '#33FF33', padding: '2px 8px', borderBottom: '1px solid #002200', fontSize: '11px', fontFamily: "'Courier New', monospace", cursor: 'pointer' });

  return (
    <div style={{ flex: 1, fontFamily: "'Courier New', monospace", fontSize: '12px', display: 'flex', flexDirection: 'column', paddingBottom: '60px' }}>
      {/* Header */}
      <div style={{ padding: '2px 8px', borderBottom: '1px solid #336633', color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', background: '#001a00' }}>
        <span>CEMT/CEDA — MASTER TERMINAL & RESOURCE DEFINITION</span>
        <span style={{ color: '#FF9933' }}>⚠ NO AUTH CHECK (VULN #5)</span>
        <span style={{ color: '#33FF33' }}>PF3=MENU</span>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', padding: '4px 8px', borderBottom: '1px solid #336633', background: '#000800' }}>
        {['inquire', 'programs', 'ceda', 'cmd'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: tab === t ? '#003300' : '#001100', border: `1px solid ${tab === t ? '#AAFFAA' : '#336633'}`,
            color: tab === t ? '#AAFFAA' : '#33FF33', fontFamily: 'inherit', fontSize: '11px',
            padding: '2px 10px', cursor: 'pointer',
          }}>{t.toUpperCase()}</button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 8px' }}>
        {/* Warning banner */}
        <div style={{ background: '#1a0000', border: '1px solid #FF3333', padding: '4px 8px', marginBottom: '8px', fontSize: '11px' }}>
          <span style={{ color: '#FF3333', fontWeight: 'bold' }}>⚠ SECURITY VULNERABILITY: </span>
          <span style={{ color: '#FF9933' }}>CEMT and CEDA are accessible without CESN signon or RACF authorisation. Any terminal user can execute master terminal commands, modify transaction definitions, and install new programs.</span>
        </div>

        {tab === 'inquire' && (
          <>
            <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px' }}>TRANSACTION DEFINITIONS — CEMT INQ TRAN ALL</div>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead><tr>
                <th style={th}>TRAN</th><th style={th}>PROGRAM</th><th style={th}>STATUS</th>
                <th style={th}>SECURITY</th><th style={th}>DESCRIPTION</th>
              </tr></thead>
              <tbody>
                {TRANSACTIONS.map(t => (
                  <tr key={t.code} onClick={() => setSelectedTx(t)} style={{ background: selectedTx?.code === t.code ? '#002200' : 'transparent' }}>
                    <td style={td(false)}>{t.code}</td>
                    <td style={td(false)}>{t.prog}</td>
                    <td style={td(false)}>{t.status}</td>
                    <td style={td(t.security !== 'NONE')}>{t.security}</td>
                    <td style={td(t.security === 'NONE' && ['CEMT','CEDA','CECI'].includes(t.code))}>{t.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {selectedTx && (
              <div style={{ marginTop: '8px', background: '#001a00', border: '1px solid #336633', padding: '6px 8px', fontSize: '11px' }}>
                <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px' }}>CEMT INQ TRAN({selectedTx.code}) ALL</div>
                <div style={{ color: '#33FF33' }}>  Transaction   : {selectedTx.code}</div>
                <div style={{ color: '#33FF33' }}>  Program       : {selectedTx.prog}</div>
                <div style={{ color: '#33FF33' }}>  Status        : {selectedTx.status}</div>
                <div style={{ color: selectedTx.security === 'NONE' ? '#FF9933' : '#33FF33' }}>
                  Security      : {selectedTx.security} {selectedTx.security === 'NONE' ? '← NO RACF/ACF2 KEY DEFINED' : ''}
                </div>
                <div style={{ color: '#33FF33' }}>  Priority      : 255 (HIGHEST)</div>
                <div style={{ color: '#33FF33' }}>  Taskdatakey   : USER</div>
                <div style={{ color: '#33FF33' }}>  Isolate       : NO  ← VULN: SHARED MEMORY</div>
              </div>
            )}
          </>
        )}

        {tab === 'programs' && (
          <>
            <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px' }}>PROGRAM LIBRARY — CEMT INQ PROG ALL</div>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead><tr>
                <th style={th}>PROGRAM</th><th style={th}>STATUS</th><th style={th}>LENGTH</th><th style={th}>NEWCOPY?</th><th style={th}>NOTE</th>
              </tr></thead>
              <tbody>
                {programs.map(p => (
                  <tr key={p.name}>
                    <td style={td(false)}>{p.name}</td>
                    <td style={td(false)}>{p.status}</td>
                    <td style={td(false)}>{p.length}</td>
                    <td style={{ ...td(true), cursor: 'pointer' }} onClick={() => {
                      setCmdOutput(prev => [...prev, { v: `CEMT SET PROG(${p.name}) NEWCOPY - RELOAD TRIGGERED (NO AUTH)`, w: true }]);
                      setTab('cmd');
                    }}>NEWCOPY</td>
                    <td style={td(false)}>VULN: HOT-RELOAD WITHOUT CHANGE CONTROL</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === 'ceda' && (
          <div style={{ lineHeight: '1.8' }}>
            <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px' }}>CEDA — RESOURCE DEFINITION ONLINE (NO AUTH)</div>
            <div style={{ color: '#FF9933', marginBottom: '8px' }}>⚠ VULN #5: CEDA accessible without RACF authorisation — attacker can install malicious programs, redefine transactions, modify mapsets and files.</div>
            {[
              { cmd: 'CEDA DEFINE TRANSACTION(HACK) GROUP(EXPLOIT)', out: 'New transaction HACK defined pointing to EXPLOIT program' },
              { cmd: 'CEDA INSTALL TRANSACTION(HACK) GROUP(EXPLOIT)', out: 'Transaction HACK INSTALLED — now executable by anyone' },
              { cmd: 'CEDA DEFINE PROGRAM(EXPLOIT) GROUP(EXPLOIT) LANGUAGE(COBOL)', out: 'Program EXPLOIT defined — NEWCOPY will load from STEPLIB' },
              { cmd: 'CEDA ALTER FILE(CUSTMAST) GROUP(BANK) ENABLED', out: 'File CUSTMAST altered — opened for BROWSE+UPDATE+ADD+DELETE' },
            ].map((item, i) => (
              <div key={i} style={{ marginBottom: '8px', background: '#001100', padding: '4px 8px', border: '1px solid #224422' }}>
                <div style={{ color: '#3399FF' }}>{item.cmd}</div>
                <div style={{ color: '#FF9933' }}>→ {item.out}</div>
              </div>
            ))}
          </div>
        )}

        {tab === 'cmd' && (
          <div>
            <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px' }}>CEMT COMMAND ENTRY — UNAUTHENTICATED</div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
              <span style={{ color: '#AAFFAA' }}>CEMT</span>
              <input value={cmdInput} onChange={e => setCmdInput(e.target.value.toUpperCase())}
                onKeyDown={e => { if (e.key === 'Enter') execCemt(); if (e.key === 'F3') onBack('MENU'); }}
                autoFocus style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF', color: '#3399FF', fontFamily: 'inherit', fontSize: '13px', outline: 'none' }} />
              <button onClick={execCemt} style={{ background: '#001100', border: '1px solid #336633', color: '#33FF33', fontFamily: 'inherit', fontSize: '11px', padding: '2px 8px', cursor: 'pointer' }}>ENTER</button>
            </div>
            <div style={{ background: '#000800', border: '1px solid #224422', padding: '4px 8px', minHeight: '120px', maxHeight: '300px', overflowY: 'auto' }}>
              {cmdOutput.map((l, i) => (
                <div key={i} style={{ color: l.w ? '#FF9933' : '#33FF33', fontFamily: 'inherit', fontSize: '11px', lineHeight: '1.6' }}>{l.v}</div>
              ))}
            </div>
            <div style={{ color: '#668866', fontSize: '11px', marginTop: '4px' }}>
              Try: INQ TASK | INQ TRAN | INQ PROG | SET TRAN(CUST) DISABLED | PERFORM SHUTDOWN IMMEDIATE
            </div>
          </div>
        )}
      </div>

      <div style={{ padding: '2px 8px', borderTop: '1px solid #336633', display: 'flex', gap: '16px' }}>
        <button onClick={() => onBack('MENU')} style={{ background: '#001100', border: '1px solid #336633', color: '#AAFFAA', fontFamily: 'inherit', fontSize: '11px', padding: '2px 8px', cursor: 'pointer' }}>PF3 MENU</button>
      </div>
    </div>
  );
}