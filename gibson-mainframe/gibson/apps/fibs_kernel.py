from __future__ import annotations
class FibsRemovedError(RuntimeError): pass
def get_fibs_session(*a, **k): raise FibsRemovedError("FIBS was removed from the Gibson golden runtime")
FibsSession = object
def render_text(*a, **k): return "FIBS REMOVED FROM GOLDEN RUNTIME"
class FibsApplicationController: pass
