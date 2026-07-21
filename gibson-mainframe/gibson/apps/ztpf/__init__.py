"""z/TPF (Transaction Processing Facility) educational simulation.

A high-volume, ECB-driven transaction processor reached from VTAM via ``L TPF``.
Phase 1: the prime CRAS operator console (Z-messages), the Entry Control Block
(ECB) transaction model with an ECB trace, two demo transactions (airline
availability and card authorisation) and a small TPFDF record model.
"""
from gibson.apps.ztpf.ztpf_engine import get_ztpf_state, ZtpfState
__all__ = ["get_ztpf_state", "ZtpfState"]
