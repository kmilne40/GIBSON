import React, { useState, useRef, useEffect } from 'react';

const S = {
  screen: { flex:1, overflow:'hidden', display:'flex', flexDirection:'column', fontFamily:"'Courier New', monospace", fontSize:'12px', color:'#33FF33', background:'#000' },
  panel: { background:'#000800', border:'1px solid #224422', padding:'8px', marginBottom:'6px' },
  warn: { background:'#1a0800', border:'1px solid #553300', padding:'5px 8px', color:'#FF9933', fontSize:'11px', marginBottom:'4px' },
  success: { background:'#001a00', border:'1px solid #336633', padding:'5px 8px', color:'#33FF33', fontSize:'11px', marginBottom:'4px' },
  btn: (a,c='#33FF33') => ({ background:a?'#001a00':'transparent', border:`1px solid ${a?c:'#224422'}`, color:a?c:'#336633', fontFamily:"'Courier New',monospace", fontSize:'11px', padding:'3px 10px', cursor:'pointer', marginRight:'4px' }),
};

// Simulated COBOL programs with EXEC CICS steps
const PROGRAMS = {
  CUSTMNT: {
    desc: 'Customer Master Maintenance',
    commarea: { 'CA-FUNCTION':'INQ', 'CA-CUSTOMER-ID':'10000001', 'CA-SCREEN-STATE':'01', 'CA-RETURN-TRANSID':'CUST', 'CA-RESP-CODE':'00' },
    steps: [
      { line:'0100', cmd:'EXEC CICS RECEIVE MAP', args:"MAP('CUSTMAP') MAPSET('CUSTMAPS') INTO(WS-MAP-DATA)", resp:'NORMAL', note:'BMS reads 3270 data stream into WS-MAP-DATA. No TLS — field data visible on wire.' },
      { line:'0200', cmd:'EXEC CICS GETMAIN', args:'SHARED LENGTH(1024) INITIMG(LOW-VALUE)', resp:'NORMAL', note:'Allocate 1024 bytes task storage. INITIMG(LOW-VALUE) avoids data leakage from reused storage.' },
      { line:'0300', cmd:'EXEC CICS READ FILE', args:"FILE('CUSTFILE') INTO(CUST-RECORD) RIDFLD(CA-CUSTOMER-ID) KEYLENGTH(8)", resp:'NORMAL', note:'VSAM KSDS lookup by customer ID. No DB2. No bind variables — VULN: key not validated.' },
      { line:'0400', cmd:'EXEC CICS WRITEQ TS', args:"QUEUE('CUSTAUDT') FROM(AUDIT-RECORD) LENGTH(512)", resp:'NORMAL', note:'Write audit record to temporary storage queue. Queue is local — not replicated.' },
      { line:'0500', cmd:'EXEC CICS SEND MAP', args:"MAP('CUSTMAP') MAPSET('CUSTMAPS') FROM(CUST-RECORD) ERASE", resp:'NORMAL', note:'Send populated map back to 3270 terminal. Entire PII record in plaintext EBCDIC on wire.' },
      { line:'0600', cmd:'EXEC CICS RETURN TRANSID', args:"TRANSID('CUST') COMMAREA(COMMAREA-DATA) LENGTH(256)", resp:'NORMAL', note:'Pseudo-conversational: pass COMMAREA to next invocation. State traverses the network plaintext.' },
    ]
  },
  TRANPST: {
    desc: 'Transaction Posting',
    commarea: { 'CA-ACCOUNT-NO':'1000000101', 'CA-TRAN-TYPE':'DR', 'CA-AMOUNT-WS':'000045000', 'CA-AUTH-TOKEN':'DFLT001', 'CA-STEP':'02' },
    steps: [
      { line:'0100', cmd:'EXEC CICS RECEIVE MAP', args:"MAP('TRANMAP') MAPSET('TRANMAPS') INTO(WS-TRAN-DATA)", resp:'NORMAL', note:'Receive transaction entry screen. Amount field is unprotected — client can alter value.' },
      { line:'0200', cmd:'EXEC CICS READ FILE', args:"FILE('ACCTFILE') INTO(ACCT-REC) RIDFLD(CA-ACCOUNT-NO) UPDATE", resp:'NORMAL', note:'Read account record with UPDATE intent — holds VSAM exclusive lock.' },
      { line:'0300', cmd:'EXEC CICS LINK PROGRAM', args:"PROGRAM('AUTHSVR') COMMAREA(AUTH-AREA) LENGTH(64)", resp:'NORMAL', note:'Calls authentication server sub-program. Auth token in COMMAREA — VULN: no MAC/HMAC.' },
      { line:'0400', cmd:'EXEC CICS REWRITE FILE', args:"FILE('ACCTFILE') FROM(ACCT-REC) LENGTH(256)", resp:'NORMAL', note:'Write updated balance. MITM can modify CA-AMOUNT-WS bytes before reaching here.' },
      { line:'0500', cmd:'EXEC CICS WRITEQ TS', args:"QUEUE('TRANALOG') FROM(TRAN-RECORD) LENGTH(256)", resp:'NORMAL', note:'Append to transaction log TS queue. Batch job reads this for EOD reconciliation.' },
      { line:'0600', cmd:'EXEC CICS SEND MAP', args:"MAP('TRANCONF') MAPSET('TRANMAPS') FROM(WS-CONF-DATA) ERASE", resp:'NORMAL', note:'Confirmation screen sent to terminal.' },
      { line:'0700', cmd:'EXEC CICS RETURN', args:'', resp:'NORMAL', note:'End of pseudo-conversational cycle. Task terminates.' },
    ]
  }
};

