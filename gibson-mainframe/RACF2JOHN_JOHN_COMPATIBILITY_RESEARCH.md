# racf2john / john Compatibility Research

Gibson exports RACF hash material in the common training shape:

```text
USER:$racf$*USER*HASH
```

If a DES provider is available, records are marked `ALG=LEGACY-DES`, `PROVIDER=REAL-DES`, and `JOHN=YES`. If DES is unavailable in a mobile/minimal Python runtime, Gibson creates deterministic simulator material marked `ALG=LEGACY-DES-SIM`, `PROVIDER=SIMULATOR`, and `JOHN=SIM-ONLY`. The simulator can crack these records, but real-John compatibility is not claimed for simulator-only material.
