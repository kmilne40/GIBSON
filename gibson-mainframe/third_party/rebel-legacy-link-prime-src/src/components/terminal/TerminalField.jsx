import React, { useRef, useEffect } from 'react';

// Protected label (high intensity)
export function Label({ text, col, row, bright = false }) {
  return (
    <span style={{
      position: 'absolute',
      left: `${col}ch`,
      top: `${(row - 1) * 1.2}em`,
      color: bright ? '#AAFFAA' : '#33FF33',
      fontWeight: bright ? 'bold' : 'normal',
      whiteSpace: 'pre',
      pointerEvents: 'none',
    }}>
      {text}
    </span>
  );
}

// Editable input field (underscored blue)
export function InputField({ id, value, onChange, col, row, length, focused, onFocus, uppercase = true, numeric = false }) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (focused && inputRef.current) {
      inputRef.current.focus();
    }
  }, [focused]);

  const handleChange = (e) => {
    let val = e.target.value;
    if (uppercase) val = val.toUpperCase();
    if (numeric) val = val.replace(/[^0-9.\-]/g, '');
    if (val.length <= length) onChange(val);
  };

  const displayVal = (value || '').padEnd(length, ' ');

  return (
    <div style={{
      position: 'absolute',
      left: `${col}ch`,
      top: `${(row - 1) * 1.2}em`,
      width: `${length}ch`,
      height: '1.2em',
    }}>
      <input
        ref={inputRef}
        id={id}
        type="text"
        value={value || ''}
        onChange={handleChange}
        onFocus={onFocus}
        maxLength={length}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'transparent',
          border: 'none',
          borderBottom: '1px solid #3399FF',
          color: '#3399FF',
          fontFamily: "'Courier New', Courier, monospace",
          fontSize: '14px',
          lineHeight: '1.2',
          outline: 'none',
          padding: 0,
          caretColor: focused ? '#33FF33' : 'transparent',
          textTransform: uppercase ? 'uppercase' : 'none',
        }}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck="false"
      />
    </div>
  );
}

// Display-only field (protected output)
export function DisplayField({ value, col, row, length, color = '#33FF33', bright = false }) {
  const display = (value !== undefined && value !== null) ? String(value).toUpperCase().padEnd(length, ' ').slice(0, length) : ''.padEnd(length, ' ');
  return (
    <span style={{
      position: 'absolute',
      left: `${col}ch`,
      top: `${(row - 1) * 1.2}em`,
      color: bright ? '#AAFFAA' : color,
      fontWeight: bright ? 'bold' : 'normal',
      whiteSpace: 'pre',
      pointerEvents: 'none',
      letterSpacing: '0',
    }}>
      {display}
    </span>
  );
}

// Error field highlight
export function ErrorField({ col, row, length }) {
  return (
    <span style={{
      position: 'absolute',
      left: `${col}ch`,
      top: `${(row - 1) * 1.2}em`,
      width: `${length}ch`,
      height: '1.2em',
      background: '#330000',
      color: '#FF3333',
      pointerEvents: 'none',
    }}>
      {'▓'.repeat(length)}
    </span>
  );
}