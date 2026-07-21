from __future__ import annotations

import socket
from typing import Any, Callable

IAC=255; DONT=254; DO=253; WONT=252; WILL=251; SB=250; SE=240

class TelnetSubsession:
    """Interactive line-mode Telnet client for Gibson USS."""
    def __init__(self, socket_factory: Callable[..., Any] | None = None, timeout: int = 10):
        self.socket_factory = socket_factory or socket.create_connection
        self.timeout = timeout
        self.sock: Any = None
        self.host = ''
        self.port = 23
        self.done = False
        self.mode = 'line'
        self.crlf = True
        self.echo = True
        self.last_rc = 'NOT CONNECTED'
        self.login_stage = 'local'
        self.authenticated = False

    def banner(self) -> str:
        return 'IBM TELNET CLIENT - GIBSON USS\n' + self.status(short=True) + '\ntelnet> '

    def connect_banner(self) -> str:
        return 'IBM TELNET CLIENT - GIBSON USS\nTELNET STATUS: CONNECTING'

    def _wrap(self, text: str) -> str:
        if self.sock and not self.authenticated:
            return (text or '').rstrip('\n')
        return (text or '').rstrip('\n') + '\ntelnet> '

    def _require(self) -> str:
        return 'EZA8203I Not connected. Use OPEN <host> [port].'

    def handle(self, raw: str) -> str:
        raw = raw or ''
        parts = raw.strip().split()
        cmd = parts[0].lower() if parts else 'status'
        args = parts[1:]
        try:
            if self.sock and not self.authenticated and cmd not in {'quit','bye','exit','close'}:
                return self._handle_login_data(raw)
            if cmd in {'quit','bye','exit'}:
                text=self.close(final=True); self.done=True; return text
            if cmd in {'help','?'}: return self._wrap(self.help())
            if cmd == 'open':
                if not args: return self._wrap('EZA8204I Usage: open <host> [port]')
                return self._wrap(self.open(args[0], int(args[1]) if len(args)>1 else 23))
            if cmd == 'close': return self._wrap(self.close())
            if cmd == 'status': return self._wrap(self.status())
            if cmd == 'mode':
                if args and args[0].lower() in {'line','character'}:
                    self.mode=args[0].lower(); return self._wrap('EZA8206I Mode set to ' + self.mode + '.')
                return self._wrap('EZA8207I Usage: mode line | mode character')
            if cmd == 'crlf':
                if args and args[0].lower() in {'on','off'}:
                    self.crlf = args[0].lower() == 'on'; return self._wrap('CRLF ' + ('ON' if self.crlf else 'OFF'))
                return self._wrap('Usage: crlf on|off')
            if cmd == 'echo':
                if args and args[0].lower() in {'on','off'}:
                    self.echo = args[0].lower() == 'on'; return self._wrap('ECHO ' + ('ON' if self.echo else 'OFF'))
                return self._wrap('Usage: echo on|off')
            if cmd in {'read','recv'}:
                return self._wrap(self.read())
            if cmd == 'send':
                return self._wrap(self.send(' '.join(args)))
            if cmd == 'escape': return self._wrap('EZA8212I Escape character is ^].')
            # Direct pass-through: when connected, unrecognised lines are sent.
            if self.sock:
                return self._wrap(self.send(raw))
            return self._wrap('EZA8213I Unknown Telnet subcommand ' + cmd.upper() + '. Use HELP.')
        except Exception as exc:
            if cmd == 'open': self.sock = None
            self.last_rc = type(exc).__name__
            return self._wrap(f'EZA8209I unable to connect - Telnet error: {type(exc).__name__}: {exc}')

    def open(self, host: str, port: int = 23) -> str:
        self.close(silent=True)
        self.host=host; self.port=int(port)
        self.sock = self.socket_factory((host,self.port), timeout=self.timeout)
        try: self.sock.settimeout(1.0)
        except Exception: pass
        self.last_rc='CONNECTED'
        self.authenticated = False
        self.login_stage = 'login'
        banner=self.read(timeout=0.6)
        text = f'EZA8201I Connected to {host} {self.port}.'
        if banner and 'No data' not in banner:
            text += '\n' + banner
        if 'login:' not in text.lower() and 'password:' not in text.lower():
            text += '\nlogin:'
        return text

    def _handle_login_data(self, raw: str) -> str:
        if not self.sock:
            return self._require()
        payload = raw + ('\r\n' if self.crlf else '\n')
        self.sock.sendall(payload.encode('utf-8', errors='replace'))
        received = self.read(timeout=0.8)
        low = received.lower()
        if 'password:' in low:
            self.login_stage = 'password'
            return received
        if 'login:' in low and self.login_stage == 'password':
            self.login_stage = 'login'
            self.authenticated = False
            return received
        self.authenticated = True
        self.login_stage = 'authenticated'
        return received if received and 'No data' not in received else 'EZA8208I Data sent.'

    def _cook_incoming(self, data: bytes) -> str:
        out=bytearray(); i=0; replies=[]
        while i < len(data):
            b=data[i]
            if b == IAC and i+1 < len(data):
                cmd=data[i+1]
                if cmd in {WILL, WONT, DO, DONT} and i+2 < len(data):
                    opt=data[i+2]
                    # Refuse options conservatively: DONT for WILL, WONT for DO.
                    if cmd == WILL: replies += [IAC, DONT, opt]
                    elif cmd == DO: replies += [IAC, WONT, opt]
                    i += 3; continue
                if cmd == IAC:
                    out.append(IAC); i += 2; continue
                if cmd == SB:
                    i += 2
                    while i+1 < len(data) and not (data[i] == IAC and data[i+1] == SE): i += 1
                    i += 2; continue
                i += 2; continue
            out.append(b); i += 1
        if replies and self.sock:
            try: self.sock.sendall(bytes(replies))
            except Exception: pass
        return out.decode('utf-8', errors='replace').replace('\r\n','\n').replace('\r','\n')

    def send(self, text: str) -> str:
        if not self.sock: return self._require()
        payload = text + ('\r\n' if self.crlf else '\n')
        self.sock.sendall(payload.encode('utf-8', errors='replace'))
        received = self.read(timeout=0.8)
        return received if received and 'No data' not in received else 'EZA8208I Data sent.'

    def read(self, timeout: float | None = None) -> str:
        if not self.sock: return self._require()
        try: self.sock.settimeout(self.timeout if timeout is None else timeout)
        except Exception: pass
        chunks=[]
        while True:
            try:
                data=self.sock.recv(4096)
            except socket.timeout:
                break
            if not data:
                self.close(silent=True); return 'EZA8211I Connection closed by foreign host.'
            chunks.append(data)
            cooked_so_far = self._cook_incoming(b''.join(chunks))
            low = cooked_so_far.lower()
            if low.rstrip().endswith(('login:', 'password:')) or low.rstrip().endswith('$'):
                break
            # Continue until timeout so short banners/replies split across TCP packets are collected.
            continue
        if not chunks: return 'EZA8210I No data available before timeout.'
        return self._cook_incoming(b''.join(chunks)).rstrip('\n')

    def close(self, final: bool=False, silent: bool=False) -> str:
        if self.sock:
            try: self.sock.close()
            except Exception: pass
        self.sock=None; self.last_rc='CLOSED'; self.authenticated=False; self.login_stage='local'
        if silent: return ''
        return 'EZA8200I Telnet session ended.' if final else 'EZA8205I Connection closed.'

    def status(self, short: bool=False) -> str:
        if short:
            return 'TELNET STATUS: ' + (f'CONNECTED {self.host} {self.port}' if self.sock else 'NOT CONNECTED')
        return '\n'.join(['IBM TELNET CLIENT STATUS',
            f"Connected . . . {'YES' if self.sock else 'NO'}", f'Host . . . . . {self.host}',
            f'Port . . . . . {self.port}', f'Mode . . . . . {self.mode.upper()}',
            f"CRLF . . . . . {'ON' if self.crlf else 'OFF'}", f'Last RC . . . {self.last_rc}'])

    def help(self) -> str:
        return ('TELNET host [port] or OPEN host [port].  The remote login prompt '
                'is displayed before telnet>; telnet> is shown only in local '
                'command mode or after authentication.  Commands: OPEN SEND READ '
                'RECV STATUS MODE LINE MODE CHARACTER CRLF ON|OFF ECHO ON|OFF '
                'ESCAPE CLOSE QUIT EXIT HELP ?.  CLOSE/QUIT/EXIT end the session.')
