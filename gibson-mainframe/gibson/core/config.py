from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Set

@dataclass
class GibsonConfig:
    host: str = "0.0.0.0"
    port: int = 23
    uss_port: int = 2022
    tn3270_port: int = 3270
    zvm_port: int = 3023
    lennox_port: int = 2380
    ftp_port: int = 21
    db2_tcp_port: int = 50000
    db2_ws_port: int = 50001
    nje_port: int = 175
    nje_tls_port: int = 2252
    dashboard_port: int = 8443
    web_terminal_port: int = 8023
    cbsa_api_port: int = 8080
    fibs_web_port: int = 9080
    # Welcome site is intentionally on port 80.
    welcome_port: int = 80
    welcome_enabled: bool = True
    default_system_hostname: str = "GIBSON"
    geo_enabled: bool = True
    geo_provider: str = "fixture"
    geo_online_enabled: bool = True
    geo_provider_timeout: float = 10.0
    geo_cache_enabled: bool = True
    cti_enabled: bool = True
    cti_online_enabled: bool = False
    cti_local_feed_enabled: bool = True
    cti_dashboard_enabled: bool = True
    cti_master_console_alerts_enabled: bool = True
    trusted_proxy_enabled: bool = False
    trusted_proxy_cidrs: str = ""
    geo_precision: str = "city"
    geo_latlon_rounding: int = 3
    identity_labs_enabled: bool = True
    passticket_labs_enabled: bool = True
    mfa_labs_enabled: bool = True
    passticket_lab_vulnerable_mode: bool = True
    mfa_lab_vulnerable_mode: bool = True
    zvm_lab_vulnerable_mode: bool = True   # True: unknown z/VM userids auto-logon (transient class G)
    zvm_jea_lab_vulnerable_mode: bool = True  # True: LINUX01 over-granted classes B,C,E (privilege-creep lab)
    endevor_lab_vulnerable_mode: bool = True  # True: Endevor browse skips the ESI scope check (broken access control lab)
    endevor_sod_lab_vulnerable_mode: bool = True  # True: package creator can self-approve (separation-of-duties bypass lab)
    ims_otma_lab_vulnerable_mode: bool = True  # True: IMS Connect /SECURE OTMA NONE, no TIMS/CIMS/RIMS (transaction/command injection lab)
    mfa_require_context_for_passticket: bool = False
    identity_dashboard_alerts_enabled: bool = True
    identity_master_console_alerts_enabled: bool = True
    with_fibs_web: bool = True
    rest_port: int = 0  # compatibility only; legacy 8082 REST service remains removed
    cbsa_vuln: bool = False
    dvca_vuln: bool = True
    with_dvca_web: bool = False
    with_web_terminal: bool = False
    suppress_localhost_scan: bool = True
    sim_root: Path = Path("~/mfsim").expanduser()
    files_root: Path = Path("~/mfsim/f").expanduser()
    commands_dir: Path = Path("~/mfsim/f/commands").expanduser()
    transfer_root: Path = Path("~/mfsim/transfers").expanduser()
    gacf_path: Path = Path("~/mfsim/GACF.DB").expanduser()
    assets_dir: Path = Path(__file__).resolve().parents[1] / "assets"
    realistic_cics_auth: bool = False
    rexx_extended: bool = True
    jcl_extended: bool = True
    indfile_mode: str = "browser"
    transmit_receive: bool = True
    console_security_audit: bool = False
    ispf_global_jump: bool = True
    sdsf_apf_popup: bool = True
    strict_tso_ptkt: bool = False
    dynamic_prog_support: bool = True
    healthchecker: bool = True
    surrogat_lab: bool = True
    security_mode: str = "vuln"
    split_console: bool = False
    logon_panel: bool = False
    mfa_required: bool = False
    secure_disable_plain_uss: bool = False
    secure_disable_plain_ftp: bool = False
    protectall_fail: bool = False
    password_interval: int = 30
    password_history: int = 0
    password_minchange: int = 0
    password_warning: int = 0
    password_revoke: int = 0
    password_algorithm: str = "LEGACY"
    active_classes: Set[str] = None  # type: ignore
    raclist_classes: Set[str] = None  # type: ignore
    audit_classes: Set[str] = None  # type: ignore
    racf_attributes: Set[str] = None  # type: ignore

    @classmethod
    def from_env(cls) -> "GibsonConfig":
        sim_root = Path(os.getenv("GIBSON_SIM_ROOT", "~/mfsim")).expanduser()
        return cls(
            host=os.getenv("GIBSON_HOST", "0.0.0.0"),
            port=int(os.getenv("GIBSON_PORT", "23")),
            ftp_port=int(os.getenv("GIBSON_FTP_PORT", "21")),
            uss_port=int(os.getenv("GIBSON_USS_PORT", "2022")),
            tn3270_port=int(os.getenv("GIBSON_TN3270_PORT", "3270")),
            zvm_port=int(os.getenv("GIBSON_ZVM_PORT", "3023")),
            lennox_port=int(os.getenv("GIBSON_LENNOX_PORT", "2380")),
            db2_tcp_port=int(os.getenv("GIBSON_DB2_TCP_PORT", "50000")),
            db2_ws_port=int(os.getenv("GIBSON_DB2_WS_PORT", "50001")),
            nje_port=int(os.getenv("GIBSON_NJE_PORT", "175")),
            nje_tls_port=int(os.getenv("GIBSON_NJE_TLS_PORT", "2252")),
            dashboard_port=int(os.getenv("GIBSON_DASHBOARD_PORT", "8443")),
            web_terminal_port=int(os.getenv("GIBSON_WEB_TERMINAL_PORT", "8023")),
            cbsa_api_port=int(os.getenv("GIBSON_CBSA_API_PORT", "8080")),
            fibs_web_port=int(os.getenv("GIBSON_FIBS_WEB_PORT", "9080")),
            welcome_port=int(os.getenv("GIBSON_WELCOME_PORT", os.getenv("GIBSON_WELCOME80_PORT", "80"))),
            welcome_enabled=os.getenv("GIBSON_WELCOME_ENABLED", os.getenv("GIBSON_WELCOME80_ENABLED", "1")) in ("1", "true", "TRUE"),
            default_system_hostname=os.getenv("GIBSON_SYSTEM_HOSTNAME", "GIBSON").strip().upper() or "GIBSON",
            geo_enabled=os.getenv("GIBSON_GEO_ENABLED", "1") in ("1", "true", "TRUE"),
            geo_provider=os.getenv("GIBSON_GEO_PROVIDER", "fixture").strip().lower() or "fixture",
            geo_online_enabled=os.getenv("GIBSON_GEO_ONLINE_ENABLED", "1") in ("1", "true", "TRUE"),
            geo_provider_timeout=float(os.getenv("GIBSON_GEO_PROVIDER_TIMEOUT", "10")),
            geo_cache_enabled=os.getenv("GIBSON_GEO_CACHE_ENABLED", "1") in ("1", "true", "TRUE"),
            cti_enabled=os.getenv("GIBSON_CTI_ENABLED", "1") in ("1", "true", "TRUE"),
            cti_online_enabled=os.getenv("GIBSON_CTI_ONLINE_ENABLED", "0") in ("1", "true", "TRUE"),
            cti_local_feed_enabled=os.getenv("GIBSON_CTI_LOCAL_FEED_ENABLED", "1") in ("1", "true", "TRUE"),
            cti_dashboard_enabled=os.getenv("GIBSON_CTI_DASHBOARD_ENABLED", "1") in ("1", "true", "TRUE"),
            cti_master_console_alerts_enabled=os.getenv("GIBSON_CTI_CONSOLE_ALERTS", "1") in ("1", "true", "TRUE"),
            trusted_proxy_enabled=os.getenv("GIBSON_TRUSTED_PROXY_ENABLED", "0") in ("1", "true", "TRUE"),
            trusted_proxy_cidrs=os.getenv("GIBSON_TRUSTED_PROXY_CIDRS", ""),
            geo_precision=os.getenv("GIBSON_GEO_PRECISION", "city"),
            geo_latlon_rounding=int(os.getenv("GIBSON_GEO_LATLON_ROUNDING", "3")),
            identity_labs_enabled=os.getenv("GIBSON_IDENTITY_LABS_ENABLED", "1") in ("1", "true", "TRUE"),
            passticket_labs_enabled=os.getenv("GIBSON_PASSTICKET_LABS_ENABLED", "1") in ("1", "true", "TRUE"),
            mfa_labs_enabled=os.getenv("GIBSON_MFA_LABS_ENABLED", "1") in ("1", "true", "TRUE"),
            passticket_lab_vulnerable_mode=os.getenv("GIBSON_PASSTICKET_LAB_VULNERABLE", "1") in ("1", "true", "TRUE"),
            mfa_lab_vulnerable_mode=os.getenv("GIBSON_MFA_LAB_VULNERABLE", "1") in ("1", "true", "TRUE"),
            zvm_lab_vulnerable_mode=os.getenv("GIBSON_ZVM_LAB_VULNERABLE", "1") in ("1", "true", "TRUE"),
            zvm_jea_lab_vulnerable_mode=os.getenv("GIBSON_ZVM_JEA_VULNERABLE", "1") in ("1", "true", "TRUE"),
            endevor_lab_vulnerable_mode=os.getenv("GIBSON_ENDEVOR_LAB_VULNERABLE", "1") in ("1", "true", "TRUE"),
            endevor_sod_lab_vulnerable_mode=os.getenv("GIBSON_ENDEVOR_SOD_VULNERABLE", "1") in ("1", "true", "TRUE"),
            ims_otma_lab_vulnerable_mode=os.getenv("GIBSON_IMS_OTMA_VULNERABLE", "1") in ("1", "true", "TRUE"),
            mfa_require_context_for_passticket=os.getenv("GIBSON_MFA_CONTEXT_FOR_PTKT", "0") in ("1", "true", "TRUE"),
            identity_dashboard_alerts_enabled=os.getenv("GIBSON_IDENTITY_DASHBOARD_ALERTS", "1") in ("1", "true", "TRUE"),
            identity_master_console_alerts_enabled=os.getenv("GIBSON_IDENTITY_CONSOLE_ALERTS", "1") in ("1", "true", "TRUE"),
            with_fibs_web=os.getenv("GIBSON_WITH_FIBS_WEB", "1") in ("1", "true", "TRUE"),
            rest_port=0,
            cbsa_vuln=os.getenv("GIBSON_CBSA_VULN", "0") in ("1", "true", "TRUE"),
            dvca_vuln=os.getenv("GIBSON_DVCA_VULN", "1") in ("1", "true", "TRUE"),
            with_dvca_web=os.getenv("GIBSON_WITH_DVCA_WEB", "0") in ("1", "true", "TRUE"),
            with_web_terminal=os.getenv("GIBSON_WITH_WEB_TERMINAL", "0") in ("1", "true", "TRUE"),
            suppress_localhost_scan=os.getenv("GIBSON_SUPPRESS_LOCALHOST_SCAN", "1") in ("1", "true", "TRUE"),
            sim_root=sim_root,
            files_root=Path(os.getenv("GIBSON_FILES_ROOT", str(sim_root / "f"))).expanduser(),
            commands_dir=Path(os.getenv("GIBSON_COMMANDS_DIR", str(sim_root / "f" / "commands"))).expanduser(),
            transfer_root=Path(os.getenv("GIBSON_TRANSFER_ROOT", str(sim_root / "transfers"))).expanduser(),
            gacf_path=Path(os.getenv("GIBSON_GACF", str(sim_root / "GACF.DB"))).expanduser(),
            realistic_cics_auth=os.getenv("GIBSON_CICS_REALISTIC", "0") in ("1", "true", "TRUE"),
            rexx_extended=os.getenv("GIBSON_REXX_EXTENDED", "1") in ("1", "true", "TRUE"),
            jcl_extended=os.getenv("GIBSON_JCL_EXTENDED", "1") in ("1", "true", "TRUE"),
            indfile_mode=os.getenv("GIBSON_INDFILE_MODE", "browser").strip().lower() or "off",
            transmit_receive=os.getenv("GIBSON_TRANSMIT_RECEIVE", "1") in ("1", "true", "TRUE"),
            console_security_audit=os.getenv("GIBSON_CONSOLE_SECURITY_AUDIT", "0") in ("1", "true", "TRUE"),
            ispf_global_jump=os.getenv("GIBSON_ISPF_GLOBAL_JUMP", "1") in ("1", "true", "TRUE"),
            sdsf_apf_popup=os.getenv("GIBSON_SDSF_APF_POPUP", "1") in ("1", "true", "TRUE"),
            strict_tso_ptkt=os.getenv("GIBSON_STRICT_TSO_PTKT", "0") in ("1", "true", "TRUE"),
            dynamic_prog_support=os.getenv("GIBSON_DYNAMIC_PROG_SUPPORT", "1") in ("1", "true", "TRUE"),
            healthchecker=os.getenv("GIBSON_HEALTHCHECKER", "1") in ("1", "true", "TRUE"),
            surrogat_lab=os.getenv("GIBSON_SURROGAT_LAB", "1") in ("1", "true", "TRUE"),
            security_mode=os.getenv("GIBSON_SECURITY_MODE", "vuln").strip().lower() or "vuln",
            split_console=os.getenv("GIBSON_SPLIT_CONSOLE", "0") in ("1", "true", "TRUE"),
            logon_panel=os.getenv("GIBSON_LOGON_PANEL", "0") in ("1", "true", "TRUE"),
        )

    def __post_init__(self) -> None:
        if self.active_classes is None:
            self.active_classes = set()
        if self.raclist_classes is None:
            self.raclist_classes = set()
        if self.audit_classes is None:
            self.audit_classes = set()
        if self.racf_attributes is None:
            self.racf_attributes = set()

    def ensure(self) -> None:
        self.sim_root.mkdir(parents=True, exist_ok=True)
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        self.transfer_root.mkdir(parents=True, exist_ok=True)
