import React, { useState } from 'react';

const S = {
  screen: { flex:1, overflow:'auto', padding:'8px', fontFamily:"'Courier New', monospace", fontSize:'12px', color:'#33FF33', background:'#000' },
  panel: { background:'#000800', border:'1px solid #224422', padding:'8px', marginBottom:'8px' },
  warnPanel: { background:'#1a0800', border:'1px solid #553300', padding:'8px', marginBottom:'8px' },
  btn: (a,c='#33FF33') => ({ background:a?'#001a00':'transparent', border:`1px solid ${a?c:'#224422'}`, color:a?c:'#336633', fontFamily:"'Courier New',monospace", fontSize:'11px', padding:'3px 10px', cursor:'pointer', marginRight:'4px' }),
  toggle: (on) => ({
    display:'inline-block', width:'42px', height:'16px', border:`1px solid ${on?'#FF3333':'#336633'}`,
    background: on?'#3a0000':'#001a00', borderRadius:'2px', cursor:'pointer', position:'relative',
    fontFamily:"'Courier New',monospace", fontSize:'10px', textAlign:'center', lineHeight:'14px',
    color: on?'#FF3333':'#33FF33', fontWeight:'bold',
  }),
};

const WEAKNESSES = [
  {
    id:'tls_disabled', category:'TRANSPORT', severity:'CRITICAL',
    label:'TLS/SSL DISABLED ON TN3270 PORT 23',
    desc:'All terminal traffic transmitted as EBCDIC plaintext. Credentials, PII, financial data visible to any network observer.',
    vuln:'VULN #1 — CWE-319 Cleartext Transmission',
    impact:'Wireshark tcp.port==23 captures all keystrokes, screens, and data in real-time.',
    cics_param:'TCPIP SERVICE definition: SSL(NO) PROTOCOL(TN3270E)',
    default: true,
  },
  {
    id:'default_creds', category:'AUTHENTICATION', severity:'HIGH',
    label:'DEFAULT VENDOR CREDENTIALS ACTIVE (DVCA/DVCA, CICS/CICS)',
    desc:'Default userids and passwords shipped with CICS have not been removed or changed.',
    vuln:'VULN #2 — CWE-1392 Default Credentials',
    impact:'Immediate admin access to any attacker with knowledge of IBM CICS defaults.',
    cics_param:'RACF: No REVOKE/ALTUSER performed post-installation',
    default: true,
  },
  {
    id:'no_lockout', category:'AUTHENTICATION', severity:'HIGH',
    label:'NO ACCOUNT LOCKOUT AFTER FAILED ATTEMPTS',
    desc:'CICS/RACF not configured with SETROPTS PASSWORD(REVOKE(n)). Unlimited brute-force attempts.',
    vuln:'VULN #2 — CWE-307 Improper Restriction of Excessive Authentication Attempts',
    impact:'hack3270 credential spray attack completes unchecked.',
    cics_param:'RACF SETROPTS PASSWORD(REVOKE(3)) not set',
    default: true,
  },
  {
    id:'ceci_noauth', category:'AUTHORISATION', severity:'CRITICAL',
    label:'CECI — NO AUTHENTICATION REQUIRED',
    desc:'CICS command interpreter accessible without CESN signon. Allows arbitrary EXEC CICS execution.',
    vuln:'VULN #6 — CWE-862 Missing Authorization',
    impact:'Remote code execution via EXEC CICS LINK/XCTL to arbitrary programs.',
    cics_param:'RDO: TRANSACTION(CECI) SECURITY(NO)',
    default: true,
  },
  {
    id:'cemt_noauth', category:'AUTHORISATION', severity:'CRITICAL',
    label:'CEMT/CEDA — NO AUTHENTICATION REQUIRED',
    desc:'Master Terminal and Resource Definition accessible without signon. Full region control.',
    vuln:'VULN #5 — CWE-862 Missing Authorization',
    impact:'Attacker can disable transactions, close files, shutdown region, install rogue programs.',
    cics_param:'RDO: TRANSACTION(CEMT) SECURITY(NO)',
    default: true,
  },
  {
    id:'field_protection', category:'DATA INTEGRITY', severity:'HIGH',
    label:'FIELD PROTECTION BYPASS (3270 ATTRIBUTE MANIPULATION)',
    desc:'No server-side validation of modified protected field data. BMS trusts client-supplied attributes.',
    vuln:'VULN #3 — CWE-284 Improper Access Control',
    impact:'hack3270 --modify-fields flips PROT bit. Hidden/read-only fields become editable.',
    cics_param:'BMS: No server-side re-validation of protected field MDT bits',
    default: true,
  },
  {
    id:'sql_injection', category:'DATA ACCESS', severity:'HIGH',
    label:'SQL INJECTION IN CUSTOMER/ACCOUNT INQUIRY',
    desc:'COBOL program builds DB2 SQL via string concatenation. No bind parameters.',
    vuln:'VULN #4 — CWE-89 SQL Injection',
    impact:"UNION SELECT to dump all customer NI numbers, DOBs, account balances.",
    cics_param:"EXEC CICS LINK PROGRAM('DB2GATE') — no parameterised queries",
    default: false,
  },
  {
    id:'commarea_overflow', category:'MEMORY', severity:'MED',
    label:'COMMAREA BUFFER OVERFLOW (PSEUDO-CONVERSATIONAL STATE)',
    desc:'CICS does not enforce COMMAREA length check. EIBCALEN not validated before MOVE.',
    vuln:'VULN #8 — CWE-120 Buffer Overflow',
    impact:'Overwrite adjacent SECURITY-CONTROL-FLAGS. AUTHENTICATED-FLAG set to Y without signon.',
    cics_param:'COBOL: No IF EIBCALEN = 256 check before MOVE COMMAREA',
    default: false,
  },
];

