# Public IP 4.180.9.35 Geolocation Fix

`4.180.9.35` is now represented by an explicit offline best-effort fixture so Gibson can render master-console context and map markers without online provider calls. The record is labelled `offline-fixture-best-effort` and uses city-level approximate coordinates.

This is not claimed to be exact personal location. Online provider integration remains optional and disabled by default.
