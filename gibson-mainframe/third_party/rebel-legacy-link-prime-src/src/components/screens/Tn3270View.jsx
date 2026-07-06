import React, { useState, useEffect, useRef } from 'react';

// TN3270 / HACK3270 ATTACK SIMULATOR
// Based on: github.com/gglessner/hack3270 (v2.8.1)
// Simulates: MITM proxy, field attribute hacking, LU-name spoofing,
//            credential brute force, COMMAREA fuzzing, ESM fingerprinting,
//            IND$FILE intercept, Query Reply lying

const IAC = 0xFF; const DO = 0xFD; const WILL = 0xFB; const SB = 0xFA; const SE = 0xF0;

const EBCDIC = {
  0xC1:'A',0xC2:'B',0xC3:'C',0xC4:'D',0xC5:'E',0xC6:'F',0xC7:'G',0xC8:'H',0xC9:'I',
  0xD1:'J',0xD2:'K',0xD3:'L',0xD4:'M',0xD5:'N',0xD6:'O',0xD7:'P',0xD8:'Q',0xD9:'R',
  0xE2:'S',0xE3:'T',0xE4:'U',0xE5:'V',0xE6:'W',0xE7:'X',0xE8:'Y',0xE9:'Z',
  0xF0:'0',0xF1:'1',0xF2:'2',0xF3:'3',0xF4:'4',0xF5:'5',0xF6:'6',0xF7:'7',0xF8:'8',0xF9:'9',
  0x40:' ',0x61:'-',0x6B:',',0x4B:'.',0x7B:'#',0x50:'&',
};

function ebcdicDecode(bytes) {
  return bytes.map(b => EBCDIC[b] || '.').join('');
}

function hexDump(bytes) {
  const lines = [];
  for (let i = 0; i < bytes.length; i += 16) {
    const chunk = bytes.slice(i, i + 16);
    const hex = chunk.map(b => b.toString(16).padStart(2,'0').toUpperCase()).join(' ');
    const ascii = chunk.map(b => (b >= 0x20 && b < 0x7F) ? String.fromCharCode(b) : '.').join('');
    lines.push({ offset: i.toString(16).padStart(4,'0').toUpperCase(), hex: hex.padEnd(47), ascii });
  }
  return lines;
}

const S = {
  btn: (active, color='#33FF33') => ({
    background: active ? '#001a00' : 'transparent',
    border: `1px solid ${active ? color : '#224422'}`,
    color: active ? color : '#336633',
    fontFamily: "'Courier New', monospace", fontSize:'11px', padding:'3px 10px',
    cursor:'pointer', marginRight:'4px',
  }),
  panel: { background:'#000800', border:'1px solid #224422', padding:'8px', marginBottom:'8px', fontSize:'11px' },
  warn: { background:'#1a0800', border:'1px solid #553300', padding:'6px 8px', marginBottom:'6px', color:'#FF9933', fontSize:'11px' },
  success: { background:'#001a00', border:'1px solid #336633', padding:'6px 8px', marginBottom:'6px', color:'#33FF33', fontSize:'11px' },
  input: { background:'transparent', border:'none', borderBottom:'1px solid #3399FF', color:'#3399FF', fontFamily:"'Courier New',monospace", fontSize:'12px', outline:'none', width:'16ch' },
};

// ── PACKET DATA ──────────────────────────────────────────────────────────────
const PACKETS = [
  { id:1, dir:'S→C', desc:'IAC DO TERMINAL-TYPE (negotiation)', vuln:'PLAINTEXT NEGOTIATION — PORT 23',
    bytes:[IAC,DO,0x18,IAC,DO,0x19,IAC,DO,0x1D,IAC,WILL,0x18],
    note:'Server sends terminal type negotiation unencrypted. Port 23 = Telnet. No TLS.' },
  { id:2, dir:'C→S', desc:'CLIENT TERMINAL-TYPE: IBM-3279-2-E', vuln:'DEVICE FINGERPRINT EXPOSED',
    bytes:[IAC,SB,0x18,0x00,0x49,0x42,0x4D,0x2D,0x33,0x32,0x37,0x39,0x2D,0x32,IAC,SE],
    ascii:'IBM-3279-2-E (color terminal, 80×24)',
    note:'Terminal model reveals OS/hardware. Attacker narrows exploit selection. LU name also exposed here.' },
  { id:3, dir:'C→S', desc:'⚠ SIGNON: OPERID=JSMITH PASSWORD=DVCA', vuln:'⚠ CLEARTEXT CREDENTIALS',
    bytes:[0x11,0x4B,0xC1,0xF0,0xD1,0xE2,0xD4,0xC9,0xE3,0xC8,0x11,0x4B,0xD9,0xC4,0xE5,0xC3,0xC1,0xF0,0xF0,0xF0,0x7D],
    ascii:'OperatorID="JSMITH" Password="DVCA" AID=ENTER',
    note:'VULN #2: Credentials in EBCDIC plaintext. "DVCA" is a default vendor password. Trivially decoded via Wireshark tcp.port==23.' },
  { id:4, dir:'S→C', desc:'SIGNON ACK — WELCOME SCREEN', vuln:'SESSION DATA UNENCRYPTED',
    bytes:[0x11,0x40,0x40,0xC2,0xC1,0xD5,0xD2,0x40,0xD4,0xC1,0xE2,0xE3,0xC5,0xD9,0x11,0x4C,0x40,0xE2,0xC9,0xC7,0xD5,0xD6,0xD5],
    ascii:'BANKMASTER/VS ... SIGNON SUCCESSFUL',
    note:'Full screen data sent unencrypted. Every character displayed to the operator is visible to attacker.' },
  { id:5, dir:'C→S', desc:'⚠ CUSTMNT INQUIRY: CUSTOMER 10000001', vuln:'⚠ PII LOOKUP ON WIRE',
    bytes:[0x11,0x5C,0xF0,0xF1,0xF0,0xF0,0xF0,0xF0,0xF0,0xF0,0xF1,0x7D],
    ascii:'CUSTOMER-ID="10000001" AID=PF8(INQUIRE)',
    note:'Customer lookup visible. Attacker can map operator activity patterns in real-time.' },
  { id:6, dir:'S→C', desc:'⚠ CUSTMNT RESPONSE — FULL PII RECORD', vuln:'⚠ NI NUMBER, DOB, ADDRESS PLAINTEXT',
    bytes:[0x11,0x5C,0xF0,0xC8,0xC1,0xD9,0xD9,0xC9,0xE2,0xD6,0xD5,0x11,0x60,0xF0,0xF1,0xF2,0x61,0xF0,0xF4,0x61,0xF5,0xF8,0x11,0x64,0xF0,0xD1,0xD9,0xF5,0xF7,0xF4,0xF8,0xF2,0xF1,0xC1],
    ascii:'SURNAME=HARRISON  DOB=12/04/58  NI=JR574821A  ADDR=14 ELMWOOD AVENUE W8 6PP',
    note:'VULN #1: Full PII record in plaintext EBCDIC. GDPR breach. One Wireshark filter exposes all customers.' },
  { id:7, dir:'C→S', desc:'⚠ TRANPST — DR £450.00 ACCT 1000000101', vuln:'⚠ FINANCIAL TRANSACTION UNENCRYPTED',
    bytes:[0x11,0x5C,0xF0,0xF1,0xF0,0xF0,0xF0,0xF0,0xF0,0xF0,0xF1,0xF0,0xF1,0x11,0x60,0xF0,0xC4,0xD9,0x11,0x64,0xF0,0xF4,0xF5,0xF0,0x4B,0xF0,0xF0,0x7D],
    ascii:'ACCOUNT=1000000101  TYPE=DR  AMOUNT=450.00  AID=PF5(POST)',
    note:'MITM attacker can modify the amount byte before it reaches the server. No integrity check on the stream.' },
  { id:8, dir:'C→S', desc:'⚠ PROTECTED FIELD OVERFLOW ATTACK', vuln:'⚠ BUFFER OVERFLOW INTO SECURITY FLAGS',
    bytes:[0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0x41,0xE8,0xE8,0xC4],
    ascii:'"AAAAAAAAAAAAAAAAAAAA" + Y(0xE8) + Y(0xE8) + D(0xC4) → SECURITY-CONTROL-FLAGS overwritten',
    note:'COBOL: USER-INPUT(100) adjacent to SECURITY-CONTROL-FLAGS in memory. AUTHENTICATED-FLAG and ADMIN-FLAG set to Y.' },
];

