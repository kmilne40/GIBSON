import React, { useState, useRef, useEffect } from 'react';
import { base44 } from '@/api/base44Client';

// REST API Security Tester — tests for common API vulnerabilities against the bank's simulated REST endpoints
// Covers: IDOR, SQLi, missing auth, mass assignment, verbose errors, etc.

const ENDPOINTS = [
  { method: 'GET',    path: '/api/v1/customers',                   desc: 'List all customers (no auth)', vuln: 'Missing Authentication' },
  { method: 'GET',    path: '/api/v1/customers/{id}',              desc: 'Get customer by ID', vuln: 'IDOR' },
  { method: 'GET',    path: '/api/v1/accounts/{id}',               desc: 'Get account by number', vuln: 'IDOR' },
  { method: 'PUT',    path: '/api/v1/accounts/{id}/balance',       desc: 'Modify balance directly', vuln: 'Mass Assignment' },
  { method: 'GET',    path: "/api/v1/customers?surname='+OR+'1'='1", desc: 'SQL injection test', vuln: 'SQL Injection' },
  { method: 'GET',    path: '/api/v1/customers?admin=true',        desc: 'Privilege escalation via param', vuln: 'Broken Access Control' },
  { method: 'GET',    path: '/api/v1/transactions?account=1000000101&debug=true', desc: 'Debug mode exposure', vuln: 'Debug Enabled' },
  { method: 'DELETE', path: '/api/v1/customers/{id}',              desc: 'Delete without CSRF token', vuln: 'Missing CSRF' },
  { method: 'GET',    path: '/api/v1/admin/users',                 desc: 'Admin endpoint, no role check', vuln: 'Broken Auth' },
  { method: 'POST',   path: '/api/v1/transactions',                desc: 'Post transaction (no idempotency key)', vuln: 'Replay Attack' },
];

const PAYLOADS = {
  'SQL Injection':      ["' OR '1'='1", "'; DROP TABLE CUSTOMERS; --", "' UNION SELECT * FROM ACCOUNTS --", "admin'--"],
  'XSS':                ["<script>alert('xss')</script>", "<img src=x onerror=alert(1)>", "javascript:alert(1)"],
  'Path Traversal':     ["../../../etc/passwd", "..\\..\\..\\windows\\system32\\", "%2e%2e%2f%2e%2e%2f"],
  'Command Injection':  ["; ls -la", "| cat /etc/shadow", "$(whoami)", "`id`"],
  'Buffer Overflow':    ["A".repeat(100), "A".repeat(256), "%n%n%n%n"],  // COBOL VULN #1
  'Hidden Field':       ['{"authenticated":"Y","admin":"Y"}', '{"privilege_level":"9999"}'],  // COBOL VULN #2/#3
};

