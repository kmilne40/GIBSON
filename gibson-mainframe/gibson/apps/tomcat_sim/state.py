from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import hashlib
import re
import uuid


@dataclass
class TomcatDeployment:
    context: str
    filename: str
    size: int
    sha256: str
    uploaded_by: str
    uploaded_at: str
    status: str = "running"
    display_name: str = ""
    requested_port: int = 31337
    raw: bytes = b""


@dataclass
class TomcatSession:
    session_id: int
    context: str
    user: str
    port: int
    created_at: str
    expires_at: str
    active: bool = True
    commands: list[dict[str, str]] = field(default_factory=list)


@dataclass
class TomcatSimState:
    deployments: dict[str, TomcatDeployment] = field(default_factory=dict)
    sessions: dict[int, TomcatSession] = field(default_factory=dict)
    next_session_id: int = 1
    listener_started: bool = False
    listener_server: Any = None

    def seed(self) -> None:
        for ctx, name in [("/", "ROOT"), ("/docs", "docs"), ("/examples", "examples")]:
            self.deployments.setdefault(ctx, TomcatDeployment(ctx, name, 0, "", "SYSTEM", "IPL", display_name=name, requested_port=0))


_CONTEXT_RE = re.compile(r"^/[A-Za-z0-9_.-]{1,64}$")


def get_state(state: Any) -> TomcatSimState:
    sim = getattr(state, "tomcat_sim_state", None)
    if sim is None:
        sim = TomcatSimState()
        sim.seed()
        state.tomcat_sim_state = sim
    return sim


def safe_context(path: str | None) -> str | None:
    p = (path or "").strip()
    if not p:
        return None
    if not p.startswith("/"):
        p = "/" + p
    if p in {"/", "/docs", "/examples"}:
        return p
    if not _CONTEXT_RE.match(p):
        return None
    if ".." in p or "//" in p or "\\" in p:
        return None
    return p


def safe_filename(name: str | None) -> str | None:
    n = (name or "upload.war").split("/")[-1].split("\\")[-1].strip()
    if not n or len(n) > 128:
        return None
    if not n.lower().endswith(".war"):
        return None
    if any(ch in n for ch in "<>:\x00"):
        return None
    return n


def deploy_war(state: Any, context: str, filename: str, data: bytes, user: str, *, update: bool = False) -> tuple[bool, str, TomcatDeployment | None]:
    from .config import get_config
    cfg = get_config(state)
    sim = get_state(state)
    ctx = safe_context(context)
    if not ctx:
        return False, "FAIL - Invalid context path", None
    if ctx in {"/", "/docs", "/examples"}:
        return False, "FAIL - Reserved context path", None
    fn = safe_filename(filename)
    if not fn:
        return False, "FAIL - Only .war files are accepted", None
    body = data or b""
    if len(body) <= 0:
        return False, "FAIL - No WAR file content supplied", None
    if len(body) > cfg.max_war_size:
        return False, f"FAIL - WAR exceeds maximum size {cfg.max_war_size}", None
    if ctx in sim.deployments and not update:
        return False, f"FAIL - Application already exists at path [{ctx}]", None
    digest = hashlib.sha256(body).hexdigest()
    requested_port = cfg.pseudo_bind_port if b"31337" in body or "shell" in fn.lower() or "shell" in ctx.lower() else cfg.pseudo_bind_port
    raw = body if cfg.allow_raw_war_readback else b""
    dep = TomcatDeployment(
        context=ctx,
        filename=fn,
        size=len(body),
        sha256=digest,
        uploaded_by=(user or "tomcat"),
        uploaded_at=datetime.now().isoformat(timespec="seconds"),
        status="running",
        display_name=fn[:-4],
        requested_port=int(requested_port),
        raw=raw,
    )
    sim.deployments[ctx] = dep
    return True, f"OK - Deployed application at context path [{ctx}]", dep


def undeploy(state: Any, context: str) -> tuple[bool, str]:
    sim = get_state(state)
    ctx = safe_context(context)
    if not ctx or ctx in {"/", "/docs", "/examples"}:
        return False, "FAIL - Invalid or reserved context path"
    if ctx not in sim.deployments:
        return False, f"FAIL - No context exists named [{ctx}]"
    del sim.deployments[ctx]
    # close sessions for this context
    for sess in sim.sessions.values():
        if sess.context == ctx:
            sess.active = False
    return True, f"OK - Undeployed application at context path [{ctx}]"


def create_session(state: Any, context: str, user: str = "tomcat") -> TomcatSession:
    from .config import get_config
    cfg = get_config(state)
    sim = get_state(state)
    # Reuse active session for deterministic labs.
    for sess in sim.sessions.values():
        if sess.context == context and sess.active:
            return sess
    sid = sim.next_session_id
    sim.next_session_id += 1
    now = datetime.now()
    sess = TomcatSession(
        session_id=sid,
        context=context,
        user=user or "tomcat",
        port=int(cfg.pseudo_bind_port),
        created_at=now.isoformat(timespec="seconds"),
        expires_at=(now + timedelta(minutes=20)).isoformat(timespec="seconds"),
    )
    sim.sessions[sid] = sess
    return sess


def active_sessions(state: Any) -> list[TomcatSession]:
    sim = get_state(state)
    return [s for s in sim.sessions.values() if s.active]
