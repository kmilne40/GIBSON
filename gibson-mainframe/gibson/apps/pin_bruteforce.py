from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import time
from typing import Any
from gibson.core import dvcapin
from gibson.render import colors

CELL_IDLE = colors.GREEN + '▪' + colors.RESET
CELL_WARM = colors.YELLOW + '■' + colors.RESET
CELL_ACTIVE = colors.RED + '■' + colors.RESET
SQUARE_FRAMES = [
    CELL_IDLE*4,
    CELL_IDLE + CELL_WARM + CELL_IDLE*2,
    CELL_IDLE + CELL_ACTIVE + CELL_IDLE + CELL_WARM,
    CELL_ACTIVE + CELL_IDLE + CELL_WARM + CELL_IDLE,
    CELL_WARM + CELL_IDLE + CELL_ACTIVE + CELL_IDLE,
    CELL_IDLE + CELL_ACTIVE + CELL_WARM + CELL_IDLE,
    CELL_WARM + CELL_ACTIVE + CELL_IDLE + CELL_WARM,
]
ASCII_FRAMES = ['....', '.+..', '.*.+', '*.+.', '+.*.', '.*+.', '+*.+']

TERMINAL_STATES = {'SUCCESS', 'FAILURE', 'CANCELLED'}
MAX_PIN_ATTEMPTS = 20

@dataclass
class PinBruteSession:
    app: str
    user: str
    dataset_name: str
    candidates: list[str]
    invalid_lines: int = 0
    attempts: int = 0
    status: str = 'READY'
    result_pin: str = ''
    current_visual: str = SQUARE_FRAMES[0]
    tick_interval_seconds: float = 1.0
    last_tick_time: float = field(default_factory=time.monotonic)
    correlation_id: str = field(default_factory=lambda: 'PIN-' + hashlib.sha1(datetime.now().isoformat().encode()).hexdigest()[:8].upper())
    frames: list[str] = field(default_factory=list)

    def maybe_tick(self, state: Any, now: float | None = None, reveal_success: bool = True) -> bool:
        """Advance when at least one interval elapsed; return True if changed.

        The interactive CICS path calls this after one-second socket/input
        timeouts so DVCA/OMEN brute-force panels progress automatically
        without requiring ENTER.  Tests can inject ``now`` for deterministic
        clock-driven validation.
        """
        if self.status in TERMINAL_STATES:
            self.frames = [self.render_frame(final=True)]
            return False
        t = time.monotonic() if now is None else float(now)
        if t - float(self.last_tick_time or 0.0) < self.tick_interval_seconds:
            self.frames = [self.render_frame(final=self.status in TERMINAL_STATES)]
            return False
        self.last_tick_time = t
        before = (self.attempts, self.status, self.current_visual, self.result_pin)
        self.tick_once(state, reveal_success=reveal_success)
        after = (self.attempts, self.status, self.current_visual, self.result_pin)
        return after != before

    def tick_once(self, state: Any, reveal_success: bool = True) -> None:
        """Advance exactly one candidate and keep only the current frame.

        Earlier Gibson builds created every brute-force frame in one server
        turn and joined them together.  That produced stacked printouts, not an
        animation.  This method is intentionally one-tick-only so a terminal,
        web poll, ENTER, or PF-key event can repaint the same logical panel.
        """
        if self.status in TERMINAL_STATES:
            self.frames = [self.render_frame(final=True)]
            return
        if not self.candidates:
            self.status = 'FAILURE'
            self.frames = [self.render_frame(final=True)]
            return
        self.status = 'RUNNING'
        idx = self.attempts
        if idx >= len(self.candidates):
            self.status = 'FAILURE'
            self.frames = [self.render_frame(final=True)]
            return
        cand = self.candidates[idx]
        self.attempts = idx + 1
        self.current_visual = SQUARE_FRAMES[self.attempts % len(SQUARE_FRAMES)]
        if dvcapin.verify(state, cand):
            self.status = 'SUCCESS'
            self.result_pin = cand if reveal_success else dvcapin.reveal_for_training(state)
            self.frames = [self.render_frame(final=True)]
            return
        self.frames = [self.render_frame()]

    def cancel(self) -> None:
        self.status = 'CANCELLED'
        self.frames = [self.render_frame(final=True)]

    def render_frame(self, visual: str = '', final: bool = False) -> str:
        visual = visual or self.current_visual or SQUARE_FRAMES[self.attempts % len(SQUARE_FRAMES)]
        pin_field = self.result_pin if final and self.status == 'SUCCESS' else visual
        result = 'PIN MATCH FOUND - ACCESS UNLOCKED' if self.status == 'SUCCESS' else ('PIN NOT FOUND' if self.status == 'FAILURE' else ('CANCELLED' if self.status == 'CANCELLED' else 'RUNNING'))
        title = f'{self.app} PIN BRUTE FORCE'
        lines = [
            title,
            '',
            f'DATASET NAME ===> {self.dataset_name}',
            f'PIN FIELD    ===> {pin_field}',
            f'ATTEMPTS     ===> {self.attempts:05d} OF {len(self.candidates):05d}',
            f'INVALID LINES===> {self.invalid_lines:05d}',
            f'STATUS       ===> {self.status}',
            f'CORRELATION  ===> {self.correlation_id}',
            '',
            'PF3/PF12/CLEAR cancels. Vulnerable training mode reveals the PIN on success.',
            f'RESULT       ===> {result}',
        ]
        return '\n'.join(lines)


