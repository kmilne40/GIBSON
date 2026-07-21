import React, { useState } from 'react';
import { SCENARIOS } from '@/data/scenarioLibrary';
import { base44 } from '@/api/base44Client';
import { logAudit } from '@/lib/auditLogger';

const S = {
  page: { background: '#000', color: '#33FF33', fontFamily: "'Courier New', monospace", minHeight: '100vh', padding: '16px', fontSize: '12px' },
  h1: { color: '#AAFFAA', fontWeight: 'bold', fontSize: '16px', letterSpacing: '3px' },
  sep: { color: '#336633', marginBottom: '12px' },
  card: { border: '1px solid #336633', padding: '12px 16px', marginBottom: '10px', cursor: 'pointer', background: '#000800' },
  cardActive: { border: '1px solid #33FF33', padding: '12px 16px', marginBottom: '10px', cursor: 'pointer', background: '#001100' },
  badge: (color) => ({ display: 'inline-block', border: `1px solid ${color}`, color, padding: '1px 6px', fontSize: '10px', marginRight: '6px' }),
  btn: (color = '#33FF33') => ({ padding: '6px 18px', background: '#001100', border: `1px solid ${color}`, color, cursor: 'pointer', fontFamily: "'Courier New', monospace", fontSize: '12px', marginRight: '8px' }),
  hint: { color: '#668866', borderLeft: '2px solid #336633', paddingLeft: '8px', marginBottom: '4px' },
  task: { color: '#AAFFAA', marginBottom: '3px' },
};

const CATEGORY_COLORS = {
  'DATA INTEGRITY': '#33FF33',
  'ACCOUNT SECURITY': '#3399FF',
  'TRANSACTION FRAUD': '#FF9933',
  'SQL INJECTION': '#FF3333',
  'BUSINESS LOGIC': '#FF9933',
  'INSIDER THREAT': '#FF3333',
  'ACCESS CONTROL': '#FF3333',
};

