import React, { useState, useRef, useEffect } from 'react';
import { base44 } from '@/api/base44Client';
import { logAudit } from '@/lib/auditLogger';

// ── Authentic mainframe bulk processing screen ──────────────────────────────
// Simulates: BACS mortgage batch, CHAPS bulk transfers, credit card approvals
// Based on real 1980s-era clearing house and authorisation workflows

const S = {
  root: { flex: 1, padding: '6px 8px', fontFamily: "'Courier New', monospace", fontSize: '13px', paddingBottom: '60px', overflowY: 'auto', color: '#33FF33' },
  hdr: { color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', marginBottom: '2px' },
  sep: { color: '#33FF33', marginBottom: '6px' },
  label: { color: '#AAFFAA', fontWeight: 'bold' },
  val: { color: '#3399FF' },
  err: { color: '#FF3333', fontWeight: 'bold' },
  ok: { color: '#AAFFAA', fontWeight: 'bold' },
  warn: { color: '#FF9933' },
  dim: { color: '#668866' },
  inp: (w) => ({
    background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF',
    color: '#3399FF', fontFamily: "'Courier New', monospace", fontSize: '13px',
    outline: 'none', textTransform: 'uppercase', padding: 0, width: `${w}ch`,
  }),
  btn: (c = '#33FF33') => ({
    background: '#001100', border: `1px solid ${c}`, color: c,
    fontFamily: "'Courier New', monospace", fontSize: '12px',
    padding: '2px 10px', cursor: 'pointer', marginRight: '6px',
  }),
  row: { display: 'flex', gap: '12px', marginBottom: '3px', alignItems: 'center' },
  tableHead: { color: '#FFFF99', fontWeight: 'bold', borderBottom: '1px solid #336633', marginBottom: '4px', paddingBottom: '2px' },
  tableRow: (sel) => ({ color: sel ? '#AAFFAA' : '#33FF33', background: sel ? '#001800' : 'transparent', padding: '1px 0', cursor: 'pointer' }),
};

// ── Pre-built mortgage batch templates ──────────────────────────────────────
const MORTGAGE_TEMPLATES = [
  { id: 'MTG-2026-MAY', desc: 'MAY 2026 MORTGAGE COLLECTION RUN', count: 312, total: 487620.00, sortCode: '20-45-14', type: 'DEBIT',  schedule: 'DD=01', status: 'READY'   },
  { id: 'MTG-2026-APR', desc: 'APR 2026 MORTGAGE COLLECTION RUN', count: 309, total: 483250.50, sortCode: '20-45-14', type: 'DEBIT',  schedule: 'DD=01', status: 'COMPLETE' },
  { id: 'REM-2026-MAY', desc: 'MAY 2026 REDEMPTION SETTLEMENTS',   count:   8, total:  95400.00, sortCode: '30-98-12', type: 'CREDIT', schedule: 'DD=15', status: 'READY'   },
  { id: 'OFF-2026-MAY', desc: 'OFFSET ACCOUNT INTEREST POSTINGS',  count:  44, total:  18320.75, sortCode: '20-45-14', type: 'CREDIT', schedule: 'DD=05', status: 'PENDING' },
];

// ── Pre-built CHAPS/BACS payment batches ────────────────────────────────────
const PAYMENT_BATCHES = [
  { id: 'BACS-SAL-MAY', desc: 'MAY 2026 SALARY CREDITS',        count: 148, total: 312450.00, type: 'BACS', priority: 'STD',  status: 'READY',    submitBy: '23/05/26 15:30' },
  { id: 'CHAPS-PROP-01', desc: 'PROPERTY COMPLETION TRANSFERS',  count:   5, total: 875000.00, type: 'CHAPS', priority: 'URG', status: 'AWAITING', submitBy: '20/05/26 12:00' },
  { id: 'BACS-SUP-MAY',  desc: 'SUPPLIER PAYMENT RUN - MAY',     count:  67, total:  95230.40, type: 'BACS', priority: 'STD',  status: 'READY',    submitBy: '24/05/26 15:30' },
  { id: 'CHAPS-INT-02',  desc: 'INTER-BANK SETTLEMENT ROUND 2', count:  12, total:2340000.00, type: 'CHAPS', priority: 'URG',  status: 'COMPLETE', submitBy: '19/05/26 14:00' },
  { id: 'BACS-DD-MAY',   desc: 'DIRECT DEBIT COLLECTION MAY',    count: 891, total: 442180.25, type: 'BACS', priority: 'STD',  status: 'PENDING',  submitBy: '25/05/26 15:30' },
];

// ── Credit card approval queue ───────────────────────────────────────────────
const INITIAL_CC_QUEUE = [
  { ref: 'CC-APP-001', surname: 'WHITMORE',  forename: 'PATRICIA', custId: '10000005', requested: 5000,  income: 32000, score: 742, dti: 28, existing_balance: 0,       rec: 'APPROVE',  limit: 4500,  status: 'PENDING' },
  { ref: 'CC-APP-002', surname: 'PEMBERTON', forename: 'ARTHUR',   custId: '10000004', requested: 8000,  income: 41000, score: 688, dti: 35, existing_balance: 342.15,  rec: 'APPROVE',  limit: 6000,  status: 'PENDING' },
  { ref: 'CC-APP-003', surname: 'MORRISON',  forename: 'ELEANOR',  custId: '10000008', requested: 12000, income: 28000, score: 591, dti: 48, existing_balance: 0,       rec: 'REFER',    limit: 0,     status: 'PENDING' },
  { ref: 'CC-APP-004', surname: 'HARRISON',  forename: 'WILLIAM',  custId: '10000001', requested: 3000,  income: 55000, score: 801, dti: 18, existing_balance: 0,       rec: 'APPROVE',  limit: 3000,  status: 'PENDING' },
  { ref: 'CC-APP-005', surname: 'THORNTON',  forename: 'RICHARD',  custId: '10000011', requested: 2500,  income: 22000, score: 534, dti: 55, existing_balance: 0,       rec: 'DECLINE',  limit: 0,     status: 'PENDING' },
  { ref: 'CC-APP-006', surname: 'BLACKWELL', forename: 'DOROTHY',  custId: '10000003', requested: 6000,  income: 38000, score: 719, dti: 31, existing_balance: 8500.00, rec: 'REFER',    limit: 0,     status: 'PENDING' },
  { ref: 'CC-APP-007', surname: 'HENDERSON', forename: 'GEORGE',   custId: '10000007', requested: 1500,  income: 19000, score: 612, dti: 22, existing_balance: 0,       rec: 'APPROVE',  limit: 1500,  status: 'PENDING' },
];

const fmt = (n) => n.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ── JCL Job log simulation ───────────────────────────────────────────────────
const buildJobLog = (jobId, desc, count, total, type) => {
  const ts = () => { const d = new Date(); return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()+Math.floor(Math.random()*5)).padStart(2,'0')}`; };
  return [
    `//JOB${jobId}  JOB (ACCT,NCB),CLASS=B,MSGCLASS=X,MSGLEVEL=(1,1)`,
    `//* NATIONAL CLEARING BANK PLC — ${desc}`,
    `//* GENERATED: ${new Date().toLocaleDateString('en-GB')} ${ts()}`,
    `//STEP010 EXEC PGM=BATCPST,REGION=4M`,
    `//STEPLIB  DD DSN=NCB.PROD.LOADLIB,DISP=SHR`,
    `//INPUTDD  DD DSN=NCB.BATCH.${jobId}.INPUT,DISP=SHR`,
    `//OUTPUTDD DD DSN=NCB.BATCH.${jobId}.OUTPUT,DISP=(NEW,CATLG)`,
    `//SYSOUT   DD SYSOUT=*`,
    `IEFC452I ${jobId} - SELECTED`,
    `IEF403I ${jobId} - STARTED`,
    `BATCPST0001  ${type} BATCH INITIALISED  RECS=${String(count).padStart(6,' ')}`,
    `BATCPST0010  VALIDATING INPUT RECORDS...`,
    `BATCPST0011  RECORDS READ    : ${count}`,
    `BATCPST0012  RECORDS VALID   : ${count}`,
    `BATCPST0013  RECORDS INVALID : 0`,
    `BATCPST0020  POSTING TO DB2 TABLE NCB.TRANSACTIONS...`,
    `BATCPST0021  RECORDS POSTED  : ${count}`,
    `BATCPST0030  TOTAL DEBIT  : GBP ${fmt(type === 'DEBIT' ? total : 0)}`,
    `BATCPST0031  TOTAL CREDIT : GBP ${fmt(type !== 'DEBIT' ? total : 0)}`,
    `BATCPST0040  GENERATING SETTLEMENT FILE...`,
    `BATCPST0041  BACS FILE WRITTEN: NCB.BACS.${jobId}.SETTLEMENT`,
    `BATCPST0050  AUDIT TRAIL WRITTEN TO NCB.AUDIT.${jobId}`,
    `IEF404I ${jobId} - ENDED    MAXCC=0000`,
    `IEFC001I ${jobId} COMPLETE — RETURN CODE 0000`,
  ];
};

