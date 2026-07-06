from __future__ import annotations

"""Training-only legacy RACF DES password hash simulator.

This module models the historic eight-character RACF DES password material
well enough for Gibson labs. It is not a real RACF database parser and it must
not be used against real systems.
"""

try:  # pycryptodomex, preferred import used by the user-provided prototype
    from Cryptodome.Cipher import DES  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    try:
        from Crypto.Cipher import DES  # type: ignore
    except Exception:
        DES = None  # type: ignore

# Fallback real-DES provider via the widely-available `cryptography` library.
# Single DES is obtained from TripleDES with K1=K2=K3 (EDE collapses to a single
# DES encryption), giving byte-exact RACF hashes without pycryptodome.
def _crypto_des_encrypt(key8: bytes, block8: bytes):
    try:
        try:
            from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
        except Exception:
            from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
        from cryptography.hazmat.primitives.ciphers import Cipher, modes
        enc = Cipher(TripleDES(key8 * 3), modes.ECB()).encryptor()
        return enc.update(block8) + enc.finalize()
    except Exception:
        return None


def _ebcdic8(value: str) -> bytes:
    raw = (value or "").upper()[:8].encode("cp037", errors="replace")
    return raw.ljust(8, b"\x40")


def _odd_parity(byte: int) -> int:
    b = byte & 0xFE
    ones = bin(b).count("1")
    return b | (0 if ones % 2 else 1)


def _password_key(password: str) -> bytes:
    pw = _ebcdic8(password)
    out = bytearray(8)
    for i, ch in enumerate(pw):
        out[i] = _odd_parity(((ch ^ 0x55) << 1) & 0xFF)
    return bytes(out)


def crypto_available() -> bool:
    return DES is not None or _crypto_des_encrypt(b"\0" * 8, b"\0" * 8) is not None


def generate_legacy_racf_des_hash(userid: str, password: str) -> str:
    """Return the uppercase legacy RACF DES hash hex for userid/password.

    Uses a real DES provider when one is available (pycryptodome, or the
    `cryptography` library via TripleDES with a repeated key), producing the
    byte-exact RACF DES hash that John the Ripper's `--format=racf` cracks. Only
    in a stripped environment with neither provider does Gibson fall back to a
    deterministic non-DES simulator value (labelled as such by docs/tests).
    """
    uid = (userid or "").upper()[:8]
    if not uid:
        raise ValueError("userid is required")
    key = _password_key(password or "")
    if DES is not None:
        cipher = DES.new(key, DES.MODE_ECB)
        return cipher.encrypt(_ebcdic8(uid)).hex().upper()
    ct = _crypto_des_encrypt(key, _ebcdic8(uid))
    if ct is not None:
        return ct.hex().upper()
    import hashlib
    return hashlib.sha256(key + _ebcdic8(uid)).hexdigest()[:16].upper()


def format_john_racf_hash(userid: str, hash_hex: str) -> str:
    uid = (userid or "").upper()[:8]
    hx = (hash_hex or "").upper().strip()
    return f"{uid}:$racf$*{uid}*{hx}"


def verify_legacy_racf_des_hash(userid: str, candidate: str, hash_hex: str) -> bool:
    try:
        return generate_legacy_racf_des_hash(userid, candidate) == (hash_hex or "").upper().strip()
    except Exception:
        return False
