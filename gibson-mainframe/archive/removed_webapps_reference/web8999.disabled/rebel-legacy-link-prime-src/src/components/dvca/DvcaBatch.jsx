import React, { useState } from 'react';

const S = { mono: "'Courier New', monospace", green: '#33FF33', bright: '#AAFFAA', blue: '#3399FF', red: '#FF3333', grey: '#668866' };

const BATCH_JOBS = [
  { id: 'BKGBAT1', desc: 'OVERNIGHT INTEREST CALCULATION', status: 'COMPLETE', rc: '0000' },
  { id: 'BKGBAT2', desc: 'DIRECT DEBIT PROCESSING', status: 'COMPLETE', rc: '0000' },
  { id: 'BKGBAT3', desc: 'STATEMENT GENERATION', status: 'ABENDED', rc: '0012' },
  { id: 'BKGBAT4', desc: 'DORMANCY REVIEW', status: 'WAITING', rc: '----' },
  { id: 'BKGPAY1', desc: 'BACS PAYMENT RUN', status: 'COMPLETE', rc: '0000' },
  { id: 'BKGPAY2', desc: 'CHAPS SETTLEMENT', status: 'RUNNING', rc: '----' },
];

export default function DvcaBatch({ operatorId, onNavigate }) {
  const [selected, setSelected] = useState(null);
  const [msg, setMsg] = useState('SELECT A BATCH JOB TO VIEW DETAILS');

  const handleKey = (e) => {
    if (e.key === 'F3') onNavigate('DVCA_MENU');
  };

  const statusColor = (s) => s === 'COMPLETE' ? S.bright : s === 'ABENDED' ? S.red : s === 'RUNNING' ? S.blue : S.grey;

  return (
    <div onKeyDown={handleKey} style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto' }}>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '2px' }}>PIBS — BATCH PROCESSING CENTRE &nbsp;&nbsp;&nbsp; BATCH</div>
      <div style={{ color: S.green, marginBottom: '8px' }}>{'─'.repeat(70)}</div>
      <div style={{ color: S.bright, fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>
        {'JOB ID'.padEnd(12)}{'DESCRIPTION'.padEnd(36)}{'STATUS'.padEnd(12)}RC
      </div>
      {BATCH_JOBS.map((job, i) => (
        <div key={i} onClick={() => { setSelected(job); setMsg(`JOB ${job.id}: ${job.desc} — RC=${job.rc}`); }}
          style={{ color: statusColor(job.status), lineHeight: '1.9', cursor: 'pointer',
            background: selected?.id === job.id ? '#001400' : 'transparent',
            borderLeft: selected?.id === job.id ? `2px solid ${S.green}` : '2px solid transparent',
            paddingLeft: '4px' }}>
          {job.id.padEnd(12)}{job.desc.padEnd(36)}{job.status.padEnd(12)}{job.rc}
        </div>
      ))}
      <div style={{ marginTop: '10px', color: msg.includes('ABENDED') ? S.red : S.green, fontWeight: 'bold' }}>==&gt; {msg}</div>
      <div style={{ color: S.grey, fontSize: '11px', marginTop: '4px' }}>PF3 = MENU &nbsp;&nbsp; CLICK ROW = SELECT JOB</div>
    </div>
  );
}