export default function SecurityWeaknessSettings({ operatorId, onBack, weaknesses, setWeaknesses }) {
  const [log, setLog] = useState([]);

  const toggle = (id) => {
    const now = new Date().toTimeString().slice(0,8);
    const current = weaknesses[id];
    const newVal = !current;
    setWeaknesses(prev => ({ ...prev, [id]: newVal }));
    const w = WEAKNESSES.find(w=>w.id===id);
    setLog(l => [...l, {
      time: now,
      action: newVal ? 'ENABLED' : 'DISABLED',
      label: w.label,
      color: newVal ? '#FF3333' : '#33FF33',
    }]);
  };

  const enableAll = () => {
    const all = {};
    WEAKNESSES.forEach(w => { all[w.id] = true; });
    setWeaknesses(all);
    setLog(l => [...l, { time:new Date().toTimeString().slice(0,8), action:'ALL ENABLED', label:'ALL VULNERABILITIES ACTIVATED', color:'#FF3333' }]);
  };

  const disableAll = () => {
    const none = {};
    WEAKNESSES.forEach(w => { none[w.id] = false; });
    setWeaknesses(none);
    setLog(l => [...l, { time:new Date().toTimeString().slice(0,8), action:'ALL DISABLED', label:'ALL VULNERABILITIES REMEDIATED', color:'#33FF33' }]);
  };

  const sevColor = { CRITICAL:'#FF3333', HIGH:'#FF9933', MED:'#FFFF66', LOW:'#3399FF' };
  const catColor = { TRANSPORT:'#3399FF', AUTHENTICATION:'#FF9933', AUTHORISATION:'#FF3333', 'DATA INTEGRITY':'#FFFF66', 'DATA ACCESS':'#FF9933', MEMORY:'#FF3333' };

  return (
    <div style={S.screen}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'2px'}}>SWKN — SECURITY WEAKNESS INJECTOR — LIVE VULNERABILITY CONTROL</div>
      <div style={{color:'#33FF33',marginBottom:'6px'}}>{'─'.repeat(79)}</div>

      <div style={{...S.warnPanel,marginBottom:'10px'}}>
        <div style={{color:'#FF3333',fontWeight:'bold',marginBottom:'4px'}}>⚠ SECURITY TRAINING ENVIRONMENT — LIVE CONTROLS</div>
        <div style={{color:'#FF9933',fontSize:'11px'}}>
          Toggling a weakness ON activates that vulnerability in the running simulation.
          DISABLED = secured (remediated). ENABLED = vulnerable (exploitable). Changes take effect immediately.
        </div>
      </div>

      {/* Bulk controls */}
      <div style={{display:'flex',gap:'8px',marginBottom:'10px'}}>
        <button onClick={enableAll} style={S.btn(false,'#FF3333')}>⚠ ENABLE ALL WEAKNESSES</button>
        <button onClick={disableAll} style={S.btn(false,'#33FF33')}>✓ DISABLE ALL (SECURE MODE)</button>
      </div>

      {/* Weakness list */}
      <div style={{display:'flex',gap:'12px',flexWrap:'wrap'}}>
        <div style={{flex:'0 0 560px'}}>
          {['TRANSPORT','AUTHENTICATION','AUTHORISATION','DATA INTEGRITY','DATA ACCESS','MEMORY'].map(cat => {
            const items = WEAKNESSES.filter(w=>w.category===cat);
            if (!items.length) return null;
            return (
              <div key={cat} style={{marginBottom:'10px'}}>
                <div style={{color:catColor[cat],fontWeight:'bold',fontSize:'11px',marginBottom:'4px',borderBottom:`1px solid ${catColor[cat]}`,paddingBottom:'2px'}}>
                  [{cat}]
                </div>
                {items.map(w=>(
                  <div key={w.id} style={{...S.panel,marginBottom:'6px',borderLeft:`3px solid ${weaknesses[w.id]?'#FF3333':'#336633'}`}}>
                    <div style={{display:'flex',alignItems:'flex-start',gap:'10px'}}>
                      <div onClick={()=>toggle(w.id)} style={S.toggle(weaknesses[w.id])}>
                        {weaknesses[w.id]?'VULN':'SAFE'}
                      </div>
                      <div style={{flex:1}}>
                        <div style={{color:weaknesses[w.id]?'#FF3333':'#AAFFAA',fontWeight:'bold',fontSize:'11px',marginBottom:'2px'}}>
                          {w.label}
                        </div>
                        <div style={{color:'#668866',fontSize:'10px',marginBottom:'2px'}}>{w.desc}</div>
                        <div style={{display:'flex',gap:'8px',fontSize:'10px',flexWrap:'wrap'}}>
                          <span style={{color:sevColor[w.severity]}}>[{w.severity}]</span>
                          <span style={{color:'#3399FF'}}>{w.vuln}</span>
                        </div>
                        {weaknesses[w.id] && (
                          <div style={{marginTop:'4px',color:'#FF9933',fontSize:'10px'}}>
                            IMPACT: {w.impact}
                          </div>
                        )}
                        <div style={{color:'#224422',fontSize:'10px',marginTop:'2px'}}>CICS: {w.cics_param}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>

        {/* Activity log */}
        <div style={{flex:1,minWidth:'240px'}}>
          <div style={{color:'#FFFF99',fontWeight:'bold',fontSize:'11px',marginBottom:'4px'}}>CHANGE LOG</div>
          <div style={S.panel}>
            {log.length===0 && <div style={{color:'#668866',fontSize:'11px'}}>No changes yet</div>}
            {[...log].reverse().map((l,i)=>(
              <div key={i} style={{fontSize:'10px',lineHeight:'1.8',borderBottom:'1px solid #001100'}}>
                <span style={{color:'#668866'}}>{l.time} </span>
                <span style={{color:l.color,fontWeight:'bold'}}>{l.action} </span>
                <span style={{color:'#AAFFAA',fontSize:'10px'}}>{l.label.slice(0,40)}</span>
              </div>
            ))}
          </div>

          {/* Status summary */}
          <div style={{color:'#FFFF99',fontWeight:'bold',fontSize:'11px',marginBottom:'4px',marginTop:'8px'}}>STATUS SUMMARY</div>
          <div style={S.panel}>
            {['CRITICAL','HIGH','MED'].map(sev=>{
              const total = WEAKNESSES.filter(w=>w.severity===sev).length;
              const active = WEAKNESSES.filter(w=>w.severity===sev&&weaknesses[w.id]).length;
              return (
                <div key={sev} style={{display:'flex',gap:'8px',fontSize:'11px',lineHeight:'1.8'}}>
                  <span style={{color:sevColor[sev],width:'8ch'}}>{sev}</span>
                  <span style={{color:'#FF3333'}}>{active} ACTIVE</span>
                  <span style={{color:'#668866'}}>/ {total} TOTAL</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{marginTop:'8px',display:'flex',gap:'10px'}}>
        <button onClick={()=>onBack('CICS')} style={S.btn(false)}>PF3 CICS MENU</button>
        <button onClick={()=>onBack('MENU')} style={S.btn(false,'#668866')}>PF12 MAIN MENU</button>
      </div>
    </div>
  );
}