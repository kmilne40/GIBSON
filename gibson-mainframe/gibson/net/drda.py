"""Minimal DRDA (Distributed Relational Database Architecture) server codec.

Lets Gibson's port-50000 listener answer like a real IBM DB2 for z/OS DRDA
server: it responds to a client EXCSAT (Exchange Server Attributes) with a
valid EXCSATRD reply, and to ACCSEC with ACCSECRD, so that nmap's
``drda-info`` / ``-sV`` detection identifies it as "IBM DB2 Database Server"
and extracts the version, platform, instance and external name.

Wire format (from the DDM / DRDA reference and Wireshark decoding, matching
nmap's nselib/drda.lua):

  DSS header (6 bytes):  length(2) 0xD0 format(1) correlation-id(2)
  DDM object:           length(2) codepoint(2) <parameters...>
  Parameter:            length(2) codepoint(2) <data>

String parameters (EXTNAM/SRVCLSNM/SRVNAM/SRVRLSLV/PRDID) are EBCDIC (cp037);
nmap reads them with getDataAsASCII() i.e. EBCDIC->ASCII.
"""
from __future__ import annotations

import struct
from typing import Optional

# ---- DDM / DRDA code points (subset; values per the DRDA reference) --------
CODEPNT = 0x000C
TYPDEFNAM = 0x002F
TYPDEFOVR = 0x0035
EXCSAT = 0x1041
ACCSEC = 0x106D
SECCHK = 0x106E
PRDID = 0x112E
SRVCLSNM = 0x1147
SVRCOD = 0x1149
SRVRLSLV = 0x115A
EXTNAM = 0x115E
SRVNAM = 0x116D
USRID = 0x11A0
PASSWORD = 0x11A1
SECMEC = 0x11A2
SECCHKCD = 0x11A4
SECCHKRM = 0x1219
MGRLVLLS = 0x1404
EXCSATRD = 0x1443
ACCSECRD = 0x14AC
ACCRDB = 0x2001
RDBNAM = 0x2110
ACCRDBRM = 0x2201
RDBNFNRM = 0x2211
RDBATHRM = 0x22CB

# Severity codes (SVRCOD)
SVRCOD_INFO = 0x0000
SVRCOD_ERROR = 0x0008
# Security check codes (SECCHKCD): 0x00 = successful
SECCHKCD_OK = 0x00

# Security mechanism: user id + password
SECMEC_USRIDPWD = 0x0003

_MAGIC = 0xD0
_RPYDSS = 0x02          # reply DSS (low nibble = DSS type 2)


def _ebcdic(text: str) -> bytes:
    try:
        return text.encode("cp037")
    except Exception:
        return text.encode("ascii", errors="replace")


def _param(codepoint: int, data: bytes) -> bytes:
    """A DDM parameter: length(2) codepoint(2) data; length includes header."""
    return struct.pack(">HH", len(data) + 4, codepoint) + data


def _dss(ddm: bytes, corr: int = 1, fmt: int = _RPYDSS) -> bytes:
    """Wrap a DDM object in a DSS reply header."""
    return struct.pack(">HBBH", len(ddm) + 6, _MAGIC, fmt, corr) + ddm


def parse_request_codepoint(data: bytes) -> Optional[int]:
    """Return the DDM code point of the first request in a DRDA buffer, or None.

    Tolerant: requires only the 6-byte DSS header plus a 4-byte DDM header.
    """
    if not data or len(data) < 10:
        return None
    if data[2] != _MAGIC:
        return None
    try:
        # DDM codepoint sits at offset 8 (after 6-byte DSS + 2-byte DDM length)
        return struct.unpack(">H", data[8:10])[0]
    except Exception:
        return None


def request_correlator(data: bytes) -> int:
    if data and len(data) >= 6 and data[2] == _MAGIC:
        try:
            return struct.unpack(">H", data[4:6])[0]
        except Exception:
            return 1
    return 1


def get_request_param(data: bytes, codepoint: int) -> Optional[bytes]:
    """Extract the data bytes of a parameter (by code point) from the first DDM
    in a DRDA request buffer.  Returns None if absent or unparyseable."""
    try:
        if not data or len(data) < 10 or data[2] != _MAGIC:
            return None
        dss_len = struct.unpack(">H", data[0:2])[0]
        ddm = data[6:dss_len]
        ddm_len = struct.unpack(">H", ddm[0:2])[0]
        off = 4
        while off + 4 <= ddm_len:
            plen = struct.unpack(">H", ddm[off:off + 2])[0]
            pcp = struct.unpack(">H", ddm[off + 2:off + 4])[0]
            if plen < 4:
                break
            if pcp == codepoint:
                return ddm[off + 4:off + plen]
            off += plen
    except Exception:
        return None
    return None


def build_excsatrd(*, extnam: str, srvclsnm: str, srvnam: str, srvrlslv: str,
                   mgrlvlls: bytes = b"", corr: int = 1) -> bytes:
    """Build an EXCSATRD reply object wrapped in a DSS."""
    if not mgrlvlls:
        # A realistic z/OS server manager-level set (AGENT/SQLAM/RDB/SECMGR/
        # CMNTCPIP/CCSIDMGR levels).  nmap does not parse the contents.
        mgrlvlls = bytes.fromhex(
            "1403000724070008240f000814400008147400081c0008146c0008")
    params = b""
    params += _param(EXTNAM, _ebcdic(extnam))
    params += _param(MGRLVLLS, mgrlvlls)
    params += _param(SRVCLSNM, _ebcdic(srvclsnm))
    params += _param(SRVNAM, _ebcdic(srvnam))
    params += _param(SRVRLSLV, _ebcdic(srvrlslv))
    ddm = struct.pack(">HH", len(params) + 4, EXCSATRD) + params
    return _dss(ddm, corr=corr)


