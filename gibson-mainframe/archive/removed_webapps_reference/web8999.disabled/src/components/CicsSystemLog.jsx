import React, { useState, useEffect, useRef } from 'react';

const S = {
  btn: (a,c='#33FF33') => ({ background:a?'#001a00':'transparent', border:`1px solid ${a?c:'#224422'}`, color:a?c:'#336633', fontFamily:"'Courier New',monospace", fontSize:'11px', padding:'3px 10px', cursor:'pointer', marginRight:'4px' }),
};

const BASE_MESSAGES = [
  { code:'DFHSI1517', sev:'INFO',  src:'CICS',  text:'CICS is initialised and ready for requests. SYSID=PROD REGION=CICSREG1' },
  { code:'DFHAC0001', sev:'INFO',  src:'CICS',  text:'Transaction CUST started by operator JSMITH on terminal LT0042' },
  { code:'DFHAC0001', sev:'INFO',  src:'CICS',  text:'Transaction TRAN started by operator JSMITH on terminal LT0042' },
  { code:'ICH408I',   sev:'INFO',  src:'RACF',  text:'User JSMITH connected from terminal LT0042. RACF access check passed.' },
  { code:'DFHCE3530', sev:'WARN',  src:'CICS',  text:'CESN: Userid BADUSER not defined to RACF. Username enumeration oracle active (pre-5.1).' },
  { code:'DFHCE3520', sev:'WARN',  src:'CICS',  text:'CESN: Password incorrect for user DVCA. Account status: ACTIVE (not revoked).' },
  { code:'DFHAC2206', sev:'WARN',  src:'CICS',  text:'Program ROGUE001 not found. Request from terminal CONS01.' },
  { code:'DFHSN1800', sev:'WARN',  src:'VTAM',  text:'SNA session table query from LU CONS01. LU names exposed: CICSA01 CICSA02 CICSA03 LT0042.' },
  { code:'IEA095I',   sev:'INFO',  src:'RACF',  text:'Password encryption: DES-56. KDFAES not active. Max password length: 8 characters.' },
  { code:'DFHAC0002', sev:'ERROR', src:'CICS',  text:'Transaction CUST ABEND ASRA on terminal LT0042. Task=00023 Program=CUSTMNT PSW=00000001.' },
  { code:'DFHZC3466', sev:'ERROR', src:'CICS',  text:'TN3270 session established on port 23 — NO TLS. Remote IP=10.0.0.55 LU=TERM099.' },
  { code:'DFHPA0001', sev:'INFO',  src:'CICS',  text:'APA: Transaction CECI executed without CESN signon. Security=NONE. (Intended — VULN #6)' },
  { code:'DFHPA0001', sev:'INFO',  src:'CICS',  text:'APA: Transaction CEMT executed without CESN signon. Security=NONE. (Intended — VULN #5)' },
  { code:'DFHCP0001', sev:'INFO',  src:'CICS',  text:'CECI EXEC CICS LINK PROGRAM(AUTHSVR) COMMAREA length=64. No MAC/HMAC on auth token.' },
  { code:'DFHDB0001', sev:'INFO',  src:'DB2',   text:'SQL executed: SELECT * FROM CUSTOMER WHERE CUST_ID=\'10000001\'. Rows=1 Duration=12ms.' },
  { code:'DFHTS0001', sev:'INFO',  src:'CICS',  text:'TS Queue CUSTAUDT written. Length=512. Queue type=LOCAL. Not replicated.' },
  { code:'DFHZC9999', sev:'WARN',  src:'CICS',  text:'IND$FILE PUT detected from terminal LT0042. File=SYS1.PAYROLL.REPORT. Size=14820 bytes.' },
  { code:'ICH70001I', sev:'WARN',  src:'RACF',  text:'JSMITH attempted access to FACILITY CLASS CICSPROD. Result=PERMITTED (no RACLIST in effect).' },
  { code:'DFHCC0001', sev:'INFO',  src:'CICS',  text:'CEMT INQ TASK — 3 active tasks. TRAN=CUST USER=JSMITH. TRAN=TRAN USER=JSMITH. TRAN=CEMT USER=SYSOP.' },
  { code:'DFHCE0001', sev:'ERROR', src:'RACF',  text:'Signon attempt #5 for user DVCA from LT0099. No lockout enforced — VULN #2.' },
];

const SEV_COLOR = { INFO:'#33FF33', WARN:'#FF9933', ERROR:'#FF3333' };
const SRC_COLOR = { CICS:'#AAFFAA', RACF:'#3399FF', VTAM:'#FFFF66', DB2:'#FF9933' };

