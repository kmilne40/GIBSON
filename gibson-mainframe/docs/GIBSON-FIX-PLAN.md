# Gibson Fix Plan — live-server defects (priority over new features)

Raised from real testing against the running server. These take priority over the
Endevor/IMS roadmap. Each item has the **root cause found at the code level**, the
**fix**, and **verification** — and verification now means exercising the *live*
session path the server actually drives, not an in-process shortcut.

## Why the earlier verification missed these
The parity harness drove `tn3270_server.py`'s line-mode `handle_tso` path, but the
running server uses the full **`tso3270` logon panel** and related app sessions.
Several defects live in the panel path the harness never touched. Fix going
forward: **every gate drives the live session class** (e.g. `Tso3270App`), and a
defect is reproduced against that path before any claim of "fixed".

---

## P1 — Add user + allow logon  ✅ FIXED
**Symptom.** A newly-added user can never get a clean, repeatable logon.
**Root cause.** In the live `tso3270` logon path, `_maybe_change_password` set the
new password in `state.racf` but never cleared `password_change_required` in
`state.uads`. So every subsequent logon re-prompted for a password change, and the
password-history rule eventually locked the user out. (The `tn3270_server.py` path
cleared it; the panel path didn't — an inconsistency between two logon
implementations.)
**Fix.** After a successful change, clear the UADS flag and sync the UADS password
(`uads.set_password(userid, hash, change_required=False)`), matching the other
path.
**Verified.** New gate `logon:live-newuser` drives the actual panel: add user →
complete forced change → log on again twice, cleanly. Green; zero regressions.

---

## P2 — `?` help facility on all commands  ◀ next (user: "vital")
**Symptom.** `LIST?` → `IKJ56500I COMMAND LIST? NOT FOUND`. Only a few commands
(e.g. `ADDUSER?`) give help; most don't, and `?` mid-command isn't honoured.
**Root cause (to confirm in code).** `?`-help is implemented per-command in the
v30289 layer rather than as a general facility; unknown `VERB?` falls through to
"command not found".
**Fix.** A general operand-help handler: any `VERB ?` (or trailing `?`) returns the
command's syntax/operands from a single help table covering the full TSO command
set, matching real TSO operand prompting.
**Verify.** Gate `tso:help-qmark` — `LISTUSER ?`, `ALLOCATE ?`, `LISTDS ?`, `EX ?`
each return syntax help, not "not found".

---

## P3 — Editor save fails / member doesn't persist  (data loss — serious)
**Symptom.** Editing `IBMUSER.IBMUSER(NEWDS)` then SAVE →
`SAVE FAILED [Errno 17] File exists '/home/.../f/IBMUSER/IBMUSER'`; the member
doesn't exist afterward.
**Root cause.** PS/PO collision: when `IBMUSER.IBMUSER` already exists as a
*sequential* file and is addressed as a PDS member, `parent.mkdir(exist_ok=True)`
raises `FileExistsError` (errno 17) because the path is a file, not a directory.
The raw `OSError` is surfaced to the panel.
**Fix.** Detect the PS-vs-PO case before writing a member: if the dataset exists as
PS, either promote/relocate or return a clean "NOT A PARTITIONED DATA SET"; ensure
new members create the member directory and persist; confirm round-trip read.
**Verify.** Gate `ds:member-save` — allocate PO, edit+save a new member, reopen and
read it back; and the PS-addressed-as-PO case returns a clean message, no errno.

---

## P4 — ANSI-garbled output on the 3270/EBCDIC path
**Symptom.** `ÝErrno 17¨` (the `[`/`]` of a Python error), and `Ý2J` (an
`ESC[2J` clear-screen escape leaking in).
**Root cause.** Two related: (a) text containing `[` `]` is EBCDIC-encoded and the
brackets render as `Ý`/`¨`; (b) ANSI escape sequences reach the 3270 datastream
where the `ESC` is dropped but `[2J` remains and mistranslates.
**Fix.** Sanitise before EBCDIC encoding: strip ANSI/VT escape sequences
(`strip_ansi`) and map/escape non-EBCDIC-safe punctuation on the 3270 output path;
ensure error/message text is plain before it reaches the encoder.
**Verify.** Gate `render:no-ansi-leak` — error and screen-clear text through the
3270 path contains no `Ý`/`¨`/stray `[2J`.

---

## P5 — `SDSF` from READY only prints a static screen
**Symptom.** Typing `SDSF` at READY dumps the SDSF panel as scroll text, then
returns to READY, instead of entering the SDSF full-screen app.
**Root cause.** The TSO command processor returns canned SDSF text rather than
transferring control to the `sdsf3270` app (the way `ISPF` launches its app).
**Fix.** Route `SDSF` (and `ISPF`, `SDSF`, other full-screen verbs) at READY to a
session transfer into the `sdsf3270` app, returning to READY on PF3.
**Verify.** Gate `tso:sdsf-launch` — `SDSF` enters the app screen (action bar +
`SDSF STATUS` panel object), PF3 returns to READY.

---

## P6 — `EX 'dataset(member)'` doesn't execute code
**Symptom.** `ex 'IBMUSER.IBMUSER(STUFF)'` (a REXX member) does not run.
**Root cause (to confirm).** The `EXEC`/`EX` path doesn't resolve+read the member
and dispatch it to the REXX interpreter.
**Fix.** `EX[EC] 'dsn(member)'` reads the member and runs it through the existing
REXX engine; report `IRX...`-style errors authentically.
**Verify.** Gate `tso:exec-member` — a stored REXX member runs and returns its
output.

---

## Sequence
P1 ✅ → P2 (help) → P3 (editor save / persistence) → P4 (ANSI sanitise) →
P5 (SDSF launch) → P6 (EX member). Then resume the feature roadmap (Endevor SoD
lab, z/VM JEA lab, IMS).

Each fix: reproduce on the **live session path**, fix, add a live-path harness
gate, keep the pristine-baseline regression diff empty, repackage and verify from a
clean extract.
