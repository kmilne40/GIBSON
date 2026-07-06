# R05 Geo Map Fix Implementation Traceability

Implemented against the R05 geo/map failure analysis.

| Recommendation | Implementation | Tests | Safety |
|---|---|---|---|
| R05/BINKY must reach live VTAM render path | Telnet and TN3270 services now pass `state.get_system_hostname()` into the canonical VTAM renderers. | `test_r05_binky_live_vtam.py` | Internal block renderer only; no shell/figlet. |
| 4.180.9.35 needs usable offline geolocation | Added explicit best-effort offline fixture with city/country/lat/lon/ASN/org/source/confidence. | `test_geo_public_4_180_9_35.py` | No external lookup by default. |
| 192.168.0.0/24 maps to Livingston | Added local private-network override in the fixture provider. | `test_geo_home_network_livingston.py` | Private IPs never sent to providers. |
| Master-console geo alerts need user/city/country context | Existing enrichment now has fixture data; local home network excluded from external alert classification. | `test_master_console_geo_user_city_country.py` | Unknown geo remains UNKNOWN; no fake values. |
| Map markers missing | Enriched geo events and active sessions now produce markers when numeric lat/lon exists. | `test_dashboard_marker_4_180_9_35.py` | Unknown public IPs remain unplotted. |
| geoloc.py useful but should be optional | Added optional `FreeIpApiGeoProvider` normalisation pattern, disabled by default. | `test_geoloc_provider_optional.py` | No default online calls. |