export default function CicsSystemLog({ operatorId, onBack }) {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [filter, setFilter] = useState('ALL');
  const [srcFilter, setSrcFilter] = useState('ALL');
  const bottomRef = useRef(null);
  const counterRef = useRef(0);

  useEffect(() => {
    if (!streaming) return;
    const t = setInterval(() => {
      if (counterRef.current < BASE_MESSAGES.length) {
        const msg = BASE_MESSAGES[counterRef.current];
        const now = new Date();
        const ts = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}.${String(now.getMilliseconds()).padStart(3,'0')}`;
        setMessages(m => [...m, { ...msg, ts, id: counterRef.current }]);
        counterRef.current++;
      } else {
        clearInterval(t);
        setStreaming(false);
      }
    }, 500);
    return () => clearInterval(t);
  }, [streaming]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }); }, [messages]);

  const startStream = () => { counterRef.current = 0; setMessages([]); setStreaming(true); };
  const loadAll = () => {
    const now = new Date();
    const ts = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}.000`;
    setMessages(BASE_MESSAGES.map((m,i)=>({...m,ts,id:i})));
  };

  const shown = messages.filter(m => {
    const sevOk = filter==='ALL' || m.sev===filter;
    const srcOk = srcFilter==='ALL' || m.src===srcFilter;
    return sevOk && srcOk;
  });

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  return (
    <div style={{flex:1,display:'flex',flexDirection:'column',fontFamily:"'Courier New', monospace",fontSize:'12px',color:'#33FF33',background:'#000',height:'100%'}}>
      {/* Header */}
      <div style={{padding:'2px 8px',borderBottom:'1px solid #336633',color:'#AAFFAA',fontWeight:'bold',background:'#001a00',flexShrink:0,display:'flex',justifyContent:'space-between'}}>
        <span>CICS SYSTEM LOG — DFH/ICH/IEA MESSAGE JOURNAL</span>
        <span style={{color:'#668866'}}>DATE: {dateStr}</span>
      </div>

      {/* Controls */}
      <div style={{padding:'4px 8px',borderBottom:'1px solid #224422',background:'#000800',display:'flex',gap:'6px',flexWrap:'wrap',flexShrink:0}}>
        <button onClick={startStream} disabled={streaming} style={S.btn(!streaming,'#AAFFAA')}>
          {streaming ? '⏺ LIVE...' : '▶ LIVE STREAM'}
        </button>
        <button onClick={loadAll} style={S.btn(false)}>LOAD ALL</button>
        <button onClick={() => setMessages([])} style={S.btn(false,'#FF3333')}>CLR</button>
        <span style={{color:'#668866',fontSize:'10px',lineHeight:'24px',marginLeft:'8px'}}>SEV:</span>
        {['ALL','INFO','WARN','ERROR'].map(f=>(
          <button key={f} onClick={()=>setFilter(f)} style={S.btn(filter===f, f==='ERROR'?'#FF3333':f==='WARN'?'#FF9933':'#33FF33')}>{f}</button>
        ))}
        <span style={{color:'#668866',fontSize:'10px',lineHeight:'24px',marginLeft:'8px'}}>SRC:</span>
        {['ALL','CICS','RACF','VTAM','DB2'].map(s=>(
          <button key={s} onClick={()=>setSrcFilter(s)} style={S.btn(srcFilter===s,SRC_COLOR[s]||'#33FF33')}>{s}</button>
        ))}
      </div>

      {/* Column headers */}
      <div style={{display:'flex',gap:'10px',padding:'2px 8px',borderBottom:'1px solid #224422',background:'#000800',color:'#668866',fontSize:'10px',flexShrink:0}}>
        <span style={{width:'14ch'}}>TIMESTAMP</span>
        <span style={{width:'5ch'}}>SEV</span>
        <span style={{width:'5ch'}}>SRC</span>
        <span style={{width:'12ch'}}>MESSAGE CODE</span>
        <span style={{flex:1}}>MESSAGE TEXT</span>
      </div>

      {/* Log body */}
      <div style={{flex:1,overflowY:'auto',padding:'0'}}>
        {shown.length===0 && <div style={{color:'#668866',padding:'12px'}}>Press LIVE STREAM or LOAD ALL to populate log</div>}
        {shown.map((m,i)=>(
          <div key={m.id} style={{
            display:'flex',gap:'10px',padding:'2px 8px',
            borderBottom:'1px solid #050505',
            background: m.sev==='ERROR'?'#1a0000':m.sev==='WARN'?'#0a0800':'#000',
          }}>
            <span style={{color:'#446644',width:'14ch',flexShrink:0,fontSize:'10px'}}>{m.ts}</span>
            <span style={{color:SEV_COLOR[m.sev],width:'5ch',flexShrink:0,fontWeight:'bold',fontSize:'10px'}}>{m.sev}</span>
            <span style={{color:SRC_COLOR[m.src]||'#33FF33',width:'5ch',flexShrink:0,fontSize:'10px'}}>{m.src}</span>
            <span style={{color:'#FFFF99',width:'12ch',flexShrink:0,fontSize:'10px'}}>{m.code}</span>
            <span style={{flex:1,color:m.sev==='ERROR'?'#FF9933':m.sev==='WARN'?'#FFFF66':'#33FF33',fontSize:'11px'}}>{m.text}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Footer */}
      <div style={{padding:'2px 8px',borderTop:'1px solid #336633',display:'flex',gap:'12px',background:'#000800',flexShrink:0}}>
        <button onClick={()=>onBack('CICS')} style={S.btn(false)}>PF3 CICS MENU</button>
        <span style={{color:'#668866',fontSize:'10px',lineHeight:'22px'}}>
          {shown.length} MESSAGES DISPLAYED | ERRORS: {messages.filter(m=>m.sev==='ERROR').length} | WARNINGS: {messages.filter(m=>m.sev==='WARN').length}
        </span>
      </div>
    </div>
  );
}