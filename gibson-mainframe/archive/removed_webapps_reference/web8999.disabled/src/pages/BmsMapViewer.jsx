import React, { useState } from 'react';

const S = {
  screen: { flex:1, overflow:'auto', padding:'8px', fontFamily:"'Courier New', monospace", fontSize:'12px', color:'#33FF33', background:'#000' },
  panel: { background:'#000800', border:'1px solid #224422', padding:'8px', marginBottom:'8px' },
  warn: { background:'#1a0800', border:'1px solid #553300', padding:'6px 8px', marginBottom:'6px', color:'#FF9933', fontSize:'11px' },
  btn: (a,c='#33FF33') => ({ background:a?'#001a00':'transparent', border:`1px solid ${a?c:'#224422'}`, color:a?c:'#336633', fontFamily:"'Courier New',monospace", fontSize:'11px', padding:'3px 10px', cursor:'pointer', marginRight:'4px' }),
  hdr: { color:'#AAFFAA', fontWeight:'bold', fontSize:'11px', marginBottom:'4px' },
  row: { display:'flex', gap:'10px', fontSize:'11px', lineHeight:'1.8', borderBottom:'1px solid #001100', paddingBottom:'2px' },
};

// Attribute byte meanings (BMS/3270)
const ATTR_BITS = [
  { bit:'MDT', mask:'0x01', desc:'Modified Data Tag — field was modified by user', security:'Attacker can set MDT=1 on protected fields to include them in AID stream' },
  { bit:'PROT', mask:'0x20', desc:'Protected — field cannot be typed into by operator', security:'hack3270 can flip PROT=0 to unprotect any field' },
  { bit:'NUM', mask:'0x10', desc:'Numeric only — terminal keyboard locks to numbers', security:'Flip NUM=0 to allow alpha injection into numeric fields' },
  { bit:'IC', mask:'0x02', desc:'Insert Cursor — positions cursor here on send', security:'No direct exploit, useful for mapping form flow' },
  { bit:'SKIP', mask:'0x30', desc:'Auto-skip — cursor skips to next unprotected field after tab', security:'Reveals intended form navigation order' },
  { bit:'DRK', mask:'0xCC', desc:'Dark (invisible) field — typically used for passwords or hidden data', security:'Deny color+highlight in Query Reply to expose hidden fields' },
  { bit:'HIGH', mask:'0xC8', desc:'High intensity — visually highlighted field', security:'Reveals security-relevant labels' },
  { bit:'NORM', mask:'0xC0', desc:'Normal intensity', security:'Standard visible field' },
];

