# zSecure handler separation implementation

`gibson/apps/zsecure_engine.py` now separates event, rare-event, summary, SMF, RACFDS, offline hash, hash cracking and IND$FILE transfer views. Generic findings remain available for posture topics but no longer hijack `EVENTS` or `RARE`.