export default function ScenarioLab() {
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [setupStatus, setSetupStatus] = useState('');
  const [setupDone, setSetupDone] = useState(false);
  const [filter, setFilter] = useState('ALL');

  const categories = ['ALL', ...Array.from(new Set(SCENARIOS.map(s => s.category)))];

  const filtered = filter === 'ALL' ? SCENARIOS : SCENARIOS.filter(s => s.category === filter);

  const activateScenario = async (scenario) => {
    setLoading(true);
    setSetupDone(false);
    setSetupStatus('INITIALISING SCENARIO...');

    const steps = [];

    if (scenario.setupCustomers?.length) {
      setSetupStatus('INSERTING TEST CUSTOMERS...');
      for (const c of scenario.setupCustomers) {
        // avoid duplicate if already exists
        const existing = await base44.entities.Customer.filter({ customer_id: c.customer_id });
        if (!existing.length) {
          await base44.entities.Customer.create(c);
          steps.push(`+ CUSTOMER ${c.customer_id} (${c.surname})`);
        } else {
          steps.push(`= CUSTOMER ${c.customer_id} ALREADY EXISTS`);
        }
      }
    }

    if (scenario.setupAccounts?.length) {
      setSetupStatus('INSERTING TEST ACCOUNTS...');
      for (const a of scenario.setupAccounts) {
        const existing = await base44.entities.Account.filter({ account_number: a.account_number });
        if (!existing.length) {
          await base44.entities.Account.create(a);
          steps.push(`+ ACCOUNT ${a.account_number} (BAL: £${a.balance.toFixed(2)})`);
        } else {
          steps.push(`= ACCOUNT ${a.account_number} ALREADY EXISTS`);
        }
      }
    }

    if (scenario.setupTransactions?.length) {
      setSetupStatus('INJECTING FRAUDULENT TRANSACTIONS...');
      for (const t of scenario.setupTransactions) {
        const existing = await base44.entities.Transaction.filter({ tran_id: t.tran_id });
        if (!existing.length) {
          await base44.entities.Transaction.create(t);
          steps.push(`+ TRANSACTION ${t.tran_id} (${t.tran_type} £${t.amount.toFixed(2)})`);
        } else {
          steps.push(`= TRANSACTION ${t.tran_id} ALREADY EXISTS`);
        }
      }
    }

    if (scenario.setupAuditLogs?.length) {
      setSetupStatus('SEEDING AUDIT TRAIL...');
      for (const log of scenario.setupAuditLogs) {
        await base44.entities.AuditLog.create({ ...log, terminal_id: log.terminal_id || 'LT0042' });
        steps.push(`+ AUDIT LOG: ${log.event_type} (${log.operator_id})`);
      }
    }

    await logAudit({
      event_type: 'NAVIGATION',
      operator_id: 'INSTRUCTOR',
      details: `SCENARIO ACTIVATED: ${scenario.id} - ${scenario.title}`,
      result: 'SUCCESS',
      affected_entity: 'ScenarioLab',
    });

    setSetupStatus(`SCENARIO ${scenario.id} READY — ${steps.length} RECORDS INJECTED`);
    setLoading(false);
    setSetupDone(true);
    setSelected(s => ({ ...s, _setupLog: steps }));
  };

  return (
    <div style={S.page}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', marginBottom: '4px', flexWrap: 'wrap' }}>
        <div style={S.h1}>VULNERABILITY CHALLENGE LAB</div>
        <div style={{ color: '#668866', fontSize: '11px' }}>BANKMASTER/VS SECURITY TRAINING — SYSID: PROD</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
          <a href="/" style={{ color: '#3399FF', fontSize: '11px' }}>← TERMINAL</a>
          <a href="/db" style={{ color: '#3399FF', fontSize: '11px' }}>DB EXPLORER</a>
          <a href="/audit" style={{ color: '#FF9933', fontSize: '11px' }}>AUDIT LOG</a>
          <a href="/solutions" style={{ color: '#FF9933', fontSize: '11px', fontWeight: 'bold' }}>SOLUTIONS [INSTRUCTOR]</a>
          <a href="/manual" style={{ color: '#3399FF', fontSize: '11px' }}>MANUAL</a>
        </div>
      </div>
      <div style={S.sep}>{'─'.repeat(100)}</div>

      <div style={{ color: '#668866', marginBottom: '12px', fontSize: '11px' }}>
        SELECT A CHALLENGE BELOW. CLICK ACTIVATE to inject the scenario state into the live database, then use DB EXPLORER or the TERMINAL to investigate.
      </div>

      {/* Category filter */}
      <div style={{ marginBottom: '14px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {categories.map(cat => (
          <button
            key={cat}
            style={{ ...S.btn(filter === cat ? '#AAFFAA' : '#336633'), background: filter === cat ? '#001100' : 'transparent', fontSize: '11px', padding: '3px 10px' }}
            onClick={() => setFilter(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        {/* Scenario list */}
        <div style={{ flex: '0 0 380px', minWidth: '280px' }}>
          {filtered.map(scenario => (
            <div
              key={scenario.id}
              style={selected?.id === scenario.id ? S.cardActive : S.card}
              onClick={() => { setSelected(scenario); setSetupDone(false); setSetupStatus(''); }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{ color: '#FFFF99', fontWeight: 'bold', fontSize: '11px' }}>{scenario.id}</span>
                <span style={S.badge(CATEGORY_COLORS[scenario.category] || '#33FF33')}>{scenario.category}</span>
                <span style={S.badge(scenario.difficultyColor)}>{scenario.difficulty}</span>
              </div>
              <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '2px' }}>{scenario.title}</div>
              <div style={{ color: '#668866', fontSize: '11px' }}>{scenario.vuln}</div>
            </div>
          ))}
        </div>

        {/* Detail panel */}
        <div style={{ flex: 1, minWidth: '300px' }}>
          {!selected && (
            <div style={{ color: '#336633', padding: '24px 0' }}>
              ← SELECT A CHALLENGE FROM THE LIST TO VIEW DETAILS
            </div>
          )}
          {selected && (
            <div>
              <div style={{ color: '#FFFF99', fontWeight: 'bold', fontSize: '14px', letterSpacing: '2px', marginBottom: '2px' }}>
                {selected.id}: {selected.title}
              </div>
              <div style={{ marginBottom: '10px' }}>
                <span style={S.badge(CATEGORY_COLORS[selected.category] || '#33FF33')}>{selected.category}</span>
                <span style={S.badge(selected.difficultyColor)}>{selected.difficulty}</span>
              </div>

              <div style={{ color: '#668866', fontSize: '11px', marginBottom: '10px', borderLeft: '2px solid #FF3333', paddingLeft: '8px' }}>
                VULNERABILITY: {selected.vuln}
              </div>

              <div style={{ color: '#AAFFAA', marginBottom: '8px' }}>{selected.objective}</div>

              <div style={{ marginBottom: '12px' }}>
                <div style={{ color: '#FFFF99', marginBottom: '4px', fontSize: '11px', fontWeight: 'bold' }}>▶ TRAINEE TASKS</div>
                {selected.tasks.map((t, i) => (
                  <div key={i} style={S.task}>  {i + 1}. {t}</div>
                ))}
              </div>

              <div style={{ marginBottom: '14px' }}>
                <div style={{ color: '#FF9933', marginBottom: '4px', fontSize: '11px', fontWeight: 'bold' }}>💡 INVESTIGATOR HINTS</div>
                {selected.hints.map((h, i) => (
                  <div key={i} style={{ ...S.hint, marginBottom: '6px' }}>{h}</div>
                ))}
              </div>

              {/* Data preview */}
              <div style={{ marginBottom: '14px', background: '#000800', border: '1px solid #224422', padding: '8px' }}>
                <div style={{ color: '#668866', fontSize: '11px', marginBottom: '4px' }}>SCENARIO WILL INJECT:</div>
                <div style={{ color: '#33FF33', fontSize: '11px' }}>
                  {selected.setupCustomers?.length > 0 && <div>+ {selected.setupCustomers.length} CUSTOMER RECORD(S)</div>}
                  {selected.setupAccounts?.length > 0 && <div>+ {selected.setupAccounts.length} ACCOUNT RECORD(S)</div>}
                  {selected.setupTransactions?.length > 0 && <div>+ {selected.setupTransactions.length} TRANSACTION RECORD(S)</div>}
                  {selected.setupAuditLogs?.length > 0 && <div>+ {selected.setupAuditLogs.length} AUDIT LOG ENTRY(IES)</div>}
                  {!selected.setupCustomers?.length && !selected.setupAccounts?.length && !selected.setupTransactions?.length && !selected.setupAuditLogs?.length && (
                    <div style={{ color: '#668866' }}>USES EXISTING DATA — NO INJECTION REQUIRED</div>
                  )}
                </div>
              </div>

              {/* Activate button */}
              <div style={{ marginBottom: '10px' }}>
                <button
                  style={S.btn(loading ? '#336633' : '#AAFFAA')}
                  onClick={() => activateScenario(selected)}
                  disabled={loading}
                >
                  {loading ? '⏳ SETTING UP...' : '▶ ACTIVATE SCENARIO'}
                </button>
                <a href="/db" style={{ ...S.btn('#3399FF'), textDecoration: 'none', display: 'inline-block' }}>
                  OPEN DB EXPLORER →
                </a>
              </div>

              {/* Setup log */}
              {setupStatus && (
                <div style={{ background: '#000800', border: '1px solid #336633', padding: '8px', fontSize: '11px' }}>
                  <div style={{ color: setupDone ? '#33FF33' : '#FF9933', fontWeight: 'bold', marginBottom: '4px' }}>
                    {setupDone ? '✓ ' : '⏳ '}{setupStatus}
                  </div>
                  {selected._setupLog?.map((line, i) => (
                    <div key={i} style={{ color: '#668866' }}>{line}</div>
                  ))}
                  {setupDone && (
                    <div style={{ color: '#AAFFAA', marginTop: '6px', borderTop: '1px solid #224422', paddingTop: '6px' }}>
                      SCENARIO ACTIVE — USE DB EXPLORER OR TERMINAL TO INVESTIGATE
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}