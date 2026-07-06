# Terminal Connectivity Stability Test Report

The telnet ISPF entry point now logs unexpected ISPF panel exceptions and displays a clean recovery message where possible. This reduces the chance of a Python exception causing the user to see a stale ISPF panel mixed with a local shell prompt.

The change is confined to the ISPF app boundary and does not alter OMVS, CICS, Db2, CTI, RSS, ports or native TN3270 transfer behaviour.
