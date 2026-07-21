import React, { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';
import { logAudit } from '@/lib/auditLogger';

const S = {
  page: { background: '#000', color: '#33FF33', fontFamily: "'Courier New', monospace", minHeight: '100vh', padding: '16px', fontSize: '12px' },
  h1: { color: '#AAFFAA', fontWeight: 'bold', fontSize: '16px', letterSpacing: '3px', marginBottom: '4px' },
  sep: { color: '#336633', marginBottom: '10px' },
  tab: { padding: '4px 12px', cursor: 'pointer', fontSize: '12px', border: '1px solid #336633', marginRight: '4px', background: 'transparent', color: '#33FF33', fontFamily: "'Courier New', monospace" },
  tabActive: { padding: '4px 12px', cursor: 'pointer', fontSize: '12px', border: '1px solid #33FF33', marginRight: '4px', background: '#001100', color: '#AAFFAA', fontWeight: 'bold', fontFamily: "'Courier New', monospace" },
  table: { borderCollapse: 'collapse', width: '100%', marginTop: '8px' },
  th: { color: '#AAFFAA', borderBottom: '1px solid #336633', padding: '3px 8px', textAlign: 'left', fontWeight: 'bold', fontSize: '11px', whiteSpace: 'nowrap' },
  td: { color: '#33FF33', padding: '2px 8px', borderBottom: '1px solid #001100', fontSize: '11px', whiteSpace: 'nowrap' },
  textarea: { width: '100%', background: '#001100', border: '1px solid #336633', color: '#3399FF', fontFamily: "'Courier New', monospace", fontSize: '13px', padding: '8px', resize: 'vertical', outline: 'none', boxSizing: 'border-box' },
  btn: { padding: '5px 16px', background: '#001100', border: '1px solid #33FF33', color: '#33FF33', cursor: 'pointer', fontFamily: "'Courier New', monospace", fontSize: '12px', marginRight: '8px' },
  label: { color: '#AAFFAA', marginRight: '8px' },
};

const TABLES = ['Customer', 'Account', 'Transaction', 'COBOLProgram'];

const SAMPLE_QUERIES = [
  { label: 'All customers', sql: 'SELECT * FROM Customer' },
  { label: 'Active customers', sql: 'SELECT * FROM Customer WHERE status = "A"' },
  { label: 'All accounts', sql: 'SELECT * FROM Account' },
  { label: 'Current accounts', sql: 'SELECT * FROM Account WHERE account_type = "CUR"' },
  { label: 'Negative balances', sql: 'SELECT * FROM Account WHERE balance < 0' },
  { label: 'All transactions', sql: 'SELECT * FROM Transaction' },
  { label: 'Credits only', sql: 'SELECT * FROM Transaction WHERE tran_type = "CR"' },
  { label: 'Large transactions', sql: 'SELECT * FROM Transaction WHERE amount > 10000' },
  { label: 'Account 1000000101', sql: 'SELECT * FROM Transaction WHERE account_number = "1000000101"' },
  { label: 'Savings accounts', sql: 'SELECT * FROM Account WHERE account_type = "SAV"' },
];

function parseSQL(sql) {
  const s = sql.trim();
  // SELECT * FROM <Table> [WHERE <field> <op> <value>] [LIMIT n]
  const selectMatch = s.match(/^SELECT\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+?))?(?:\s+LIMIT\s+(\d+))?$/i);
  if (!selectMatch) return { error: 'SYNTAX ERROR: Only SELECT * FROM <Table> [WHERE field op value] [LIMIT n] supported' };
  const table = selectMatch[2];
  const whereClause = selectMatch[3] || null;
  const limit = selectMatch[4] ? parseInt(selectMatch[4]) : null;
  if (!TABLES.includes(table)) return { error: `TABLE NOT FOUND: ${table}  (valid: ${TABLES.join(', ')})` };
  return { table, whereClause, limit };
}

function applyWhere(rows, clause) {
  if (!clause) return rows;
  // Support: field op value  where op is =, !=, <, >, <=, >=
  const m = clause.match(/^(\w+)\s*(=|!=|<>|<=|>=|<|>)\s*"?([^"]*)"?$/i);
  if (!m) return { error: `INVALID WHERE: ${clause}` };
  const [, field, op, val] = m;
  const numVal = parseFloat(val);
  const isNum = !isNaN(numVal) && val.trim() !== '';
  return rows.filter(row => {
    const rv = row[field];
    if (rv === undefined) return false;
    const lv = isNum ? parseFloat(rv) : String(rv);
    const rv2 = isNum ? numVal : val;
    if (op === '=' || op === '==') return lv == rv2;
    if (op === '!=' || op === '<>') return lv != rv2;
    if (op === '<') return lv < rv2;
    if (op === '>') return lv > rv2;
    if (op === '<=') return lv <= rv2;
    if (op === '>=') return lv >= rv2;
    return false;
  });
}

