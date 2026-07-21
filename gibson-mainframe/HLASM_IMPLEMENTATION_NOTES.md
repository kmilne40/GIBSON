# HLASM Implementation Notes

- Added a new safe HLASM simulator in `gibson/languages/hlasm.py`.
- Supports source parsing, symbol table creation, CSECT/DSECT/USING/DROP/DC/DS/EQU recognition and a tiny bounded instruction simulation.
- Supports LA, L, ST, MVC, CLC, CLI, A, S and simple branch instructions.
- JES ASMA90/ASMAHL integration produces assembler listing and object-module spool output.
