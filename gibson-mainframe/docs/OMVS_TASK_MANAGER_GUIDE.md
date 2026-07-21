# OMVS Task Manager Guide

The `task` command implements a compact Taskwarrior-style workflow:

```sh
task add "Review SMF119 records" project:gibson pri:H due:tomorrow +cti
task list
task 1 done
task projects
task tags
task export
```

Tasks are stored per user in `.gibson_tasks.json`.
