# Manual Validation Script

1. Start Gibson from this package.
2. Connect using the terminal method used in the screenshots.
3. Log on as IBMUSER.
4. Enter ISPF.
5. Open DSLIST for SYS1 or another large HLQ.
6. Confirm the cursor is on `Command ===>`.
7. Type `Q` and confirm it appears on `Command ===>`, not above it.
8. Reopen DSLIST.
9. Type `E 1` and confirm no crash and no screen corruption.
10. Return to DSLIST.
11. Type `B 1` and confirm stable behaviour.
12. Type `M` against a PDS row and confirm member list or clear message.
13. Press F7/F8 and confirm no visible escape text.
14. Press F3 and confirm clean exit.
15. Open the editor for SYS1.BRODCAST/SYS1.BROADCAST or another editable dataset.
16. Type a line longer than half the screen and confirm it does not wrap after half the line.
17. Press ENTER and confirm the next logical record is selected/created cleanly.
18. Type `CANCEL` on `Command ===>` and confirm clean exit.
19. Confirm Option 5 / Batch still opens with existing behaviour.
20. Confirm TSO, OMVS, ZSEC and IND$FILE smoke checks still work.
21. Confirm no removed ports are active.
