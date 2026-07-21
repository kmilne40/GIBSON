# ISPF Render Width Guards

Changes:
- DSLIST title generation now keeps visible lines within the panel width.
- Editor draw tests validate rendered visible line width after ANSI stripping.
- The editor clamps cursor placement to avoid terminal auto-wrap before the intended visible width.
