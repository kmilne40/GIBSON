# SMF Core Engine Implementation

Implemented under `gibson/core/smf/`:

- `base.py`: `SmfHeader`, `SmfRecord`, `make_record`.
- `writer.py`: `SmfWriter`, `get_smf_writer`, compatibility writer.
- `formatters.py`: list, detail, timeline and unload export views.
- `records/`: typed record constructors for RACF, CICS, JES, USS, network, Db2, API, data-loss and ICSF evidence.
- `m4m_smf.py`: ten M4M/Navigator forensic scenarios.

The writer also mirrors structured records into the existing audit log so old SDSF/zSecure/console flows remain compatible.
