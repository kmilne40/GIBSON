# Terminal Session Stability Hardening

ISPF application dispatch in the NVT/ANSI telnet path is now wrapped with a session-boundary exception handler. Unexpected panel exceptions are logged through the existing Gibson issue log and, where possible, the user is shown a small recovery panel instead of being silently dropped back to the workstation shell with a stale full-screen panel still displayed.

This wrapper is intentionally narrow: direct unit tests of ISPF panel code still raise failures normally, so defects are not hidden from the test suite.
