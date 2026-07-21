import React, { useState } from 'react';

const S = {
  screen: { flex:1, position:'relative', overflow:'hidden', padding:'8px', fontFamily:"'Courier New', monospace", fontSize:'13px', color:'#33FF33', background:'#000' },
  header: { color:'#AAFFAA', fontWeight:'bold', marginBottom:'2px' },
  divider: { color:'#33FF33', marginBottom:'8px' },
  title: { textAlign:'center', color:'#AAFFAA', fontWeight:'bold', fontSize:'15px', letterSpacing:'2px', marginBottom:'4px' },
  subtitle: { textAlign:'center', color:'#33FF33', marginBottom:'16px' },
  menuItem: (highlight) => ({ color: highlight ? '#FFFF66' : '#33FF33', lineHeight:'1.9', cursor:'pointer' }),
  label: { color:'#AAFFAA', fontWeight:'bold' },
  input: { width:'8ch', background:'transparent', border:'none', borderBottom:'1px solid #3399FF', color:'#3399FF', fontFamily:"'Courier New', monospace", fontSize:'14px', outline:'none', textTransform:'uppercase' },
};

const MENU_ITEMS = [
  { key:'1', code:'CEMT', label:'MASTER TERMINAL OPERATOR', desc:'Inquire/Set CICS resources', color:'#AAFFAA' },
  { key:'2', code:'CECI', label:'COMMAND LEVEL INTERPRETER', desc:'Execute EXEC CICS commands interactively', color:'#AAFFAA' },
  { key:'3', code:'CEDA', label:'RESOURCE DEFINITION ONLINE', desc:'View/Install CICS resource definitions', color:'#AAFFAA' },
  { key:'4', code:'CEDF', label:'EXECUTION DIAGNOSTIC FACILITY', desc:'Step-through COBOL debugger', color:'#AAFFAA' },
  { key:'5', code:'BMSV', label:'BMS MAP VIEWER', desc:'Browse/analyse BMS screen maps & field attributes', color:'#AAFFAA' },
  { key:'6', code:'SWKN', label:'SECURITY WEAKNESS INJECTOR', desc:'Toggle live vulnerability settings', color:'#FF9933' },
  { key:'7', code:'SLOG', label:'CICS SYSTEM LOG', desc:'View DFH/ICH/IEA message journal', color:'#AAFFAA' },
  { key:'9', code:'BLAB', label:'BANKING LAB', desc:'Interactive CICS vulnerability simulation', color:'#3399FF' },
  { key:'8', code:'BACK', label:'RETURN TO BANKMASTER MENU', desc:'', color:'#668866' },
];

export default function CicsMenu({ operatorId, onNavigate }) {
  const [sel, setSel] = useState('');
  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  const handleKey = (e) => {
    if (e.key === 'Enter') {
      const v = sel.trim().toUpperCase();
      if (v==='1'||v==='CEMT') onNavigate('CEMT');
      else if (v==='2'||v==='CECI') onNavigate('CECI');
      else if (v==='3'||v==='CEDA') onNavigate('CEDA');
      else if (v==='4'||v==='CEDF') onNavigate('CEDF');
      else if (v==='5'||v==='BMSV') onNavigate('BMSV');
      else if (v==='6'||v==='SWKN') onNavigate('SWKN');
      else if (v==='7'||v==='SLOG') onNavigate('SLOG');
      else if (v==='9'||v==='BLAB') onNavigate('BLAB');
      else if (v==='8'||v==='BACK') onNavigate('MENU');
      setSel('');
    }
    if (e.key==='F3') onNavigate('MENU');
  };

  return (
    <div style={S.screen} onKeyDown={handleKey}>
      <div style={S.header}>{'BANKMASTER/VS'.padEnd(30)}{'CICSMNUC'.padEnd(20)}{'DATE: '+dateStr}</div>
      <div style={S.divider}>{'─'.repeat(79)}</div>
      <div style={S.title}>CICS TRANSACTION SERVICES — CONTROL MENU</div>
      <div style={{textAlign:'center',color:'#33FF33',marginBottom:'4px'}}>IBM CICS/VS 2.1.1  REGION: CICSREG1  SYSID: PROD</div>
      <div style={{...S.subtitle}}>{'─'.repeat(55)}</div>

      <div style={{marginLeft:'8ch',lineHeight:'2.0'}}>
        {MENU_ITEMS.map(item => (
          <div key={item.key} style={S.menuItem(false)}>
            <span style={{color:item.color,fontWeight:'bold'}}>  {item.key}   {item.code}</span>
            <span style={{color:item.color}}>   -   {item.label}</span>
            {item.desc && <span style={{color:'#446644',fontSize:'12px'}}>   ({item.desc})</span>}
          </div>
        ))}
      </div>

      <div style={{marginTop:'20px',display:'flex',alignItems:'center',gap:'8px',marginLeft:'8px'}}>
        <span style={S.label}>SELECTION ===&gt;</span>
        <input autoFocus type="text" value={sel}
          onChange={e=>setSel(e.target.value.toUpperCase().slice(0,4))}
          maxLength={4} style={S.input} />
        <span style={{color:'#33FF33'}}>OR TYPE CODE DIRECTLY</span>
      </div>

      <div style={{position:'absolute',bottom:'60px',left:'8px',right:'8px',color:'#33FF33',fontSize:'12px',borderTop:'1px solid #004400',paddingTop:'4px'}}>
        OPERATOR: {operatorId}{'   '}TERMINAL: LT0042{'   '}REGION: CICSREG1{'   '}DATE: {dateStr}
      </div>
    </div>
  );
}