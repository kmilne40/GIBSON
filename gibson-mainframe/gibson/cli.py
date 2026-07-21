from __future__ import annotations
import argparse
import signal
import time
from pathlib import Path

from gibson.apps.master_console import MasterConsoleUI
from gibson.core.config import GibsonConfig
from gibson.core.service_control import ManagedService
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor
from gibson.core.security_mode import SECURE, VULN, audit_mode_event, security_mode_banner
from gibson.security.secure_profile import apply_secure_profile


def build_state(args) -> GibsonState:
    cfg = GibsonConfig.from_env()
    if args.gacf:
        cfg.gacf_path = Path(args.gacf).expanduser()
    if args.sim_root:
        cfg.sim_root = Path(args.sim_root).expanduser()
        cfg.files_root = cfg.sim_root / "f"
        cfg.commands_dir = cfg.sim_root / "f" / "commands"
        if not args.gacf:
            cfg.gacf_path = cfg.sim_root / "GACF.DB"
    if getattr(args, "secure", False) and getattr(args, "vuln", False):
        raise SystemExit("GIBSON SECURITY MODE ERROR: --secure and --vuln are mutually exclusive")
    if getattr(args, "secure", False) and getattr(args, "cbsa_vuln", False):
        raise SystemExit("GIBSON SECURITY MODE ERROR: --secure and --cbsa-vuln are mutually exclusive")
    if getattr(args, "secure", False) and getattr(args, "dvca_vuln", False):
        raise SystemExit("GIBSON SECURITY MODE ERROR: --secure and --dvca-vuln are mutually exclusive")
    if getattr(args, "secure", False):
        cfg.security_mode = SECURE
        cfg.port = 1023
        cfg.dashboard_port = 8443
        cfg.console_security_audit = True
        cfg.strict_tso_ptkt = True
    elif getattr(args, "vuln", False):
        cfg.security_mode = VULN
    if getattr(args, "split_console", False):
        print("IEE305I --split-console OPTION NOT AVAILABLE IN GIBSON v26.1; STANDARD CONSOLE WILL START")
        cfg.split_console = False
    if getattr(args, "logon_panel", False):
        cfg.logon_panel = True
    if args.host:
        cfg.host = args.host
    if getattr(args, "ipl_hostname", None):
        cfg.default_system_hostname = args.ipl_hostname.strip().upper() or cfg.default_system_hostname
    if args.port:
        cfg.port = args.port
    if args.ftp_port:
        cfg.ftp_port = args.ftp_port
    if args.uss_port is not None:
        cfg.uss_port = args.uss_port
    if getattr(args, "tn3270_port", None):
        cfg.tn3270_port = args.tn3270_port
    if args.db2_tcp_port:
        cfg.db2_tcp_port = args.db2_tcp_port
    if args.db2_ws_port:
        cfg.db2_ws_port = args.db2_ws_port
    if getattr(args, "no_web_terminal", False):
        cfg.with_web_terminal = False
    elif getattr(args, "with_web_terminal", False) or getattr(cfg, "with_web_terminal", False):
        cfg.with_web_terminal = True
    if getattr(args, "web_terminal_port", None):
        cfg.web_terminal_port = args.web_terminal_port
    if getattr(args, "cbsa_api_port", None):
        cfg.cbsa_api_port = args.cbsa_api_port
    if getattr(args, "fibs_web_port", None):
        cfg.fibs_web_port = args.fibs_web_port
    # Welcome site now listens on port 80 by default. Deprecated
    # welcome8000 flags are accepted as compatibility aliases only.
    if getattr(args, "welcome_port", None):
        cfg.welcome_port = args.welcome_port
    elif getattr(args, "welcome8000_port", None):
        cfg.welcome_port = args.welcome8000_port
    if getattr(args, "no_welcome", False) or getattr(args, "no_welcome8000", False):
        cfg.welcome_enabled = False
    elif getattr(args, "with_welcome", False) or getattr(args, "with_welcome8000", False):
        cfg.welcome_enabled = True
    if getattr(args, "no_fibs_web", False):
        cfg.with_fibs_web = False
    elif getattr(args, "with_fibs_web", False):
        cfg.with_fibs_web = True
    cfg.cbsa_vuln = bool(getattr(args, "cbsa_vuln", False) or getattr(args, "vuln", False) or getattr(cfg, "cbsa_vuln", False))
    cfg.dvca_vuln = bool(getattr(args, "dvca_vuln", False) or getattr(args, "vuln", False) or getattr(cfg, "dvca_vuln", True))
    cfg.with_dvca_web = bool(getattr(args, "with_dvca_web", False) or getattr(args, "with_dvca", False) or getattr(args, "with_app8080", False) or getattr(cfg, "with_dvca_web", False))
    state = GibsonState.create(cfg)
    try:
        from gibson.core import v26_features
        if getattr(cfg, "split_console", False):
            v26_features.set_split(state, True)
    except Exception:
        pass
    if state.config.security_mode == SECURE:
        apply_secure_profile(state)
        audit_mode_event(state, "SECURE MODE STARTUP", "CIS-ALIGNED SIMULATOR PROFILE")
    else:
        audit_mode_event(state, "VULNERABLE MODE STARTUP", "TRAINING COMPATIBILITY PROFILE")
    if getattr(args, "ctf", False):
        try:
            from gibson.ctf_seed import seed_ctf
            seed_ctf(state)
        except Exception as _ctf_exc:
            print(f"GIBSON-CTF: seed error (continuing without CTF): {_ctf_exc}")
    return state


