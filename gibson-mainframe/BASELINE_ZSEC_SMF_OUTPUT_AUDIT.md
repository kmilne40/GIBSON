# Baseline zSecure / SMF output audit

The previous `zsecure_engine.py` routed several commands through broad finding filters. `ZSEC EVENTS` and `ZSEC RARE` could return near-identical generic posture output instead of distinct event and rare-event views. Structured SMF views could also appear empty when audit/security events existed through another buffer.

The fix creates distinct view functions for events, rare events, SMF reviews, RACFDS, offline hashes, hash cracking and IND$FILE transfers. Security period summaries now use a shared event summary helper.
