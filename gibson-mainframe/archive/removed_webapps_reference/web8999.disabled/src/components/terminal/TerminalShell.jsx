import React, { useEffect, useRef } from 'react';

export default function TerminalShell({ children, onKeyDown }) {
  const shellRef = useRef(null);

  useEffect(() => {
    if (shellRef.current) {
      shellRef.current.focus();
    }
  }, []);

  const handleKeyDown = (e) => {
    // Prevent default for F-keys
    if (e.key.startsWith('F') && !isNaN(e.key.slice(1))) {
      e.preventDefault();
    }
    if (e.key === 'Enter') {
      e.preventDefault();
    }
    if (onKeyDown) onKeyDown(e);
  };

  return (
    <div
      ref={shellRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      className="terminal-shell outline-none"
      style={{
        backgroundColor: '#000000',
        color: '#33FF33',
        fontFamily: "'Courier New', Courier, monospace",
        fontSize: '14px',
        lineHeight: '1.2',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* CRT Scanline Overlay */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.15) 2px, rgba(0,0,0,0.15) 4px)',
        pointerEvents: 'none',
        zIndex: 100,
      }} />
      {/* CRT Vignette */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: 0,
        background: 'radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,0.5) 100%)',
        pointerEvents: 'none',
        zIndex: 99,
      }} />
      {children}
    </div>
  );
}