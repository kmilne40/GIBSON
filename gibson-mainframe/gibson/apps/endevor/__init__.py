"""Simulated CA/Broadcom Endevor SCM subsystem for Gibson.

Provides a teaching model of the Endevor software change manager: an element
inventory keyed by Environment/Stage/System/Subsystem/Type/Element, the core
element actions, and an External Security Interface (ESI) authorization layer
that mirrors the real product's RACROUTE REQUEST=AUTH model.

The subsystem ships a deliberate broken-access-control training lab (CWE-639):
when ``config.endevor_lab_vulnerable_mode`` is on, the element browse path skips
the ESI scope check, so a low-privilege user can read elements outside their
scope.  Turning the lab off enforces the ESI check and records an SMF80
violation -- the before/after a security team needs to see.
"""

from gibson.apps.endevor.endevor_engine import (  # noqa: F401
    endevor_command,
    get_endevor_store,
)