export default function DbExplorer() {
  const [activeTab, setActiveTab] = useState('SQL');
  const [tableTab, setTableTab] = useState('Customer');
  const [tableData, setTableData] = useState({});
  const [loading, setLoading] = useState(false);
  const [sql, setSql] = useState('SELECT * FROM Customer');
  const [queryResult, setQueryResult] = useState(null);
  const [queryError, setQueryError] = useState('');
  const [queryTime, setQueryTime] = useState(null);

  useEffect(() => {
    loadTable(tableTab);
  }, [tableTab]);

  const loadTable = async (name) => {
    if (tableData[name]) return;
    setLoading(true);
    const rows = await base44.entities[name].list();
    setTableData(prev => ({ ...prev, [name]: rows }));
    setLoading(false);
  };

  const runQuery = async () => {
    setQueryError('');
    setQueryResult(null);
    const t0 = performance.now();
    const parsed = parseSQL(sql);
    if (parsed.error) {
      setQueryError(parsed.error);
      logAudit({ event_type: 'SQL_QUERY', operator_id: 'DB_EXPLORER', details: sql, result: 'ERROR', affected_entity: '', row_count: 0, duration_ms: 0 });
      return;
    }
    const { table, whereClause, limit } = parsed;
    setLoading(true);
    let rows = tableData[table] || await base44.entities[table].list();
    if (!tableData[table]) setTableData(prev => ({ ...prev, [table]: rows }));
    if (whereClause) {
      const filtered = applyWhere(rows, whereClause);
      if (filtered && filtered.error) {
        setQueryError(filtered.error);
        logAudit({ event_type: 'SQL_QUERY', operator_id: 'DB_EXPLORER', details: sql, result: 'ERROR', affected_entity: table, row_count: 0, duration_ms: 0 });
        setLoading(false);
        return;
      }
      rows = filtered;
    }
    if (limit) rows = rows.slice(0, limit);
    const ms = parseFloat((performance.now() - t0).toFixed(1));
    setQueryTime(ms);
    setQueryResult({ rows, table });
    setLoading(false);
    logAudit({ event_type: 'SQL_QUERY', operator_id: 'DB_EXPLORER', details: sql, result: 'SUCCESS', affected_entity: table, row_count: rows.length, duration_ms: ms });
  };

  const cols = (rows) => rows.length > 0 ? Object.keys(rows[0]).filter(k => k !== '__v') : [];

  return (
    <div style={S.page}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', marginBottom: '4px' }}>
        <div style={S.h1}>DB2 DATABASE EXPLORER</div>
        <div style={{ color: '#668866', fontSize: '11px' }}>BANKMASTER/VS  —  SYSID: PROD</div>
        <a href="/" style={{ color: '#3399FF', fontSize: '11px', marginLeft: 'auto' }}>← BACK TO TERMINAL</a>
        <a href="/manual" style={{ color: '#3399FF', fontSize: '11px' }}>MANUAL</a>
        <a href="/audit" style={{ color: '#FF9933', fontSize: '11px' }}>AUDIT LOG</a>
        <a href="/scenarios" style={{ color: '#AAFFAA', fontSize: '11px', fontWeight: 'bold' }}>SCENARIO LAB</a>
      </div>
      <div style={S.sep}>{'─'.repeat(90)}</div>

      <div style={{ marginBottom: '10px' }}>
        <button style={activeTab === 'SQL' ? S.tabActive : S.tab} onClick={() => setActiveTab('SQL')}>SQL QUERY</button>
        <button style={activeTab === 'TABLES' ? S.tabActive : S.tab} onClick={() => setActiveTab('TABLES')}>BROWSE TABLES</button>
        <button style={activeTab === 'SCHEMA' ? S.tabActive : S.tab} onClick={() => setActiveTab('SCHEMA')}>SCHEMA</button>
      </div>

      {activeTab === 'SQL' && (
        <div>
          <div style={{ marginBottom: '6px', color: '#668866' }}>
            SUPPORTED: SELECT * FROM &lt;Table&gt; [WHERE field op value] [LIMIT n]  —  Tables: {TABLES.join('  ')}
          </div>
          <textarea
            style={{ ...S.textarea, height: '80px' }}
            value={sql}
            onChange={e => setSql(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runQuery(); } }}
            spellCheck={false}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px', marginBottom: '10px', flexWrap: 'wrap' }}>
            <button style={S.btn} onClick={runQuery}>▶ EXECUTE (Ctrl+Enter)</button>
            {SAMPLE_QUERIES.map(q => (
              <button key={q.label} style={{ ...S.btn, border: '1px solid #336633', color: '#668866', fontSize: '11px' }} onClick={() => setSql(q.sql)}>{q.label}</button>
            ))}
          </div>

          {loading && <div style={{ color: '#FF9933' }}>EXECUTING QUERY...</div>}
          {queryError && <div style={{ color: '#FF3333', marginBottom: '8px' }}>ERROR: {queryError}</div>}
          {queryResult && !loading && (
            <div>
              <div style={{ color: '#668866', marginBottom: '4px', fontSize: '11px' }}>
                {queryResult.rows.length} ROW(S) RETURNED  —  TABLE: {queryResult.table}  —  {queryTime}ms
              </div>
              {queryResult.rows.length === 0
                ? <div style={{ color: '#FF9933' }}>NO ROWS FOUND</div>
                : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={S.table}>
                      <thead><tr>{cols(queryResult.rows).map(c => <th key={c} style={S.th}>{c.toUpperCase()}</th>)}</tr></thead>
                      <tbody>
                        {queryResult.rows.map((row, i) => (
                          <tr key={i}>
                            {cols(queryResult.rows).map(c => (
                              <td key={c} style={{ ...S.td, color: c.includes('balance') || c.includes('amount') ? (parseFloat(row[c]) < 0 ? '#FF3333' : '#FFFF99') : S.td.color }}>
                                {row[c] === null || row[c] === undefined ? <span style={{ color: '#336633' }}>NULL</span> : String(row[c])}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              }
            </div>
          )}
        </div>
      )}

      {activeTab === 'TABLES' && (
        <div>
          <div style={{ marginBottom: '8px' }}>
            {TABLES.map(t => <button key={t} style={tableTab === t ? S.tabActive : S.tab} onClick={() => setTableTab(t)}>{t.toUpperCase()}</button>)}
          </div>
          {loading && <div style={{ color: '#FF9933' }}>LOADING...</div>}
          {tableData[tableTab] && (
            <div>
              <div style={{ color: '#668866', marginBottom: '4px', fontSize: '11px' }}>{tableData[tableTab].length} ROWS IN {tableTab.toUpperCase()}</div>
              <div style={{ overflowX: 'auto' }}>
                <table style={S.table}>
                  <thead><tr>{cols(tableData[tableTab]).map(c => <th key={c} style={S.th}>{c.toUpperCase()}</th>)}</tr></thead>
                  <tbody>
                    {tableData[tableTab].map((row, i) => (
                      <tr key={i}>
                        {cols(tableData[tableTab]).map(c => (
                          <td key={c} style={{ ...S.td, color: c.includes('balance') || c.includes('amount') ? (parseFloat(row[c]) < 0 ? '#FF3333' : '#FFFF99') : S.td.color }}>
                            {row[c] === null || row[c] === undefined ? <span style={{ color: '#336633' }}>NULL</span> : String(row[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'SCHEMA' && (
        <div>
          {[
            { name: 'Customer', cols: [['customer_id','VARCHAR(8)','PK'],['surname','VARCHAR(30)','NOT NULL'],['forename','VARCHAR(20)','NOT NULL'],['dob','VARCHAR(8)',''],['sort_code','VARCHAR(6)',''],['ni_number','VARCHAR(9)',''],['address1','VARCHAR(40)',''],['address2','VARCHAR(40)',''],['address3','VARCHAR(30)',''],['postcode','VARCHAR(8)',''],['status','CHAR(1)','A/I/D'],['customer_type','CHAR(1)','P/C'],['open_date','VARCHAR(8)',''],['operator_id','VARCHAR(8)',''],['last_update_date','VARCHAR(8)','']] },
            { name: 'Account', cols: [['account_number','VARCHAR(10)','PK'],['customer_id','VARCHAR(8)','FK→Customer'],['account_type','CHAR(3)','CUR/SAV/OVD/LON'],['sort_code','VARCHAR(6)',''],['open_date','VARCHAR(8)',''],['currency','CHAR(3)','GBP/USD/EUR'],['balance','DECIMAL(13,2)',''],['credit_limit','DECIMAL(13,2)',''],['interest_rate','DECIMAL(5,2)',''],['status','CHAR(1)','A/D/F'],['operator_id','VARCHAR(8)',''],['last_update_date','VARCHAR(8)','']] },
            { name: 'Transaction', cols: [['tran_id','VARCHAR(10)','PK'],['account_number','VARCHAR(10)','FK→Account'],['tran_type','CHAR(3)','CR/DR/TRF'],['amount','DECIMAL(13,2)','NOT NULL'],['description','VARCHAR(40)',''],['reference','VARCHAR(10)',''],['to_account','VARCHAR(10)','TRF only'],['value_date','VARCHAR(8)',''],['post_date','VARCHAR(8)',''],['post_time','VARCHAR(6)',''],['balance_after','DECIMAL(13,2)',''],['operator_id','VARCHAR(8)','']] },
          ].map(({ name, cols }) => (
            <div key={name} style={{ marginBottom: '20px' }}>
              <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '4px' }}>TABLE: {name.toUpperCase()}</div>
              <table style={S.table}>
                <thead><tr><th style={S.th}>COLUMN</th><th style={S.th}>TYPE</th><th style={S.th}>NOTES</th></tr></thead>
                <tbody>
                  {cols.map(([col, type, note]) => (
                    <tr key={col}><td style={{ ...S.td, color: '#3399FF' }}>{col}</td><td style={{ ...S.td, color: '#FFFF99' }}>{type}</td><td style={{ ...S.td, color: '#668866' }}>{note}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}