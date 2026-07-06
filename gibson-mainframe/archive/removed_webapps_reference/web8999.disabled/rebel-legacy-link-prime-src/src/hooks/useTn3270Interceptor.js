import { useRef, useCallback } from 'react';

const HIDDEN_FIELDS = ['pin', 'password', 'auth_token', 'session_key', 'internal_ref'];
const PROTECTED_FIELDS = ['account_number', 'open_date', 'dob', 'sort_code', 'customer_id'];

export function useTn3270Interceptor(weaknesses = {}) {
  const screenBuffer = useRef([]);

  const addToBuffer = useCallback((entry) => {
    screenBuffer.current = [...screenBuffer.current.slice(-9), entry];
  }, []);

  const getFieldProps = useCallback((fieldName, baseProps = {}) => {
    const name = fieldName.toLowerCase();
    const props = { ...baseProps };

    if (weaknesses.tn3270_expose_hidden && HIDDEN_FIELDS.includes(name)) {
      props.type = 'text';
      props.hidden = undefined;
      props.style = {
        ...(props.style || {}),
        color: '#FF9933',
        borderBottom: '1px dashed #FF9933',
      };
      addToBuffer({
        field: fieldName.toUpperCase(),
        value: baseProps.value || '',
        timestamp: new Date().toTimeString().slice(0, 8),
        type: 'HIDDEN_EXPOSED',
      });
    }

    if (weaknesses.tn3270_overtype_protected && PROTECTED_FIELDS.includes(name)) {
      delete props.readOnly;
      delete props.disabled;
      props.style = {
        ...(props.style || {}),
        borderBottom: '1px dashed #FF3333',
        color: '#FF3333',
      };
    }

    return props;
  }, [weaknesses, addToBuffer]);

  const fieldAuditTag = useCallback((fieldName) => {
    const name = fieldName.toLowerCase();
    if (weaknesses.tn3270_expose_hidden && HIDDEN_FIELDS.includes(name)) return '[EXPOSED]';
    if (weaknesses.tn3270_overtype_protected && PROTECTED_FIELDS.includes(name)) return '[OVERTYPED]';
    return '';
  }, [weaknesses]);

  const logOvertype = useCallback((fieldName, value) => {
    addToBuffer({
      field: fieldName.toUpperCase(),
      value,
      timestamp: new Date().toTimeString().slice(0, 8),
      type: 'PROTECTED_OVERTYPE',
    });
  }, [addToBuffer]);

  return { getFieldProps, fieldAuditTag, screenBuffer, logOvertype };
}