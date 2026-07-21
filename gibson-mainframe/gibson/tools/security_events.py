from __future__ import annotations

import re
import time
import secrets
from typing import Any, Mapping

_SECRET_PATTERNS = [
    (re.compile(r'(?i)(pass(word)?|passwd|pwd|api[_-]?key|token|secret|pin)=([^\s&]+)'), r'\1=REDACTED'),
    (re.compile(r'(?i)(using\s+)(\S+)'), r'\1REDACTED'),
    (re.compile(r'(?i)(-id\s+[^:\s]+:)(\S+)'), r'\1REDACTED'),
    (re.compile(r'(?i)([?&](?:token|key|apikey|api_key|password|pass|secret)=)[^&\s]+'), r'\1REDACTED'),
]

def redact(value: Any) -> str:
    text = str(value or '')
    for pat, repl in _SECRET_PATTERNS:
        text = pat.sub(repl, text)
    return text[:500]

def _user_from_env(env: Any, user: str | None = None) -> str:
    if user:
        return str(user).upper()
    try:
        cwd = getattr(env, 'cwd', '') or ''
        if cwd.startswith('/u/'):
            return cwd.split('/')[2].upper()
    except Exception:
        pass
    return 'IBMUSER'

def make_corrid(tool: str, action: str | None = None) -> str:
    head = re.sub(r'[^A-Z0-9]+', '-', (tool or 'OMVS').upper()).strip('-')[:16] or 'OMVS'
    tail = re.sub(r'[^A-Z0-9]+', '-', (action or 'TOOL').upper()).strip('-')[:16]
    prefix = head if not tail or tail == 'TOOL' else f'{head}-{tail}'
    return f'{prefix}-{time.strftime("%Y%m%d-%H%M%S")}-{secrets.token_hex(2).upper()}'

def emit_omvs_tool_event(env: Any = None, *, state: Any = None, user: str | None = None,
                         tool: str = 'OMVS', subcommand: str = '', script: str = '', target: str = '',
                         target_host: str = '', target_port: str | int = '', result: str = 'OK',
                         severity: str = 'INFO', details: str | Mapping[str, Any] | None = None,
                         correlation_id: str | None = None, command_line: str = '',
                         evidence_type: str = 'OMVS_TOOL', smf_type: str = '80', service: str = 'OMVS') -> str:
    state = state or getattr(env, 'state', None)
    user_u = _user_from_env(env, user)
    tool_u = (tool or 'OMVS').upper()
    script_u = (script or subcommand or '').upper()
    corr = correlation_id or make_corrid(tool_u, script_u or subcommand)
    if isinstance(details, Mapping):
        detail_text = ' '.join(f'{str(k).upper()}={redact(v)}' for k, v in sorted(details.items()))
    else:
        detail_text = redact(details or '')
    cmd_redacted = redact(command_line or '')
    extra = {
        'EVENT': evidence_type.upper(), 'USERID': user_u, 'TOOL': tool_u, 'SUBCOMMAND': (subcommand or '').upper(),
        'SCRIPT': script_u, 'TARGET': redact(target or target_host), 'TARGET_HOST': redact(target_host or target),
        'TARGET_PORT': str(target_port or ''), 'RESULT': (result or 'OK').upper(), 'SEVERITY': (severity or 'INFO').upper(),
        'CORRID': corr, 'DETAIL': detail_text, 'SERVICE': service.upper(), 'COMMAND_LINE': cmd_redacted,
        'REDACTED': 'YES', 'RECORD_TYPE': smf_type,
    }
    try:
        if state is not None and getattr(state, 'audit', None) is not None:
            state.audit.record_smf80(user_u, f'{evidence_type.upper()} RUN',
                                     f'TOOL={tool_u} SCRIPT={script_u} TARGET={extra["TARGET"]} RESULT={extra["RESULT"]} CORRID={corr} {detail_text}'.strip(),
                                     result=extra['RESULT'], extra=extra)
    except Exception:
        pass
    try:
        if state is not None and getattr(state, 'console_log', None) is not None:
            state.console_log.record(f'GIBOMV080I OMVS TOOL EVENT USER({user_u}) TOOL({tool_u}) SCRIPT({script_u or "-"}) TARGET({extra["TARGET"] or "-"}) RESULT({extra["RESULT"]}) CORRID({corr})')
    except Exception:
        pass
    try:
        if state is not None:
            if not hasattr(state, 'tool_events'):
                setattr(state, 'tool_events', [])
            ev = {'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'user': user_u, 'tool': tool_u, 'subcommand': subcommand,
                  'script': script_u, 'target': extra['TARGET'], 'target_port': str(target_port or ''), 'result': extra['RESULT'],
                  'severity': extra['SEVERITY'], 'correlation_id': corr, 'detail': detail_text, 'command_line': cmd_redacted}
            state.tool_events.append(ev)
            if len(state.tool_events) > 1000:
                del state.tool_events[:-1000]
            try:
                state.raise_dashboard_alert(f'OMVS TOOL {tool_u} {script_u} TARGET({extra["TARGET"]}) RESULT({extra["RESULT"]}) CORRID({corr})', severity=severity, event_type='OMVS_TOOL')
            except Exception:
                pass
    except Exception:
        pass
    return corr

def format_corr_line(corrid: str) -> str:
    return f'\nCorrelation ID: {corrid}\nForensic event written to SMF80, OPERLOG, audit.log and dashboard activity.'