def build_accsecrd(*, secmec: int = SECMEC_USRIDPWD, corr: int = 1) -> bytes:
    """Build an ACCSECRD reply advertising a security mechanism (USRID/PWD)."""
    params = _param(SECMEC, struct.pack(">H", secmec))
    ddm = struct.pack(">HH", len(params) + 4, ACCSECRD) + params
    return _dss(ddm, corr=corr)


def build_secchkrm(*, secchkcd: int = SECCHKCD_OK, corr: int = 1) -> bytes:
    """Build a SECCHKRM (security-check reply message).  secchkcd 0 = accepted."""
    params = _param(SVRCOD, struct.pack(">H", SVRCOD_INFO))
    params += _param(SECCHKCD, bytes([secchkcd & 0xFF]))
    ddm = struct.pack(">HH", len(params) + 4, SECCHKRM) + params
    return _dss(ddm, corr=corr)


def build_accrdbrm(*, prdid: str, corr: int = 1) -> bytes:
    """Build an ACCRDBRM (access-RDB reply message) - successful DB connect."""
    params = _param(SVRCOD, struct.pack(">H", SVRCOD_INFO))
    params += _param(PRDID, _ebcdic(prdid))
    params += _param(TYPDEFNAM, _ebcdic("QTDSQLASC"))   # ASCII SQL type def
    ddm = struct.pack(">HH", len(params) + 4, ACCRDBRM) + params
    return _dss(ddm, corr=corr)


def build_rdbnfnrm(*, rdbnam: bytes, corr: int = 1) -> bytes:
    """Build an RDBNFNRM (RDB-not-found reply message)."""
    params = _param(SVRCOD, struct.pack(">H", SVRCOD_ERROR))
    params += _param(RDBNAM, rdbnam)
    ddm = struct.pack(">HH", len(params) + 4, RDBNFNRM) + params
    return _dss(ddm, corr=corr)


def build_db2_zos_excsatrd(state, corr: int = 1) -> bytes:
    """Build a DB2-for-z/OS EXCSATRD from Gibson's DB2 system info."""
    from gibson.apps.db2_sim import SYSTEM_INFO
    ver = str(SYSTEM_INFO.get("VERSION", "12.1"))
    # Map "12.1" -> DSN release level "DSN12015" (DB2 12 for z/OS).
    major = ver.split(".")[0].rjust(2, "0")
    srvrlslv = f"DSN{major}015"
    ssid = SYSTEM_INFO.get("SUBSYSTEM", "DB2A")
    location = SYSTEM_INFO.get("LOCATION", "GIBSONDB2")
    return build_excsatrd(
        extnam=f"{location} DDF {ssid}",
        srvclsnm="QDB2/zOS",        # contains "DB2" -> nmap: IBM DB2 Database Server
        srvnam=location,
        srvrlslv=srvrlslv,
        corr=corr,
    )


def respond(data: bytes, state) -> Optional[bytes]:
    """Given an inbound DRDA request buffer, return the bytes to send back.

    Implements the server side of the DB2 connect handshake:
      EXCSAT  -> EXCSATRD   (exchange server attributes)
      ACCSEC  -> ACCSECRD   (advertise USRID/PWD security)
      SECCHK  -> SECCHKRM   (validate credentials via RACF)
      ACCRDB  -> ACCRDBRM   (open the database if the RDB name matches)
                 RDBNFNRM   (if the requested RDB is not this location)

    Returns None if the buffer is not recognisable DRDA (caller may fall back
    to the DB2 DAS text response).
    """
    cp = parse_request_codepoint(data)
    if cp is None:
        return None
    corr = request_correlator(data)
    if cp == EXCSAT:
        return build_db2_zos_excsatrd(state, corr=corr)
    if cp == ACCSEC:
        return build_accsecrd(corr=corr)
    if cp == SECCHK:
        # Validate user id / password against RACF where possible; a real DB2
        # accepts (SECCHKCD=0) and lets RDB-level authority decide afterwards.
        secchkcd = SECCHKCD_OK
        try:
            uid = get_request_param(data, USRID)
            pwd = get_request_param(data, PASSWORD)
            if uid is not None and pwd is not None:
                userid = uid.decode("cp037").strip()
                password = pwd.decode("cp037").strip()
                if userid and not state.racf.verify_password(userid, password):
                    secchkcd = 0x0F          # 0x0F = password invalid
                try:
                    state.record_security_event(
                        userid or "UNKNOWN", "DB2 DRDA SECCHK",
                        f"SECCHKCD={secchkcd:02X}", service="DB2",
                        result="SUCCESS" if secchkcd == 0 else "FAILURE", terminal="DRDA")
                except Exception:
                    pass
        except Exception:
            secchkcd = SECCHKCD_OK
        return build_secchkrm(secchkcd=secchkcd, corr=corr)
    if cp == ACCRDB:
        from gibson.apps.db2_sim import SYSTEM_INFO
        location = SYSTEM_INFO.get("LOCATION", "GIBSONDB2")
        rdb = get_request_param(data, RDBNAM)
        rdbname = ""
        if rdb is not None:
            try:
                rdbname = rdb.decode("cp037").strip()
            except Exception:
                rdbname = ""
        if rdbname and rdbname.upper() != location.upper():
            return build_rdbnfnrm(rdbnam=rdb, corr=corr)
        ver = str(SYSTEM_INFO.get("VERSION", "12.1")).split(".")[0].rjust(2, "0")
        return build_accrdbrm(prdid=f"DSN{ver}015", corr=corr)
    # Unknown but valid-looking DRDA: still answer with server attributes so a
    # version probe gets a useful reply.
    return build_db2_zos_excsatrd(state, corr=corr)