// ── LU NAMES (harvest wordlist — from hack3270/injections/lu-names.txt) ──────
const LU_NAMES = ['CONSOLE','CICSA01','CICSA02','CICSA03','CICSB01','CICSB02','LU001','LU002',
  'VTAM001','ADMIN01','SYS001','BATCH01','BATCH02','OPER001','OPER002','TERM001','TERM042',
  'BANKOP1','BANKOP2','AUTHSVR','SYSOP01','LT0042','LT0001','LT0099','NCBBANK1'];

// ── CREDENTIALS WORDLISTS (from hack3270/injections/) ────────────────────────
const DEFAULT_USERIDS = ['DVCA','CICS','TEST','BATCH','ADMIN','SYS1','IBMUSER','RACF',
  'OPER','OPERATOR','SYSADM','SYSPROG','MASTER','CICSUSR','CICSADM'];
const DEFAULT_PASSWORDS = ['DVCA','CICS','TEST','BATCH','PASS','PASSWORD','IBM','SECRET',
  'ADMIN','SYSADM','CHANGE','CHANGEIT','INITIAL','RACF','12345678','IBMPASS'];

// ── COMMAREA MUTATIONS (State Fuzzer) ────────────────────────────────────────
const MUTATIONS = [
  { id:'length_plus_1', label:'LENGTH+1', desc:'Original COMMAREA + 1 byte — tests EIBCALEN check', color:'#FF9933' },
  { id:'length_double', label:'LENGTH×2', desc:'COMMAREA doubled — buffer overflow in RECEIVE MAP', color:'#FF3333' },
  { id:'type_confusion', label:'TYPE CONFUSE', desc:'Numeric fields replaced with alpha — tests PIC 9 validation', color:'#FF9933' },
  { id:'extra_sba', label:'EXTRA SBA', desc:'Phantom field appended — tests BMS field count validation', color:'#FF9933' },
  { id:'step_swap', label:'STEP SWAP', desc:'Replay step 0 input at step N — state desynchronisation', color:'#FF3333' },
  { id:'null_flood', label:'NULL FLOOD', desc:'All COMMAREA bytes set to 0x00 — tests null handling', color:'#AAFFAA' },
];

const COMMAREA_FLOWS = [
  { id:'CUST-INQ', steps:['CESN LOGIN','BKGMENU','CUSTMNT-SCREEN','CUSTMNT-RESULT'], fields:['CUSTOMER-ID','OPERATOR-ID','SCREEN-STATE','RETURN-TRANSID'] },
  { id:'TRAN-POST', steps:['BKGMENU','TRANPST-ENTRY','TRANPST-CONFIRM','TRANPST-RESULT'], fields:['ACCOUNT-NO','TRAN-TYPE','AMOUNT-WS','AUTH-TOKEN-WS'] },
  { id:'ACCT-MOD', steps:['BKGMENU','ACCTMNT-INQ','ACCTMNT-MOD','ACCTMNT-CONFIRM'], fields:['ACCOUNT-NO','NEW-LIMIT','OPERATOR-CLASS','SCREEN-STATE'] },
];

// ── QUERY REPLY PROFILES ──────────────────────────────────────────────────────
const QR_PRESETS = [
  { id:'normal', label:'NORMAL (80×24)', rows:24, cols:80, color:true, highlight:true },
  { id:'large', label:'OVERFLOW (62×160)', rows:62, cols:160, color:false, highlight:false },
  { id:'minimal', label:'MINIMAL (12×40)', rows:12, cols:40, color:false, highlight:false },
  { id:'mono', label:'MONO (24×80 no colour)', rows:24, cols:80, color:false, highlight:false },
];

// ── ESM FINDINGS DATABASE ─────────────────────────────────────────────────────
const ESM_PATTERNS = [
  { code:'DFHCE3530', severity:'HIGH', meaning:'Username enumeration oracle — CICS pre-5.1 tells "userid invalid" vs "password invalid" separately', cwe:'CWE-204' },
  { code:'ICH408I', severity:'INFO', meaning:'RACF confirmed as ESM (not ACF2 or TopSecret)', cwe:'CWE-200' },
  { code:'DFHCE3520', severity:'HIGH', meaning:'Account state leak — distinguishes REVOKED from BAD-PASSWORD', cwe:'CWE-204' },
  { code:'IEA095I', severity:'MED', meaning:'RACF without KDFAES — passwords limited to 8 chars, no mixed case', cwe:'CWE-916' },
  { code:'DFHAC2206', severity:'MED', meaning:'Program not found — reveals installed program names via error messages', cwe:'CWE-209' },
  { code:'CESF LOGOFF', severity:'LOW', meaning:'Sign-off transaction visible — session lifecycle exposed', cwe:'CWE-319' },
  { code:'DFHSN1800', severity:'HIGH', meaning:'CICS SNA/VTAM session table exposed in error — LU names leaked', cwe:'CWE-200' },
];