export default function RestApiTester({ operatorId, onBack }) {
  const [tab, setTab] = useState('endpoints');
  const [selectedEndpoint, setSelectedEndpoint] = useState(ENDPOINTS[0]);
  const [customPath, setCustomPath] = useState('');
  const [customMethod, setCustomMethod] = useState('GET');
  const [customBody, setCustomBody] = useState('');
  const [headers, setHeaders] = useState('{"Authorization": "Bearer <token>", "X-Operator-ID": "' + operatorId + '"}');
  const [responses, setResponses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [payloadType, setPayloadType] = useState('SQL Injection');
  const [payloadInput, setPayloadInput] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [responses]);

  const addResponse = (res) => setResponses(p => [...p, { ...res, ts: new Date().toTimeString().slice(0,8) }]);

  const executeRequest = async (endpoint, body = null, injectedPayload = null) => {
    setLoading(true);
    const path = endpoint?.path || customPath;
    const method = endpoint?.method || customMethod;
    const vuln = endpoint?.vuln || 'Custom';

    addResponse({ type: 'request', method, path, body, payload: injectedPayload, vuln });

    // Simulate realistic API responses with vulnerability demonstrations
    await new Promise(r => setTimeout(r, 300 + Math.random() * 400));

    let responseData = null;
    let statusCode = 200;
    let findings = [];

    if (path.includes('/customers') && !path.includes('{id}') && method === 'GET') {
      // VULN: No auth — returns all customers
      const customers = await base44.entities.Customer.list('-created_date', 5);
      responseData = { data: customers.map(c => ({ ...c, ni_number: c.ni_number, dob: c.dob })) };
      findings = ['NO AUTHENTICATION REQUIRED', 'NI NUMBERS AND DOB EXPOSED IN RESPONSE', 'PII DATA LEAKED WITHOUT CONSENT'];
    } else if (path.includes('/customers?admin=true')) {
      // VULN: Privilege escalation
      const customers = await base44.entities.Customer.list();
      responseData = { data: customers, admin_mode: true, total: customers.length, _debug: { query: 'SELECT * FROM CUSTMAST', operator: operatorId } };
      statusCode = 200;
      findings = ['ADMIN FLAG ACCEPTED WITHOUT ROLE CHECK', 'ALL RECORDS RETURNED', 'DEBUG INFO IN RESPONSE', 'INTERNAL SQL QUERY EXPOSED'];
    } else if (path.includes("OR '1'='1") || injectedPayload?.includes("'")) {
      // VULN: SQL injection returns all records
      const customers = await base44.entities.Customer.list();
      responseData = { data: customers, rows_returned: customers.length, query_executed: `SELECT * FROM CUSTMAST WHERE SURNAME='' OR '1'='1'` };
      findings = ['SQL INJECTION SUCCESSFUL', `ALL ${customers.length} CUSTOMER RECORDS RETURNED`, 'RAW SQL QUERY VISIBLE IN RESPONSE'];
    } else if (path.includes('/balance') && method === 'PUT') {
      // VULN: Mass assignment — balance can be set directly
      const payload = body || '{"balance": 999999.99, "credit_limit": 9999999}';
      responseData = { updated: true, new_balance: 999999.99, message: 'Balance updated without validation' };
      findings = ['BALANCE MODIFIED WITHOUT TRANSACTION LOG', 'NO AUTHORISATION FOR PRIVILEGED FIELD', 'MASS ASSIGNMENT: credit_limit also modified', 'AUDIT TRAIL BYPASSED'];
    } else if (path.includes('debug=true')) {
      const transactions = await base44.entities.Transaction.list('-created_date', 3);
      responseData = {
        data: transactions,
        _debug: {
          query: 'SELECT * FROM TRANLOG WHERE ACCT=?',
          session_token: 'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJvcCI6IkpTTUlUSCIsImFkbWluIjp0cnVlfQ.',
          server: 'BANKMASTER-PROD-01',
          java_version: '1.4.2_19',
          db_user: 'BANKAPP',
          db_password: 'bankpass123',
        }
      };
      findings = ['DEBUG MODE ENABLED IN PRODUCTION', 'DB CREDENTIALS IN RESPONSE', 'SESSION TOKEN WITH ALG=NONE (JWT VULN)', 'SERVER VERSION DISCLOSED'];
    } else if (path.includes('/admin/users')) {
      const users = [
        { id: 'JSMITH',  role: 'ADMIN', last_login: '20/05/87', pin_hash: '9999' },
        { id: 'ABROWN',  role: 'ADMIN', last_login: '19/05/87', pin_hash: '1234' },
        { id: 'CJONES',  role: 'USER',  last_login: '18/05/87', pin_hash: '5678' },
        { id: 'DVCA',    role: 'ADMIN', last_login: 'NEVER',    pin_hash: '9999', note: 'DEFAULT VENDOR ACCOUNT' },
      ];
      responseData = { users, _vuln: 'PIN HASHES RETURNED — COBOL VULN: CUST-PIN PIC X(4) EASILY OVERFLOWABLE' };
      findings = ['ADMIN ENDPOINT ACCESSIBLE WITHOUT ROLE CHECK', 'PIN HASHES RETURNED IN PLAINTEXT', 'DEFAULT VENDOR ACCOUNT (DVCA) EXPOSED', 'COBOL CUST-PIN BUFFER OVERFLOW RISK'];
    } else if (method === 'DELETE') {
      responseData = { deleted: true, id: path.split('/').pop() };
      findings = ['NO CSRF TOKEN REQUIRED', 'DELETE ACCEPTED WITHOUT CONFIRMATION', 'NO AUDIT LOG CREATED'];
    } else if (injectedPayload && (injectedPayload.includes('authenticated') || injectedPayload.includes('privilege'))) {
      // VULN: Hidden field exploitation
      const parsed = JSON.parse(injectedPayload);
      responseData = { accepted: true, processed_fields: parsed, hidden_field_accepted: true, elevated: parsed.authenticated === 'Y' || parsed.privilege_level === '9999' };
      findings = ['HIDDEN FIELD ACCEPTED BY SERVER', 'AUTHENTICATED FLAG OVERRIDDEN', 'COBOL SECURITY-CONTROL-FLAGS MANIPULATED', 'ADMIN ACCESS GRANTED VIA HIDDEN FIELD'];
    } else {
      responseData = { status: 'ok', message: 'Request processed', operator: operatorId };
      findings = [];
    }

    addResponse({ type: 'response', statusCode, data: responseData, findings, vuln, path, method });
    setLoading(false);
  };

  const runPayloadTest = () => {
    if (!payloadInput) return;
    const endpoint = { method: 'GET', path: `/api/v1/customers?surname=${encodeURIComponent(payloadInput)}`, vuln: payloadType };
    executeRequest(endpoint, null, payloadInput);
  };

  const methodColor = (m) => ({ GET: '#33FF33', POST: '#AAFFAA', PUT: '#FF9933', DELETE: '#FF3333', PATCH: '#3399FF' }[m] || '#33FF33');

  const tabStyle = (active) => ({
    background: active ? '#003300' : '#001100', border: `1px solid ${active ? '#AAFFAA' : '#336633'}`,
    color: active ? '#AAFFAA' : '#33FF33', fontFamily: 'inherit', fontSize: '11px', padding: '2px 10px', cursor: 'pointer',
  });

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', fontFamily: "'Courier New', monospace", fontSize: '12px', paddingBottom: '60px' }}>
      {/* Header */}
      <div style={{ padding: '2px 8px', borderBottom: '1px solid #336633', color: '#AAFFAA', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', background: '#001a00' }}>
        <span>REST API SECURITY TESTER — BANKMASTER/VS API GATEWAY</span>
        <span style={{ color: '#3399FF' }}>http://bankmaster-prod:8080</span>
        <span style={{ color: '#33FF33' }}>PF3=MENU</span>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', padding: '4px 8px', borderBottom: '1px solid #336633', background: '#000800' }}>
        {['endpoints', 'payloads', 'headers', 'results'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={tabStyle(tab === t)}>{t.toUpperCase()}</button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 8px' }}>

        {tab === 'endpoints' && (
          <div>
            <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '6px' }}>
              KNOWN VULNERABLE ENDPOINTS — CLICK TO TEST
            </div>
            {ENDPOINTS.map((ep, i) => (
              <div key={i}
                onClick={() => { setSelectedEndpoint(ep); executeRequest(ep); setTab('results'); }}
                style={{ display: 'flex', gap: '8px', alignItems: 'center', padding: '3px 6px', marginBottom: '2px', background: '#001100', border: '1px solid #224422', cursor: 'pointer' }}
              >
                <span style={{ color: methodColor(ep.method), width: '6ch', fontWeight: 'bold' }}>{ep.method}</span>
                <span style={{ color: '#3399FF', flex: 1, fontSize: '11px' }}>{ep.path}</span>
                <span style={{ color: '#FF9933', fontSize: '10px', width: '22ch', textAlign: 'right' }}>⚠ {ep.vuln}</span>
              </div>
            ))}
            <div style={{ marginTop: '8px', color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px' }}>CUSTOM REQUEST</div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '4px' }}>
              <select value={customMethod} onChange={e => setCustomMethod(e.target.value)}
                style={{ background: '#001100', border: '1px solid #336633', color: '#33FF33', fontFamily: 'inherit', fontSize: '12px', padding: '2px 4px' }}>
                {['GET','POST','PUT','DELETE','PATCH'].map(m => <option key={m}>{m}</option>)}
              </select>
              <input value={customPath} onChange={e => setCustomPath(e.target.value)} placeholder="/api/v1/..."
                style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF', color: '#3399FF', fontFamily: 'inherit', fontSize: '12px', outline: 'none' }} />
            </div>
            <textarea value={customBody} onChange={e => setCustomBody(e.target.value)} placeholder='Request body (JSON)...'
              style={{ width: '100%', background: '#001100', border: '1px solid #336633', color: '#33FF33', fontFamily: 'inherit', fontSize: '11px', minHeight: '60px', outline: 'none', padding: '4px', resize: 'vertical', boxSizing: 'border-box' }} />
            <button onClick={() => { executeRequest({ method: customMethod, path: customPath, vuln: 'Custom' }, customBody); setTab('results'); }}
              disabled={!customPath || loading}
              style={{ background: '#001100', border: '1px solid #AAFFAA', color: '#AAFFAA', fontFamily: 'inherit', fontSize: '12px', padding: '3px 12px', cursor: 'pointer', marginTop: '4px' }}>
              {loading ? 'SENDING...' : '▶ SEND REQUEST'}
            </button>
          </div>
        )}

        {tab === 'payloads' && (
          <div>
            <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '6px' }}>INJECTION PAYLOAD TESTER</div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
              {Object.keys(PAYLOADS).map(pt => (
                <button key={pt} onClick={() => setPayloadType(pt)} style={{ ...tabStyle(payloadType === pt), fontSize: '10px' }}>{pt}</button>
              ))}
            </div>
            <div style={{ color: '#668866', marginBottom: '4px' }}>PRESET PAYLOADS (click to use):</div>
            {PAYLOADS[payloadType].map((p, i) => (
              <div key={i} onClick={() => setPayloadInput(p)}
                style={{ background: '#001100', border: '1px solid #224422', padding: '3px 8px', marginBottom: '2px', color: '#3399FF', cursor: 'pointer', fontSize: '11px' }}>
                {p}
              </div>
            ))}
            <div style={{ marginTop: '8px', color: '#AAFFAA', marginBottom: '4px' }}>CUSTOM PAYLOAD:</div>
            <input value={payloadInput} onChange={e => setPayloadInput(e.target.value)}
              style={{ width: '100%', background: 'transparent', border: 'none', borderBottom: '1px solid #3399FF', color: '#3399FF', fontFamily: 'inherit', fontSize: '13px', outline: 'none', boxSizing: 'border-box' }} />
            {payloadType === 'Hidden Field' && (
              <div style={{ color: '#FF9933', fontSize: '11px', marginTop: '4px' }}>
                ⚠ COBOL VULN: SECURITY-CONTROL-FLAGS adjacent to USER-INPUT buffer. Overflow AUTHENTICATED-FLAG='Y' via oversized input.
              </div>
            )}
            <button onClick={() => { runPayloadTest(); setTab('results'); }}
              disabled={!payloadInput || loading}
              style={{ background: '#001100', border: '1px solid #AAFFAA', color: '#AAFFAA', fontFamily: 'inherit', fontSize: '12px', padding: '3px 12px', cursor: 'pointer', marginTop: '8px' }}>
              {loading ? 'TESTING...' : '▶ INJECT PAYLOAD'}
            </button>
          </div>
        )}

        {tab === 'headers' && (
          <div>
            <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '6px' }}>REQUEST HEADERS — SECURITY ANALYSIS</div>
            <textarea value={headers} onChange={e => setHeaders(e.target.value)}
              style={{ width: '100%', background: '#001100', border: '1px solid #336633', color: '#33FF33', fontFamily: 'inherit', fontSize: '11px', minHeight: '120px', outline: 'none', padding: '4px', resize: 'vertical', boxSizing: 'border-box' }} />
            <div style={{ marginTop: '8px', color: '#FF9933', fontSize: '11px' }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>⚠ HEADER VULNERABILITIES DETECTED:</div>
              <div>• No X-Content-Type-Options header (MIME sniffing)</div>
              <div>• No X-Frame-Options header (clickjacking)</div>
              <div>• No Content-Security-Policy (XSS amplification)</div>
              <div>• Authorization: Bearer — JWT with ALG=NONE accepted</div>
              <div>• No rate limiting headers (brute force possible)</div>
              <div>• Server version exposed: IBM WebSphere 3.5.4</div>
            </div>
          </div>
        )}

        {tab === 'results' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>REQUEST/RESPONSE LOG</span>
              <button onClick={() => setResponses([])} style={{ background: '#001100', border: '1px solid #336633', color: '#FF3333', fontFamily: 'inherit', fontSize: '10px', padding: '1px 6px', cursor: 'pointer' }}>CLEAR</button>
            </div>
            {responses.length === 0 && <div style={{ color: '#668866' }}>No requests yet. Go to ENDPOINTS tab and click a test.</div>}
            {responses.map((r, i) => (
              <div key={i} style={{ marginBottom: '8px', border: `1px solid ${r.type === 'request' ? '#224422' : r.findings?.length ? '#553300' : '#224422'}`, background: '#000800' }}>
                <div style={{ padding: '3px 8px', background: r.type === 'request' ? '#001a00' : '#1a0800', display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: r.type === 'request' ? '#3399FF' : r.findings?.length ? '#FF9933' : '#AAFFAA', fontWeight: 'bold' }}>
                    {r.type === 'request' ? '→ REQUEST' : `← RESPONSE ${r.statusCode}`}
                  </span>
                  <span style={{ color: methodColor(r.method) }}>{r.method}</span>
                  <span style={{ color: '#668866', fontSize: '10px' }}>{r.ts}</span>
                </div>
                <div style={{ padding: '4px 8px' }}>
                  <div style={{ color: '#3399FF', fontSize: '11px', marginBottom: '2px' }}>{r.path}</div>
                  {r.payload && <div style={{ color: '#FFFF66', fontSize: '11px' }}>PAYLOAD: {r.payload}</div>}
                  {r.data && (
                    <pre style={{ color: '#33FF33', fontSize: '10px', overflow: 'auto', maxHeight: '150px', margin: '4px 0', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      {JSON.stringify(r.data, null, 2)}
                    </pre>
                  )}
                  {r.findings?.length > 0 && (
                    <div style={{ marginTop: '4px', borderTop: '1px solid #553300', paddingTop: '4px' }}>
                      {r.findings.map((f, j) => (
                        <div key={j} style={{ color: '#FF9933', fontSize: '11px' }}>⚠ {f}</div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div style={{ padding: '2px 8px', borderTop: '1px solid #336633', display: 'flex', gap: '8px', background: '#000800' }}>
        <button onClick={() => onBack('MENU')} style={{ background: '#001100', border: '1px solid #336633', color: '#AAFFAA', fontFamily: 'inherit', fontSize: '11px', padding: '2px 8px', cursor: 'pointer' }}>PF3 MENU</button>
        {loading && <span style={{ color: '#FF9933' }}>SENDING REQUEST...</span>}
      </div>
    </div>
  );
}