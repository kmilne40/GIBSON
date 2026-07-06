import React, { useState } from 'react';
import { COBOL_PROGRAMS } from '@/data/cobolPrograms';

export default function CobolOverlay({ transactionCode, onClose }) {
  const [tab, setTab] = useState('cobol'); // 'cobol' | 'sql'
  const program = COBOL_PROGRAMS[transactionCode] || COBOL_PROGRAMS['CUST'];

  return (
    <div style={{
      position: 'absolute',
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: '#000000',
      zIndex: 200,
      fontFamily: "'Courier New', Courier, monospace",
      fontSize: '13px',
      display: 'flex',
      flexDirection: 'column',
      padding: '8px',
    }}>
      {/* Header */}
      <div style={{ color: '#AAFFAA', fontWeight: 'bold', marginBottom: '4px', borderBottom: '1px solid #33FF33', paddingBottom: '4px' }}>
        {'IBM CICS/VS  PROGRAM LIBRARY VIEWER  '.padEnd(60)}
        <span style={{ color: '#33FF33' }}>PF3=RETURN</span>
      </div>
      <div style={{ color: '#33FF33', marginBottom: '4px' }}>
        {`PROGRAM: ${program.program_name.padEnd(12)} TRANS: ${program.transaction_code.padEnd(8)} ${program.description}`}
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', marginBottom: '4px', gap: '4px' }}>
        <button
          onClick={() => setTab('cobol')}
          style={{
            background: tab === 'cobol' ? '#003300' : 'transparent',
            border: `1px solid ${tab === 'cobol' ? '#AAFFAA' : '#33FF33'}`,
            color: tab === 'cobol' ? '#AAFFAA' : '#33FF33',
            fontFamily: 'inherit',
            fontSize: '12px',
            padding: '2px 10px',
            cursor: 'pointer',
          }}
        >
          [ COBOL SOURCE ]
        </button>
        <button
          onClick={() => setTab('sql')}
          style={{
            background: tab === 'sql' ? '#003300' : 'transparent',
            border: `1px solid ${tab === 'sql' ? '#AAFFAA' : '#33FF33'}`,
            color: tab === 'sql' ? '#AAFFAA' : '#33FF33',
            fontFamily: 'inherit',
            fontSize: '12px',
            padding: '2px 10px',
            cursor: 'pointer',
          }}
        >
          [ DB2 SQL DDL / RUNTIME ]
        </button>
        <span style={{ marginLeft: 'auto', color: '#33FF33', alignSelf: 'center', fontSize: '12px' }}>
          SCROLL WITH MOUSE/TRACKPAD
        </span>
      </div>

      {/* Code panel */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        overflowX: 'auto',
        background: '#000800',
        border: '1px solid #004400',
        padding: '8px',
        whiteSpace: 'pre',
        color: tab === 'cobol' ? '#33FF33' : '#AAFFAA',
        fontSize: '12px',
        lineHeight: '1.5',
      }}>
        {tab === 'cobol' ? renderCobol(program.source_code) : renderSQL(program.sql_ddl)}
      </div>

      {/* Legend */}
      <div style={{ color: '#33FF33', fontSize: '11px', marginTop: '4px', display: 'flex', gap: '16px' }}>
        <span><span style={{ color: '#AAFFAA' }}>■</span> DIVISION/SECTION HEADERS</span>
        <span><span style={{ color: '#33FF33' }}>■</span> CODE STATEMENTS</span>
        <span><span style={{ color: '#668866' }}>■</span> COMMENTS / DDL</span>
      </div>

      {/* Bottom instruction */}
      <div style={{ color: '#AAFFAA', textAlign: 'center', marginTop: '4px', fontWeight: 'bold', fontSize: '12px' }}>
        *** PRESS PF3 OR CLICK BELOW TO RETURN TO TRANSACTION SCREEN ***
      </div>
      <button
        onClick={onClose}
        style={{
          marginTop: '4px',
          background: '#001100',
          border: '1px solid #AAFFAA',
          color: '#AAFFAA',
          fontFamily: 'inherit',
          fontSize: '13px',
          padding: '4px',
          cursor: 'pointer',
          fontWeight: 'bold',
        }}
      >
        PF3 - RETURN TO TRANSACTION
      </button>
    </div>
  );
}

function renderCobol(source) {
  if (!source) return '';
  return source.split('\n').map((line, i) => {
    const trimmed = line.trimStart();
    let color = '#33FF33';
    if (trimmed.startsWith('*')) color = '#668866';
    else if (trimmed.endsWith('DIVISION.') || trimmed.endsWith('SECTION.')) color = '#AAFFAA';
    else if (trimmed.startsWith('EXEC CICS') || trimmed.startsWith('EXEC SQL')) color = '#AAFFAA';
    return <span key={i} style={{ color }}>{line + '\n'}</span>;
  });
}

function renderSQL(source) {
  if (!source) return '';
  return source.split('\n').map((line, i) => {
    const trimmed = line.trimStart();
    let color = '#AAFFAA';
    if (trimmed.startsWith('--')) color = '#668866';
    else if (/^(SELECT|INSERT|UPDATE|DELETE|CREATE|FROM|WHERE|ORDER|SET|VALUES|INTO|ON|GRANT|CONSTRAINT|REFERENCES)/i.test(trimmed)) color = '#AAFFAA';
    else color = '#33FF33';
    return <span key={i} style={{ color }}>{line + '\n'}</span>;
  });
}