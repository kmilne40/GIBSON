import React, { useState } from 'react';

// hack3270 toolbar — mimics the real hack3270-gibson tool UI
export default function Hack3270Toolbar({ hackFields, onHackFieldsChange, activeTab, onTabChange, injectLog = [], apiLeakLog = [], stats = {} }) {
  const tabs = ['Hack Field Attributes', 'Inject Info Fields', 'Inject Key Presses', 'BATCH PIN', 'API Leakage', 'Logs', 'Statistics', 'Help'];

  const toolbarStyle = {
    background: '#d4d0c8',
    border: '1px solid #808080',
    fontFamily: 'Tahoma, Arial, sans-serif',
    fontSize: '11px',
    color: '#000',
    userSelect: 'none',
  };

  const tabStyle = (t) => ({
    display: 'inline-block',
    padding: '2px 8px',
    marginRight: '2px',
    background: activeTab === t ? '#d4d0c8' : '#bbb8b0',
    border: '1px solid #808080',
    borderBottom: activeTab === t ? '1px solid #d4d0c8' : '1px solid #808080',
    cursor: 'pointer',
    fontFamily: 'Tahoma, Arial, sans-serif',
    fontSize: '11px',
    color: '#000',
    fontWeight: activeTab === t ? 'bold' : 'normal',
  });

  const toggle = (key) => onHackFieldsChange({ ...hackFields, [key]: !hackFields[key] });

  const cbStyle = { marginRight: '4px', cursor: 'pointer' };
  const labelStyle = { marginRight: '16px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center' };

  return (
    <div style={toolbarStyle}>
      {/* Title bar */}
      <div style={{ background: '#0a246a', color: '#fff', padding: '2px 6px', fontSize: '11px', display: 'flex', justifyContent: 'space-between' }}>
        <span>hack3270-glbson v1.0</span>
        <span style={{ fontSize: '10px', color: '#aad' }}>training simulation only</span>
      </div>

      {/* Tab bar */}
      <div style={{ padding: '4px 4px 0 4px', borderBottom: '1px solid #808080' }}>
        {tabs.map(t => (
          <span key={t} style={tabStyle(t)} onClick={() => onTabChange(t)}>{t}</span>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ padding: '6px 8px', minHeight: '78px' }}>
        {activeTab === 'Hack Field Attributes' && (
          <HackFieldAttribsTab hackFields={hackFields} toggle={toggle} cbStyle={cbStyle} labelStyle={labelStyle} />
        )}
        {activeTab === 'Inject Info Fields' && (
          <InjectInfoFieldsTab hackFields={hackFields} toggle={toggle} cbStyle={cbStyle} labelStyle={labelStyle} />
        )}
        {activeTab === 'Inject Key Presses' && (
          <InjectKeyPressesTab hackFields={hackFields} toggle={toggle} cbStyle={cbStyle} labelStyle={labelStyle} />
        )}
        {activeTab === 'BATCH PIN' && (
          <BatchPinTab hackFields={hackFields} toggle={toggle} />
        )}
        {activeTab === 'API Leakage' && (
          <ApiLeakageTab apiLeakLog={apiLeakLog} />
        )}
        {activeTab === 'Logs' && (
          <LogsTab injectLog={injectLog} />
        )}
        {activeTab === 'Statistics' && (
          <StatisticsTab stats={stats} />
        )}
        {activeTab === 'Help' && (
          <HelpTab />
        )}
      </div>
    </div>
  );
}

function HackFieldAttribsTab({ hackFields, toggle, cbStyle, labelStyle }) {
  return (
    <div>
      <div style={{ marginBottom: '4px' }}>
        <label style={labelStyle}>
          <span style={{ marginRight: '6px', fontWeight: 'bold' }}>Hack Fields:</span>
          <span
            onClick={() => toggle('master')}
            style={{
              display: 'inline-block', padding: '1px 8px',
              background: hackFields.master ? '#c0392b' : '#bbb',
              color: '#fff', fontWeight: 'bold', cursor: 'pointer',
              border: '1px solid #808080', fontSize: '11px',
              minWidth: '32px', textAlign: 'center',
            }}
          >{hackFields.master ? 'ON' : 'OFF'}</span>
        </label>
        <label style={labelStyle}>
          <input type="checkbox" checked={!!hackFields.disable_field_protection} onChange={() => toggle('disable_field_protection')} style={cbStyle} />
          Disable Field Protection
        </label>
        <label style={labelStyle}>
          <input type="checkbox" checked={!!hackFields.enable_hidden_fields} onChange={() => toggle('enable_hidden_fields')} style={cbStyle} />
          Enable Hidden Fields
        </label>
        <label style={labelStyle}>
          <input type="checkbox" checked={!!hackFields.remove_numeric_only} onChange={() => toggle('remove_numeric_only')} style={cbStyle} />
          Remove Numeric Only Restrictions
        </label>
      </div>
      <div>
        <label style={labelStyle}>
          <input type="checkbox" checked={!!hackFields.start_field} onChange={() => toggle('start_field')} style={cbStyle} />
          Start Field
        </label>
        <label style={labelStyle}>
          <input type="checkbox" checked={!!hackFields.start_field_extended} onChange={() => toggle('start_field_extended')} style={cbStyle} />
          Start Field Extended
        </label>
        <label style={labelStyle}>
          <input type="checkbox" checked={!!hackFields.modify_field} onChange={() => toggle('modify_field')} style={cbStyle} />
          Modify Field
        </label>
        {hackFields.enable_hidden_fields && (
          <span style={{ marginLeft: '20px', color: '#800000', fontWeight: 'bold' }}>
            Hidden Field Highlighting: &nbsp;
            <span style={{ color: '#00f', textDecoration: 'underline', cursor: 'pointer' }}>Enable Intensity</span>
            &nbsp;&nbsp;
            <span style={{ color: '#00f', textDecoration: 'underline', cursor: 'pointer' }}>High Visibility</span>
          </span>
        )}
      </div>
    </div>
  );
}

function InjectInfoFieldsTab({ hackFields, toggle, cbStyle, labelStyle }) {
  return (
    <div>
      <div style={{ marginBottom: '4px', color: '#555', fontStyle: 'italic' }}>
        Inject data into protected/hidden fields on the current CICS screen.
      </div>
      <label style={labelStyle}>
        <input type="checkbox" checked={!!hackFields.inject_cust_id} onChange={() => toggle('inject_cust_id')} style={cbStyle} />
        Inject PURCHASABLE field override (N→Y, enables banned items)
      </label>
      <label style={labelStyle}>
        <input type="checkbox" checked={!!hackFields.inject_acct_no} onChange={() => toggle('inject_acct_no')} style={cbStyle} />
        Inject PRICE field (bypass FSET protection — MCOR)
      </label>
      <label style={labelStyle}>
        <input type="checkbox" checked={!!hackFields.inject_pin} onChange={() => toggle('inject_pin')} style={cbStyle} />
        Inject supervisor PIN into MCAD (value: 1337)
      </label>
    </div>
  );
}

function InjectKeyPressesTab({ hackFields, toggle, cbStyle, labelStyle }) {
  return (
    <div>
      <div style={{ marginBottom: '4px', color: '#555', fontStyle: 'italic' }}>
        Simulate AID key injection into CICS transaction stream.
      </div>
      <label style={labelStyle}>
        <input type="checkbox" checked={!!hackFields.inject_enter} onChange={() => toggle('inject_enter')} style={cbStyle} />
        Auto-ENTER on screen load
      </label>
      <label style={labelStyle}>
        <input type="checkbox" checked={!!hackFields.inject_pf3} onChange={() => toggle('inject_pf3')} style={cbStyle} />
        Inject PF3 (return to menu)
      </label>
      <label style={labelStyle}>
        <input type="checkbox" checked={!!hackFields.inject_clear} onChange={() => toggle('inject_clear')} style={cbStyle} />
        Inject CLEAR (reset screen)
      </label>
    </div>
  );
}

function BatchPinTab({ hackFields, toggle }) {
  return (
    <div>
      <div style={{ marginBottom: '4px', color: '#555', fontStyle: 'italic' }}>
        BATCH PIN brute-force against MCAD supervisor PIN (4 digits, 0000–9999, no lockout — VULN #3).
        Use the brute force button on the MCAD screen directly, or enable here for inline injection.
      </div>
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <input type="checkbox" checked={!!hackFields.batch_pin_enabled} onChange={() => toggle('batch_pin_enabled')} />
          Enable BATCH PIN Mode
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          Range start:
          <input type="text" defaultValue="0000" maxLength={4}
            style={{ width: '4ch', border: '1px solid #808080', fontFamily: 'monospace', fontSize: '11px' }} />
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          Range end:
          <input type="text" defaultValue="9999" maxLength={4}
            style={{ width: '4ch', border: '1px solid #808080', fontFamily: 'monospace', fontSize: '11px' }} />
        </label>
        <div style={{ color: hackFields.batch_pin_enabled ? '#c0392b' : '#555', fontWeight: hackFields.batch_pin_enabled ? 'bold' : 'normal' }}>
          {hackFields.batch_pin_enabled ? '⚠ BATCH PIN ACTIVE — TARGETING MCAD SUPERVISOR PIN' : 'Disabled'}
        </div>
      </div>
    </div>
  );
}

function ApiLeakageTab({ apiLeakLog }) {
  return (
    <div>
      <div style={{ marginBottom: '3px', color: '#555', fontStyle: 'italic' }}>
        Intercepted REST API responses leaking sensitive data:
      </div>
      <div style={{
        background: '#fff', border: '1px solid #808080', height: '52px', overflowY: 'auto',
        fontFamily: 'Courier New, monospace', fontSize: '10px', padding: '2px 4px',
      }}>
        {apiLeakLog.length === 0
          ? <div style={{ color: '#aaa' }}>No API leakage detected yet. Navigate DVCA screens to intercept.</div>
          : apiLeakLog.map((l, i) => <div key={i} style={{ color: '#800000' }}>{l}</div>)
        }
      </div>
    </div>
  );
}

function LogsTab({ injectLog }) {
  return (
    <div>
      <div style={{ marginBottom: '3px', color: '#555', fontStyle: 'italic' }}>
        hack3270 field injection & intercept log:
      </div>
      <div style={{
        background: '#fff', border: '1px solid #808080', height: '52px', overflowY: 'auto',
        fontFamily: 'Courier New, monospace', fontSize: '10px', padding: '2px 4px',
      }}>
        {injectLog.length === 0
          ? <div style={{ color: '#aaa' }}>No events logged yet.</div>
          : injectLog.map((l, i) => <div key={i} style={{ color: l.type === 'warn' ? '#b8860b' : l.type === 'error' ? '#c0392b' : '#000' }}>{l.text}</div>)
        }
      </div>
    </div>
  );
}

function StatisticsTab({ stats }) {
  const items = [
    ['Screens visited', stats.screens || 0],
    ['Hidden fields exposed', stats.hidden_exposed || 0],
    ['Protected fields overtyped', stats.protected_overtyped || 0],
    ['PINs attempted', stats.pins_attempted || 0],
    ['PINs found', stats.pins_found || 0],
    ['API responses intercepted', stats.api_intercepted || 0],
    ['Fields injected', stats.fields_injected || 0],
  ];
  return (
    <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
      {items.map(([k, v]) => (
        <div key={k} style={{ fontSize: '11px' }}>
          <span style={{ color: '#555' }}>{k}: </span>
          <span style={{ fontWeight: 'bold', color: v > 0 ? '#c0392b' : '#000' }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

function HelpTab() {
  return (
    <div style={{ fontSize: '11px', lineHeight: '1.6' }}>
      <b>hack3270 Help</b> — Training simulation only.<br />
      <b>Hack Field Attributes:</b> Disable field protection, expose hidden fields, remove numeric-only restrictions.<br />
      <b>Inject Info Fields:</b> Push data into protected/hidden TN3270 fields.<br />
      <b>Inject Key Presses:</b> Simulate AID key injection (ENTER, PF3, CLEAR).<br />
      <b>BATCH PIN:</b> Brute-force MCAD supervisor PIN (4-digit, no lockout — VULN #3). Answer: 1337.<br />
      <b>API Leakage:</b> Intercept REST API responses with sensitive data.<br />
      <b>Logs:</b> Full audit trail of injections and intercepts.
    </div>
  );
}