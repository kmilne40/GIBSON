import React, { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';

const S = {
  page: { background: '#000', color: '#33FF33', fontFamily: "'Courier New', monospace", minHeight: '100vh', padding: '16px', fontSize: '12px' },
  h1: { color: '#AAFFAA', fontWeight: 'bold', fontSize: '16px', letterSpacing: '3px', marginBottom: '4px' },
  sep: { color: '#336633', marginBottom: '10px' },
  tab: { padding: '4px 12px', cursor: 'pointer', fontSize: '12px', border: '1px solid #336633', marginRight: '4px', background: 'transparent', color: '#33FF33', fontFamily: "'Courier New', monospace" },
  tabActive: { padding: '4px 12px', cursor: 'pointer', fontSize: '12px', border: '1px solid #33FF33', marginRight: '4px', background: '#001100', color: '#AAFFAA', fontWeight: 'bold', fontFamily: "'Courier New', monospace" },
  table: { borderCollapse: 'collapse', width: '100%', marginTop: '8px' },
  th: { color: '#AAFFAA', borderBottom: '1px solid #336633', padding: '4px 10px', textAlign: 'left', fontWeight: 'bold', fontSize: '11px', whiteSpace: 'nowrap' },
  td: { color: '#33FF33', padding: '3px 10px', borderBottom: '1px solid #001100', fontSize: '11px', whiteSpace: 'nowrap' },
  btn: { padding: '4px 14px', background: '#001100', border: '1px solid #33FF33', color: '#33FF33', cursor: 'pointer', fontFamily: "'Courier New', monospace", fontSize: '12px', marginRight: '6px' },
  detail: { background: '#001100', border: '1px solid #336633', padding: '12px', fontFamily: "'Courier New', monospace", fontSize: '12px', color: '#3399FF', whiteSpace: 'pre-wrap', wordBreak: 'break-all', marginTop: '8px' },
};

const TYPE_COLORS = {
  SQL_QUERY:   '#3399FF',
  TRANSACTION: '#FFFF99',
  LOGIN:       '#AAFFAA',
  NAVIGATION:  '#668866',
};

const RESULT_COLORS = {
  SUCCESS: '#33FF33',
  ERROR:   '#FF3333',
};

const FILTERS = ['ALL', 'SQL_QUERY', 'TRANSACTION', 'LOGIN'];

export default function AuditLogScreen() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [selected, setSelected] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchLogs = async () => {
    setLoading(true);
    const data = await base44.entities.AuditLog.list('-created_date', 200);
    setLogs(data);
    setLoading(false);
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchLogs, 3000);
    return () => clearInterval(id);
  }, [autoRefresh]);

  const filtered = filter === 'ALL' ? logs : logs.filter(l => l.event_type === filter);

  const fmt = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
  };

  const stats = {
    total: logs.length,
    sql: logs.filter(l => l.event_type === 'SQL_QUERY').length,
    tran: logs.filter(l => l.event_type === 'TRANSACTION').length,
    errors: logs.filter(l => l.result === 'ERROR').length,
  };

  return (
    <div style={S.page}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', marginBottom: '4px' }}>
        <div style={S.h1}>AUDIT TRAIL — BANKMASTER/VS</div>
        <div style={{ color: '#668866', fontSize: '11px' }}>TERMINAL: LT0042  SYSID: PROD</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
          <a href="/" style={{ color: '#3399FF', fontSize: '11px' }}>← TERMINAL</a>
          <a href="/db" style={{ color: '#3399FF', fontSize: '11px' }}>DB EXPLORER</a>
          <a href="/manual" style={{ color: '#3399FF', fontSize: '11px' }}>MANUAL</a>
        </div>
      </div>
      <div style={S.sep}>{'─'.repeat(90)}</div>

      {/* Stats bar */}
      <div style={{ display: 'flex', gap: '24px', marginBottom: '10px', padding: '6px 0', borderBottom: '1px solid #002200' }}>
        {[['TOTAL EVENTS', stats.total, '#AAFFAA'], ['SQL QUERIES', stats.sql, '#3399FF'], ['TRANSACTIONS', stats.tran, '#FFFF99'], ['ERRORS', stats.errors, '#FF3333']].map(([label, val, col]) => (
          <div key={label}>
            <span style={{ color: '#668866', fontSize: '11px' }}>{label}: </span>
            <span style={{ color: col, fontWeight: 'bold' }}>{val}</span>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button style={S.btn} onClick={fetchLogs}>↺ REFRESH</button>
          <button
            style={{ ...S.btn, borderColor: autoRefresh ? '#33FF33' : '#336633', color: autoRefresh ? '#33FF33' : '#668866' }}
            onClick={() => setAutoRefresh(a => !a)}
          >
            {autoRefresh ? '● LIVE' : '○ LIVE'}
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ marginBottom: '10px' }}>
        {FILTERS.map(f => (
          <button key={f} style={filter === f ? S.tabActive : S.tab} onClick={() => setFilter(f)}>{f}</button>
        ))}
        <span style={{ color: '#668866', fontSize: '11px', marginLeft: '8px' }}>{filtered.length} records shown</span>
      </div>

      {loading && <div style={{ color: '#FF9933' }}>LOADING AUDIT RECORDS...</div>}

      {!loading && filtered.length === 0 && (
        <div style={{ color: '#668866', marginTop: '24px', textAlign: 'center' }}>
          NO AUDIT RECORDS FOUND — EVENTS WILL APPEAR HERE AS YOU USE THE SYSTEM
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div style={{ display: 'flex', gap: '12px' }}>
          {/* Log table */}
          <div style={{ flex: 1, overflowX: 'auto' }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>TIMESTAMP</th>
                  <th style={S.th}>TYPE</th>
                  <th style={S.th}>OPERATOR</th>
                  <th style={S.th}>DETAILS</th>
                  <th style={S.th}>ENTITY</th>
                  <th style={S.th}>ROWS</th>
                  <th style={S.th}>MS</th>
                  <th style={S.th}>RESULT</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((log) => (
                  <tr
                    key={log.id}
                    onClick={() => setSelected(selected?.id === log.id ? null : log)}
                    style={{ cursor: 'pointer', background: selected?.id === log.id ? '#001a00' : 'transparent' }}
                  >
                    <td style={{ ...S.td, color: '#668866' }}>{fmt(log.created_date)}</td>
                    <td style={{ ...S.td, color: TYPE_COLORS[log.event_type] || '#33FF33' }}>{log.event_type}</td>
                    <td style={{ ...S.td, color: '#AAFFAA' }}>{log.operator_id}</td>
                    <td style={{ ...S.td, maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', color: '#33FF33' }}>
                      {log.details?.slice(0, 80)}{log.details?.length > 80 ? '…' : ''}
                    </td>
                    <td style={{ ...S.td, color: '#FFFF99' }}>{log.affected_entity}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{log.row_count ?? ''}</td>
                    <td style={{ ...S.td, textAlign: 'right', color: '#668866' }}>{log.duration_ms != null ? log.duration_ms : ''}</td>
                    <td style={{ ...S.td, color: RESULT_COLORS[log.result] || '#33FF33', fontWeight: 'bold' }}>{log.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Detail panel */}
          {selected && (
            <div style={{ width: '340px', flexShrink: 0 }}>
              <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '6px' }}>EVENT DETAIL</div>
              <div style={{ color: '#668866', fontSize: '11px', marginBottom: '4px' }}>{fmt(selected.created_date)}  —  {selected.terminal_id}</div>
              <div style={{ marginBottom: '6px' }}>
                <span style={{ color: TYPE_COLORS[selected.event_type], fontWeight: 'bold' }}>{selected.event_type}</span>
                {'  '}
                <span style={{ color: RESULT_COLORS[selected.result] || '#33FF33' }}>{selected.result}</span>
              </div>
              <div style={{ color: '#668866', fontSize: '11px', marginBottom: '2px' }}>OPERATOR: <span style={{ color: '#AAFFAA' }}>{selected.operator_id}</span></div>
              {selected.affected_entity && <div style={{ color: '#668866', fontSize: '11px', marginBottom: '2px' }}>ENTITY: <span style={{ color: '#FFFF99' }}>{selected.affected_entity}</span></div>}
              {selected.row_count != null && <div style={{ color: '#668866', fontSize: '11px', marginBottom: '2px' }}>ROWS: <span style={{ color: '#33FF33' }}>{selected.row_count}</span></div>}
              {selected.duration_ms != null && <div style={{ color: '#668866', fontSize: '11px', marginBottom: '4px' }}>DURATION: <span style={{ color: '#33FF33' }}>{selected.duration_ms}ms</span></div>}
              <div style={{ color: '#668866', fontSize: '11px', marginBottom: '2px' }}>DETAILS:</div>
              <div style={S.detail}>{selected.details}</div>
              <button style={{ ...S.btn, marginTop: '8px' }} onClick={() => setSelected(null)}>CLOSE</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}