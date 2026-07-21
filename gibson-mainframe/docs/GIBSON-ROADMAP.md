# Gibson Roadmap — Endevor, Security Labs, IMS, and the VTAM banner

A value-ordered plan for the next round of work. Each item lists **what**, **why
it's valuable**, the **security angle**, a rough **effort** estimate (grounded in
existing subsystem sizes: z/VM ~1,200 lines, CICS ~1,600, zSecure ~400,
racf_admin ~215), and how it's **verified** (the established discipline: a
parity-harness gate plus a pristine-baseline regression diff that stays empty).

---

## 0. The VTAM "pulsing half-block" hostname — explanation (not a regression)

The banner renderer is byte-identical to the pristine baseline; nothing in this
project changed it. The behaviour is path-dependent by design:

- The banner **model** always emits an ASCII-safe `#` logo so the TN3270/EBCDIC
  bytes stay stable and pass the parity tests (a real 3270 has **no Unicode
  half-block code point** — `▄` U+2584 simply cannot be represented in EBCDIC).
- The **ANSI / netcat path** swaps `#` for the chosen display glyph (default `▄`,
  the half-height block) via `solidify_banner()`, and animates it with the
  breathing `GIBSON_HOSTNAME_PULSE` glow (on by default).

So if you connect with a real 3270 emulator you correctly see `#`; the pulsing
`▄` is an ANSI-path affordance. To restore/tune it:

- ANSI path: ensure `GIBSON_BANNER_FILL` is unset or `half`, and
  `GIBSON_HOSTNAME_PULSE` is `on`.
- **3270-native pulse (proposed, tiny):** a 3270 cannot show `▄`, but it *can*
  blink a field via the extended highlight attribute (`0xF1` blink in
  `screen3270.py`). Adding a blink attribute to the banner field gives the
  authentic IBM "pulse" on the EBCDIC path — the hardware-blink the real
  terminals used — without any Unicode. **Effort: ~30 lines + a gate.** A good
  quick win to bundle with Phase 1.

---

## Priority order (greatest value first)

### Phase 1 — Endevor MVP + broken-access-control lab  ◀ highest value
**What.** A new `gibson/apps/endevor/` subsystem: the C1 primary-options panel,
an element store keyed by Environment/Stage/System/Subsystem/Type/Element, and
the core actions Display, Browse, Retrieve, Add — fronted by an **External
Security Interface (ESI)** layer that mirrors the real product's
`RACROUTE REQUEST=AUTH` authorization model.

**Why.** Endevor is a daily-driver SCM tool real mainframe developers live in;
adding it makes Gibson recognisable to practitioners, and it reuses the existing
dataset core, RACF store, panel framework and SMF pipeline.

**Security angle — the lab you asked for.** A deliberate **broken object-level
authorization** flaw (CWE-639): the Browse/Display path validates that an element
*exists* but never asks ESI whether the requesting user is **in scope** for that
System/Subsystem/Stage. A low-privilege developer keys another team's
`System.Subsystem` (e.g. `PAYROLL.SALARY`) and reads source they should never
see. Shipped as a **before/after toggle** (`GIBSON_ENDEVOR_LAB_VULNERABLE`,
mirroring `GIBSON_ZVM_LAB_VULNERABLE`):
- *vulnerable* mode: scope check skipped → source leaks;
- *fixed* mode: the same action issues the ESI `RACROUTE` scope check → authentic
  `ICH408I` denial + an SMF type-80 violation record.

That before/after is the team demo **and** the remediation spec in one artifact.
Entirely sandboxed in the simulator.

**Effort.** ~400–600 lines engine + a panel front-end (≈ one z/VM-sized
subsystem). **Verified by** `endevor:browse` (happy path) and `endevor:authz`
(vuln leaks / fixed denies + audits) gates; baseline diff empty.

**Deliverables.** The subsystem, a `docs/endevor_security_lab.md` walkthrough,
harness gates, repackaged build.

---

### Phase 2 — z/VM "Just Enough Authority" privilege lab
**What.** A guided lab on top of the existing z/VM subsystem demonstrating
privilege-class creep and its blast radius.

