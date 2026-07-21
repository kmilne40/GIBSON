from pathlib import Path
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tso import TsoCommandProcessor


def make_state(tmp_path: Path) -> GibsonState:
    cfg = GibsonConfig(sim_root=tmp_path, files_root=tmp_path/"f", commands_dir=tmp_path/"f"/"commands", transfer_root=tmp_path/"transfers", gacf_path=tmp_path/"GACF.DB")
    cfg.ensure()
    cfg.gacf_path.write_text("IBMUSER:SYS1:SPECIAL:OMVS:SYS1\nGUEST:SYS1:NONE:NOOMVS:STUDENT\n")
    return GibsonState.create(cfg)


def test_ikjtso_passwordpreprompt_and_setropts_inactive(tmp_path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, "IBMUSER")
    guest = TsoCommandProcessor(st, "GUEST")
    assert "PASSWORDPREPROMPT ENABLED" in admin.run("SET IKJTSO PASSWORDPREPROMPT(ON)")
    assert "PASSWORDPREPROMPT(ON)" in admin.run("D IKJTSO")
    assert "PASSWORDPREPROMPT(ON)" in admin.run("PARMLIB DISPLAY IKJTSOxx")
    assert "INSUFFICIENT ACCESS AUTHORITY" in guest.run("SET IKJTSO PASSWORDPREPROMPT(OFF)")
    assert "INACTIVE INTERVAL IS NOW 90 DAYS" in admin.run("SETROPTS INACTIVE(90)")
    assert "INACTIVE         : 90" in admin.run("SETROPTS LIST")
    assert "INACTIVE PROCESSING IS NOW DISABLED" in admin.run("SETROPTS NOINACTIVE")
    assert "NOINACTIVE" in admin.run("SETROPTS LIST")
    assert "PASSWORDPREPROMPT" in admin.run("HELP PASSWORDPREPROMPT")


def test_cics_expanded_sit_and_zsecure_reflects_state(tmp_path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, "IBMUSER")
    assert "CICSUSER" in admin.run("LISTUSER CICSUSER ALL")
    assert "PROTECTED" in admin.run("LISTUSER CICSUSER ALL")
    before = admin.run("CICS DISPLAY SIT")
    assert "XTST" in before and "XDCT" in before and "XPPT" in before
    out = admin.run("CICS SET SIT SEC(NO) XTST(NO) XDCT(NO) XPPT(NO) DFLTUSER(CICSUSER)")
    assert "SEC SET TO NO" in out and "XTST SET TO NO" in out
    after = admin.run("CICS DISPLAY SIT")
    assert "SEC      : NO" in after and "XTST     : NO" in after and "XDCT     : NO" in after and "XPPT     : NO" in after
    zsec = admin.run("ZSEC CICS")
    assert "FINDING: SEC NOT ACTIVE" in zsec and "FINDING: XTST NOT ACTIVE" in zsec
    assert "CICS" in admin.run("HELP CICS") and "CEMT" in admin.run("HELP CEMT") and "CEDA" in admin.run("HELP CEDA")


def test_db2_tls_catalog_state_and_zsecure(tmp_path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, "IBMUSER")
    assert "TLS SET TO OFF" in admin.run("DB2 SET DDF TLS(OFF)")
    assert "TLS=OFF" in admin.run("DB2 DISPLAY DDF")
    assert "DDF TLS=OFF" in admin.run("ZSEC DB2")
    assert "FINDING: DDF TLS WEAK" in admin.run("ZSEC DB2")
    assert "PUBLIC REVOKED" in admin.run("DB2 REVOKE SELECT ON SYSIBM.SYSUSERAUTH FROM PUBLIC")
    assert "PUBLIC=NO" in admin.run("DB2 DISPLAY SECURITY")
    assert "SECADMIN GRANTED" in admin.run("DB2 GRANT SELECT ON SYSIBM.SYSUSERAUTH TO SECADMIN")
    assert "SECADMIN" in admin.run("DB2 DISPLAY SECURITY")


def test_started_stdata_racdcert_and_rare_events(tmp_path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, "IBMUSER")
    assert "DEFINED" in admin.run("RDEFINE STARTED CICS*.CICS STDATA(USER(CICSUSER) GROUP(STCGROUP) TRUSTED(NO))")
    rlist = admin.run("RLIST STARTED CICS*.CICS ALL")
    assert "STDATA INFORMATION" in rlist and "USER=CICSUSER" in rlist and "GROUP=STCGROUP" in rlist and "TRUSTED=NO" in rlist
    assert "CICSUSER" in admin.run("D STARTED")
    assert "KEY RING WEBRING CREATED" in admin.run("RACDCERT ID(IBMUSER) ADDRING(WEBRING)")
    assert "CERTIFICATE WEBTLS ADDED" in admin.run("RACDCERT ID(IBMUSER) ADD('IBMUSER.CERT') WITHLABEL('WEBTLS')")
    assert "CONNECTED TO KEY RING WEBRING" in admin.run("RACDCERT ID(IBMUSER) CONNECT(ID(IBMUSER) LABEL('WEBTLS') RING(WEBRING))")
    assert "WEBTLS" in admin.run("RACDCERT ID(IBMUSER) LISTRING(WEBRING)")
    assert "IBMUSER.CERT" in admin.run("RACDCERT ID(IBMUSER) LIST")
    rare = admin.run("D SECURITY,RARE")
    assert "RACDCERT" in rare or "STARTED" in rare
    assert "RACDCERT" in admin.run("ZSEC RACDCERT")
    assert "RACDCERT" in admin.run("ZSEC RARE")


def test_adduser_altuser_phrase_nooidcard_and_help(tmp_path):
    st = make_state(tmp_path)
    admin = TsoCommandProcessor(st, "IBMUSER")
    out = admin.run("ADDUSER SVC001 NOPASSWORD NOPHRASE NOOIDCARD PHRASE('do not store me')")
    assert "USER SVC001 DEFINED" in out and "PROTECTED" in out and "MATERIAL PROTECTED" in out
    listed = admin.run("LISTUSER SVC001 ALL")
    assert "PROTECTED" in listed and "PHRASE=DEFINED" in listed and "NOOIDCARD=YES" in listed
    alt = admin.run("ALTUSER SVC001 NOPHRASE")
    assert "PASSWORD PHRASE REMOVED" in alt
    assert "PHRASE=NONE" in admin.run("LISTUSER SVC001 ALL")
    for cmd in ["HELP IKJTSO", "HELP INACTIVE", "DB2 ?", "RACDCERT ?", "HELP SECURITY", "ZSEC ?"]:
        out = admin.run(cmd)
        assert "HELP" in out or "ZSECURE" in out or "SYNTAX" in out
