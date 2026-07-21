import React, { useState } from 'react';
import { SCENARIOS } from '@/data/scenarioLibrary';
import { SOLUTIONS } from '@/data/scenarioSolutions';

const UNLOCK_CODE = 'INSTRUCTOR';

const S = {
  page: { background: '#000', color: '#33FF33', fontFamily: "'Courier New', monospace", minHeight: '100vh', padding: '16px', fontSize: '12px' },
  h1: { color: '#AAFFAA', fontWeight: 'bold', fontSize: '16px', letterSpacing: '3px' },
  sep: { color: '#336633', marginBottom: '12px' },
  card: { border: '1px solid #336633', padding: '10px 14px', marginBottom: '8px', cursor: 'pointer', background: '#000800' },
  cardActive: { border: '1px solid #AAFFAA', padding: '10px 14px', marginBottom: '8px', cursor: 'pointer', background: '#001100' },
  badge: (color) => ({ display: 'inline-block', border: `1px solid ${color}`, color, padding: '1px 6px', fontSize: '10px', marginRight: '6px' }),
  btn: (color = '#33FF33') => ({ padding: '6px 18px', background: '#001100', border: `1px solid ${color}`, color, cursor: 'pointer', fontFamily: "'Courier New', monospace", fontSize: '12px', marginRight: '8px' }),
  stepCard: { border: '1px solid #224422', padding: '12px', marginBottom: '10px', background: '#000800' },
  query: { background: '#001100', border: '1px solid #336633', color: '#3399FF', padding: '8px', fontFamily: "'Courier New', monospace", fontSize: '12px', marginTop: '6px', marginBottom: '6px', whiteSpace: 'pre-wrap' },
  finding: { color: '#FFFF99', borderLeft: '2px solid #FF9933', paddingLeft: '8px', marginTop: '6px', fontSize: '11px' },
  remedItem: { color: '#33FF33', marginBottom: '4px', paddingLeft: '8px' },
};

const DIFFICULTY_COLOR = { BEGINNER: '#33FF33', INTERMEDIATE: '#FF9933', ADVANCED: '#FF3333' };

