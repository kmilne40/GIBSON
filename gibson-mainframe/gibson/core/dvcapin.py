from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import hashlib, secrets

FALLBACK_PIN = '1337'

@dataclass
class DVCAPinState:
    pin_hash: str = ""
    salt: str = ""
    pin_set_time: str = ""
    pin_set_by: str = ""
    # Vulnerable training simulator: keep runtime-only clear value so the
    # successful brute-force training panel can reveal the discovered PIN.
    training_pin: str = ""


def validate_pin_format(pin: str) -> bool:
    return isinstance(pin, str) and pin.isdigit() and len(pin) == 4


def _hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 120_000).hex()


def _state(state) -> DVCAPinState:
    st = getattr(state, 'dvcapin_state', None)
    if st is None:
        st = DVCAPinState()
        setattr(state, 'dvcapin_state', st)
    return st


def set_pin(state, pin: str, actor: str = 'CONSOLE') -> str:
    pin = (pin or '').strip()
    if not validate_pin_format(pin):
        raise ValueError('DVCAPIN MUST BE EXACTLY 4 NUMERIC DIGITS')
    st = _state(state)
    st.salt = secrets.token_hex(16)
    st.pin_hash = _hash(pin, st.salt)
    st.pin_set_time = datetime.now().isoformat(timespec='seconds')
    st.pin_set_by = (actor or 'CONSOLE').upper()
    st.training_pin = pin
    try:
        state.record_security_event(st.pin_set_by, 'R06 DVCAPIN UPDATED', 'DVCAPIN SET - SECRET NOT LOGGED', service='CONSOLE')
    except Exception:
        pass
    try:
        state.notify_console('R06 DVCAPIN UPDATED - SECRET NOT LOGGED', severity='INFO')
    except Exception:
        pass
    return 'DVCAPIN SET'


def is_set(state) -> bool:
    st = getattr(state, 'dvcapin_state', None)
    return bool(st and st.pin_hash and st.salt)


def verify(state, pin: str) -> bool:
    st = getattr(state, 'dvcapin_state', None)
    if not st or not st.pin_hash or not st.salt:
        # vulnerable lab default until R06 has been configured
        return (pin or '').strip() == FALLBACK_PIN
    return secrets.compare_digest(_hash((pin or '').strip(), st.salt), st.pin_hash)


def reveal_for_training(state) -> str:
    st = getattr(state, 'dvcapin_state', None)
    if st and st.training_pin:
        return st.training_pin
    return FALLBACK_PIN


def active_training_pin(state) -> str:
    """Return the active training PIN, falling back to 1337.

    DVCA/CBSA PIN brute-force training must use the configured DVCAPIN when
    one has been set.  If no valid runtime PIN is present, the documented
    backup training PIN is 1337.
    """
    st = getattr(state, 'dvcapin_state', None)
    if st and validate_pin_format(getattr(st, 'training_pin', '')):
        return st.training_pin
    return FALLBACK_PIN


def status(state) -> str:
    return 'DVCAPIN SET' if is_set(state) else 'DVCAPIN NOT SET'
