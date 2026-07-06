# Legacy RACF DES Hash Research

The implementation models the legacy eight-character RACF DES training workflow: uppercase userid/password, EBCDIC representation, password-derived key material, and John-style `$racf$*USER*HASH` output. Where a DES provider is unavailable on small/mobile Python installs, Gibson uses a deterministic simulator fallback so the lab remains repeatable. It is labelled as simulator material, not byte-perfect IBM RACF cryptography.
