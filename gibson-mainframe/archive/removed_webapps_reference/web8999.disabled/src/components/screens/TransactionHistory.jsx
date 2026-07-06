import React, { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';

export default function TransactionHistory({ accountNumber, operatorId, onBack, onTopBack }) {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 12;

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const res = await base44.entities.Transaction.filter({ account_number: accountNumber }, '-post_date', 200);
      setTransactions(res);
      setLoading(false);
    };
    load();
  }, [accountNumber]);

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getFullYear()).slice(2)}`;

  const total = transactions.length;
  const pageCount = Math.ceil(total / PAGE_SIZE);
  const slice = transactions.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const handleKeyDown = (e) => {
    if (e.key === 'F3') onBack();
    if (e.key === 'F7') { e.preventDefault(); setPage(p => Math.max(0, p - 1)); }
    if (e.key === 'F8') { e.preventDefault(); setPage(p => Math.min(pageCount - 1, p + 1)); }
    if (e.key === 'F12') onTopBack('CODE_TRAN');
  };

  const fmtAmt = (type, amount) => {
    const sign = type === 'CR' ? '+' : '-';
    return `${sign}${Math.abs(amount).toFixed(2).padStart(12)}`;
  };

  const fmtBal = (bal) => {
    if (bal === undefined || bal === null) return '             ';
    return `${bal < 0 ? '-' : ' '}${Math.abs(bal).toFixed(2).padStart(12)}`;
  };

  return (
    <div onKeyDown={handleKeyDown} style={{ flex: 1, padding: '6px 8px', fontFamily: "'Courier New', monospace", fontSize: '12px', paddingBottom: '60px', overflowY: 'auto' }}>
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span>BANKMASTER/VS - TRANSACTION HISTORY INQUIRY</span>
        <span>TRANINQ</span>
        <span>DATE: {dateStr}</span>
      </div>
      <div style={{ color: '#33FF33', marginBottom: '4px' }}>{'─'.repeat(79)}</div>

      <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px' }}>
        ACCOUNT: {accountNumber}{'   '}RECORDS: {total}{'   '}PAGE: {page + 1} OF {Math.max(1, pageCount)}
      </div>

      {/* Column headers */}
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '2px', borderBottom: '1px solid #336633', paddingBottom: '2px', fontSize: '11px' }}>
        {'DATE    '} {'TIME  '} {'TYP '} {'         AMOUNT'} {'   BALANCE-AFTER'} {'  REFERENCE  '} {'DESCRIPTION'}
      </div>

      {loading ? (
        <div style={{ color: '#33FF33', marginTop: '16px', textAlign: 'center' }}>READING FROM DATABASE... PLEASE WAIT</div>
      ) : transactions.length === 0 ? (
        <div style={{ color: '#FF3333', marginTop: '16px', textAlign: 'center' }}>NOTFND - NO TRANSACTIONS ON FILE FOR ACCOUNT {accountNumber}</div>
      ) : (
        <div>
          {slice.map((t, i) => (
            <div key={t.id || i} style={{
              color: t.tran_type === 'CR' ? '#AAFFAA' : t.tran_type === 'TRF' ? '#3399FF' : '#FF9933',
              fontSize: '12px',
              lineHeight: '1.5',
              borderBottom: '1px solid #002200',
              paddingBottom: '1px',
              fontFamily: "'Courier New', monospace",
            }}>
              <span style={{ color: '#33FF33' }}>{(t.post_date || '        ').padEnd(8)}</span>
              {' '}
              <span style={{ color: '#33FF33' }}>{(t.post_time || '      ').slice(0,6).padEnd(6)}</span>
              {' '}
              <span style={{ color: t.tran_type === 'CR' ? '#AAFFAA' : t.tran_type === 'TRF' ? '#3399FF' : '#FF9933', fontWeight: 'bold' }}>{(t.tran_type || '   ').padEnd(4)}</span>
              {' '}
              <span style={{ color: t.tran_type === 'CR' ? '#AAFFAA' : '#FF9933' }}>{fmtAmt(t.tran_type, t.amount).padStart(15)}</span>
              {' '}
              <span style={{ color: parseFloat(t.balance_after) < 0 ? '#FF3333' : '#33FF33' }}>{fmtBal(t.balance_after).padStart(16)}</span>
              {' '}
              <span style={{ color: '#3399FF' }}>{(t.reference || '            ').padEnd(13)}</span>
              {' '}
              <span style={{ color: '#33FF33' }}>{(t.description || '').slice(0, 30)}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ color: '#33FF33', marginTop: '4px' }}>{'─'.repeat(79)}</div>
      <div style={{ color: '#33FF33', marginTop: '4px', display: 'flex', gap: '16px' }}>
        <span style={{ color: '#AAFFAA' }}>KEY: </span>
        <span style={{ color: '#AAFFAA' }}>+ CREDIT</span>
        <span style={{ color: '#FF9933' }}>- DEBIT</span>
        <span style={{ color: '#3399FF' }}>TRF TRANSFER</span>
        <span style={{ color: '#FF3333' }}>NEGATIVE BALANCE</span>
      </div>
      <div style={{ color: '#668866', fontSize: '12px', marginTop: '4px' }}>
        PF7=SCROLL UP  PF8=SCROLL DOWN  PF3=RETURN TO POSTING  PF12=VIEW CODE
      </div>
      <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
        <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={{ background: '#001100', border: '1px solid #336633', color: '#33FF33', fontFamily: 'inherit', fontSize: '12px', padding: '2px 8px', cursor: 'pointer', opacity: page === 0 ? 0.4 : 1 }}>PF7 SCROLL UP</button>
        <button onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} disabled={page >= pageCount - 1} style={{ background: '#001100', border: '1px solid #336633', color: '#33FF33', fontFamily: 'inherit', fontSize: '12px', padding: '2px 8px', cursor: 'pointer', opacity: page >= pageCount - 1 ? 0.4 : 1 }}>PF8 SCROLL DOWN</button>
        <button onClick={onBack} style={{ background: '#001100', border: '1px solid #AAFFAA', color: '#AAFFAA', fontFamily: 'inherit', fontSize: '12px', padding: '2px 8px', cursor: 'pointer' }}>PF3 RETURN</button>
      </div>
    </div>
  );
}