// ─────────────────────────────────────────────────────────────────────────────
export default function BulkProcessingScreen({ operatorId, onBack }) {
  const [tab, setTab] = useState('MORTGAGE'); // MORTGAGE | PAYMENTS | CARDAPPR
  const [jobLog, setJobLog] = useState([]);
  const [running, setRunning] = useState(false);
  const [jobRunning, setJobRunning] = useState(null);
  const [msg, setMsg] = useState({ text: 'BULK PROCESSING CENTRE  -  SELECT FUNCTION', type: 'normal' });

  // Mortgage state
  const [selMtg, setSelMtg] = useState(null);
  const [mtgList, setMtgList] = useState(MORTGAGE_TEMPLATES);
  const [confirmJob, setConfirmJob] = useState(false);
  const confirmRef = useRef('');

  // Payments state
  const [selPayment, setSelPayment] = useState(null);
  const [payList, setPayList] = useState(PAYMENT_BATCHES);
  const [newBatch, setNewBatch] = useState({ desc: '', count: '', total: '', type: 'BACS', priority: 'STD' });
  const [showNewBatch, setShowNewBatch] = useState(false);

  // Credit card state
  const [ccQueue, setCcQueue] = useState(INITIAL_CC_QUEUE);
  const [selCC, setSelCC] = useState(null);
  const [overrideLimit, setOverrideLimit] = useState('');
  const [overrideReason, setOverrideReason] = useState('');

  const logRef = useRef(null);
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [jobLog]);

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  const setMsg2 = (text, type = 'normal') => setMsg({ text, type });
  const msgColor = msg.type === 'error' ? '#FF3333' : msg.type === 'success' ? '#AAFFAA' : msg.type === 'warn' ? '#FF9933' : '#33FF33';

  // ── Simulate job execution with step-by-step log output ──────────────────
  const runJob = async (jobId, desc, count, total, type, onComplete) => {
    setRunning(true);
    setJobRunning(jobId);
    setJobLog([]);
    const lines = buildJobLog(jobId, desc, count, total, type);
    for (let i = 0; i < lines.length; i++) {
      await new Promise(r => setTimeout(r, 80 + Math.random() * 60));
      setJobLog(prev => [...prev, lines[i]]);
    }
    logAudit({
      event_type: 'TRANSACTION',
      operator_id: operatorId,
      details: `BULK JOB ${jobId}: ${desc} — ${count} RECORDS — GBP ${fmt(total)} — TYPE: ${type}`,
      result: 'SUCCESS',
      affected_entity: jobId,
      row_count: count,
    });
    setRunning(false);
    setJobRunning(null);
    if (onComplete) onComplete();
  };

  // ── MORTGAGE tab ──────────────────────────────────────────────────────────
  const handleRunMortgage = () => {
    if (!selMtg) { setMsg2('SELECT A BATCH JOB FIRST', 'error'); return; }
    if (selMtg.status === 'COMPLETE') { setMsg2('JOB ALREADY COMPLETE — SELECT A READY OR PENDING JOB', 'error'); return; }
    setConfirmJob(true);
  };

  const handleConfirmMortgage = () => {
    setConfirmJob(false);
    const job = selMtg;
    setMsg2(`SUBMITTING JCL JOB ${job.id}...`, 'warn');
    runJob(job.id, job.desc, job.count, job.total, job.type, () => {
      setMtgList(l => l.map(m => m.id === job.id ? { ...m, status: 'COMPLETE' } : m));
      setMsg2(`JOB ${job.id} COMPLETE — ${job.count} RECORDS PROCESSED — GBP ${fmt(job.total)}`, 'success');
    });
  };

  // ── PAYMENTS tab ──────────────────────────────────────────────────────────
  const handleSubmitPayment = (batch) => {
    if (batch.status === 'COMPLETE') { setMsg2('BATCH ALREADY SUBMITTED', 'error'); return; }
    setMsg2(`SUBMITTING ${batch.type} BATCH ${batch.id}...`, 'warn');
    runJob(batch.id, batch.desc, batch.count, batch.total, batch.type === 'CHAPS' ? 'CREDIT' : 'DEBIT', () => {
      setPayList(l => l.map(p => p.id === batch.id ? { ...p, status: 'COMPLETE' } : p));
      setMsg2(`BATCH ${batch.id} SUBMITTED — ${batch.count} PAYMENTS — GBP ${fmt(batch.total)}`, 'success');
    });
  };

  const handleAddBatch = () => {
    if (!newBatch.desc || !newBatch.count || !newBatch.total) { setMsg2('ALL FIELDS REQUIRED', 'error'); return; }
    const id = `${newBatch.type}-MAN-${Date.now().toString().slice(-4)}`;
    setPayList(l => [...l, {
      id, desc: newBatch.desc.toUpperCase(),
      count: parseInt(newBatch.count), total: parseFloat(newBatch.total),
      type: newBatch.type, priority: newBatch.priority,
      status: 'READY', submitBy: dateStr + ' 15:30'
    }]);
    setNewBatch({ desc: '', count: '', total: '', type: 'BACS', priority: 'STD' });
    setShowNewBatch(false);
    setMsg2(`BATCH ${id} ADDED TO QUEUE`, 'success');
  };

  // ── CREDIT CARD tab ───────────────────────────────────────────────────────
  const handleCCDecision = (app, decision, limitOverride) => {
    const finalLimit = limitOverride ? parseFloat(limitOverride) : app.limit;
    setCcQueue(q => q.map(c => c.ref === app.ref
      ? { ...c, status: decision, limit: finalLimit, decidedBy: operatorId, decidedAt: dateStr }
      : c
    ));
    logAudit({
      event_type: 'TRANSACTION',
      operator_id: operatorId,
      details: `CC APPLICATION ${app.ref}: ${app.surname} ${app.forename} — DECISION: ${decision} — LIMIT: £${fmt(finalLimit)} — SYSTEM REC: ${app.rec}`,
      result: decision,
      affected_entity: app.custId,
      row_count: 1,
    });
    setSelCC(null);
    setOverrideLimit('');
    setOverrideReason('');
    setMsg2(`APPLICATION ${app.ref} ${decision} — LIMIT GBP ${fmt(finalLimit)}`, decision === 'APPROVED' ? 'success' : decision === 'DECLINED' ? 'error' : 'warn');
  };

  const recColor = (rec) => rec === 'APPROVE' ? '#AAFFAA' : rec === 'DECLINE' ? '#FF3333' : '#FF9933';
  const statusColor = (s) => s === 'APPROVED' ? '#AAFFAA' : s === 'DECLINED' ? '#FF3333' : s === 'REFERRED' ? '#FF9933' : '#33FF33';

  const handleKeyDown = (e) => {
    if (e.key === 'F3') onBack('MENU');
    if (e.key === 'Escape') { setSelMtg(null); setSelPayment(null); setSelCC(null); setConfirmJob(false); setShowNewBatch(false); }
  };

  const TABS = ['MORTGAGE', 'PAYMENTS', 'CARDAPPR'];
  const TAB_LABELS = { MORTGAGE: 'MORTGAGE BATCH', PAYMENTS: 'BULK PAYMENTS', CARDAPPR: 'CARD APPROVALS' };

  return (
    <div onKeyDown={handleKeyDown} style={S.root} tabIndex={-1}>
      {/* Header */}
      <div style={S.hdr}>
        <span>BANKMASTER/VS — BULK PROCESSING CENTRE</span>
        <span>BLKPRC</span>
        <span>DATE: {dateStr}</span>
      </div>
      <div style={S.sep}>{'─'.repeat(79)}</div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '2px', marginBottom: '8px' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => { setTab(t); setJobLog([]); }}
            style={{
              ...S.btn(tab === t ? '#FFFF99' : '#668866'),
              background: tab === t ? '#002200' : '#000800',
              fontWeight: tab === t ? 'bold' : 'normal',
              letterSpacing: '1px',
            }}>
            {TAB_LABELS[t]}
          </button>
        ))}
        <span style={{ color: '#668866', marginLeft: 'auto', fontSize: '11px', alignSelf: 'center' }}>
          OPERATOR: {operatorId}  REGION: CICSREG1
        </span>
      </div>

      {/* ── MORTGAGE BATCH TAB ────────────────────────────────────────── */}
      {tab === 'MORTGAGE' && (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ flex: '0 0 380px' }}>
            <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>MORTGAGE BATCH QUEUE — MTGBATCH REGION</div>
            <div style={{ color: '#668866', fontSize: '10px', marginBottom: '6px' }}>
              BACS ORIGINATION  ·  CLEARING CYCLE: D+3  ·  VOCA SUBMISSION 15:30
            </div>
            <div style={S.tableHead}>
              {'JOB-ID'.padEnd(15)} {'DESCRIPTION'.padEnd(30)} {'RECS'.padStart(5)} {'GBP TOTAL'.padStart(12)} {'ST'}
            </div>
            {mtgList.map(m => (
              <div key={m.id}
                style={{ ...S.tableRow(selMtg?.id === m.id), fontSize: '12px', padding: '3px 0', fontFamily: "'Courier New', monospace" }}
                onClick={() => setSelMtg(m)}>
                <span style={{ color: selMtg?.id === m.id ? '#FFFF99' : '#3399FF' }}>{m.id.padEnd(15)}</span>
                <span style={{ color: '#33FF33' }}>{m.desc.slice(0,30).padEnd(30)}</span>
                <span style={{ color: '#AAFFAA' }}>{String(m.count).padStart(5)}</span>
                <span style={{ color: '#AAFFAA' }}>{fmt(m.total).padStart(12)}</span>
                <span style={{ color: m.status === 'COMPLETE' ? '#336633' : m.status === 'READY' ? '#AAFFAA' : '#FF9933', marginLeft: '4px' }}>
                  {m.status === 'COMPLETE' ? '✓' : m.status === 'READY' ? '▶' : '⏸'}
                </span>
              </div>
            ))}

            {selMtg && !confirmJob && (
              <div style={{ border: '1px solid #336633', padding: '8px', marginTop: '10px', background: '#000800' }}>
                <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>JOB DETAILS — {selMtg.id}</div>
                {[
                  ['DESCRIPTION', selMtg.desc],
                  ['RECORD COUNT', selMtg.count],
                  ['TOTAL VALUE', 'GBP ' + fmt(selMtg.total)],
                  ['SORT CODE', selMtg.sortCode],
                  ['TRAN TYPE', selMtg.type],
                  ['SCHEDULE', selMtg.schedule],
                  ['STATUS', selMtg.status],
                ].map(([k, v]) => (
                  <div key={k} style={S.row}>
                    <span style={{ ...S.label, width: '14ch', fontSize: '11px' }}>{k}</span>
                    <span style={{ color: '#3399FF', fontSize: '11px' }}>{v}</span>
                  </div>
                ))}
                <div style={{ marginTop: '8px' }}>
                  <button style={S.btn(selMtg.status === 'COMPLETE' ? '#336633' : '#AAFFAA')}
                    onClick={handleRunMortgage} disabled={running}>
                    {running && jobRunning === selMtg.id ? 'RUNNING...' : 'PF5 SUBMIT JOB'}
                  </button>
                  <button style={S.btn('#668866')} onClick={() => setSelMtg(null)}>PF3 CANCEL</button>
                </div>
              </div>
            )}

            {confirmJob && selMtg && (
              <div style={{ border: '1px solid #FF9933', padding: '10px', marginTop: '10px', background: '#080400' }}>
                <div style={{ color: '#FF9933', fontWeight: 'bold', marginBottom: '6px' }}>
                  CONFIRM JOB SUBMISSION
                </div>
                <div style={{ color: '#AAFFAA', marginBottom: '4px', fontSize: '12px' }}>
                  JOB: {selMtg.id} — {selMtg.count} RECORDS — GBP {fmt(selMtg.total)}
                </div>
                <div style={{ color: '#FF9933', fontSize: '11px', marginBottom: '8px' }}>
                  THIS WILL POST LIVE TRANSACTIONS. APPROVE?
                </div>
                <button style={S.btn('#AAFFAA')} onClick={handleConfirmMortgage}>ENTER APPROVE</button>
                <button style={S.btn('#FF3333')} onClick={() => setConfirmJob(false)}>PF3 CANCEL</button>
              </div>
            )}
          </div>

          {/* Job log */}
          <div style={{ flex: 1, minWidth: '260px' }}>
            <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>
              JCL SPOOL OUTPUT {jobRunning ? `— ${jobRunning}` : ''}
              {running && <span style={{ color: '#FF9933', marginLeft: '8px' }}>● RUNNING</span>}
            </div>
            <div ref={logRef} style={{ background: '#000800', border: '1px solid #224422', padding: '6px', height: '280px', overflowY: 'auto', fontSize: '11px', color: '#AAFFAA' }}>
              {jobLog.length === 0 && <div style={{ color: '#336633' }}>NO JOB OUTPUT — SELECT AND SUBMIT A BATCH JOB</div>}
              {jobLog.map((l, i) => (
                <div key={i} style={{
                  color: l.includes('COMPLETE') || l.includes('MAXCC=0000') ? '#AAFFAA'
                    : l.includes('ERROR') || l.includes('ABEND') ? '#FF3333'
                    : l.startsWith('//') ? '#668866'
                    : l.startsWith('IEF') || l.startsWith('IEFC') ? '#FF9933'
                    : '#33FF33',
                  fontFamily: "'Courier New', monospace", fontSize: '11px',
                }}>{l}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── BULK PAYMENTS TAB ─────────────────────────────────────────── */}
      {tab === 'PAYMENTS' && (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ flex: '0 0 420px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '6px' }}>
              <div style={{ color: '#FFFF99', fontWeight: 'bold', fontSize: '11px' }}>BACS/CHAPS PAYMENT QUEUE</div>
              <button style={S.btn('#3399FF')} onClick={() => setShowNewBatch(b => !b)}>
                {showNewBatch ? 'CANCEL' : 'PF5 NEW BATCH'}
              </button>
            </div>

            {showNewBatch && (
              <div style={{ border: '1px solid #336633', padding: '8px', marginBottom: '10px', background: '#000800' }}>
                <div style={{ color: '#FFFF99', marginBottom: '6px', fontSize: '11px', fontWeight: 'bold' }}>NEW BATCH ENTRY</div>
                {[
                  { label: 'DESCRIPTION (40)', key: 'desc', w: 32 },
                  { label: 'RECORD COUNT', key: 'count', w: 8 },
                  { label: 'TOTAL VALUE', key: 'total', w: 14 },
                ].map(({ label, key, w }) => (
                  <div key={key} style={S.row}>
                    <span style={{ ...S.label, width: '18ch', fontSize: '11px' }}>{label} :</span>
                    <input style={S.inp(w)} value={newBatch[key]}
                      onChange={e => setNewBatch(b => ({ ...b, [key]: e.target.value }))} />
                  </div>
                ))}
                <div style={S.row}>
                  <span style={{ ...S.label, width: '18ch', fontSize: '11px' }}>TYPE :</span>
                  <select style={{ ...S.inp(6), borderBottom: '1px solid #3399FF' }}
                    value={newBatch.type}
                    onChange={e => setNewBatch(b => ({ ...b, type: e.target.value }))}>
                    <option value="BACS">BACS</option>
                    <option value="CHAPS">CHAPS</option>
                  </select>
                  <span style={{ ...S.label, width: '10ch', fontSize: '11px', marginLeft: '12px' }}>PRIORITY :</span>
                  <select style={{ ...S.inp(4), borderBottom: '1px solid #3399FF' }}
                    value={newBatch.priority}
                    onChange={e => setNewBatch(b => ({ ...b, priority: e.target.value }))}>
                    <option value="STD">STD</option>
                    <option value="URG">URG</option>
                  </select>
                </div>
                <button style={{ ...S.btn('#AAFFAA'), marginTop: '6px' }} onClick={handleAddBatch}>ADD TO QUEUE</button>
              </div>
            )}

            <div style={S.tableHead}>
              <span style={{ fontFamily: "'Courier New', monospace", fontSize: '11px' }}>
                {'BATCH-ID'.padEnd(16)} {'TYPE'.padEnd(6)} {'PRI'.padEnd(4)} {'RECS'.padStart(5)} {'GBP TOTAL'.padStart(13)} {' ST'}
              </span>
            </div>
            {payList.map(p => (
              <div key={p.id}
                style={{ ...S.tableRow(selPayment?.id === p.id), fontSize: '11px', padding: '2px 0', fontFamily: "'Courier New', monospace" }}
                onClick={() => setSelPayment(p)}>
                <span style={{ color: selPayment?.id === p.id ? '#FFFF99' : '#3399FF' }}>{p.id.padEnd(16)}</span>
                <span style={{ color: p.type === 'CHAPS' ? '#FF9933' : '#33FF33' }}>{p.type.padEnd(6)}</span>
                <span style={{ color: p.priority === 'URG' ? '#FF3333' : '#668866' }}>{p.priority.padEnd(4)}</span>
                <span style={{ color: '#AAFFAA' }}>{String(p.count).padStart(5)}</span>
                <span style={{ color: '#AAFFAA' }}>{fmt(p.total).padStart(13)}</span>
                <span style={{ color: p.status === 'COMPLETE' ? '#336633' : p.status === 'READY' ? '#AAFFAA' : p.status === 'AWAITING' ? '#3399FF' : '#FF9933', marginLeft: '2px' }}>
                  {p.status.slice(0,3)}
                </span>
              </div>
            ))}

            {selPayment && (
              <div style={{ border: '1px solid #336633', padding: '8px', marginTop: '10px', background: '#000800' }}>
                <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>{selPayment.id}</div>
                <div style={{ color: '#33FF33', fontSize: '11px', marginBottom: '2px' }}>{selPayment.desc}</div>
                <div style={{ fontSize: '11px', color: '#668866' }}>
                  SUBMIT BY: {selPayment.submitBy}  ·  {selPayment.count} RECORDS  ·  GBP {fmt(selPayment.total)}
                </div>
                {selPayment.type === 'CHAPS' && (
                  <div style={{ color: '#FF9933', fontSize: '10px', marginTop: '2px' }}>
                    ⚠ CHAPS: SAME-DAY SETTLEMENT — IRREVOCABLE ONCE SUBMITTED
                  </div>
                )}
                <div style={{ marginTop: '6px' }}>
                  <button style={S.btn(selPayment.status === 'COMPLETE' ? '#336633' : '#AAFFAA')}
                    onClick={() => handleSubmitPayment(selPayment)}
                    disabled={running || selPayment.status === 'COMPLETE'}>
                    {running && jobRunning === selPayment.id ? 'SUBMITTING...' : 'PF5 SUBMIT'}
                  </button>
                  <button style={S.btn('#668866')} onClick={() => setSelPayment(null)}>CANCEL</button>
                </div>
              </div>
            )}
          </div>

          {/* Spool log */}
          <div style={{ flex: 1, minWidth: '260px' }}>
            <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>
              BATCH SUBMISSION LOG {running && <span style={{ color: '#FF9933' }}>● PROCESSING</span>}
            </div>
            <div ref={logRef} style={{ background: '#000800', border: '1px solid #224422', padding: '6px', height: '320px', overflowY: 'auto', fontSize: '11px' }}>
              {jobLog.length === 0 && <div style={{ color: '#336633' }}>NO JOB OUTPUT</div>}
              {jobLog.map((l, i) => (
                <div key={i} style={{
                  color: l.includes('COMPLETE') || l.includes('MAXCC=0000') ? '#AAFFAA'
                    : l.includes('ERROR') ? '#FF3333'
                    : l.startsWith('//') ? '#668866'
                    : l.startsWith('IEF') || l.startsWith('IEFC') ? '#FF9933'
                    : '#33FF33',
                  fontFamily: "'Courier New', monospace",
                }}>{l}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── CREDIT CARD APPROVALS TAB ─────────────────────────────────── */}
      {tab === 'CARDAPPR' && (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ flex: '0 0 460px' }}>
            <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '2px', fontSize: '11px' }}>
              CREDIT CARD APPLICATION QUEUE — CARDAUTH SYSTEM
            </div>
            <div style={{ color: '#668866', fontSize: '10px', marginBottom: '6px' }}>
              AUTOMATED SCORING: EXPERIAN LINK  ·  DUAL CONTROL REQUIRED FOR OVERRIDE
            </div>

            {/* Queue table */}
            <div style={{ ...S.tableHead, fontSize: '11px', fontFamily: "'Courier New', monospace" }}>
              {'REF'.padEnd(12)} {'APPLICANT'.padEnd(18)} {'REQUESTED'.padStart(10)} {'SCORE'.padStart(6)} {'DTI%'.padStart(5)} {'REC'.padEnd(8)} {'ST'}
            </div>
            {ccQueue.map(app => (
              <div key={app.ref}
                style={{ ...S.tableRow(selCC?.ref === app.ref), fontSize: '11px', fontFamily: "'Courier New', monospace", padding: '2px 0' }}
                onClick={() => { setSelCC(app); setOverrideLimit(String(app.limit || '')); setOverrideReason(''); }}>
                <span style={{ color: selCC?.ref === app.ref ? '#FFFF99' : '#3399FF' }}>{app.ref.padEnd(12)}</span>
                <span style={{ color: '#AAFFAA' }}>{(app.surname + ', ' + app.forename.slice(0,1)).slice(0,18).padEnd(18)}</span>
                <span style={{ color: '#33FF33' }}>{'£'+fmt(app.requested).padStart(9)}</span>
                <span style={{ color: app.score >= 720 ? '#AAFFAA' : app.score >= 620 ? '#FF9933' : '#FF3333' }}>{String(app.score).padStart(6)}</span>
                <span style={{ color: app.dti <= 35 ? '#AAFFAA' : app.dti <= 45 ? '#FF9933' : '#FF3333' }}>{String(app.dti).padStart(5)}</span>
                <span style={{ color: recColor(app.rec) }}>{app.rec.padEnd(8)}</span>
                <span style={{ color: statusColor(app.status) }}>{app.status.slice(0,4)}</span>
              </div>
            ))}

            {/* Summary counts */}
            <div style={{ marginTop: '8px', fontSize: '11px', color: '#668866', borderTop: '1px solid #224422', paddingTop: '4px' }}>
              PENDING: {ccQueue.filter(c => c.status === 'PENDING').length}  |
              APPROVED: {ccQueue.filter(c => c.status === 'APPROVED').length}  |
              REFERRED: {ccQueue.filter(c => c.status === 'REFERRED').length}  |
              DECLINED: {ccQueue.filter(c => c.status === 'DECLINED').length}
            </div>
          </div>

          {/* Application detail / decision panel */}
          <div style={{ flex: 1, minWidth: '280px' }}>
            {!selCC && (
              <div style={{ color: '#336633', padding: '12px 0' }}>← SELECT AN APPLICATION TO REVIEW AND DECIDE</div>
            )}
            {selCC && (
              <div>
                <div style={{ color: '#FFFF99', fontWeight: 'bold', fontSize: '12px', marginBottom: '6px' }}>
                  APPLICATION DETAIL — {selCC.ref}
                </div>
                <div style={{ border: '1px solid #336633', padding: '8px', background: '#000800', marginBottom: '8px' }}>
                  <div style={{ color: '#FF9933', fontWeight: 'bold', fontSize: '10px', marginBottom: '4px' }}>APPLICANT</div>
                  {[
                    ['NAME', selCC.forename + ' ' + selCC.surname],
                    ['CUSTOMER ID', selCC.custId],
                    ['REQUESTED LIMIT', 'GBP ' + fmt(selCC.requested)],
                    ['ANNUAL INCOME', 'GBP ' + fmt(selCC.income)],
                    ['EXISTING BALANCE', selCC.existing_balance > 0 ? 'GBP ' + fmt(selCC.existing_balance) : 'NIL'],
                  ].map(([k, v]) => (
                    <div key={k} style={{ ...S.row, fontSize: '11px' }}>
                      <span style={{ ...S.label, width: '17ch' }}>{k}</span>
                      <span style={{ color: '#3399FF' }}>{v}</span>
                    </div>
                  ))}
                </div>

                <div style={{ border: `1px solid ${recColor(selCC.rec)}`, padding: '8px', background: '#000800', marginBottom: '8px' }}>
                  <div style={{ color: '#FF9933', fontWeight: 'bold', fontSize: '10px', marginBottom: '4px' }}>AUTOMATED SCORING</div>
                  {[
                    ['CREDIT SCORE', String(selCC.score), selCC.score >= 720 ? '#AAFFAA' : selCC.score >= 620 ? '#FF9933' : '#FF3333'],
                    ['DEBT-TO-INCOME', selCC.dti + '%', selCC.dti <= 35 ? '#AAFFAA' : selCC.dti <= 45 ? '#FF9933' : '#FF3333'],
                    ['SYSTEM RECOMMENDATION', selCC.rec, recColor(selCC.rec)],
                    ['RECOMMENDED LIMIT', selCC.rec === 'APPROVE' ? 'GBP ' + fmt(selCC.limit) : 'N/A', '#AAFFAA'],
                  ].map(([k, v, c]) => (
                    <div key={k} style={{ ...S.row, fontSize: '11px' }}>
                      <span style={{ ...S.label, width: '22ch' }}>{k}</span>
                      <span style={{ color: c || '#3399FF', fontWeight: 'bold' }}>{v}</span>
                    </div>
                  ))}
                </div>

                {selCC.existing_balance > 5000 && (
                  <div style={{ color: '#FF9933', fontSize: '10px', border: '1px solid #FF9933', padding: '4px 8px', marginBottom: '8px' }}>
                    ⚠ HIGH EXISTING DEBT EXPOSURE — MANUAL REVIEW RECOMMENDED
                  </div>
                )}

                {selCC.status === 'PENDING' && (
                  <div style={{ border: '1px solid #336633', padding: '8px', background: '#000800' }}>
                    <div style={{ color: '#FFFF99', fontWeight: 'bold', fontSize: '10px', marginBottom: '6px' }}>AUTHORISER DECISION</div>
                    <div style={S.row}>
                      <span style={{ ...S.label, fontSize: '11px', width: '16ch' }}>APPROVED LIMIT :</span>
                      <input style={S.inp(10)} value={overrideLimit}
                        onChange={e => setOverrideLimit(e.target.value)}
                        placeholder={String(selCC.limit || '0')} />
                      <span style={{ color: '#668866', fontSize: '10px', marginLeft: '4px' }}>GBP (OVERRIDE SYS REC)</span>
                    </div>
                    <div style={S.row}>
                      <span style={{ ...S.label, fontSize: '11px', width: '16ch' }}>REASON/NOTES   :</span>
                      <input style={S.inp(28)} value={overrideReason}
                        onChange={e => setOverrideReason(e.target.value.toUpperCase())} />
                    </div>
                    <div style={{ marginTop: '8px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      <button style={S.btn('#AAFFAA')} onClick={() => handleCCDecision(selCC, 'APPROVED', overrideLimit)}>
                        PF5 APPROVE
                      </button>
                      <button style={S.btn('#FF9933')} onClick={() => handleCCDecision(selCC, 'REFERRED', overrideLimit)}>
                        PF6 REFER
                      </button>
                      <button style={S.btn('#FF3333')} onClick={() => handleCCDecision(selCC, 'DECLINED', '')}>
                        PF7 DECLINE
                      </button>
                      <button style={S.btn('#668866')} onClick={() => setSelCC(null)}>
                        PF3 BACK
                      </button>
                    </div>
                  </div>
                )}

                {selCC.status !== 'PENDING' && (
                  <div style={{ border: `1px solid ${statusColor(selCC.status)}`, padding: '8px', background: '#000800' }}>
                    <div style={{ color: statusColor(selCC.status), fontWeight: 'bold' }}>
                      DECISION: {selCC.status}
                    </div>
                    {selCC.limit > 0 && <div style={{ color: '#AAFFAA', fontSize: '11px' }}>APPROVED LIMIT: GBP {fmt(selCC.limit)}</div>}
                    <div style={{ color: '#668866', fontSize: '10px', marginTop: '2px' }}>
                      DECIDED BY: {selCC.decidedBy || 'SYSTEM'}  DATE: {selCC.decidedAt || dateStr}
                    </div>
                    <button style={{ ...S.btn('#668866'), marginTop: '6px' }} onClick={() => setSelCC(null)}>BACK</button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Status bar */}
      <div style={{ borderTop: '1px solid #004400', marginTop: '10px', paddingTop: '4px' }}>
        <div style={{ color: msgColor, fontWeight: 'bold', fontSize: '12px' }}>{`==>`} {msg.text}</div>
        <div style={{ color: '#668866', fontSize: '11px', marginTop: '2px' }}>
          PF3=MENU  PF5=SUBMIT/APPROVE  PF6=REFER  PF7=DECLINE  ESC=CLEAR SELECTION
        </div>
      </div>
    </div>
  );
}