// BMS Map definitions
const MAPS = {
  CUSTMAP: {
    mapset: 'CUSTMAPS', size: '24×80', program: 'CUSTMNT', tran: 'CUST',
    desc: 'Customer Master Maintenance Screen',
    fields: [
      { name:'CUSTID',  row:8,  col:20, len:8,  attr:'UNPROT', color:'TURQ', num:true,  prot:false, drk:false, desc:'Customer ID input field' },
      { name:'SURNAML', row:10, col:2,  len:8,  attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'Surname label (protected)' },
      { name:'SURNAMI', row:10, col:20, len:30, attr:'UNPROT', color:'TURQ', num:false, prot:false, drk:false, desc:'Surname input' },
      { name:'FORENML', row:11, col:2,  len:8,  attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'Forename label' },
      { name:'FORENMI', row:11, col:20, len:20, attr:'UNPROT', color:'TURQ', num:false, prot:false, drk:false, desc:'Forename input' },
      { name:'DOBL',    row:12, col:2,  len:4,  attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'DOB label' },
      { name:'DOBI',    row:12, col:20, len:8,  attr:'UNPROT', color:'TURQ', num:false, prot:false, drk:false, desc:'Date of Birth input DD/MM/YY' },
      { name:'NIL',     row:13, col:2,  len:10, attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'NI Number label' },
      { name:'NII',     row:13, col:20, len:9,  attr:'UNPROT', color:'TURQ', num:false, prot:false, drk:false, desc:'National Insurance number input — PII' },
      { name:'OPIDL',   row:22, col:2,  len:11, attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'Operator ID label' },
      { name:'OPIDI',   row:22, col:14, len:8,  attr:'PROT+DRK',color:'DEFAULT',num:false,prot:true,drk:true,  desc:'⚠ HIDDEN operator ID — dark field. Visible if colour denied.' },
      { name:'AUTHTOK', row:23, col:2,  len:16, attr:'PROT+DRK',color:'DEFAULT',num:false,prot:true,drk:true,  desc:'⚠ HIDDEN auth token — dark field. No encryption.' },
    ]
  },
  TRANMAP: {
    mapset: 'TRANMAPS', size: '24×80', program: 'TRANPST', tran: 'TRAN',
    desc: 'Transaction Posting Screen',
    fields: [
      { name:'ACCTNO',  row:8,  col:20, len:10, attr:'UNPROT', color:'TURQ', num:true,  prot:false, drk:false, desc:'Account number input' },
      { name:'TTYPE',   row:9,  col:20, len:3,  attr:'UNPROT', color:'TURQ', num:false, prot:false, drk:false, desc:'Transaction type CR/DR/TRF' },
      { name:'AMOUNT',  row:10, col:20, len:10, attr:'UNPROT', color:'TURQ', num:true,  prot:false, drk:false, desc:'⚠ Amount field — unprotected, no server-side re-validation before write' },
      { name:'DESCR',   row:11, col:20, len:40, attr:'UNPROT', color:'TURQ', num:false, prot:false, drk:false, desc:'Description free text — no sanitization' },
      { name:'STEPWS',  row:23, col:2,  len:2,  attr:'PROT+DRK',color:'DEFAULT',num:false,prot:true,drk:true,  desc:'⚠ COMMAREA step counter — hidden. Replay step 0 = state desync.' },
      { name:'AUTHTOK', row:23, col:5,  len:16, attr:'PROT+DRK',color:'DEFAULT',num:false,prot:true,drk:true,  desc:'⚠ Hidden auth token — sent in every AID stream.' },
    ]
  },
  LOGINMAP: {
    mapset: 'CESNMAPS', size: '24×80', program: 'DFHZCP', tran: 'CESN',
    desc: 'CICS Sign-on Screen (CESN)',
    fields: [
      { name:'USERIDL', row:12, col:20, len:8,  attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'Userid label' },
      { name:'USERIDI', row:12, col:30, len:8,  attr:'UNPROT', color:'TURQ', num:false, prot:false, drk:false, desc:'Userid input — EBCDIC plaintext on wire' },
      { name:'PASSWDL', row:13, col:20, len:8,  attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'Password label' },
      { name:'PASSWDI', row:13, col:30, len:8,  attr:'UNPROT+DRK',color:'DEFAULT',num:false,prot:false,drk:true, desc:'⚠ Password field — dark on screen but EBCDIC plaintext in stream' },
      { name:'NEWSPDL', row:14, col:20, len:12, attr:'PROT',   color:'GREEN',num:false, prot:true,  drk:false, desc:'New password label' },
      { name:'NEWSPDI', row:14, col:33, len:8,  attr:'UNPROT+DRK',color:'DEFAULT',num:false,prot:false,drk:true, desc:'⚠ New password — also plaintext in stream' },
    ]
  }
};

// Render a mock 3270 screen layout
function ScreenPreview({ map, showDark }) {
  const grid = Array(24).fill(null).map(()=>Array(80).fill(' '));
  map.fields.forEach(f => {
    const label = f.name.padEnd(f.len).slice(0,f.len);
    for (let i=0;i<label.length&&f.col-1+i<80;i++) {
      grid[f.row-1][f.col-1+i] = (f.drk && !showDark) ? ' ' : label[i];
    }
  });
  return (
    <div style={{background:'#000',border:'1px solid #224422',padding:'4px',overflowX:'auto',fontSize:'10px',lineHeight:'1.3',color:'#33FF33',fontFamily:"'Courier New',monospace"}}>
      {grid.map((row,r)=>(
        <div key={r} style={{whiteSpace:'pre',height:'1.3em'}}>
          {map.fields.filter(f=>f.row-1===r).length > 0
            ? map.fields.filter(f=>f.row-1===r).reduce((acc, f) => {
                return acc;
              }, row.join(''))
            : row.join('')}
        </div>
      ))}
    </div>
  );
}