def _session_store(state: Any) -> dict[tuple[str, str, str], PinBruteSession]:
    store = getattr(state, 'pin_brute_sessions', None)
    if store is None:
        store = {}
        setattr(state, 'pin_brute_sessions', store)
    return store




def get_active_pin_bruteforce(state: Any, userid: str, app: str) -> PinBruteSession | None:
    user = (userid or 'GUEST').upper()
    appu = (app or 'PIN').upper()
    for (sapp, suser, _dsn), sess in list(_session_store(state).items()):
        if sapp == appu and suser == user and sess.status not in TERMINAL_STATES:
            return sess
    return None

def _normalise_pin_candidates(state: Any, candidates: list[str]) -> list[str]:
    """Return exactly MAX_PIN_ATTEMPTS candidates including the active PIN.

    DVCA/CBSA MCAD training is deliberately bounded: the screen should always
    show a 20-attempt workflow while still honouring DVCAPIN.  Short datasets
    are padded and long datasets are truncated without losing the target PIN.
    """
    target = dvcapin.active_training_pin(state)
    clean: list[str] = []
    for raw in candidates:
        cand = (raw or '').strip()
        if len(cand) == 4 and cand.isdigit() and cand not in clean:
            clean.append(cand)
    if target not in clean:
        clean.append(target)
    i = 0
    while len(clean) < MAX_PIN_ATTEMPTS:
        cand = f'{i:04d}'
        if cand != target and cand not in clean:
            clean.append(cand)
        i += 1
    if len(clean) > MAX_PIN_ATTEMPTS:
        clean = clean[:MAX_PIN_ATTEMPTS]
        if target not in clean:
            clean[-1] = target
    return clean


def load_candidates_from_dataset(state: Any, userid: str, dsname: str, max_candidates: int = 10000) -> tuple[list[str], int, str]:
    dsn = (dsname or '').strip().strip("'").upper()
    if not dsn:
        raise ValueError('DATASET NAME REQUIRED')
    try:
        text = state.datasets.read(userid.upper(), dsn)
    except Exception:
        target = dvcapin.active_training_pin(state)
        text = f'0000\n0001\n9999\n{target}\n'
        try:
            state.datasets.allocate(userid.upper(), dsn, org='PS')
            state.datasets.write(userid.upper(), dsn, text)
        except Exception:
            pass
    candidates: list[str] = []
    invalid = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if len(line) == 4 and line.isdigit():
            if len(candidates) < max_candidates:
                candidates.append(line)
        else:
            invalid += 1
    return _normalise_pin_candidates(state, candidates), invalid, dsn

def start_pin_bruteforce(state: Any, userid: str, app: str, dsname: str, *, now: float | None = None) -> PinBruteSession:
    cands, invalid, dsn = load_candidates_from_dataset(state, userid, dsname)
    sess = PinBruteSession(app=app.upper(), user=userid.upper(), dataset_name=dsn, candidates=cands, invalid_lines=invalid)
    if now is not None:
        sess.last_tick_time = float(now)
    _session_store(state)[(sess.app, sess.user, sess.dataset_name)] = sess
    try:
        state.record_security_event(userid.upper(), f'{app.upper()}_PIN_BRUTE_START', f'DATASET={dsn} CANDIDATES={len(cands)}', service=app.upper())
    except Exception:
        pass
    return sess


def run_pin_bruteforce(state: Any, userid: str, app: str, dsname: str, *, advance: int = 1) -> PinBruteSession:
    """Start or advance a bounded brute-force session.

    A single call returns exactly one rendered panel in sess.frames[0].  Callers
    must not concatenate historical frames; that was the source of the stacked
    printout defect seen in v2.
    """
    user = (userid or 'GUEST').upper()
    appu = (app or 'PIN').upper()
    dsn = (dsname or f'{user}.4CHAR.PIN').strip().strip("'").upper()
    key = (appu, user, dsn)
    store = _session_store(state)
    sess = store.get(key)
    if sess is None or sess.status in TERMINAL_STATES:
        sess = start_pin_bruteforce(state, user, appu, dsn)
    for _ in range(max(1, int(advance or 1))):
        sess.tick_once(state, reveal_success=True)
        if sess.status in TERMINAL_STATES:
            break
    try:
        if sess.status in TERMINAL_STATES:
            state.record_security_event(user, f'{appu}_PIN_BRUTE_{sess.status}', f'DATASET={dsn} ATTEMPTS={sess.attempts} CORR={sess.correlation_id}', service=appu)
    except Exception:
        pass
    return sess
