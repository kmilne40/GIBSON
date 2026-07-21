from __future__ import annotations

import ftplib
import io
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Callable

DEFAULT_TIMEOUT = 10

@dataclass
class FtpCommandResult:
    text: str
    done: bool = False

class FtpSubsession:
    """Interactive z/OS-like USS FTP client backed by ftplib.

    The object is kept on GibsonState by OMVS so subsequent lines continue to
    use the same FTP connection until QUIT/BYE.  It never scans or retries; it
    connects only to the explicitly supplied host.
    """
    def __init__(self, env: Any, cwd_getter: Callable[[], str],
                 cwd_setter: Callable[[str], None], ftp_factory: Any = None,
                 timeout: int = DEFAULT_TIMEOUT):
        self.env = env
        self.cwd_getter = cwd_getter
        self.cwd_setter = cwd_setter
        self.ftp_factory = ftp_factory or ftplib.FTP
        self.timeout = timeout
        self.ftp: Any = None
        self.host = ''
        self.port = 21
        self.binary = False
        self.passive = True
        self.done = False
        self.last_rc = 'NOT CONNECTED'
        self.pending_user = ''
        self.logged_in_user = ''
        self.login_stage = 'local'

    def banner(self) -> str:
        return 'IBM FTP CLIENT - GIBSON USS\nEZA1450I IBM FTP CS - EXPLICIT CLIENT SESSION\n' + self.status(short=True) + '\nftp> '

    def connect_banner(self) -> str:
        return 'IBM FTP CS V2R4'

    def prompt(self) -> str:
        return 'ftp> '

    def connected(self) -> bool:
        return self.ftp is not None

    def _wrap(self, text: str) -> str:
        if self.ftp is not None and not self.logged_in_user and self.login_stage in {'need_user', 'need_pass'}:
            return (text or '').rstrip('\n')
        return (text or '').rstrip('\n') + '\nftp> '

    def _not_connected(self) -> str:
        return 'EZA1735I Not connected. Use OPEN <host> [port].\nftp> '

    def handle(self, raw: str) -> str:
        raw = raw or ''
        parts = raw.strip().split()
        cmd = parts[0].lower() if parts else 'status'
        args = parts[1:]
        try:
            if self.ftp is not None and not self.logged_in_user and self.login_stage == 'need_user' and cmd not in {'quit','bye','close','disconnect','open','help','?'}:
                return self.user([raw.strip()])
            if self.ftp is not None and not self.logged_in_user and self.login_stage == 'need_pass' and cmd not in {'quit','bye','close','disconnect','open','help','?'}:
                return self.password([raw])
            if cmd in {'quit','bye'}:
                text = self.close(final=True)
                self.done = True
                return text
            if cmd in {'help','?'}:
                return self._wrap(self.help())
            if cmd == 'open':
                if not args: return self._wrap('EZA1736I Usage: open <host> [port]')
                return self.open(args[0], int(args[1]) if len(args)>1 else 21)
            if cmd == 'user':
                return self._wrap(self.user(args))
            if cmd == 'pass':
                return self._wrap(self.password(args))
            if cmd == 'account':
                if not self.ftp: return self._not_connected()
                return self._wrap(str(self.ftp.sendcmd('ACCT ' + ' '.join(args))))
            if cmd == 'status': return self._wrap(self.status())
            if cmd in {'close','disconnect'}: return self._wrap(self.close())
            if cmd == 'pwd':
                if not self.ftp: return self._not_connected()
                return self._wrap(str(self.ftp.pwd()))
            if cmd == 'lpwd': return self._wrap(self.cwd_getter())
            if cmd in {'cd','cwd'}:
                if not self.ftp: return self._not_connected()
                target=args[0] if args else '/'
                return self._wrap(str(self.ftp.cwd(target)))
            if cmd == 'cdup':
                if not self.ftp: return self._not_connected()
                return self._wrap(str(self.ftp.cwd('..')))
            if cmd == 'lcd':
                target=args[0] if args else '/'
                self.cwd_setter(target)
                return self._wrap('Local directory now ' + self.cwd_getter())
            if cmd in {'ls','dir'}: return self._wrap(self.listing('LIST', args))
            if cmd == 'nlist': return self._wrap(self.nlist(args))
            if cmd == 'get': return self._wrap(self.get(args))
            if cmd == 'put': return self._wrap(self.put(args))
            if cmd == 'mget': return self._wrap(self.mget(args))
            if cmd == 'mput': return self._wrap(self.mput(args))
            if cmd == 'delete':
                if not self.ftp: return self._not_connected()
                return self._wrap(str(self.ftp.delete(args[0]))) if args else self._wrap('EZA1740I Usage: delete <remote>')
            if cmd == 'mkdir':
                if not self.ftp: return self._not_connected()
                return self._wrap(str(self.ftp.mkd(args[0]))) if args else self._wrap('EZA1741I Usage: mkdir <dir>')
            if cmd == 'rmdir':
                if not self.ftp: return self._not_connected()
                return self._wrap(str(self.ftp.rmd(args[0]))) if args else self._wrap('EZA1742I Usage: rmdir <dir>')
            if cmd == 'rename':
                if not self.ftp: return self._not_connected()
                return self._wrap(str(self.ftp.rename(args[0], args[1]))) if len(args)>=2 else self._wrap('EZA1743I Usage: rename <from> <to>')
            if cmd in {'ascii','binary','type'}:
                return self._wrap(self.set_type(cmd, args))
            if cmd == 'passive':
                self.passive=True
                if self.ftp: self.ftp.set_pasv(True)
                return self._wrap('EZA1709I Passive mode enabled.')
            if cmd == 'active':
                self.passive=False
                if self.ftp: self.ftp.set_pasv(False)
                return self._wrap('EZA1710I Active mode enabled.')
            if cmd in {'quote','site'}:
                if not self.ftp: return self._not_connected()
                if not args: return self._wrap('EZA1744I Usage: ' + cmd + ' <command>')
                command = 'SITE ' + ' '.join(args) if cmd == 'site' else ' '.join(args)
                return self._wrap(str(self.ftp.sendcmd(command)))
            return self._wrap('EZA1737I Unknown FTP subcommand ' + cmd.upper() + '. Use HELP.')
        except Exception as exc:
            self.last_rc = type(exc).__name__
            if cmd == 'open': self.ftp = None
            return self._wrap(f'EZA1735I FTP error: {type(exc).__name__}: {exc}')

    def open(self, host: str, port: int = 21) -> str:
        self.close(silent=True)
        self.host = host
        self.port = int(port)
        ftp = self.ftp_factory()
        resp = ftp.connect(host, self.port, timeout=self.timeout)
        try: ftp.set_pasv(self.passive)
        except Exception: pass
        self.ftp = ftp
        self.last_rc = 'CONNECTED'
        self.login_stage = 'need_user'
        default_user = 'IBMUSER'
        return (f'IBM FTP CS V2R4\nEZA1450I {resp}\n'
                f'Connected to {host}.\n'
                f'Name ({host}:{default_user}):')

    def user(self, args: list[str]) -> str:
        if not args: return 'EZA1702I Usage: user <userid> [password]'
        if not self.ftp: return 'EZA1735I Not connected.'
        self.pending_user = args[0]
        self.login_stage = 'need_pass'
        if len(args) > 1:
            resp = self.ftp.login(args[0], args[1])
            self.logged_in_user = args[0]
            self.pending_user = ''
            self.login_stage = 'authenticated'
            return str(resp) + '\nftp> '
        return '331 Send password please.\nPassword:'

    def password(self, args: list[str]) -> str:
        if not self.ftp: return 'EZA1735I Not connected.'
        if not self.pending_user: return 'EZA1704I No pending USER. Issue USER userid first.'
        resp = self.ftp.login(self.pending_user, args[0] if args else '')
        self.logged_in_user = self.pending_user
        self.pending_user = ''
        self.login_stage = 'authenticated'
        return str(resp) + '\nftp> '

    def set_type(self, cmd: str, args: list[str]) -> str:
        if cmd == 'type' and args:
            val = args[0].upper()
            binary = val in {'I','IMAGE','BINARY'}
        else:
            binary = cmd == 'binary'
        self.binary = binary
        if self.ftp: self.ftp.voidcmd('TYPE I' if binary else 'TYPE A')
        return 'EZA1706I Representation type is ' + ('Image' if binary else 'ASCII')

    def listing(self, verb: str, args: list[str]) -> str:
        if not self.ftp: return 'EZA1735I Not connected.'
        lines: list[str] = []
        self.ftp.retrlines(verb + ((' ' + ' '.join(args)) if args else ''), lines.append)
        return '\n'.join(lines) or 'EZA1705I No entries.'

    def nlist(self, args: list[str]) -> str:
        if not self.ftp: return 'EZA1735I Not connected.'
        rows = self.ftp.nlst(*args) if args else self.ftp.nlst()
        return '\n'.join(str(x) for x in rows) or 'EZA1705I No entries.'

    def mget(self, args: list[str]) -> str:
        if not args: return 'EZA1745I Usage: mget <pattern>'
        names = self.ftp.nlst(args[0]) if self.ftp else []
        done=[]
        for n in names:
            done.append(self.get([n, PurePosixPath(str(n)).name]))
        return '\n'.join(done) if done else 'EZA1705I No entries matched.'

    def mput(self, args: list[str]) -> str:
        if not args: return 'EZA1746I Usage: mput <local-pattern>'
        import glob
        base = self.env.real_path(self.cwd_getter())
        rows=[]
        for path in glob.glob(str(base / args[0])):
            rows.append(self.put([path, PurePosixPath(path).name]))
        return '\n'.join(rows) if rows else 'EZA1705I No local entries matched.'

    def _is_dataset_syntax(self, operand: str) -> bool:
        return operand.startswith('//') or operand.startswith("'") or operand.upper().startswith('DSN:')

    def _dataset_name(self, operand: str) -> str:
        op=operand
        if op.upper().startswith('DSN:'): op=op[4:]
        if op.startswith('//'): op=op[2:]
        return op.strip().strip("'").upper()

    def _local_real_path(self, operand: str):
        virt = self.env.resolve(self.cwd_getter(), operand)
        return self.env.real_path(virt)

    def get(self, args: list[str]) -> str:
        if not self.ftp: return 'EZA1735I Not connected.'
        if not args: return 'EZA1738I Usage: get <remote> [local]'
        remote=args[0]
        local=args[1] if len(args)>1 else PurePosixPath(remote).name
        if self._is_dataset_syntax(local):
            chunks: list[bytes] = []
            if self.binary:
                self.ftp.retrbinary('RETR ' + remote, chunks.append)
                data=b''.join(chunks).decode('latin-1', errors='replace')
            else:
                lines: list[str] = []
                self.ftp.retrlines('RETR ' + remote, lines.append)
                data='\n'.join(lines)+'\n'
            dsn=self._dataset_name(local)
            try: self.env.state.datasets.allocate('IBMUSER', dsn, org='PS', recfm='VB', lrecl=1024)
            except Exception: pass
            self.env.state.datasets.write('IBMUSER', dsn, data)
            return f"EZA1712I Transfer complete: {remote} -> //'{dsn}'"
        path=self._local_real_path(local)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.binary:
            with path.open('wb') as fh: self.ftp.retrbinary('RETR ' + remote, fh.write)
        else:
            lines=[]; self.ftp.retrlines('RETR ' + remote, lines.append)
            path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        return f'EZA1712I Transfer complete: {remote} -> {local}'

    def put(self, args: list[str]) -> str:
        if not self.ftp: return 'EZA1735I Not connected.'
        if not args: return 'EZA1739I Usage: put <local> [remote]'
        local=args[0]
        remote=args[1] if len(args)>1 else PurePosixPath(local).name
        if self._is_dataset_syntax(local):
            dsn=self._dataset_name(local)
            data=self.env.state.datasets.read('IBMUSER', dsn).encode('utf-8')
            self.ftp.storbinary('STOR ' + remote, io.BytesIO(data))
            return f"EZA1714I Transfer complete: //'{dsn}' -> {remote}"
        path=self._local_real_path(local)
        with path.open('rb') as fh: self.ftp.storbinary('STOR ' + remote, fh)
        return f'EZA1714I Transfer complete: {local} -> {remote}'

    def close(self, final: bool=False, silent: bool=False) -> str:
        if self.ftp:
            try:
                if final: self.ftp.quit()
                else: self.ftp.close()
            except Exception:
                try: self.ftp.close()
                except Exception: pass
        self.ftp=None
        self.pending_user=''
        self.logged_in_user=''
        self.login_stage='local'
        self.last_rc='CLOSED'
        if silent: return ''
        return 'EZA1701I FTP session ended.' if final else 'EZA1708I Connection closed.'

    def status(self, short: bool=False) -> str:
        if short:
            return 'FTP STATUS: ' + (f'CONNECTED {self.host} {self.port}' if self.ftp else 'NOT CONNECTED')
        return '\n'.join(['IBM FTP CLIENT STATUS',
            f"Connected . . . {'YES' if self.ftp else 'NO'}",
            f'Host . . . . . {self.host}', f'Port . . . . . {self.port}',
            f'User . . . . . {self.logged_in_user}',
            f"Type . . . . . {'BINARY' if self.binary else 'ASCII'}",
            f"Mode . . . . . {'PASSIVE' if self.passive else 'ACTIVE'}",
            f'Last RC . . . {self.last_rc}'])

    def help(self) -> str:
        return ('FTP host [port] or OPEN host [port].  Name/login and Password '
                'prompts appear before ftp>; ftp> appears only after successful '
                'authentication.  Commands after login: USER PASS PWD CD CWD LS '
                'DIR GET PUT ASCII BINARY STATUS CLOSE DISCONNECT BYE QUIT HELP ?. '
                'Additional commands: ACCOUNT LPWD CDUP LCD NLIST MGET MPUT DELETE '
                'MKDIR RMDIR RENAME TYPE PASSIVE ACTIVE QUOTE SITE LOCSITE.')
