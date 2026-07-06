# RACFDS SMF / Master Console / CTI Implementation

RACFDS reads, hash extraction and hash cracking emit structured training evidence. The Master Console receives realistic SMF/security messages such as `SMF080I`, `SMF030I`, `GIBSSEC2A` and `GIBSSEC3A`, mapped to MF-TTP08 / MITRE T1110.002. Existing zSecure and CTI event normalisation can consume these records through the existing event/audit paths.