def _register_services(state: GibsonState, servers: list, args) -> None:
    mgr = state.service_manager
    from gibson.services.ftp_server import serve_ftp
    from gibson.services.uss_server import serve_uss
    from gibson.services.dashboard import serve_dashboard
    from gibson.services.db2_server import serve_db2das, serve_db2ws
    from gibson.services.nje_server import serve_nje
    from gibson.services.cbsa_rest8080 import serve_cbsa_rest8080
    from gibson.services.fibs_web9080 import serve_fibs_web9080
    from gibson.services.welcome80 import serve_welcome

    mgr.register(ManagedService(
        "JES2", kind="logical", description="Job Entry Subsystem", state="STARTED",
        start_msgs=("$HASP100 JES2     ON STCINRDR", "$HASP373 JES2     STARTED"),
        stop_msgs=("$HASP395 JES2     ENDED",),
        pause_msgs=("$HASP250 JES2     PAUSED",),
    ))
    mgr.register(ManagedService(
        "RACF", kind="logical", description="Security authentication service", state="STARTED",
        start_msgs=("IRR54001I RACF SUBSYSTEM INITIALIZED",),
        stop_msgs=("IRR54002I RACF SUBSYSTEM STOPPED",),
        pause_msgs=("IRR54003I RACF SUBSYSTEM PAUSED",),
    ))
    mgr.register(ManagedService(
        "OMVS", kind="logical", port=state.config.uss_port, description="z/OS UNIX System Services",
        state="STARTED" if not args.no_uss else "STOPPED", listener_tokens=("OMVS", "USS"),
        starter=lambda: serve_uss(state),
        start_msgs=("BPXM010I OMVS INITIALIZATION COMPLETE", f"BPXM011I USS LISTENER ACTIVE ON PORT {state.config.uss_port}"),
        stop_msgs=("BPXM012I OMVS SHUTDOWN COMPLETE",),
        pause_msgs=("BPXM013I OMVS PAUSED",),
    ))
    mgr.register(ManagedService(
        "TN3270", kind="logical", port=state.config.tn3270_port, description="Dedicated TN3270 listener for web3270/x3270 clients",
        state="STARTED" if state.config.tn3270_port else "STOPPED", listener_tokens=("TN3270",),
        starter=lambda: __import__('gibson.services.tn3270_server', fromlist=['serve_tn3270']).serve_tn3270(state),
        start_msgs=(f"IST001I TN3270 LISTENER ACTIVE ON PORT {state.config.tn3270_port}",),
        stop_msgs=("IST002I TN3270 LISTENER STOPPED",),
        pause_msgs=("IST003I TN3270 LISTENER PAUSED",),
    ))
    mgr.register(ManagedService(
        "ZVM3270", kind="logical", port=getattr(state.config, "zvm_port", 3023), description="EBCDIC z/VM 3270 logon listener (c3270/x3270)",
        state="STARTED" if (getattr(state.config, "zvm_port", 0) and not getattr(args, "no_zvm", False)) else "STOPPED", listener_tokens=("ZVM3270", "ZVM"),
        starter=lambda: __import__('gibson.services.zvm3270_server', fromlist=['serve_zvm3270']).serve_zvm3270(state),
        start_msgs=(f"IST001I ZVM 3270 LOGON LISTENER ACTIVE ON PORT {getattr(state.config, 'zvm_port', 3023)}",),
        stop_msgs=("IST002I ZVM 3270 LISTENER STOPPED",),
        pause_msgs=("IST003I ZVM 3270 LISTENER PAUSED",),
    ))
    mgr.register(ManagedService(
        "LENNOX", port=getattr(state.config, "lennox_port", 2380),
        description="LENNOX standalone Linux training system (telnet, CTF jump box)",
        state="STARTED" if getattr(state.config, "lennox_port", 0) else "STOPPED",
        listener_tokens=("LENNOX",),
        starter=lambda: __import__('gibson.services.lennox_server', fromlist=['serve_lennox']).serve_lennox(state),
        start_msgs=(f"LNX001I LENNOX TRAINING SYSTEM ACTIVE ON PORT {getattr(state.config, 'lennox_port', 2380)}",),
        stop_msgs=("LNX002I LENNOX TRAINING SYSTEM STOPPED",),
    ))
    mgr.register(ManagedService(
        "FTPD", port=state.config.ftp_port, description="IBM FTP CS simulated listener",
        state="STARTED" if args.with_ftp else "STOPPED", listener_tokens=("FTP",), starter=lambda: serve_ftp(state),
        start_msgs=("$HASP100 FTPD     ON STCINRDR", "$HASP373 FTPD     STARTED", "IEF403I FTPD - STARTED - TIME=00.00.00"),
        stop_msgs=("IEF404I FTPD - ENDED - TIME=00.00.00", "$HASP395 FTPD     ENDED"),
        pause_msgs=("IEE341I FTPD PAUSED",),
    ))
    mgr.register(ManagedService(
        "GIBDASH", port=state.config.dashboard_port, description="Gibson dashboard",
        state="STOPPED" if args.no_dashboard else "STARTED", listener_tokens=("DASH",), starter=lambda: serve_dashboard(state),
        start_msgs=(f"IEE352I GIBDASH STARTED ON PORT {state.config.dashboard_port}",),
        stop_msgs=("IEE334I GIBDASH STOPPED",),
        pause_msgs=("IEE341I GIBDASH PAUSED",),
    ))
    mgr.register(ManagedService(
        "WEBTERM", port=state.config.web_terminal_port, description="Gibson browser terminal with PF-key buttons",
        state="STARTED" if getattr(state.config, "with_web_terminal", False) else "STOPPED", listener_tokens=("WEBTERM", "BROWSERTERM"),
        starter=lambda: __import__('gibson.services.web_terminal', fromlist=['serve_web_terminal']).serve_web_terminal(state),
        start_msgs=(f"IEE352I WEBTERM STARTED ON PORT {state.config.web_terminal_port}",),
        stop_msgs=("IEE334I WEBTERM STOPPED",),
        pause_msgs=("IEE341I WEBTERM PAUSED",),
    ))
    mgr.register(ManagedService(
        "DB2DAS", port=state.config.db2_tcp_port, description="Db2 DAS/DRDA style listener",
        state="STOPPED" if args.no_db2 else "STARTED", listener_tokens=("DB2DAS",), starter=lambda: serve_db2das(state),
        start_msgs=(f"DSN3200I DB2DAS STARTED ON PORT {state.config.db2_tcp_port}",),
        stop_msgs=("DSN3201I DB2DAS STOPPED",),
        pause_msgs=("DSN3202I DB2DAS PAUSED",),
    ))
    mgr.register(ManagedService(
        "NJE", port=state.config.nje_port, description="JES2 Network Job Entry (NJE/TCP) listener",
        state="STARTED" if getattr(state.config, "nje_port", 0) else "STOPPED",
        listener_tokens=("NJE", "NETSERV"), starter=lambda: serve_nje(state),
        start_msgs=(f"$HASP880 NJE/TCP NETSERV ACTIVE ON PORT {state.config.nje_port}",
                    f"$HASP880 NJE/TCP TLS NETSERV ACTIVE ON PORT {state.config.nje_tls_port}"),
        stop_msgs=("$HASP881 NJE/TCP NETSERV STOPPED",),
        pause_msgs=("$HASP882 NJE/TCP NETSERV PAUSED",),
    ))
    mgr.register(ManagedService(
        "DB2WS", port=state.config.db2_ws_port, description="Db2 WebSocket shell",
        state="STOPPED" if args.no_db2 else "STARTED", listener_tokens=("DB2WS",), starter=lambda: serve_db2ws(state),
        start_msgs=(f"DSN3300I DB2WS STARTED ON PORT {state.config.db2_ws_port}",),
        stop_msgs=("DSN3301I DB2WS STOPPED",),
        pause_msgs=("DSN3302I DB2WS PAUSED",),
    ))

    mgr.register(ManagedService(
        "APP8080", port=state.config.cbsa_api_port, description="Unified CBSA/DVCA/hack3270 app server",
        state="STARTED" if (getattr(args, "with_cbsa_api", False) or getattr(args, "with_app8080", False) or getattr(args, "with_dvca_web", False)) else "STOPPED", listener_tokens=("APP8080", "CBSA", "DVCA", "HACK3270"),
        starter=lambda: serve_cbsa_rest8080(state),
        start_msgs=(f"IEE352I APP8080 STARTED ON PORT {state.config.cbsa_api_port}",),
        stop_msgs=("IEE334I APP8080 STOPPED",),
        pause_msgs=("IEE341I APP8080 PAUSED",),
    ))
    mgr.register(ManagedService(
        "WELCOME", port=state.config.welcome_port, description="Welcome to Gibson orientation site",
        state="STARTED" if getattr(state.config, "welcome_enabled", True) else "STOPPED", listener_tokens=("WELCOME", "PORT80"),
        starter=lambda: serve_welcome(state),
        start_msgs=(f"IEE352I WELCOME STARTED ON PORT {state.config.welcome_port}",),
        stop_msgs=("IEE334I WELCOME STOPPED",),
        pause_msgs=("IEE341I WELCOME PAUSED",),
    ))
    mgr.register(ManagedService(
        "FIBSWEB9080", port=state.config.fibs_web_port, description="FIBS BANK web banking frontend",
        state="STOPPED" if getattr(args, "no_fibs_web", False) else "STARTED", listener_tokens=("FIBS", "WEB9080", "CBSAWEB"),
        starter=lambda: serve_fibs_web9080(state),
        start_msgs=(f"IEE352I FIBSWEB9080 STARTED ON PORT {state.config.fibs_web_port} MODE={state.config.security_mode.upper()}",),
        stop_msgs=("IEE334I FIBSWEB9080 STOPPED",),
        pause_msgs=("IEE341I FIBSWEB9080 PAUSED",),
    ))
    mgr.register(ManagedService(
        "TCPIP", kind="logical", description="Communications Server master task", state="STARTED",
        start_msgs=("EZZ6035I TCPIP PROC STARTED",),
        stop_msgs=("EZZ6037I TCPIP PROC STOPPED",),
        pause_msgs=("EZZ6036I TCPIP PROC PAUSED",),
    ))

    for srv in servers:
        try:
            name = getattr(getattr(srv, 'RequestHandlerClass', None), '__name__', '')
        except Exception:
            name = ''
        if getattr(srv, 'server_address', None) == (state.config.host, state.config.tn3270_port):
            mgr.get("TN3270").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.uss_port):
            mgr.get("OMVS").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.ftp_port):
            mgr.get("FTPD").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.dashboard_port):
            mgr.get("GIBDASH").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.web_terminal_port):
            mgr.get("WEBTERM").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.db2_tcp_port):
            mgr.get("DB2DAS").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.db2_ws_port):
            mgr.get("DB2WS").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, getattr(state.config, "nje_port", 0)):
            mgr.get("NJE").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, getattr(state.config, "zvm_port", 0)):
            mgr.get("ZVM3270").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, getattr(state.config, "lennox_port", 0)):
            mgr.get("LENNOX").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.cbsa_api_port):
            mgr.get("APP8080").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.fibs_web_port):
            mgr.get("FIBSWEB9080").server = srv
        elif getattr(srv, 'server_address', None) == (state.config.host, state.config.welcome_port):
            mgr.get("WELCOME").server = srv