export default function SolutionViewer() {
  const [unlocked, setUnlocked] = useState(false);
  const [code, setCode] = useState('');
  const [codeError, setCodeError] = useState('');
  const [selected, setSelected] = useState(null);
  const [expandedStep, setExpandedStep] = useState(null);

  const handleUnlock = () => {
    if (code.trim().toUpperCase() === UNLOCK_CODE) {
      setUnlocked(true);
      setCodeError('');
    } else {
      setCodeError('ACCESS DENIED — INVALID INSTRUCTOR CODE');
    }
  };

  const solution = selected ? SOLUTIONS[selected.id] : null;
  const scenario = selected ? SCENARIOS.find(s => s.id === selected.id) : null;

  if (!unlocked) {
    return (
      <div style={S.page}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', marginBottom: '4px' }}>
          <div style={S.h1}>SOLUTION VIEWER</div>
          <div style={{ color: '#668866', fontSize: '11px' }}>INSTRUCTOR ACCESS ONLY</div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
            <a href="/scenarios" style={{ color: '#3399FF', fontSize: '11px' }}>← SCENARIO LAB</a>
            <a href="/" style={{ color: '#3399FF', fontSize: '11px' }}>TERMINAL</a>
          </div>
        </div>
        <div style={S.sep}>{'─'.repeat(90)}</div>

        <div style={{ maxWidth: '420px', margin: '60px auto 0', textAlign: 'center' }}>
          <div style={{ color: '#FF3333', fontSize: '14px', fontWeight: 'bold', marginBottom: '4px', letterSpacing: '2px' }}>
            ⚠ RESTRICTED ACCESS
          </div>
          <div style={{ color: '#668866', marginBottom: '24px', fontSize: '11px' }}>
            This screen contains full vulnerability solutions and walkthrough answers.<br />
            Enter the instructor access code to proceed.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#AAFFAA' }}>INSTRUCTOR CODE :</span>
              <input
                type="password"
                value={code}
                onChange={e => setCode(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleUnlock()}
                autoFocus
                style={{
                  width: '14ch', background: 'transparent', border: 'none',
                  borderBottom: '1px solid #3399FF', color: '#3399FF',
                  fontFamily: "'Courier New', monospace", fontSize: '14px',
                  outline: 'none', textAlign: 'center',
                }}
              />
            </div>
            <button style={S.btn('#AAFFAA')} onClick={handleUnlock}>UNLOCK</button>
            {codeError && <div style={{ color: '#FF3333', fontSize: '11px' }}>{codeError}</div>}
          </div>

          <div style={{ color: '#224422', fontSize: '10px', marginTop: '32px' }}>
            DEFAULT CODE: INSTRUCTOR — CHANGE BEFORE STUDENT USE
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', marginBottom: '4px', flexWrap: 'wrap' }}>
        <div style={S.h1}>SOLUTION VIEWER</div>
        <div style={{ color: '#FF9933', fontSize: '11px', fontWeight: 'bold' }}>● INSTRUCTOR MODE ACTIVE</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
          <a href="/scenarios" style={{ color: '#3399FF', fontSize: '11px' }}>← SCENARIO LAB</a>
          <a href="/db" style={{ color: '#3399FF', fontSize: '11px' }}>DB EXPLORER</a>
          <a href="/audit" style={{ color: '#FF9933', fontSize: '11px' }}>AUDIT LOG</a>
          <a href="/" style={{ color: '#3399FF', fontSize: '11px' }}>TERMINAL</a>
        </div>
      </div>
      <div style={S.sep}>{'─'.repeat(100)}</div>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        {/* Scenario list */}
        <div style={{ flex: '0 0 300px', minWidth: '240px' }}>
          <div style={{ color: '#668866', fontSize: '11px', marginBottom: '8px' }}>SELECT SCENARIO:</div>
          {SCENARIOS.map(s => (
            <div
              key={s.id}
              style={selected?.id === s.id ? S.cardActive : S.card}
              onClick={() => { setSelected(s); setExpandedStep(null); }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <span style={{ color: '#FFFF99', fontSize: '11px', fontWeight: 'bold' }}>{s.id}</span>
                <span style={S.badge(DIFFICULTY_COLOR[s.difficulty] || '#33FF33')}>{s.difficulty}</span>
              </div>
              <div style={{ color: '#AAFFAA', fontSize: '11px' }}>{s.title}</div>
              <div style={{ color: '#668866', fontSize: '10px', marginTop: '2px' }}>{s.category}</div>
            </div>
          ))}
        </div>

        {/* Solution panel */}
        <div style={{ flex: 1, minWidth: '300px' }}>
          {!selected && (
            <div style={{ color: '#336633', padding: '24px 0' }}>← SELECT A SCENARIO TO VIEW ITS SOLUTION</div>
          )}

          {selected && solution && (
            <div>
              {/* Header */}
              <div style={{ color: '#FFFF99', fontWeight: 'bold', fontSize: '14px', letterSpacing: '1px', marginBottom: '4px' }}>
                {scenario.id}: {scenario.title}
              </div>
              <div style={{ marginBottom: '8px' }}>
                <span style={S.badge(DIFFICULTY_COLOR[scenario.difficulty])}>{scenario.difficulty}</span>
                <span style={S.badge('#668866')}>{scenario.category}</span>
              </div>

              {/* Summary */}
              <div style={{ background: '#000800', border: '1px solid #336633', padding: '10px', marginBottom: '14px' }}>
                <div style={{ color: '#FF9933', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>SCENARIO SUMMARY</div>
                <div style={{ color: '#AAFFAA' }}>{solution.summary}</div>
              </div>

              {/* Step-by-step walkthrough */}
              <div style={{ color: '#FFFF99', fontWeight: 'bold', marginBottom: '8px' }}>STEP-BY-STEP SOLUTION</div>
              {solution.steps.map((step) => (
                <div key={step.step} style={S.stepCard}>
                  <div
                    style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}
                    onClick={() => setExpandedStep(expandedStep === step.step ? null : step.step)}
                  >
                    <span style={{ color: '#FF9933', fontWeight: 'bold', minWidth: '24px' }}>
                      {expandedStep === step.step ? '▼' : '▶'} {step.step}.
                    </span>
                    <span style={{ color: '#AAFFAA', fontWeight: 'bold' }}>{step.title}</span>
                  </div>

                  {expandedStep === step.step && (
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ color: '#668866', fontSize: '11px', marginBottom: '4px' }}>QUERY TO RUN:</div>
                      <div style={S.query}>{step.query}</div>
                      <div style={{ color: '#33FF33', marginTop: '6px' }}>{step.explanation}</div>
                      <div style={S.finding}>FINDING: {step.finding}</div>
                    </div>
                  )}
                </div>
              ))}

              {/* Root cause */}
              <div style={{ border: '1px solid #FF3333', padding: '10px', marginBottom: '12px', background: '#0a0000' }}>
                <div style={{ color: '#FF3333', fontWeight: 'bold', marginBottom: '4px', fontSize: '11px' }}>ROOT CAUSE ANALYSIS</div>
                <div style={{ color: '#AAFFAA' }}>{solution.rootCause}</div>
              </div>

              {/* Remediation */}
              <div style={{ border: '1px solid #336633', padding: '10px', background: '#000800' }}>
                <div style={{ color: '#33FF33', fontWeight: 'bold', marginBottom: '6px', fontSize: '11px' }}>REMEDIATION STEPS</div>
                {solution.remediation.map((r, i) => (
                  <div key={i} style={S.remedItem}>✓ {r}</div>
                ))}
              </div>
            </div>
          )}

          {selected && !solution && (
            <div style={{ color: '#FF9933' }}>NO SOLUTION AVAILABLE FOR THIS SCENARIO YET.</div>
          )}
        </div>
      </div>
    </div>
  );
}