# racf2john Enrichment Implementation

`racf2john` remains a bounded Gibson simulator. It accepts Gibson dataset names only, rejects host paths, extracts only `ALG=LEGACY-DES` records and skips KDFAES/protected users. It supports `--summary` and `--json` and emits SMF80/30/92 evidence plus Master Console alerts.