export default function CedfDebugger({ operatorId, onBack }) {
  const [prog, setProg] = useState('CUSTMNT');
  const [stepIdx, setStepIdx] = useState(0);
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState([]);
  const [commareaEdits, setCommareaEdits] = useState({});
  const [breakpoints, setBreakpoints] = useState([]);
  const [abend, setAbend] = useState(null);
  const logRef = useRef(null);

  const program = PROGRAMS[prog];
  const steps = program.steps;
  const commarea = { ...program.commarea, ...commareaEdits };

  useEffect(() => { logRef.current?.scrollIntoView({ behavior:'smooth' }); }, [completed]);

  const reset = () => { setStepIdx(0); setCompleted([]); setAbend(null); };

  const stepForward = () => {
    if (stepIdx >= steps.length) return;
    const s = steps[stepIdx];
    const hit = breakpoints.includes(stepIdx);
    setCompleted(p => [...p, { ...s, hit }]);
    if (stepIdx + 1 >= steps.length) { setRunning(false); }
    setStepIdx(i => i + 1);
  };

  const runAll = () => {
    setRunning(true);
    let i = stepIdx;
    const t = setInterval(() => {
      if (i < steps.length) {
        const s = steps[i];
        const hit = breakpoints.includes(i);
        setCompleted(p => [...p, { ...s, hit }]);
        i++;
        if (hit) { clearInterval(t); setRunning(false); setStepIdx(i); return; }
      } else { clearInterval(t); setRunning(false); setStepIdx(steps.length); }
    }, 600);
  };

  const toggleBreakpoint = (idx) => {
    setBreakpoints(b => b.includes(idx) ? b.filter(x=>x!==idx) : [...b,idx]);
  };

  const injectAbend = () => {
    setAbend({ code:'ASRA', msg:'PROTECTION EXCEPTION — COMMAREA overflow into adjacent storage. DFHAC0002 CUST ABEND ASRA.' });
  };

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  return (
    <div style={S.screen}>
      {/* Header */}
      <div style={{padding:'2px 8px',borderBottom:'1px solid #336633',color:'#AAFFAA',fontWeight:'bold',background:'#001a00',flexShrink:0,display:'flex',justifyContent:'space-between'}}>
        <span>CEDF — EXECUTION DIAGNOSTIC FACILITY — {prog}</span>
        <span style={{color:'#668866'}}>DATE: {dateStr}</span>
      </div>
      <div style={{color:'#668866',fontSize:'10px',padding:'1px 8px',background:'#000800',borderBottom:'1px solid #224422',flexShrink:0}}>
        IBM CICS/VS 2.1.1 | REGION: CICSREG1 | OPERATOR: {operatorId} | TERMINAL: LT0042
      </div>

      <div style={{flex:1,overflow:'hidden',display:'flex',gap:'0'}}>
        {/* Left: step list */}
        <div style={{width:'340px',borderRight:'1px solid #224422',overflowY:'auto',flexShrink:0}}>
          {/* Program selector */}
          <div style={{padding:'4px 8px',borderBottom:'1px solid #224422',background:'#000800',display:'flex',gap:'6px',alignItems:'center',flexShrink:0}}>
            <span style={{color:'#AAFFAA',fontSize:'11px'}}>PROGRAM:</span>
            {Object.keys(PROGRAMS).map(p=>(
              <button key={p} onClick={()=>{setProg(p);reset();}} style={S.btn(prog===p,'#AAFFAA')}>{p}</button>
            ))}
          </div>
          {/* Controls */}
          <div style={{padding:'4px 8px',borderBottom:'1px solid #224422',background:'#000800',display:'flex',gap:'4px',flexWrap:'wrap'}}>
            <button onClick={stepForward} disabled={stepIdx>=steps.length||running} style={S.btn(true,'#33FF33')}>▶ STEP</button>
            <button onClick={runAll} disabled={running||stepIdx>=steps.length} style={S.btn(true,'#FFFF66')}>▶▶ RUN</button>
            <button onClick={reset} style={S.btn(false,'#668866')}>↺ RESET</button>
            <button onClick={injectAbend} style={S.btn(false,'#FF3333')}>⚠ INJECT ABEND</button>
          </div>
          {/* Steps */}
          {steps.map((s,i) => (
            <div key={i} onClick={()=>toggleBreakpoint(i)} style={{
              padding:'4px 8px', borderBottom:'1px solid #111', cursor:'pointer',
              background: i===stepIdx ? '#002200' : completed.find(c=>c.line===s.line) ? '#001100' : '#000',
              borderLeft: breakpoints.includes(i) ? '3px solid #FF3333' : i===stepIdx ? '3px solid #33FF33' : '3px solid transparent',
            }}>
              <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                <span style={{color:'#668866',fontSize:'10px',width:'4ch'}}>{s.line}</span>
                <span style={{color: completed.find(c=>c.line===s.line) ? '#AAFFAA' : '#336633', fontSize:'10px', flex:1, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}}>{s.cmd}</span>
                {breakpoints.includes(i) && <span style={{color:'#FF3333',fontSize:'10px'}}>●</span>}
                {i===stepIdx && <span style={{color:'#33FF33',fontSize:'10px'}}>→</span>}
              </div>
            </div>
          ))}
        </div>

        {/* Right: details + commarea */}
        <div style={{flex:1,overflowY:'auto',padding:'6px 8px'}}>
          {abend && (
            <div style={{...S.warn,borderColor:'#FF3333',marginBottom:'8px'}}>
              <div style={{color:'#FF3333',fontWeight:'bold',fontSize:'12px'}}>ABEND: {abend.code}</div>
              <div style={{color:'#FFFF66',fontSize:'11px'}}>{abend.msg}</div>
            </div>
          )}

          {/* COMMAREA editor */}
          <div style={{color:'#FFFF99',fontWeight:'bold',fontSize:'11px',marginBottom:'4px'}}>COMMAREA DATA (click value to edit)</div>
          <div style={{...S.panel,marginBottom:'8px'}}>
            {Object.entries(commarea).map(([k,v])=>(
              <div key={k} style={{display:'flex',gap:'12px',fontSize:'11px',lineHeight:'1.7'}}>
                <span style={{color:'#AAFFAA',width:'22ch'}}>{k}</span>
                <span style={{color:'#668866'}}>=</span>
                <input
                  value={commareaEdits[k]!==undefined ? commareaEdits[k] : v}
                  onChange={e=>setCommareaEdits(prev=>({...prev,[k]:e.target.value}))}
                  style={{background:'transparent',border:'none',borderBottom:'1px solid #224422',color:'#3399FF',fontFamily:"'Courier New',monospace",fontSize:'11px',outline:'none',width:'20ch'}}
                />
              </div>
            ))}
          </div>

          {/* Execution log */}
          <div style={{color:'#FFFF99',fontWeight:'bold',fontSize:'11px',marginBottom:'4px'}}>EXECUTION TRACE</div>
          {completed.length===0 && <div style={{color:'#668866',fontSize:'11px'}}>Press STEP or RUN to begin</div>}
          {completed.map((s,i)=>(
            <div key={i} style={{...S.panel,marginBottom:'4px',borderLeft:`3px solid ${s.hit?'#FF3333':'#336633'}`}}>
              <div style={{display:'flex',gap:'8px',marginBottom:'2px'}}>
                <span style={{color:'#668866',width:'4ch'}}>{s.line}</span>
                <span style={{color:'#AAFFAA',fontWeight:'bold'}}>{s.cmd}</span>
                <span style={{color:'#3399FF',fontSize:'10px'}}>{s.args}</span>
                <span style={{color:s.resp==='NORMAL'?'#33FF33':'#FF3333',marginLeft:'auto',fontSize:'10px'}}>RESP={s.resp}</span>
              </div>
              <div style={{color:'#668866',fontSize:'10px',paddingLeft:'4ch'}}>{s.note}</div>
              {s.hit && <div style={{color:'#FF3333',fontSize:'10px',paddingLeft:'4ch'}}>⏸ BREAKPOINT HIT — execution paused</div>}
            </div>
          ))}
          {stepIdx>=steps.length && !abend && (
            <div style={{...S.success,marginTop:'4px'}}>✓ PROGRAM {prog} EXECUTED SUCCESSFULLY — {steps.length} EXEC CICS COMMANDS TRACED</div>
          )}
          <div ref={logRef}/>
        </div>
      </div>

      <div style={{padding:'2px 8px',borderTop:'1px solid #336633',display:'flex',gap:'12px',background:'#000800',flexShrink:0}}>
        <button onClick={()=>onBack('CICS')} style={S.btn(false)}>PF3 CICS MENU</button>
        <span style={{color:'#668866',fontSize:'10px',lineHeight:'22px'}}>CEDF | STEP=F1 RUN=F2 RESET=F5 BREAKPOINT=CLICK LINE | {prog}: {program.desc}</span>
      </div>
    </div>
  );
}