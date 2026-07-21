from __future__ import annotations
import ipaddress


def classify_ip(ip: str) -> str:
    try:
        obj = ipaddress.ip_address(str(ip))
    except Exception:
        return "invalid"
    if obj.is_loopback:
        return "localhost"
    if obj.version == 4 and str(obj).startswith("100."):
        return "cgnat" if ipaddress.ip_address(ip) in ipaddress.ip_network("100.64.0.0/10") else "public"
    if obj.is_private:
        return "private"
    if obj.is_link_local:
        return "link-local"
    if obj.is_reserved:
        return "reserved"
    if obj.is_multicast:
        return "multicast"
    return "public"