export default function BmsMapViewer({ operatorId, onBack }) {
  const [selectedMap, setSelectedMap] = useState('CUSTMAP');
  const [showDark, setShowDark] = useState(false);
  const [selectedField, setSelectedField] = useState(null);

  const map = MAPS[selectedMap];

  return (
    <div style={S.screen}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'2px'}}>BMSVIEW — BMS MAP STRUCTURE ANALYSER — MAPSET BROWSER</div>
      <div style={{color:'#33FF33',marginBottom:'8px'}}>{'─'.repeat(79)}</div>

      {/* Map selector */}
      <div style={{display:'flex',gap:'4px',marginBottom:'8px',flexWrap:'wrap',alignItems:'center'}}>
        <span style={{color:'#AAFFAA',fontSize:'11px'}}>MAPSET: </span>
        {Object.keys(MAPS).map(m=>(
          <button key={m} onClick={()=>{setSelectedMap(m);setSelectedField(null);}} style={S.btn(selectedMap===m,'#AAFFAA')}>{m}</button>
        ))}
        <button onClick={()=>setShowDark(d=>!d)} style={S.btn(showDark,'#FF9933')}>
          {showDark ? '☑ REVEAL DARK FIELDS' : '☐ REVEAL DARK FIELDS'}
        </button>
      </div>

      <div style={{color:'#668866',fontSize:'11px',marginBottom:'8px'}}>
        MAP: {selectedMap} | MAPSET: {map.mapset} | SIZE: {map.size} | PROG: {map.program} | TRAN: {map.tran} — {map.desc}
      </div>

      {showDark && (
        <div style={S.warn}>
          ⚠ DARK FIELD REVEAL ACTIVE — simulates Query Reply lying (deny color+highlight). Hidden fields now visible.
          This is how hack3270's --deny-color flag exposes password fields and hidden auth tokens.
        </div>
      )}

      <div style={{display:'flex',gap:'12px',flexWrap:'wrap'}}>
        {/* Field table */}
        <div style={{flex:'0 0 500px'}}>
          <div style={S.hdr}>FIELD ATTRIBUTE TABLE</div>
          <div style={{...S.row,color:'#668866',fontWeight:'bold'}}>
            <span style={{width:'10ch'}}>FIELD</span><span style={{width:'5ch'}}>ROW</span>
            <span style={{width:'5ch'}}>COL</span><span style={{width:'5ch'}}>LEN</span>
            <span style={{width:'12ch'}}>ATTR</span><span style={{width:'7ch'}}>COLOR</span>
            <span style={{flex:1}}>DESCRIPTION</span>
          </div>
          {map.fields.map((f,i)=>(
            <div key={i} onClick={()=>setSelectedField(f)}
              style={{...S.row, cursor:'pointer',
                background:selectedField?.name===f.name?'#002200':'transparent',
                color: f.drk ? (showDark?'#FF9933':'#224422') : f.prot ? '#668866' : '#33FF33',
                borderLeft: f.drk ? '3px solid #FF9933' : '3px solid transparent',
              }}>
              <span style={{width:'10ch',color:f.drk?(showDark?'#FF3333':'#224422'):'#AAFFAA',fontWeight:'bold'}}>{f.name}</span>
              <span style={{width:'5ch'}}>{f.row}</span>
              <span style={{width:'5ch'}}>{f.col}</span>
              <span style={{width:'5ch'}}>{f.len}</span>
              <span style={{width:'12ch',color:f.drk?'#FF9933':f.prot?'#668866':'#3399FF',fontSize:'10px'}}>{f.attr}</span>
              <span style={{width:'7ch',color:'#668866',fontSize:'10px'}}>{f.color}</span>
              <span style={{flex:1,fontSize:'10px',color:f.desc.startsWith('⚠')?'#FF9933':'#668866'}}>{f.desc}</span>
            </div>
          ))}
        </div>

        {/* Field detail + attr bits */}
        <div style={{flex:1,minWidth:'260px'}}>
          {selectedField ? (
            <>
              <div style={S.hdr}>FIELD DETAIL: {selectedField.name}</div>
              <div style={S.panel}>
                <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'4px'}}>{selectedField.name} @ ROW {selectedField.row} COL {selectedField.col}</div>
                <div style={{color:'#33FF33',fontSize:'11px',lineHeight:'1.8'}}>
                  <div>LENGTH   : {selectedField.len}</div>
                  <div>ATTRIBUTE: <span style={{color:'#3399FF'}}>{selectedField.attr}</span></div>
                  <div>COLOR    : {selectedField.color}</div>
                  <div>PROTECTED: <span style={{color:selectedField.prot?'#AAFFAA':'#FF9933'}}>{selectedField.prot?'YES':'NO — OPERATOR EDITABLE'}</span></div>
                  <div>DARK/HIDDEN: <span style={{color:selectedField.drk?'#FF3333':'#33FF33'}}>{selectedField.drk?'YES — NOT RENDERED':'NO'}</span></div>
                  <div>NUMERIC: {selectedField.num?'YES':'NO'}</div>
                </div>
                {selectedField.drk && (
                  <div style={{...S.warn,marginTop:'6px'}}>
                    ⚠ DARK FIELD — visible in TN3270 data stream even though not rendered. hack3270 --deny-color reveals content.
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{color:'#668866',fontSize:'11px',marginTop:'8px'}}>← Click a field to inspect attributes</div>
          )}

          <div style={{marginTop:'8px',...S.hdr}}>3270 ATTRIBUTE BYTE REFERENCE</div>
          <div style={S.panel}>
            {ATTR_BITS.map((a,i)=>(
              <div key={i} style={{marginBottom:'6px',borderBottom:'1px solid #001100',paddingBottom:'4px'}}>
                <div style={{display:'flex',gap:'8px'}}>
                  <span style={{color:'#FFFF99',width:'6ch',fontWeight:'bold'}}>{a.bit}</span>
                  <span style={{color:'#3399FF',width:'6ch'}}>{a.mask}</span>
                  <span style={{color:'#AAFFAA',flex:1,fontSize:'10px'}}>{a.desc}</span>
                </div>
                <div style={{color:'#668866',fontSize:'10px',paddingLeft:'12ch'}}>{a.security}</div>
              </div>
            ))}
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