from __future__ import annotations

def normalize_aid(value: str) -> str:
    u=(value or "").strip().upper()
    if u.startswith("AID="): u=u[4:]
    aliases={"F1":"PF1","F3":"PF3","F5":"PF5","F7":"PF7","F8":"PF8","F10":"PF10","F12":"PF12","RETURN":"ENTER","CR":"ENTER"}
    return aliases.get(u,u)

def is_aid(value: str) -> bool:
    return normalize_aid(value) in {"PF1","PF3","PF5","PF7","PF8","PF10","PF12","ENTER","CLEAR","PA1","PA2"}