def _write_pid(pid_file: str | None) -> None:
    if not pid_file:
        return
    Path(pid_file).write_text(str(__import__('os').getpid()), encoding='utf-8')


def _remove_pid(pid_file: str | None) -> None:
    if not pid_file:
        return
    try:
        Path(pid_file).unlink(missing_ok=True)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Gibson mainframe simulator")
    parser.add_argument("--diagnose", action="store_true", help="Load state and show diagnostics")
    parser.add_argument("--secure", action="store_true", help="Start Gibson with the CIS-aligned secure simulator profile")
    parser.add_argument("--vuln", action="store_true", help="Start Gibson with the vulnerable training profile (default)")
    parser.add_argument("--ctf", action="store_true", help="Seed the Operation Summer Guest CTF (users, clue datasets, vulns) on startup")
    parser.add_argument("--command", help="Run a TSO command as a user and print output")
    parser.add_argument("--user", default="IBMUSER")
    parser.add_argument("--serve", action="store_true", help="Start VTAM/TSO/CICS and optional services")
    parser.add_argument("--with-ftp", action="store_true", help="Start shared-state FTP server")
    parser.add_argument("--no-uss", action="store_true", help="Do not start the dedicated USS terminal listener on port 2022")
    parser.add_argument("--no-db2", action="store_true", help="Do not start DB2DAS/WebSocket services with --serve")
    parser.add_argument("--no-dashboard", action="store_true", help="Do not start the Gibson web dashboard on port 8443")
    parser.add_argument("--with-web-terminal", action="store_true", help="Start browser terminal on port 8023")
    parser.add_argument("--no-web-terminal", action="store_true", help="Do not start browser terminal even if enabled by environment/controller")
    parser.add_argument("--web-terminal-port", type=int, default=None, help="Browser terminal port, default 8023")
    parser.add_argument("--with-app8080", action="store_true", help="Start unified Gibson app server on port 8080 for CBSA + DVCA + hack3270")
    parser.add_argument("--with-dvca", action="store_true", help="Enable DVCA CICS/web training subsystem")
    parser.add_argument("--with-dvca-web", action="store_true", help="Serve DVCA/hack3270 web frontend on unified 8080 app server")
    parser.add_argument("--dvca-vuln", action="store_true", help="Enable DVCA/hack3270 vulnerable training mode")
    parser.add_argument("--with-cbsa-api", action="store_true", help="Start CBSA z/OS Connect-style REST API on port 8080")
    parser.add_argument("--cbsa-api-port", type=int, default=None, help="CBSA REST API port, default 8080")
    parser.add_argument("--cbsa-vuln", action="store_true", help="Enable CBSA Security Training Mode when the CBSA API is started")
    parser.add_argument("--with-fibs-web", action="store_true", help="Start FIBS BANK web banking frontend on port 9080")
    parser.add_argument("--no-fibs-web", action="store_true", help="Do not start FIBS BANK web banking frontend")
    parser.add_argument("--fibs-web-port", type=int, default=None, help="FIBS BANK web banking port, default 9080")
    parser.add_argument("--with-welcome", action="store_true", help="Start Welcome to Gibson site on port 80")
    parser.add_argument("--no-welcome", action="store_true", help="Do not start Welcome to Gibson site")
    parser.add_argument("--welcome-port", type=int, default=None, help="Welcome to Gibson site port, default 80")
    parser.add_argument("--with-welcome8000", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-welcome8000", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--welcome8000-port", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--with-tn3270", action="store_true", help="Start dedicated TN3270 listener (default: on)")
    parser.add_argument("--no-tn3270", action="store_true", help="Do not start the dedicated TN3270 listener")
    parser.add_argument("--with-zvm", action="store_true", help="Start the dedicated EBCDIC z/VM 3270 logon listener (default: on)")
    parser.add_argument("--no-zvm", action="store_true", help="Do not start the z/VM 3270 logon listener on port 3023")
    parser.add_argument("--no-nje", action="store_true", help="Do not start the JES2 NJE/TCP listener on port 175")
    parser.add_argument("--no-lennox", action="store_true", help="Do not start the LENNOX Linux training system listener on port 2380")
    parser.add_argument("--master-console", action="store_true", help="Run an IBM-style master console in the current terminal")
    parser.add_argument("--ipl-prestart-console", action="store_true", help="Run the pre-service IPL reply sequence and persist MFA PIN, then exit")
    parser.add_argument("--ipl-mfa-pin", help="Non-interactively define the 4-digit simulator MFA PIN during --ipl-prestart-console")
    parser.add_argument("--ipl-hostname", help="Non-interactively set the simulated system hostname for R 05,NAME")
    parser.add_argument("--plain", action="store_true", help="Use plain text master console renderer")
    parser.add_argument("--curses", action="store_true", help="Use enhanced curses master console renderer when available")
    parser.add_argument("--no-color", action="store_true", help="Disable colour in enhanced master console")
    parser.add_argument("--demo-events", action="store_true", help="Generate demonstration events in enhanced master console")
    parser.add_argument("--poll-interval", type=float, default=30.0, help="Master console real-event polling interval in seconds")
    parser.add_argument("--split-console", action="store_true", help="Unavailable in v26.1; accepted with warning for compatibility")
    parser.add_argument("--logon-panel", action="store_true", help="Show the interactive TSO/E LOGON panel and default Command ===> ISPF")
    parser.add_argument("--pid-file", help="Write the running process ID to this file")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--ftp-port", type=int)
    parser.add_argument("--uss-port", type=int)
    parser.add_argument("--tn3270-port", type=int, help="Dedicated TN3270 listener port (default: 3270)")
    parser.add_argument("--db2-tcp-port", type=int)
    parser.add_argument("--db2-ws-port", type=int)
    parser.add_argument("--gacf", help="Path to GACF.DB")
    parser.add_argument("--sim-root", help="Simulator root, default ~/mfsim")
    args = parser.parse_args()

    state = build_state(args)

    if args.diagnose:
        print(security_mode_banner(state))
        print(f"Users loaded: {len(state.racf.users)}")
        print(f"GACF: {state.config.gacf_path}")
        print(f"Files root: {state.config.files_root}")
        print(f"Assets: {state.config.assets_dir}")
        try:
            from gibson.core.racf import HAS_PASSLIB
            print(f"GACF auth backend: passlib={'yes' if HAS_PASSLIB else 'no'}, pure-md5crypt=yes")
        except Exception:
            pass
        print("Loaded userids: " + ", ".join(sorted(state.racf.users.keys())))
        for issue in state.racf.issues:
            print(f"GACF issue line {issue.line_no}: {issue.code} {issue.detail}")
        return

    if args.command:
        print(TsoCommandProcessor(state, args.user).run(args.command))
        return

    if getattr(args, "ipl_prestart_console", False):
        ctl = __import__("gibson.apps.master_console", fromlist=["MasterConsoleController"]).MasterConsoleController(state, args.user)
        print(ctl.boot_text())
        supplied_pin = (getattr(args, "ipl_mfa_pin", None) or "").strip()
        if supplied_pin:
            host = (getattr(args, "ipl_hostname", None) or getattr(state.config, "default_system_hostname", "GIBSON") or "GIBSON").strip().upper()
            scripted_replies = ["R 01,CLPA", "R 02,U", "R 03,Y", f"R 04,{supplied_pin}", f"R 05,{host}", "R 06,SKIP"]
            for raw in scripted_replies:
                print(f"MASTER CONSOLE REPLY ===> {raw}")
                result = ctl.execute(raw)
                if result.text:
                    print(result.text)
                if result.action in {"quit", "shutdown"}:
                    print("GIBMCS011E IPL REPLY SEQUENCE CANCELLED")
                    raise SystemExit(4)
                if ctl._state_obj().get("boot_complete", False):
                    break
            if not ctl._state_obj().get("boot_complete", False):
                print("GIBMCS010E IPL REPLY SEQUENCE ENDED BEFORE COMPLETION")
                raise SystemExit(3)
            print("GIBMCS012I IPL REPLY SEQUENCE COMPLETE - SERVICES MAY START")
            return
        while not ctl._state_obj().get("boot_complete", False):
            try:
                raw = input("MASTER CONSOLE REPLY ===> ")
            except EOFError:
                print("GIBMCS010E IPL REPLY SEQUENCE ENDED BEFORE COMPLETION")
                raise SystemExit(3)
            result = ctl.execute(raw)
            if result.text:
                print(result.text)
            if result.action in {"quit", "shutdown"}:
                print("GIBMCS011E IPL REPLY SEQUENCE CANCELLED")
                raise SystemExit(4)
        print("GIBMCS012I IPL REPLY SEQUENCE COMPLETE - SERVICES MAY START")
        return

    def _run_master_console() -> str:
        use_plain = bool(getattr(args, "plain", False))
        use_curses = bool(getattr(args, "curses", False)) or not use_plain
        if use_curses and not use_plain:
            try:
                from gibson.apps.master_console_curses import CursesMasterConsoleUI
                if CursesMasterConsoleUI.available():
                    return CursesMasterConsoleUI(
                        state, userid=args.user,
                        no_color=bool(getattr(args, "no_color", False)),
                        demo_events=bool(getattr(args, "demo_events", False)),
                        poll_interval=float(getattr(args, "poll_interval", 30.0)),
                    ).run()
                print("GIBMCS001W Enhanced console unavailable; using plain console mode.")
            except Exception as exc:
                print(f"GIBMCS001W Enhanced console unavailable; using plain console mode. {exc}")
        return MasterConsoleUI(state, userid=args.user, poll_interval=float(getattr(args, "poll_interval", 30.0))).run()

    if args.master_console and not args.serve:
        _run_master_console()
        return

    if args.serve:
        from gibson.services.telnet_server import serve_telnet
        servers = []
        servers.append(serve_telnet(state))
        if state.config.security_mode == SECURE:
            args.no_uss = True
            args.with_ftp = False
        if not args.no_uss:
            from gibson.services.uss_server import serve_uss
            servers.append(serve_uss(state))
        if not getattr(args, "no_tn3270", False) and state.config.tn3270_port:
            from gibson.services.tn3270_server import serve_tn3270
            servers.append(serve_tn3270(state))
        if getattr(state.config, "zvm_port", 0) and not getattr(args, "no_zvm", False):
            from gibson.services.zvm3270_server import serve_zvm3270
            servers.append(serve_zvm3270(state))
        if getattr(state.config, "lennox_port", 0) and not getattr(args, "no_lennox", False):
            from gibson.services.lennox_server import serve_lennox
            servers.append(serve_lennox(state))
        if not args.no_dashboard:
            from gibson.services.dashboard import serve_dashboard
            servers.append(serve_dashboard(state))
        if getattr(state.config, "with_web_terminal", False):
            from gibson.services.web_terminal import serve_web_terminal
            servers.append(serve_web_terminal(state))
        if not args.no_db2:
            from gibson.services.db2_server import serve_db2das, serve_db2ws
            servers.append(serve_db2das(state))
            servers.append(serve_db2ws(state))
        if args.with_ftp:
            from gibson.services.ftp_server import serve_ftp
            servers.append(serve_ftp(state))
        if getattr(state.config, "nje_port", 0) and not getattr(args, "no_nje", False):
            from gibson.services.nje_server import serve_nje
            servers.append(serve_nje(state))
        if getattr(args, "with_cbsa_api", False) or getattr(args, "with_app8080", False) or getattr(args, "with_dvca_web", False):
            from gibson.services.cbsa_rest8080 import serve_cbsa_rest8080
            servers.append(serve_cbsa_rest8080(state))
        if getattr(state.config, "with_fibs_web", True) and not getattr(args, "no_fibs_web", False):
            from gibson.services.fibs_web9080 import serve_fibs_web9080
            servers.append(serve_fibs_web9080(state))
        if getattr(state.config, "welcome_enabled", True) and not (getattr(args, "no_welcome", False) or getattr(args, "no_welcome8000", False)):
            from gibson.services.welcome80 import serve_welcome
            servers.append(serve_welcome(state))
        _register_services(state, servers, args)
        _write_pid(args.pid_file)
        stop = False

        def _sig(_signum, _frame):
            nonlocal stop
            stop = True
        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
        try:
            if args.master_console:
                action = _run_master_console()
                if action in {"shutdown", "quit", "error"}:
                    stop = True
            else:
                print(security_mode_banner(state))
                print(f"Gibson VTAM/TSO/CICS listening on {state.config.host}:{state.config.port}")
                if not getattr(args, "no_tn3270", False) and state.config.tn3270_port:
                    print(f"Gibson TN3270 listener on {state.config.host}:{state.config.tn3270_port}")
                if getattr(state.config, "zvm_port", 0) and not getattr(args, "no_zvm", False):
                    print(f"Gibson z/VM EBCDIC 3270 logon listening on {state.config.host}:{state.config.zvm_port}")
                if not args.no_uss:
                    print(f"Gibson USS listener listening on {state.config.host}:{state.config.uss_port}")
                if not args.no_dashboard:
                    print(f"Gibson dashboard listening on {state.config.host}:{state.config.dashboard_port}")
                if getattr(state.config, "with_web_terminal", False):
                    print(f"Gibson browser terminal listening on {state.config.host}:{state.config.web_terminal_port}")
                if not args.no_db2:
                    print(f"DB2DAS simulator listening on {state.config.host}:{state.config.db2_tcp_port}")
                    print(f"DB2 WebSocket shell listening on {state.config.host}:{state.config.db2_ws_port}")
                if args.with_ftp:
                    print(f"GIBSONFTP listening on {state.config.host}:{state.config.ftp_port}")
                if getattr(args, "with_cbsa_api", False) or getattr(args, "with_app8080", False) or getattr(args, "with_dvca_web", False):
                    print(f"APP8080 CBSA/DVCA/hack3270 listening on {state.config.host}:{state.config.cbsa_api_port}")
                    print(f"CBSA Security Training Mode: {'ENABLED' if getattr(state.config, 'cbsa_vuln', False) else 'DISABLED'}")
                    print(f"DVCA/hack3270 Training Mode: {'ENABLED' if getattr(state.config, 'dvca_vuln', False) else 'DISABLED'}")
                if getattr(state.config, "with_fibs_web", True) and not getattr(args, "no_fibs_web", False):
                    print(f"FIBS BANK web banking listening on {state.config.host}:{state.config.fibs_web_port}")
                if getattr(state.config, "welcome_enabled", True) and not (getattr(args, "no_welcome", False) or getattr(args, "no_welcome8000", False)):
                    print(f"Gibson Welcome site listening on {state.config.host}:{state.config.welcome_port}")
                while not stop:
                    if getattr(state, "shutdown_requested", False):
                        stop = True
                        break
                    time.sleep(0.25)
        finally:
            state.service_manager.stop_all()
            for srv in servers:
                if hasattr(srv, "shutdown"):
                    try:
                        srv.shutdown()
                    except Exception:
                        pass
                if hasattr(srv, "server_close"):
                    try:
                        srv.server_close()
                    except Exception:
                        pass
            _remove_pid(args.pid_file)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
