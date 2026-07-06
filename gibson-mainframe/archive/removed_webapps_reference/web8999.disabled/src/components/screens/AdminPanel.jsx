import React, { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';
import { SAMPLE_CUSTOMERS, SAMPLE_ACCOUNTS, SAMPLE_TRANSACTIONS } from '@/data/sampleData';

export default function AdminPanel({ operatorId, onBack }) {
  const [tab, setTab] = useState('overview');
  const [customers, setCustomers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    const [c, a, t] = await Promise.all([
      base44.entities.Customer.list(),
      base44.entities.Account.list(),
      base44.entities.Transaction.list(),
    ]);
    setCustomers(c);
    setAccounts(a);
    setTransactions(t);
    setLoading(false);
  };

  const seedDatabase = async () => {
    setSeeding(true);
    setMsg('SEEDING DATABASE - PLEASE WAIT...');
    try {
      // Check if already seeded
      const existing = await base44.entities.Customer.filter({ customer_id: '10000001' });
      if (existing.length > 0) {
        setMsg('DATABASE ALREADY CONTAINS SEED DATA - SKIPPING DUPLICATE PREVENTION ACTIVE');
        setSeeding(false);
        return;
      }
      await base44.entities.Customer.bulkCreate(SAMPLE_CUSTOMERS);
      setMsg('CUSTOMERS SEEDED...');
      await base44.entities.Account.bulkCreate(SAMPLE_ACCOUNTS);
      setMsg('ACCOUNTS SEEDED...');
      await base44.entities.Transaction.bulkCreate(SAMPLE_TRANSACTIONS);
      setMsg(`SEED COMPLETE - ${SAMPLE_CUSTOMERS.length} CUSTOMERS, ${SAMPLE_ACCOUNTS.length} ACCOUNTS, ${SAMPLE_TRANSACTIONS.length} TRANSACTIONS CREATED`);
      await loadData();
    } catch(e) {
      setMsg('ERROR DURING SEEDING: ' + e.message);
    }
    setSeeding(false);
  };

  const resetAll = async () => {
    if (!window.confirm('RESET ALL DATA? THIS CANNOT BE UNDONE.')) return;
    setSeeding(true);
    setMsg('RESETTING DATABASE...');
    const [c, a, t] = await Promise.all([
      base44.entities.Customer.list(),
      base44.entities.Account.list(),
      base44.entities.Transaction.list(),
    ]);
    for (const r of t) await base44.entities.Transaction.delete(r.id);
    for (const r of a) await base44.entities.Account.delete(r.id);
    for (const r of c) await base44.entities.Customer.delete(r.id);
    setMsg('ALL DATA DELETED. USE SEED BUTTON TO RESTORE SAMPLE DATA.');
    setSeeding(false);
    await loadData();
  };

  const btnStyle = (active) => ({
    background: active ? '#003300' : '#001100',
    border: `1px solid ${active ? '#AAFFAA' : '#336633'}`,
    color: active ? '#AAFFAA' : '#33FF33',
    fontFamily: "'Courier New', monospace",
    fontSize: '13px', padding: '4px 12px', cursor: 'pointer', marginRight: '4px',
  });

  const tableStyle = { borderCollapse: 'collapse', width: '100%', fontSize: '11px', fontFamily: "'Courier New', monospace" };
  const thStyle = { color: '#AAFFAA', fontWeight: 'bold', padding: '2px 6px', borderBottom: '1px solid #336633', textAlign: 'left' };
  const tdStyle = { color: '#33FF33', padding: '2px 6px', borderBottom: '1px solid #002200' };

  return (
    <div style={{ background: '#000000', color: '#33FF33', fontFamily: "'Courier New', monospace", minHeight: '100vh', padding: '12px', fontSize: '13px' }}>
      {/* Header */}
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', fontSize: '15px', marginBottom: '4px' }}>
        BANKMASTER/VS  -  SYSTEM ADMINISTRATOR PANEL
      </div>
      <div style={{ color: '#33FF33', marginBottom: '8px' }}>{'─'.repeat(79)}</div>
      <div style={{ color: '#33FF33', marginBottom: '8px' }}>
        OPERATOR: {operatorId}{'   '}
        RECORDS: {customers.length} CUSTOMERS / {accounts.length} ACCOUNTS / {transactions.length} TRANSACTIONS
        <button onClick={onBack} style={{ ...btnStyle(false), marginLeft: '16px' }}>◄ RETURN TO TERMINAL</button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', marginBottom: '8px', flexWrap: 'wrap', gap: '4px' }}>
        {['overview', 'customers', 'accounts', 'transactions', 'cobol'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={btnStyle(tab === t)}>
            {t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
        <button onClick={seedDatabase} disabled={seeding} style={{ ...btnStyle(false), color: '#AAFFAA', borderColor: '#AAFFAA' }}>
          {seeding ? '⏳ WORKING...' : '▶ SEED SAMPLE DATABASE'}
        </button>
        <button onClick={loadData} disabled={loading} style={btnStyle(false)}>
          ↻ REFRESH DATA
        </button>
        <button onClick={resetAll} disabled={seeding} style={{ ...btnStyle(false), color: '#FF3333', borderColor: '#FF3333' }}>
          ✕ RESET ALL DATA
        </button>
      </div>

      {msg && (
        <div style={{ color: '#AAFFAA', background: '#001100', border: '1px solid #336633', padding: '4px 8px', marginBottom: '8px', fontSize: '12px' }}>
          STATUS: {msg}
        </div>
      )}

      {loading ? (
        <div style={{ color: '#33FF33', textAlign: 'center', marginTop: '32px' }}>LOADING DATABASE RECORDS...</div>
      ) : (
        <>
          {tab === 'overview' && (
            <div style={{ lineHeight: '2' }}>
              <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '8px' }}>DATABASE OVERVIEW - BANKDB01</div>
              <div>CUSTOMER MASTER (CUSTMAST)  :  {customers.length} RECORDS</div>
              <div>ACCOUNT MASTER  (ACCTMAST)  :  {accounts.length} RECORDS</div>
              <div>TRANSACTION LOG (TRANLOG)   :  {transactions.length} RECORDS</div>
              <div style={{ marginTop: '8px', color: '#668866' }}>
                ACTIVE CUSTOMERS    : {customers.filter(c => c.status === 'A').length}<br />
                INACTIVE CUSTOMERS  : {customers.filter(c => c.status === 'I').length}<br />
                DELETED CUSTOMERS   : {customers.filter(c => c.status === 'D').length}<br />
                ACTIVE ACCOUNTS     : {accounts.filter(a => a.status === 'A').length}<br />
                DORMANT ACCOUNTS    : {accounts.filter(a => a.status === 'D').length}<br />
                FROZEN ACCOUNTS     : {accounts.filter(a => a.status === 'F').length}<br />
              </div>
              <div style={{ marginTop: '8px', color: '#33FF33' }}>
                TOTAL DEPOSITS (GBP): {accounts.filter(a => a.balance > 0).reduce((s, a) => s + a.balance, 0).toFixed(2)}<br />
                TOTAL LOANS (GBP)   : {Math.abs(accounts.filter(a => a.balance < 0).reduce((s, a) => s + a.balance, 0)).toFixed(2)}
              </div>
            </div>
          )}

          {tab === 'customers' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>CUST-ID</th>
                    <th style={thStyle}>SURNAME</th>
                    <th style={thStyle}>FORENAME</th>
                    <th style={thStyle}>DOB</th>
                    <th style={thStyle}>SORT</th>
                    <th style={thStyle}>POSTCODE</th>
                    <th style={thStyle}>STS</th>
                    <th style={thStyle}>TYPE</th>
                    <th style={thStyle}>OPEN</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map(c => (
                    <tr key={c.id}>
                      <td style={tdStyle}>{c.customer_id}</td>
                      <td style={tdStyle}>{c.surname}</td>
                      <td style={tdStyle}>{c.forename}</td>
                      <td style={tdStyle}>{c.dob}</td>
                      <td style={tdStyle}>{c.sort_code}</td>
                      <td style={tdStyle}>{c.postcode}</td>
                      <td style={{ ...tdStyle, color: c.status === 'A' ? '#AAFFAA' : c.status === 'D' ? '#FF3333' : '#FF9933' }}>{c.status}</td>
                      <td style={tdStyle}>{c.customer_type}</td>
                      <td style={tdStyle}>{c.open_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tab === 'accounts' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>ACCOUNT-NUM</th>
                    <th style={thStyle}>CUST-ID</th>
                    <th style={thStyle}>TYPE</th>
                    <th style={thStyle}>CCY</th>
                    <th style={thStyle}>BALANCE</th>
                    <th style={thStyle}>CREDIT-LIM</th>
                    <th style={thStyle}>INT %</th>
                    <th style={thStyle}>STS</th>
                    <th style={thStyle}>OPEN-DATE</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map(a => (
                    <tr key={a.id}>
                      <td style={tdStyle}>{a.account_number}</td>
                      <td style={tdStyle}>{a.customer_id}</td>
                      <td style={tdStyle}>{a.account_type}</td>
                      <td style={tdStyle}>{a.currency}</td>
                      <td style={{ ...tdStyle, color: parseFloat(a.balance) < 0 ? '#FF3333' : '#AAFFAA', textAlign: 'right' }}>{parseFloat(a.balance || 0).toFixed(2)}</td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>{parseFloat(a.credit_limit || 0).toFixed(2)}</td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>{parseFloat(a.interest_rate || 0).toFixed(2)}</td>
                      <td style={{ ...tdStyle, color: a.status === 'A' ? '#AAFFAA' : '#FF3333' }}>{a.status}</td>
                      <td style={tdStyle}>{a.open_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tab === 'transactions' && (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>TRAN-ID</th>
                    <th style={thStyle}>ACCOUNT</th>
                    <th style={thStyle}>TYPE</th>
                    <th style={thStyle}>AMOUNT</th>
                    <th style={thStyle}>BAL-AFTER</th>
                    <th style={thStyle}>POST-DATE</th>
                    <th style={thStyle}>REFERENCE</th>
                    <th style={thStyle}>DESCRIPTION</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.slice(0, 100).map(t => (
                    <tr key={t.id}>
                      <td style={tdStyle}>{t.tran_id}</td>
                      <td style={tdStyle}>{t.account_number}</td>
                      <td style={{ ...tdStyle, color: t.tran_type === 'CR' ? '#AAFFAA' : t.tran_type === 'TRF' ? '#3399FF' : '#FF9933', fontWeight: 'bold' }}>{t.tran_type}</td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>{parseFloat(t.amount || 0).toFixed(2)}</td>
                      <td style={{ ...tdStyle, color: parseFloat(t.balance_after) < 0 ? '#FF3333' : '#33FF33', textAlign: 'right' }}>{parseFloat(t.balance_after || 0).toFixed(2)}</td>
                      <td style={tdStyle}>{t.post_date}</td>
                      <td style={tdStyle}>{t.reference}</td>
                      <td style={tdStyle}>{(t.description || '').slice(0, 30)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {transactions.length > 100 && <div style={{ color: '#668866', marginTop: '4px' }}>SHOWING FIRST 100 OF {transactions.length} RECORDS</div>}
            </div>
          )}

          {tab === 'cobol' && (
            <div style={{ lineHeight: '1.8' }}>
              <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '8px' }}>PROGRAM LIBRARY - BANKMASTER/VS COBOL PROGRAMS</div>
              {[
                { name: 'CUSTMNT', trans: 'CUST', desc: 'Customer Master Maintenance', size: '4.2KB', date: '15/03/84' },
                { name: 'CUSTINQ', trans: 'CSTQ', desc: 'Customer Master Inquiry Only', size: '2.8KB', date: '15/03/84' },
                { name: 'ACCTMNT', trans: 'ACCT', desc: 'Account Maintenance & Balance', size: '5.1KB', date: '22/06/84' },
                { name: 'ACCTINQ', trans: 'AQRY', desc: 'Account Inquiry Read-Only', size: '3.2KB', date: '22/06/84' },
                { name: 'TRANPST', trans: 'TRAN', desc: 'Transaction Posting Program', size: '6.8KB', date: '10/09/84' },
                { name: 'TRANINQ', trans: 'TQRY', desc: 'Transaction History Inquiry', size: '4.4KB', date: '10/09/84' },
                { name: 'BKGMENU', trans: 'MENU', desc: 'Main Banking Menu', size: '1.9KB', date: '01/01/84' },
                { name: 'DFHDFLT', trans: 'CICS', desc: 'CICS Default Error Handler', size: '2.1KB', date: '01/01/84' },
              ].map(p => (
                <div key={p.name} style={{ display: 'flex', gap: '16px', color: '#33FF33' }}>
                  <span style={{ color: '#AAFFAA', fontWeight: 'bold', width: '10ch' }}>{p.name}</span>
                  <span style={{ color: '#3399FF', width: '6ch' }}>{p.trans}</span>
                  <span style={{ width: '38ch' }}>{p.desc}</span>
                  <span style={{ color: '#668866' }}>{p.size}</span>
                  <span style={{ color: '#668866' }}>{p.date}</span>
                </div>
              ))}
              <div style={{ color: '#668866', marginTop: '12px', fontSize: '11px' }}>
                USE PF12 ON ANY TRANSACTION SCREEN TO VIEW FULL COBOL SOURCE AND DB2 SQL
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}