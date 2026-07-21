import React, { useState } from 'react';

const S = {
  screen: { flex:1, overflow:'auto', padding:'8px', fontFamily:"'Courier New', monospace", fontSize:'12px', color:'#33FF33', background:'#000' },
  panel: { background:'#000800', border:'1px solid #224422', padding:'8px', marginBottom:'8px' },
  warn: { background:'#1a0800', border:'1px solid #553300', padding:'6px 8px', marginBottom:'6px', color:'#FF9933', fontSize:'11px' },
  success: { background:'#001a00', border:'1px solid #336633', padding:'6px 8px', color:'#33FF33', fontSize:'11px' },
  btn: (a,c='#33FF33') => ({ background:a?'#001a00':'transparent', border:`1px solid ${a?c:'#224422'}`, color:a?c:'#336633', fontFamily:"'Courier New',monospace", fontSize:'11px', padding:'3px 10px', cursor:'pointer', marginRight:'4px' }),
  row: { display:'flex', gap:'12px', fontSize:'11px', lineHeight:'1.8', borderBottom:'1px solid #001100', paddingBottom:'2px', color:'#33FF33' },
  hdr: { color:'#AAFFAA', fontWeight:'bold', fontSize:'11px', marginBottom:'4px' },
};

const PROGRAMS = [
  { name:'CUSTMNT', group:'BANKGRP1', lang:'COBOL', status:'ENABLED', res:'NO',  len:'65536', use:'00012', desc:'Customer Master Maintenance' },
  { name:'ACCTMNT', group:'BANKGRP1', lang:'COBOL', status:'ENABLED', res:'NO',  len:'65536', use:'00007', desc:'Account Maintenance' },
  { name:'TRANPST', group:'BANKGRP1', lang:'COBOL', status:'ENABLED', res:'NO',  len:'32768', use:'00034', desc:'Transaction Posting' },
  { name:'BLKPRC',  group:'BANKGRP2', lang:'COBOL', status:'ENABLED', res:'YES', len:'131072',use:'00001', desc:'Bulk Processing' },
  { name:'CESN',    group:'DFHSYS',   lang:'ASSEMBLER', status:'ENABLED', res:'YES',len:'8192', use:'00099', desc:'CICS Sign-on Program' },
  { name:'DFHEMTA', group:'DFHSYS',   lang:'ASSEMBLER', status:'ENABLED', res:'YES',len:'4096', use:'00045', desc:'Master Terminal Application' },
  { name:'DFHZCP',  group:'DFHSYS',   lang:'ASSEMBLER', status:'ENABLED', res:'YES',len:'16384',use:'00099', desc:'CICS Command Processor' },
];

const TRANSACTIONS = [
  { tran:'CUST', prog:'CUSTMNT', grp:'BANKGRP1', status:'ENABLED',  sec:'Y', pri:'1', twa:'256',  desc:'Customer Maintenance' },
  { tran:'ACCT', prog:'ACCTMNT', grp:'BANKGRP1', status:'ENABLED',  sec:'Y', pri:'1', twa:'256',  desc:'Account Maintenance' },
  { tran:'TRAN', prog:'TRANPST', grp:'BANKGRP1', status:'ENABLED',  sec:'Y', pri:'1', twa:'512',  desc:'Transaction Posting' },
  { tran:'BULK', prog:'BLKPRC',  grp:'BANKGRP2', status:'ENABLED',  sec:'Y', pri:'2', twa:'1024', desc:'Bulk Processing' },
  { tran:'CECI', prog:'DFHEZCI', grp:'DFHSYS',   status:'ENABLED',  sec:'N', pri:'1', twa:'0',    desc:'Command Interpreter (VULN: NO AUTH)' },
  { tran:'CEMT', prog:'DFHEMTA', grp:'DFHSYS',   status:'ENABLED',  sec:'N', pri:'2', twa:'0',    desc:'Master Terminal (VULN: NO AUTH)' },
  { tran:'CEDA', prog:'DFHEDAP', grp:'DFHSYS',   status:'ENABLED',  sec:'N', pri:'1', twa:'0',    desc:'Resource Definition Online' },
  { tran:'CESN', prog:'DFHZCP',  grp:'DFHSYS',   status:'ENABLED',  sec:'N', pri:'3', twa:'0',    desc:'CICS Sign-on' },
  { tran:'CEDF', prog:'DFHEDFD', grp:'DFHSYS',   status:'ENABLED',  sec:'N', pri:'1', twa:'0',    desc:'Execution Diagnostic Facility' },
];

const FILES = [
  { name:'CUSTFILE', dsn:'BANK.PROD.CUSTOMER', org:'KSDS', acc:'RDUPD', status:'OPEN',  rlen:'512', desc:'Customer Master File' },
  { name:'ACCTFILE', dsn:'BANK.PROD.ACCOUNT',  org:'KSDS', acc:'RDUPD', status:'OPEN',  rlen:'256', desc:'Account Master File' },
  { name:'TRANFILE', dsn:'BANK.PROD.TRANSACT', org:'ESDS', acc:'RD',    status:'OPEN',  rlen:'256', desc:'Transaction Log ESDS' },
  { name:'AUDITLOG', dsn:'BANK.PROD.AUDIT',    org:'ESDS', acc:'ADD',   status:'OPEN',  rlen:'512', desc:'Security Audit Log' },
  { name:'SORTTMP1', dsn:'BANK.TEMP.SORT01',   org:'ESDS', acc:'RDUPD', status:'CLOSED',rlen:'1024',desc:'Sort Work File 1' },
];