**Why / security angle.** Research backs why this matters: a hypervisor
compromise is never one-VM. On z/VM specifically, IBM's own guidance warns that
**class G may be too much for a standard Linux guest**, that admins are often
**over-powered** (no split between "hypervisor admin" and "storage admin"), and
that **HiperSockets can bypass LPAR EAL5+ isolation**. The canonical reference
(Altmark, *z/VM Security and Integrity*) notes that altering host real memory via
`CP STORE HOST` is a **privilege class C** command. The lab: a Linux guest
over-granted class B/C, a `CP STORE HOST` cross-guest memory peek, a
privilege-class-creep audit, and the remediation (least privilege, split admin
roles). This is the mainframe analog of the VM-escape lessons teams already
understand from VMware/ESXi.

**Effort.** Mostly leverages existing z/VM CP enforcement; ~150–250 lines + a
`CP STORE HOST` class-C façade + a doc. **Verified by** `zvm:jea` gate; baseline
diff empty.

---

### Phase 3 — Endevor packages + separation-of-duties bypass lab
**What.** Extend Endevor with Packages: create / cast / approve / execute, and a
Move action with signout enforcement.

**Why / security angle.** Separation of duties is the #1 real-world SCM control
failure. The lab: a developer who can both **cast and approve their own package**
straight to production (self-approval), shown before/after with an approver-role
check toggle and an audit trail. Natural follow-on once the Phase-1 element store
exists.

**Effort.** ~300–500 lines on top of Phase 1. **Verified by** `endevor:package`
and `endevor:sod` gates; baseline diff empty.

---

### Phase 4 — IMS: Connect/OTMA security lab (+ optional IMS DB learning module)
**What.** Model **IMS Connect** (the TCP/IP gateway) + **OTMA** message flow,
the IMS RACF resource classes (**TIMS** transactions, **CIMS** commands, **RIMS**
resume-TPIPE), and the `/SECURE OTMA NONE|CHECK|FULL` control. Optionally a small
**IMS DB** module (DBD/PSB/PCB + a few DL/I `GU`/`GN`/`ISRT` calls) for learning
value.

**Why.** IMS still runs enormous production workloads and is a major gap in
mainframe training tools. Educationally the hierarchical DB model + DL/I is high
value even though the security angle is more specialised than RACF/Endevor.

**Security angle (real, but more specialised).** The compelling story is **IMS
Connect exposed on the network with weak/`NONE` OTMA security**: the gateway
flows a client-supplied userid to IMS, and if OTMA security is `NONE` (or the
client is a trusted member) an attacker reaching IMS Connect can **inject
transactions and operator commands** (`/DIS`, `/STA`, `/STO`, `/DBR`) as a chosen
identity. Lab: IMS Connect reachable, `/SECURE OTMA NONE`, no `TIMS`/`CIMS`
profiles → unauthorised transaction/command execution; fixed mode flips
`/SECURE OTMA FULL` + defines the classes → `RACF`-checked denial. Very analogous
to the Tomcat-weak-cred and z/VM labs already in Gibson.

**Effort.** Security lab: ~400–600 lines (Connect/OTMA + TIMS/CIMS auth +
toggle). Full IMS DB learning module: another ~400–700 lines. The two halves can
ship independently. **Verified by** `ims:otma` (and optionally `ims:dli`) gates;
baseline diff empty.

**Verdict.** Worth doing, but **after** Endevor and the z/VM lab: the security
payoff per line is lower than Endevor's, though the learning-value-per-line is
high. Recommend the **Connect/OTMA security lab first**, defer the DB module
unless learning breadth is the goal.

---

### Phase 5 — Endevor full realism + IMS DB module (completeness)
Generate/Delete with signout, SCL batch parsing, footprints; and the IMS DB
learning module if not already done in Phase 4. Lower marginal security value;
do when polishing for breadth.

---

## Suggested build sequence
1. Banner 3270-native blink (quick win) **+** Endevor MVP + access-control lab
2. z/VM Just-Enough-Authority lab
3. Endevor packages + SoD bypass lab
4. IMS Connect/OTMA security lab
5. Full realism (Endevor SCL/footprints, IMS DB module)

Every phase ships with a parity-harness gate and an empty pristine-baseline
regression diff, and the build zip is repackaged and verified from a clean
extract on delivery — same discipline as the completed enhancement work.