// ─────────────────────────────────────────────────────────────────────────────
// TAB COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────

function PacketAnalyser() {
  const [selected, setSelected] = useState(null);
  const [captureLog, setCaptureLog] = useState([]);
  const [capturing, setCapturing] = useState(false);
  const [filter, setFilter] = useState('ALL');
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!capturing) return;
    let idx = 0;
    const t = setInterval(() => {
      if (idx < PACKETS.length) { setCaptureLog(p => [...p, PACKETS[idx++]]); }
      else { clearInterval(t); setCapturing(false); }
    }, 800);
    return () => clearInterval(t);
  }, [capturing]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }); }, [captureLog]);

  const shown = filter === 'ALL' ? captureLog : captureLog.filter(p => p.vuln?.includes('⚠'));

  return (
    <div style={{ display:'flex', flex:1, overflow:'hidden' }}>
      <div style={{ width:'380px', borderRight:'1px solid #336633', overflowY:'auto', flexShrink:0 }}>
        <div style={{ padding:'4px 8px', borderBottom:'1px solid #224422', display:'flex', gap:'6px', background:'#000800', flexWrap:'wrap' }}>
          <button onClick={() => { setCaptureLog([]); setCapturing(true); setSelected(null); }} disabled={capturing}
            style={S.btn(!capturing,'#AAFFAA')}>{capturing ? '⏺ LIVE...' : '▶ CAPTURE'}</button>
          <button onClick={() => { setCaptureLog(PACKETS); setSelected(null); }} style={S.btn(false)}>LOAD ALL</button>
          <button onClick={() => setCaptureLog([])} style={S.btn(false,'#FF3333')}>CLR</button>
          <button onClick={() => setFilter(f => f==='ALL'?'VULN':'ALL')} style={S.btn(filter==='VULN','#FF9933')}>
            {filter==='VULN'?'SHOW ALL':'VULN ONLY'}
          </button>
        </div>
        <div style={{ display:'flex', gap:'6px', padding:'2px 6px', borderBottom:'1px solid #224422', color:'#668866', fontSize:'10px' }}>
          <span style={{width:'3ch'}}>#</span><span style={{width:'4ch'}}>DIR</span><span style={{flex:1}}>DESCRIPTION</span>
        </div>
        {shown.length === 0 && <div style={{color:'#668866',padding:'8px',fontSize:'11px'}}>Press CAPTURE or LOAD ALL</div>}
        {shown.map((pkt,i) => (
          <div key={pkt.id} onClick={() => setSelected(pkt)} style={{
            padding:'3px 6px', borderBottom:'1px solid #111', cursor:'pointer',
            background: selected?.id===pkt.id ? '#002200' : pkt.vuln?.includes('⚠') ? '#1a0800' : '#000',
            borderLeft: pkt.vuln?.includes('⚠') ? '3px solid #FF9933' : '3px solid transparent',
          }}>
            <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
              <span style={{color:'#668866',width:'3ch',fontSize:'10px'}}>{String(i+1).padStart(2,'0')}</span>
              <span style={{color:pkt.dir==='S→C'?'#AAFFAA':'#3399FF',width:'4ch',fontSize:'10px'}}>{pkt.dir}</span>
              <span style={{color:'#33FF33',flex:1,fontSize:'10px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{pkt.desc}</span>
            </div>
            {pkt.vuln && <div style={{color:'#FF9933',fontSize:'10px',paddingLeft:'7ch'}}>{pkt.vuln}</div>}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div style={{ flex:1, overflowY:'auto', padding:'6px 8px' }}>
        {!selected ? <div style={{color:'#668866',marginTop:'16px'}}>← SELECT A PACKET TO INSPECT</div> : (
          <>
            <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'4px'}}>PKT #{selected.id} — {selected.desc}</div>
            <div style={S.warn}><b>VULNERABILITY: </b><span style={{color:'#FFFF66'}}>{selected.vuln}</span></div>
            <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'2px',fontSize:'11px'}}>HEX DUMP</div>
            <div style={{...S.panel,overflowX:'auto'}}>
              <div style={{color:'#668866',fontSize:'10px',marginBottom:'2px'}}>OFFSET   00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F   ASCII</div>
              {hexDump(selected.bytes).map((row,i) => (
                <div key={i} style={{display:'flex',gap:'12px',color:'#33FF33',fontSize:'11px',lineHeight:'1.5',whiteSpace:'pre'}}>
                  <span style={{color:'#668866'}}>{row.offset}</span>
                  <span>{row.hex}</span>
                  <span style={{color:'#AAFFAA'}}>{row.ascii}</span>
                </div>
              ))}
            </div>
            {selected.ascii && (
              <>
                <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'2px',fontSize:'11px'}}>EBCDIC → ASCII DECODE</div>
                <div style={{...S.panel,color:'#AAFFAA',background:'#001a00',border:'1px solid #336633'}}>{selected.ascii}</div>
              </>
            )}
            <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'2px',fontSize:'11px'}}>SECURITY ANALYSIS</div>
            <div style={{...S.panel,color:'#33FF33',lineHeight:'1.8'}}>{selected.note}</div>
            {selected.id === 8 && (
              <div style={{marginTop:'6px',...S.warn,borderColor:'#FF3333'}}>
                <div style={{color:'#FF3333',fontWeight:'bold',marginBottom:'4px'}}>COBOL MEMORY LAYOUT AFTER OVERFLOW:</div>
                <pre style={{color:'#FFFF66',margin:0,fontSize:'11px'}}>{
`01  INPUT-DATA.
    05  USER-INPUT        PIC X(100)  ← 20×'A' + overflow
01  SECURITY-CONTROL-FLAGS.           ← ADJACENT IN MEMORY
    05  AUTHENTICATED-FLAG PIC X = 'Y'  ← OVERWRITTEN (0xE8)
    05  ADMIN-FLAG         PIC X = 'Y'  ← OVERWRITTEN (0xE8)
    05  DEBUG-FLAG         PIC X = 'D'  ← OVERWRITTEN (0xC4)`
                }</pre>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function LuNameSpoofer() {
  const [mode, setMode] = useState('HARVEST'); // HARVEST | SINGLE | WORDLIST
  const [harvested, setHarvested] = useState([]);
  const [harvesting, setHarvesting] = useState(false);
  const [target, setTarget] = useState('');
  const [wordlistIdx, setWordlistIdx] = useState(0);
  const [results, setResults] = useState([]);
  const [running, setRunning] = useState(false);

  const OUTCOMES = {
    'CONSOLE': { screen:'MAIN MENU', win:true },
    'CICSA01': { screen:'MAIN MENU', win:true },
    'LT0042':  { screen:'MAIN MENU', win:true },
    'ADMIN01': { screen:'ADMIN PANEL', win:true },
    'BANKOP1': { screen:'MAIN MENU', win:true },
    'SYSOP01': { screen:'SYSTEM OPERATIONS', win:true },
  };

  const startHarvest = () => {
    setHarvesting(true); setHarvested([]);
    let i = 0;
    const t = setInterval(() => {
      if (i < 8) { setHarvested(h => [...h, LU_NAMES[Math.floor(Math.random()*LU_NAMES.length)]]); i++; }
      else { clearInterval(t); setHarvesting(false); }
    }, 400);
  };

  const tryWordlist = () => {
    if (running) return;
    setRunning(true); setResults([]);
    let i = 0;
    const t = setInterval(() => {
      if (i < LU_NAMES.length) {
        const lu = LU_NAMES[i];
        const outcome = OUTCOMES[lu] || { screen:'CESN LOGIN', win:false };
        setResults(r => [...r, { lu, ...outcome }]);
        setWordlistIdx(i);
        i++;
      } else { clearInterval(t); setRunning(false); }
    }, 120);
  };

  const trySingle = () => {
    if (!target) return;
    const outcome = OUTCOMES[target.toUpperCase()] || { screen:'CESN LOGIN', win:false };
    setResults([{ lu:target.toUpperCase(), ...outcome }]);
  };

  return (
    <div style={{ flex:1, overflowY:'auto', padding:'8px' }}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'4px'}}>LU-NAME SPOOFING (RFC 2355 PRESET-TERMINAL ATTACK)</div>
      <div style={S.warn}>
        If CICS region binds USERID→TERMID/LU, spoofing a known LU name bypasses CESN signon entirely.
        This proxy splices the LU name into the DEVICE-TYPE REQUEST before the host sees it.
        Win condition: results show "MAIN MENU" instead of "CESN LOGIN".
      </div>

      <div style={{marginBottom:'10px',display:'flex',gap:'6px'}}>
        {['HARVEST','SINGLE','WORDLIST'].map(m => (
          <button key={m} onClick={() => setMode(m)} style={S.btn(mode===m,'#AAFFAA')}>{m} MODE</button>
        ))}
      </div>

      {mode === 'HARVEST' && (
        <div style={S.panel}>
          <div style={{color:'#668866',marginBottom:'6px',fontSize:'11px'}}>
            Passive mode — watch the VTAM LU assignments as terminals connect. Builds your wordlist.
          </div>
          <button onClick={startHarvest} disabled={harvesting} style={S.btn(!harvesting,'#33FF33')}>
            {harvesting ? '⏺ HARVESTING...' : '▶ START HARVEST'}
          </button>
          {harvested.length > 0 && (
            <div style={{marginTop:'8px'}}>
              <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>HARVESTED LU NAMES ({harvested.length}):</div>
              {harvested.map((lu,i) => (
                <div key={i} style={{color:'#33FF33',fontSize:'11px'}}>  {lu.padEnd(12)}  ← VTAM ASSIGNED</div>
              ))}
            </div>
          )}
        </div>
      )}

      {mode === 'SINGLE' && (
        <div style={S.panel}>
          <div style={{color:'#668866',marginBottom:'6px',fontSize:'11px'}}>
            Type a specific LU name to spoof (from harvest or known list). Proxy splices into DEVICE-TYPE REQUEST.
          </div>
          <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'8px'}}>
            <span style={{color:'#AAFFAA'}}>LU TARGET ==&gt;</span>
            <input value={target} onChange={e => setTarget(e.target.value.toUpperCase().slice(0,8))}
              maxLength={8} style={{...S.input,width:'10ch'}} />
            <button onClick={trySingle} style={S.btn(true,'#33FF33')}>SET TARGET + RECONNECT</button>
          </div>
          {results.length > 0 && (
            <div style={results[0].win ? S.success : S.warn}>
              LU: <b>{results[0].lu}</b> → Screen: <b style={{color:results[0].win?'#33FF33':'#FF9933'}}>{results[0].screen}</b>
              {results[0].win && ' ← ✓ BYPASSED SIGNON!'}
            </div>
          )}
          <div style={{marginTop:'8px',color:'#668866',fontSize:'10px'}}>
            KNOWN BYPASS LUs (from this system): CONSOLE, CICSA01, LT0042, ADMIN01, BANKOP1, SYSOP01
          </div>
        </div>
      )}

      {mode === 'WORDLIST' && (
        <div style={S.panel}>
          <div style={{color:'#668866',marginBottom:'6px',fontSize:'11px'}}>
            Iterates 686 common LU name patterns from injections/lu-names.txt. "Try Next" logic — each attempt reconnects.
          </div>
          <button onClick={tryWordlist} disabled={running} style={S.btn(!running,'#33FF33')}>
            {running ? `⏺ TRYING ${LU_NAMES[wordlistIdx]}... (${wordlistIdx+1}/${LU_NAMES.length})` : '▶ START WORDLIST ATTACK'}
          </button>
          {results.length > 0 && (
            <div style={{marginTop:'8px',maxHeight:'200px',overflowY:'auto'}}>
              <div style={{color:'#668866',fontSize:'10px',marginBottom:'4px'}}>LU NAME → LANDING SCREEN</div>
              {results.map((r,i) => (
                <div key={i} style={{display:'flex',gap:'12px',fontSize:'11px',lineHeight:'1.6',
                  color:r.win?'#33FF33':'#668866'}}>
                  <span style={{width:'12ch'}}>{r.lu}</span>
                  <span>→</span>
                  <span style={{color:r.win?'#AAFFAA':'#668866'}}>{r.screen}</span>
                  {r.win && <span style={{color:'#33FF33'}}>← WIN</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CredBrute() {
  const [mode, setMode] = useState('DEFAULT'); // DEFAULT | CUSTOM | INJECT
  const [uid, setUid] = useState('');
  const [pass, setPass] = useState('');
  const [uidList, setUidList] = useState('DVCA');
  const [passList, setPassList] = useState('DVCA');
  const [results, setResults] = useState([]);
  const [running, setRunning] = useState(false);
  const [injectField, setInjectField] = useState('OPERATOR-ID');
  const [injectPayload, setInjectPayload] = useState("' OR '1'='1");

  const VALID = { DVCA:'DVCA', CICS:'CICS', TEST:'TEST', BATCH:'BATCH', ADMIN:'ADMIN' };

  const runDefault = () => {
    setRunning(true); setResults([]);
    let i = 0;
    const pairs = DEFAULT_USERIDS.flatMap(u => DEFAULT_PASSWORDS.map(p => [u,p])).slice(0,30);
    const t = setInterval(() => {
      if (i < pairs.length) {
        const [u,p] = pairs[i];
        const success = VALID[u] === p;
        setResults(r => [...r, { u, p, success }]);
        i++;
      } else { clearInterval(t); setRunning(false); }
    }, 80);
  };

  const tryCustom = () => {
    const u = uid.toUpperCase(), p = pass.toUpperCase();
    const success = VALID[u] === p || (p.length > 0 && p === u);
    setResults([{ u, p, success }]);
  };

  const tryInject = () => {
    const hit = injectPayload.includes("'") || injectPayload.includes('--') || injectPayload.includes('OR');
    setResults([{
      u: injectField,
      p: injectPayload,
      success: hit,
      note: hit ? 'SQL INJECTION SUCCESSFUL — bypassed COBOL EVALUATE check' : 'Payload rejected by input length restriction'
    }]);
  };

  return (
    <div style={{ flex:1, overflowY:'auto', padding:'8px' }}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'4px'}}>CREDENTIAL BRUTE FORCE + FIELD INJECTION</div>
      <div style={S.warn}>
        hack3270 injects wordlists from injections/common-userids.txt + injections/default-passwords.txt directly into
        the 3270 data stream. No lockout on this system (VULN #2).
      </div>
      <div style={{marginBottom:'10px',display:'flex',gap:'6px'}}>
        {['DEFAULT','CUSTOM','INJECT'].map(m => (
          <button key={m} onClick={() => { setMode(m); setResults([]); }} style={S.btn(mode===m,'#AAFFAA')}>{m}</button>
        ))}
      </div>

      {mode === 'DEFAULT' && (
        <div style={S.panel}>
          <div style={{color:'#668866',fontSize:'11px',marginBottom:'6px'}}>
            Spray 30 credential pairs from default-passwords.txt × common-userids.txt. No lockout enforced.
          </div>
          <button onClick={runDefault} disabled={running} style={S.btn(!running,'#33FF33')}>
            {running ? '⏺ SPRAYING...' : '▶ LAUNCH SPRAY ATTACK'}
          </button>
          {results.length > 0 && (
            <div style={{marginTop:'8px',maxHeight:'200px',overflowY:'auto'}}>
              {results.map((r,i) => (
                <div key={i} style={{display:'flex',gap:'12px',fontSize:'11px',lineHeight:'1.6',
                  color:r.success?'#33FF33':'#668866'}}>
                  <span style={{width:'10ch'}}>{r.u}</span>
                  <span style={{width:'12ch'}}>{r.p}</span>
                  <span style={{color:r.success?'#AAFFAA':'#336633'}}>{r.success?'✓ VALID':'✗'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {mode === 'CUSTOM' && (
        <div style={S.panel}>
          <div style={{color:'#668866',fontSize:'11px',marginBottom:'6px'}}>Test a specific credential pair.</div>
          <div style={{display:'flex',gap:'12px',alignItems:'center',marginBottom:'6px',flexWrap:'wrap'}}>
            <div><span style={{color:'#AAFFAA'}}>OPERATOR ==&gt; </span>
              <input value={uid} onChange={e=>setUid(e.target.value.toUpperCase().slice(0,8))} style={S.input} maxLength={8} /></div>
            <div><span style={{color:'#AAFFAA'}}>PASSWORD ==&gt; </span>
              <input type="password" value={pass} onChange={e=>setPass(e.target.value.slice(0,12))} style={S.input} maxLength={12} /></div>
            <button onClick={tryCustom} style={S.btn(true,'#33FF33')}>TEST</button>
          </div>
          {results.map((r,i) => (
            <div key={i} style={r.success?S.success:S.warn}>
              {r.u}/{r.p} → {r.success ? '✓ ACCESS GRANTED' : '✗ ACCESS DENIED'}
            </div>
          ))}
        </div>
      )}

      {mode === 'INJECT' && (
        <div style={S.panel}>
          <div style={{color:'#668866',fontSize:'11px',marginBottom:'6px'}}>
            Inject a DB2 SQL payload into a 3270 input field. Tests whether COBOL EVALUATE sanitises input.
          </div>
          <div style={{marginBottom:'6px'}}>
            <span style={{color:'#AAFFAA'}}>TARGET FIELD: </span>
            {['OPERATOR-ID','CUSTOMER-ID','ACCOUNT-NO'].map(f => (
              <button key={f} onClick={() => setInjectField(f)} style={S.btn(injectField===f,'#FF9933')}>{f}</button>
            ))}
          </div>
          <div style={{marginBottom:'8px'}}>
            <span style={{color:'#AAFFAA'}}>PAYLOAD ==&gt; </span>
            <input value={injectPayload} onChange={e=>setInjectPayload(e.target.value)} style={{...S.input,width:'36ch'}} />
          </div>
          <div style={{color:'#668866',fontSize:'10px',marginBottom:'6px'}}>
            Common payloads: &nbsp;
            {["' OR '1'='1","' OR 1=1--","'; DROP TABLE CUSTOMER;--","' UNION SELECT customer_id,ni_number FROM CUSTOMER--"].map(p => (
              <span key={p} onClick={() => setInjectPayload(p)} style={{color:'#3399FF',cursor:'pointer',marginRight:'8px'}}>{p}</span>
            ))}
          </div>
          <button onClick={tryInject} style={S.btn(true,'#FF3333')}>INJECT PAYLOAD</button>
          {results.map((r,i) => (
            <div key={i} style={r.success?S.warn:S.panel}>
              <div style={{color:r.success?'#FF3333':'#AAFFAA',fontWeight:'bold'}}>{r.success?'⚠ INJECTION HIT':'✗ BLOCKED'}</div>
              <div style={{color:'#33FF33',fontSize:'11px',marginTop:'2px'}}>{r.note}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StateFuzzer() {
  const [selectedFlow, setSelectedFlow] = useState(null);
  const [recording, setRecording] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const [selectedMutation, setSelectedMutation] = useState(null);
  const [results, setResults] = useState([]);
  const [fuzzing, setFuzzing] = useState(false);

  const FUZZ_OUTCOMES = {
    'length_plus_1': { color:'#FF9933', result:'SCREEN_DIFFERS', detail:'COMMAREA length mismatch — EIBCALEN not checked — app processed oversized data' },
    'length_double': { color:'#FF3333', result:'ABEND ASRA', detail:'DFHAC0002 ASRA — Access violation in RECEIVE MAP. Buffer overflow confirmed. Program CUSTMNT abended.' },
    'type_confusion': { color:'#FF9933', result:'SCREEN_DIFFERS', detail:'COBOL EVALUATE fell through — PIC 9 field accepted alpha. Screen shows INVREQ but data stored.' },
    'extra_sba': { color:'#FF9933', result:'SCREEN_DIFFERS', detail:'Extra SBA caused BMS field count mismatch. DFHBM0101 warning in spool.' },
    'step_swap': { color:'#FF3333', result:'ABEND ASRD', detail:'State desync — app expected step 2 COMMAREA, got step 0. XCTL to wrong program.' },
    'null_flood': { color:'#AAFFAA', result:'IDENTICAL', detail:'App initialises COMMAREA on entry — null flood had no effect.' },
  };

  const startRecord = () => { setRecording(true); setRecorded(false); setResults([]); };
  const stopRecord = () => { setRecording(false); setRecorded(true); };

  const fuzz = () => {
    if (!selectedMutation || !selectedFlow || !recorded || fuzzing) return;
    setFuzzing(true); setResults([]);
    const outcome = FUZZ_OUTCOMES[selectedMutation.id];
    setTimeout(() => {
      setResults([{
        flow: selectedFlow.id,
        mutation: selectedMutation.id,
        ...outcome
      }]);
      setFuzzing(false);
    }, 1800);
  };

  return (
    <div style={{ flex:1, overflowY:'auto', padding:'8px' }}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'4px'}}>COMMAREA STATE FUZZER (PSEUDO-CONVERSATIONAL)</div>
      <div style={S.warn}>
        CICS pseudo-conversational apps round-trip state through hidden screen fields between RETURN TRANSID calls.
        Record a flow, analyze COMMAREA fields, then mutate and replay to find ABEND conditions.
      </div>

      <div style={{display:'flex',gap:'16px',flexWrap:'wrap'}}>
        {/* Flow selection */}
        <div style={{flex:'0 0 220px'}}>
          <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>1. SELECT FLOW TO RECORD</div>
          {COMMAREA_FLOWS.map(f => (
            <div key={f.id} onClick={() => { setSelectedFlow(f); setRecorded(false); setResults([]); }}
              style={{...S.panel, cursor:'pointer', border:`1px solid ${selectedFlow?.id===f.id?'#33FF33':'#224422'}`, marginBottom:'4px'}}>
              <div style={{color:'#AAFFAA',fontWeight:'bold'}}>{f.id}</div>
              <div style={{color:'#668866',fontSize:'10px'}}>{f.steps.join(' → ')}</div>
            </div>
          ))}
        </div>

        {/* Record & Analyze */}
        <div style={{flex:1}}>
          <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>2. RECORD FLOW</div>
          <div style={S.panel}>
            <button onClick={startRecord} disabled={recording||!selectedFlow} style={S.btn(recording,'#FF9933')}>
              {recording ? '⏺ RECORDING...' : '● RECORD'}
            </button>
            <button onClick={stopRecord} disabled={!recording} style={{...S.btn(!recording,'#AAFFAA'),marginLeft:'6px'}}>■ STOP</button>
            {recording && selectedFlow && (
              <div style={{color:'#FF9933',fontSize:'11px',marginTop:'6px'}}>
                Intercepting flow: {selectedFlow.id}<br/>
                {selectedFlow.steps.map((s,i) => <div key={i} style={{color:'#668866',paddingLeft:'8px'}}>{i+1}. {s}</div>)}
              </div>
            )}
            {recorded && selectedFlow && (
              <div style={{...S.success,marginTop:'6px'}}>
                ✓ FLOW RECORDED — {selectedFlow.fields.length} COMMAREA fields identified:<br/>
                {selectedFlow.fields.map((f,i) => <div key={i} style={{color:'#AAFFAA',paddingLeft:'8px',fontSize:'11px'}}>{i+1}. {f}</div>)}
              </div>
            )}
          </div>

          {recorded && (
            <>
              <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px',marginTop:'8px'}}>3. SELECT MUTATION + FUZZ</div>
              <div style={{display:'flex',flexWrap:'wrap',gap:'4px',marginBottom:'8px'}}>
                {MUTATIONS.map(m => (
                  <button key={m.id} onClick={() => setSelectedMutation(m)} style={S.btn(selectedMutation?.id===m.id,m.color)}>
                    {m.label}
                  </button>
                ))}
              </div>
              {selectedMutation && (
                <div style={{...S.panel,marginBottom:'6px',color:'#668866',fontSize:'11px'}}>
                  {selectedMutation.desc}
                </div>
              )}
              <button onClick={fuzz} disabled={!selectedMutation||fuzzing} style={S.btn(!fuzzing,'#FF3333')}>
                {fuzzing ? '⏺ FUZZING...' : '▶ FUZZ SELECTED TARGET'}
              </button>
            </>
          )}

          {results.length > 0 && (
            <div style={{...S.panel,marginTop:'8px',border:`1px solid ${results[0].color}`,borderLeft:`4px solid ${results[0].color}`}}>
              <div style={{color:results[0].color,fontWeight:'bold',fontSize:'12px',marginBottom:'4px'}}>
                {results[0].result === 'IDENTICAL' ? '⬜' : results[0].result.includes('ABEND') ? '🟥' : '🟧'} {results[0].result}
              </div>
              <div style={{color:'#AAFFAA',fontSize:'11px'}}>{results[0].detail}</div>
              <div style={{color:'#668866',fontSize:'10px',marginTop:'4px'}}>
                FLOW: {results[0].flow} | MUTATION: {results[0].mutation}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function QueryReplyLiar() {
  const [preset, setPreset] = useState(null);
  const [rows, setRows] = useState('24');
  const [cols, setCols] = useState('80');
  const [denyColor, setDenyColor] = useState(false);
  const [denyHighlight, setDenyHighlight] = useState(false);
  const [armed, setArmed] = useState(false);
  const [indFile, setIndFile] = useState(false);
  const [indCaptures, setIndCaptures] = useState([]);
  const [simResult, setSimResult] = useState(null);

  const applyPreset = (p) => {
    setPreset(p); setRows(String(p.rows)); setCols(String(p.cols));
    setDenyColor(!p.color); setDenyHighlight(!p.highlight);
  };

  const arm = () => {
    setArmed(true);
    const r = parseInt(rows)||24, c = parseInt(cols)||80;
    const bufSize = r * c;
    let result = null;
    if (bufSize > 5000) result = { type:'ABEND', msg:`ASRA — BMS allocated ${bufSize} byte buffer (${r}×${c}). Fixed-size COMMAREA overflowed. DFHAC0002.` };
    else if (denyColor && denyHighlight) result = { type:'SCREEN_DIFFERS', msg:`Color+highlight denied — hidden DRK fields now visible. Black-on-black hiding bypassed.` };
    else result = { type:'IDENTICAL', msg:`No exploitable difference detected for ${r}×${c} terminal.` };
    setSimResult(result);
  };

  const captureIndFile = () => {
    setIndCaptures(c => [...c, {
      time: new Date().toTimeString().slice(0,8),
      file: 'SYS1.PAYROLL.REPORT',
      size: '14,820 bytes',
      user: 'BATCH01',
      dest: '_captures/indfile_capture_' + Date.now() + '.bin'
    }]);
  };

  return (
    <div style={{ flex:1, overflowY:'auto', padding:'8px' }}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'4px'}}>STRUCTURED FIELDS: QUERY REPLY LYING + IND$FILE INTERCEPT</div>
      <div style={S.warn}>
        When CICS sends Read Partition Query, the proxy answers FOR YOU with manipulated terminal capabilities.
        BMS allocates buffers based on Usable Area — lying about dimensions can cause ASRA abends.
      </div>

      <div style={{display:'flex',gap:'16px',flexWrap:'wrap'}}>
        <div style={{flex:'0 0 300px'}}>
          <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>TERMINAL CAPABILITY PRESETS</div>
          {QR_PRESETS.map(p => (
            <button key={p.id} onClick={() => applyPreset(p)} style={{...S.btn(preset?.id===p.id,'#AAFFAA'),display:'block',width:'100%',marginBottom:'4px',textAlign:'left'}}>
              {p.label}
            </button>
          ))}
          <div style={{marginTop:'10px',color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>CUSTOM DIMENSIONS</div>
          <div style={{display:'flex',gap:'8px',alignItems:'center',fontSize:'11px',color:'#AAFFAA',marginBottom:'4px'}}>
            <span>ROWS:</span>
            <input value={rows} onChange={e=>setRows(e.target.value)} style={{...S.input,width:'5ch'}} maxLength={3} />
            <span>COLS:</span>
            <input value={cols} onChange={e=>setCols(e.target.value)} style={{...S.input,width:'5ch'}} maxLength={3} />
          </div>
          <div style={{display:'flex',gap:'8px',marginBottom:'8px'}}>
            <button onClick={() => setDenyColor(d=>!d)} style={S.btn(denyColor,'#FF9933')}>
              {denyColor ? '☑' : '☐'} DENY COLOR
            </button>
            <button onClick={() => setDenyHighlight(d=>!d)} style={S.btn(denyHighlight,'#FF9933')}>
              {denyHighlight ? '☑' : '☐'} DENY HIGHLIGHT
            </button>
          </div>
          <button onClick={arm} style={S.btn(armed,'#FF3333')}>ARM QUERY REPLY LIAR + RECONNECT</button>
          {simResult && (
            <div style={{...S.panel,marginTop:'8px',border:`1px solid ${simResult.type==='ABEND'?'#FF3333':simResult.type==='SCREEN_DIFFERS'?'#FF9933':'#336633'}`}}>
              <div style={{color:simResult.type==='ABEND'?'#FF3333':simResult.type==='SCREEN_DIFFERS'?'#FF9933':'#33FF33',fontWeight:'bold'}}>
                {simResult.type}
              </div>
              <div style={{color:'#AAFFAA',fontSize:'11px',marginTop:'2px'}}>{simResult.msg}</div>
            </div>
          )}
        </div>

        <div style={{flex:1}}>
          <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>IND$FILE CARBON COPY MODE</div>
          <div style={S.panel}>
            <div style={{color:'#668866',fontSize:'11px',marginBottom:'6px'}}>
              When armed, any IND$FILE GET/PUT operation passing through the proxy is silently copied to _captures/.
              Works even if the transfer is not your session.
            </div>
            <button onClick={() => setIndFile(f=>!f)} style={S.btn(indFile,'#FF9933')}>
              {indFile ? '■ DISARM CARBON COPY' : '▶ ARM CARBON COPY MODE'}
            </button>
            {indFile && (
              <>
                <div style={{...S.warn,marginTop:'6px'}}>⏺ CARBON COPY ACTIVE — monitoring IND$FILE transfers</div>
                <button onClick={captureIndFile} style={{...S.btn(true,'#3399FF'),marginTop:'4px'}}>
                  SIMULATE IND$FILE CAPTURE
                </button>
              </>
            )}
            {indCaptures.length > 0 && (
              <div style={{marginTop:'8px'}}>
                <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>CAPTURED FILES ({indCaptures.length}):</div>
                {indCaptures.map((c,i) => (
                  <div key={i} style={{...S.panel,background:'#001a00',marginBottom:'4px'}}>
                    <div style={{color:'#AAFFAA'}}>{c.file}</div>
                    <div style={{color:'#668866',fontSize:'10px'}}>USER: {c.user}  SIZE: {c.size}  TIME: {c.time}</div>
                    <div style={{color:'#3399FF',fontSize:'10px'}}>{c.dest}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function EsmFingerprint() {
  const [scanning, setScanning] = useState(false);
  const [findings, setFindings] = useState([]);
  const [txLog, setTxLog] = useState([]);

  const TX_SEQUENCE = [
    { tx:'CESN', input:'BADUSER/BADPASS', delay:400 },
    { tx:'CESN', input:'DVCA/WRONGPASS', delay:600 },
    { tx:'CUST', input:'10000001', delay:500 },
    { tx:'CEMT', input:'INQ TRAN(*)', delay:700 },
    { tx:'CECI', input:'EXEC CICS ASSIGN USERID(WS-UID)', delay:500 },
  ];

  const startScan = () => {
    setScanning(true); setFindings([]); setTxLog([]);
    let i = 0;
    const t = setInterval(() => {
      if (i < TX_SEQUENCE.length) {
        const tx = TX_SEQUENCE[i];
        setTxLog(l => [...l, tx]);
        // Reveal ESM findings progressively
        if (i === 0) setFindings(f => [...f, ESM_PATTERNS[0]]);
        if (i === 1) setFindings(f => [...f, ESM_PATTERNS[1], ESM_PATTERNS[2]]);
        if (i === 2) setFindings(f => [...f, ESM_PATTERNS[4]]);
        if (i === 3) setFindings(f => [...f, ESM_PATTERNS[6]]);
        i++;
      } else { clearInterval(t); setScanning(false); }
    }, 700);
  };

  const sevColor = { HIGH:'#FF3333', MED:'#FF9933', INFO:'#3399FF', LOW:'#668866' };

  return (
    <div style={{ flex:1, overflowY:'auto', padding:'8px' }}>
      <div style={{color:'#AAFFAA',fontWeight:'bold',marginBottom:'4px'}}>ESM PASSIVE FINGERPRINTING (RACF/ACF2/TopSecret)</div>
      <div style={S.warn}>
        Watches every screen for ESM-revealing error codes. Fully passive — no extra requests needed.
        DFHCE3530 = username oracle (pre-CICS-TS-5.1). ICH408I = RACF confirmed.
      </div>
      <div style={{display:'flex',gap:'16px',flexWrap:'wrap'}}>
        <div style={{flex:'0 0 300px'}}>
          <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>TRANSACTION SEQUENCE</div>
          <button onClick={startScan} disabled={scanning} style={S.btn(!scanning,'#33FF33')}>
            {scanning ? '⏺ SCANNING...' : '▶ START PASSIVE SCAN'}
          </button>
          {txLog.length > 0 && (
            <div style={{...S.panel,marginTop:'8px'}}>
              {txLog.map((tx,i) => (
                <div key={i} style={{color:'#33FF33',fontSize:'11px',lineHeight:'1.6'}}>
                  <span style={{color:'#3399FF'}}>[{tx.tx}]</span> {tx.input}
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{flex:1}}>
          <div style={{color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>ESM FINDINGS DOCK</div>
          {findings.length === 0 && <div style={{color:'#668866',fontSize:'11px'}}>No findings yet — start passive scan</div>}
          {findings.map((f,i) => (
            <div key={i} style={{...S.panel,marginBottom:'6px',borderLeft:`3px solid ${sevColor[f.severity]}`,background:'#000800'}}>
              <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'2px'}}>
                <span style={{color:sevColor[f.severity],fontWeight:'bold',fontSize:'11px'}}>{f.severity}</span>
                <span style={{color:'#FFFF99',fontWeight:'bold'}}>{f.code}</span>
                <span style={{color:'#668866',fontSize:'10px'}}>{f.cwe}</span>
              </div>
              <div style={{color:'#AAFFAA',fontSize:'11px'}}>{f.meaning}</div>
            </div>
          ))}
          {!scanning && findings.length > 0 && (
            <div style={S.success}>✓ ESM SCAN COMPLETE — {findings.length} findings. RACF confirmed. Username oracle active.</div>
          )}
        </div>
      </div>

      <div style={{marginTop:'12px',color:'#FFFF99',fontSize:'11px',marginBottom:'4px'}}>REFERENCE: ESM CODE DICTIONARY</div>
      <div style={{...S.panel}}>
        {ESM_PATTERNS.map((p,i) => (
          <div key={i} style={{display:'flex',gap:'10px',fontSize:'11px',lineHeight:'1.7',borderBottom:'1px solid #001100',paddingBottom:'2px',marginBottom:'2px'}}>
            <span style={{color:sevColor[p.severity],width:'5ch'}}>{p.severity}</span>
            <span style={{color:'#FFFF99',width:'14ch'}}>{p.code}</span>
            <span style={{color:'#AAFFAA',flex:1}}>{p.meaning}</span>
            <span style={{color:'#668866',fontSize:'10px'}}>{p.cwe}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── MAIN COMPONENT ────────────────────────────────────────────────────────────
const TABS = [
  { id:'PACKETS',   label:'PACKET CAPTURE', color:'#33FF33' },
  { id:'LU',        label:'LU SPOOF',       color:'#AAFFAA' },
  { id:'CREDS',     label:'CRED BRUTE',     color:'#3399FF' },
  { id:'FUZZER',    label:'STATE FUZZER',   color:'#FF9933' },
  { id:'QREPLY',    label:'QR LIAR/IND$',   color:'#FF9933' },
  { id:'ESM',       label:'ESM FINGERPRINT',color:'#FF3333' },
];

export default function Tn3270View({ operatorId, onBack }) {
  const [tab, setTab] = useState('PACKETS');

  return (
    <div style={{ flex:1, display:'flex', flexDirection:'column', fontFamily:"'Courier New', monospace", fontSize:'12px', paddingBottom:'52px', height:'100%' }}>
      {/* Header */}
      <div style={{ padding:'2px 8px', borderBottom:'1px solid #336633', color:'#AAFFAA', fontWeight:'bold', display:'flex', justifyContent:'space-between', background:'#001a00', flexShrink:0 }}>
        <span>HACK3270 ATTACK SIMULATOR — TN3270 PENTEST TOOLKIT</span>
        <span style={{color:'#FF9933'}}>PORT 23 — NO TLS/SSL</span>
        <span style={{color:'#33FF33'}}>PF3=MENU</span>
      </div>
      <div style={{color:'#668866',fontSize:'10px',padding:'1px 8px',background:'#000800',borderBottom:'1px solid #224422',flexShrink:0}}>
        Based on: github.com/gglessner/hack3270 v2.8.1 | MITM proxy | Field hacking | LU spoof | COMMAREA fuzz | ESM fingerprint | IND$FILE intercept
      </div>

      {/* Tab bar */}
      <div style={{ display:'flex', gap:'2px', padding:'4px 8px', borderBottom:'1px solid #336633', background:'#000800', flexShrink:0, flexWrap:'wrap' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{ ...S.btn(tab===t.id, t.color), fontSize:'11px', padding:'3px 10px' }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column' }}>
        {tab === 'PACKETS'  && <PacketAnalyser />}
        {tab === 'LU'       && <LuNameSpoofer />}
        {tab === 'CREDS'    && <CredBrute />}
        {tab === 'FUZZER'   && <StateFuzzer />}
        {tab === 'QREPLY'   && <QueryReplyLiar />}
        {tab === 'ESM'      && <EsmFingerprint />}
      </div>

      {/* Footer */}
      <div style={{ padding:'2px 8px', borderTop:'1px solid #336633', display:'flex', gap:'12px', background:'#000800', position:'absolute', bottom:0, left:0, right:0 }}>
        <button onClick={() => onBack('MENU')} style={S.btn(false)}>PF3 MENU</button>
        <span style={{color:'#668866',fontSize:'10px',lineHeight:'22px'}}>
          HACK3270 SIM | 6 ATTACK MODULES | PORT 23 PLAINTEXT | CWE-319 CWE-639 CWE-89 CWE-862
        </span>
      </div>
    </div>
  );
}