const TERMINALS = [
  { termid:'LT0042', net:'BANKLUA1', status:'INS', tran:'CUST',  oper:'JSMITH', model:'3279-2' },
  { termid:'LT0001', net:'BANKLUB1', status:'INS', tran:'',      oper:'',       model:'3279-2' },
  { termid:'LT0099', net:'BANKLUC1', status:'OUT', tran:'',      oper:'',       model:'3279-2' },
  { termid:'BATCH1', net:'BATCHLU1', status:'INS', tran:'BULK',  oper:'BATCH',  model:'3287-2' },
  { termid:'CONS01', net:'CONSOLE1', status:'INS', tran:'CEMT',  oper:'SYSOP',  model:'3278-2' },
];

export default function CedaViewer({ operatorId, onBack }) {
  const [tab, setTab] = useState('PROG');
  const [installing, setInstalling] = useState(null);
  const [installed, setInstalled] = useState([]);

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  const install = (name) => {
    setInstalling(name);
    setTimeout(() => { setInstalled(p=>[...p,name]); setInstalling(null); }, 1200);
  };

  return (
    <div style={S.screen}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'2px'}}>{'BANKMASTER/VS'.padEnd(30)}{'CEDA'.padEnd(20)}{'DATE: '+dateStr}</div>
      <div style={{color:'#33FF33',marginBottom:'6px'}}>{'─'.repeat(79)}</div>
      <div style={{textAlign:'center',color:'#AAFFAA',fontWeight:'bold',marginBottom:'6px'}}>
        CEDA — RESOURCE DEFINITION ONLINE — CICSREG1
      </div>

      {/* Tabs */}
      <div style={{display:'flex',gap:'4px',marginBottom:'8px',flexWrap:'wrap'}}>
        {[['PROG','PROGRAMS'],['TRAN','TRANSACTIONS'],['FILE','FILES'],['TERM','TERMINALS']].map(([id,lbl])=>(
          <button key={id} onClick={()=>setTab(id)} style={S.btn(tab===id,'#AAFFAA')}>{lbl}</button>
        ))}
      </div>

      {tab==='PROG' && (
        <>
          <div style={S.hdr}>INSTALLED PROGRAMS — GROUP DEFINITIONS</div>
          <div style={{...S.row,color:'#668866',fontWeight:'bold'}}>
            <span style={{width:'10ch'}}>PROGRAM</span><span style={{width:'10ch'}}>GROUP</span>
            <span style={{width:'6ch'}}>LANG</span><span style={{width:'9ch'}}>STATUS</span>
            <span style={{width:'4ch'}}>RES</span><span style={{width:'7ch'}}>LENGTH</span>
            <span style={{width:'6ch'}}>USE</span><span style={{flex:1}}>DESCRIPTION</span>
          </div>
          {PROGRAMS.map((p,i)=>(
            <div key={i} style={{...S.row,color:p.group==='DFHSYS'?'#668866':'#33FF33'}}>
              <span style={{width:'10ch',color:'#AAFFAA',fontWeight:'bold'}}>{p.name}</span>
              <span style={{width:'10ch'}}>{p.group}</span>
              <span style={{width:'6ch'}}>{p.lang}</span>
              <span style={{width:'9ch',color:p.status==='ENABLED'?'#33FF33':'#FF3333'}}>{p.status}</span>
              <span style={{width:'4ch'}}>{p.res}</span>
              <span style={{width:'7ch'}}>{p.len}</span>
              <span style={{width:'6ch'}}>{p.use}</span>
              <span style={{flex:1,color:'#668866',fontSize:'10px'}}>{p.desc}</span>
            </div>
          ))}
        </>
      )}

      {tab==='TRAN' && (
        <>
          <div style={S.hdr}>INSTALLED TRANSACTIONS — GROUP DEFINITIONS</div>
          <div style={{...S.row,color:'#668866',fontWeight:'bold'}}>
            <span style={{width:'6ch'}}>TRAN</span><span style={{width:'10ch'}}>PROGRAM</span>
            <span style={{width:'10ch'}}>GROUP</span><span style={{width:'9ch'}}>STATUS</span>
            <span style={{width:'5ch'}}>SEC</span><span style={{width:'4ch'}}>PRI</span>
            <span style={{width:'6ch'}}>TWA</span><span style={{flex:1}}>DESCRIPTION</span>
          </div>
          {TRANSACTIONS.map((t,i)=>(
            <div key={i} style={{...S.row,color:t.sec==='N'?'#FF9933':'#33FF33'}}>
              <span style={{width:'6ch',color:'#AAFFAA',fontWeight:'bold'}}>{t.tran}</span>
              <span style={{width:'10ch'}}>{t.prog}</span>
              <span style={{width:'10ch',color:'#668866'}}>{t.grp}</span>
              <span style={{width:'9ch',color:t.status==='ENABLED'?'#33FF33':'#FF3333'}}>{t.status}</span>
              <span style={{width:'5ch',color:t.sec==='N'?'#FF3333':'#33FF33',fontWeight:'bold'}}>{t.sec==='N'?'NONE':'RACF'}</span>
              <span style={{width:'4ch'}}>{t.pri}</span>
              <span style={{width:'6ch'}}>{t.twa}</span>
              <span style={{flex:1,color:t.sec==='N'?'#FF9933':'#668866',fontSize:'10px'}}>{t.desc}</span>
            </div>
          ))}
          <div style={{...S.warn,marginTop:'8px'}}>
            ⚠ TRANSACTIONS WITH SEC=NONE ARE ACCESSIBLE WITHOUT CESN SIGNON — VULN #5, #6, #7
          </div>
        </>
      )}

      {tab==='FILE' && (
        <>
          <div style={S.hdr}>FILE CONTROL TABLE — VSAM DATASET DEFINITIONS</div>
          <div style={{...S.row,color:'#668866',fontWeight:'bold'}}>
            <span style={{width:'10ch'}}>DDNAME</span><span style={{width:'22ch'}}>DSN</span>
            <span style={{width:'6ch'}}>ORG</span><span style={{width:'6ch'}}>ACCESS</span>
            <span style={{width:'8ch'}}>STATUS</span><span style={{width:'6ch'}}>RLEN</span>
            <span style={{flex:1}}>DESCRIPTION</span>
          </div>
          {FILES.map((f,i)=>(
            <div key={i} style={{...S.row}}>
              <span style={{width:'10ch',color:'#AAFFAA',fontWeight:'bold'}}>{f.name}</span>
              <span style={{width:'22ch',color:'#668866',fontSize:'10px'}}>{f.dsn}</span>
              <span style={{width:'6ch'}}>{f.org}</span>
              <span style={{width:'6ch'}}>{f.acc}</span>
              <span style={{width:'8ch',color:f.status==='OPEN'?'#33FF33':'#FF9933'}}>{f.status}</span>
              <span style={{width:'6ch'}}>{f.rlen}</span>
              <span style={{flex:1,color:'#668866',fontSize:'10px'}}>{f.desc}</span>
            </div>
          ))}
        </>
      )}

      {tab==='TERM' && (
        <>
          <div style={S.hdr}>TERMINAL CONTROL TABLE — VTAM DEFINITIONS</div>
          <div style={{...S.row,color:'#668866',fontWeight:'bold'}}>
            <span style={{width:'8ch'}}>TERMID</span><span style={{width:'10ch'}}>NETNAME</span>
            <span style={{width:'6ch'}}>STATUS</span><span style={{width:'7ch'}}>TRAN</span>
            <span style={{width:'10ch'}}>OPERATOR</span><span style={{flex:1}}>MODEL</span>
          </div>
          {TERMINALS.map((t,i)=>(
            <div key={i} style={{...S.row}}>
              <span style={{width:'8ch',color:'#AAFFAA',fontWeight:'bold'}}>{t.termid}</span>
              <span style={{width:'10ch'}}>{t.net}</span>
              <span style={{width:'6ch',color:t.status==='INS'?'#33FF33':'#FF9933'}}>{t.status}</span>
              <span style={{width:'7ch',color:'#3399FF'}}>{t.tran||'─'}</span>
              <span style={{width:'10ch'}}>{t.oper||'─'}</span>
              <span style={{flex:1,color:'#668866'}}>{t.model}</span>
            </div>
          ))}
        </>
      )}

      {/* Install simulation */}
      <div style={{marginTop:'16px',borderTop:'1px solid #224422',paddingTop:'8px'}}>
        <div style={S.hdr}>CEDA INSTALL — SIMULATE RESOURCE INSTALLATION</div>
        <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginBottom:'6px'}}>
          {['BANKGRP1','BANKGRP2','DFHSYS'].map(g=>(
            <button key={g} onClick={()=>install(g)} disabled={!!installing||installed.includes(g)}
              style={S.btn(!installing&&!installed.includes(g),'#FFFF66')}>
              {installing===g?'INSTALLING...':installed.includes(g)?`✓ ${g} INSTALLED`:`INSTALL ${g}`}
            </button>
          ))}
        </div>
        {installed.length>0 && (
          <div style={S.success}>
            {installed.map(g=>`DFHSG0101I GROUP ${g} INSTALLED SUCCESSFULLY`).join('\n')}
          </div>
        )}
      </div>

      <div style={{marginTop:'8px',display:'flex',gap:'10px'}}>
        <button onClick={()=>onBack('CICS')} style={S.btn(false)}>PF3 CICS MENU</button>
        <button onClick={()=>onBack('MENU')} style={S.btn(false,'#668866')}>PF12 MAIN MENU</button>
      </div>
    </div>
  );
}