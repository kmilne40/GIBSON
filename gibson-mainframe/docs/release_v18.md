# Gibson v18 client/RACF/IND$FILE update

## Package

`gibson-mainframe-v30277-v18-client-racf-indfile.zip`

## Highlights

- Runtime fingerprinting and spoofed service identity were removed from live client paths.
- Port 2023 remains the main VTAM selector and now cleanly separates ASCII/NVT and TN3270 client handling.
- c3270/x3270 are no longer rejected or confused by fingerprinting logic.
- Netcat and standard telnet continue to receive the ASCII VTAM selector.
- WARNING-mode dataset access now raises console, SMF80, dashboard, and SECEVENTS evidence.
- Dataset READ, UPDATE, and ALTER are enforced through the central dataset security layer.
- Group dataset permits are supported and shown by RLIST/LISTDSD.
- REVOKE, PERMIT DELETE, DELUSER, and DELETEUSER support were added or strengthened.
- SETROPTS REFRESH and SETROPTS RACLIST(class) REFRESH are accepted and audited.
- IND$FILE GET/PUT now transfers through a safe transfer root and blocks path traversal.

## Compatibility note

Nmap probe/helper files may still exist as documentation or static simulator tooling, but they do not gate live connections or inject fake negotiation into real client sessions.

## Validation

See `gibson_v18_client_racf_indfile_validation_report.md` for tests, limitations, and smoke-test notes.
