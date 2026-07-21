from __future__ import annotations

from html import escape
from pathlib import Path

VULN_NOTES = {
    "USER-INPUT               PIC X(100)": ("Oversized external input buffer", "A large external buffer is later moved into smaller records, creating the simulator's overflow condition.", "Validate length before MOVE and copy into fields with explicit bounds."),
    "CUSTOMER-ID         PIC X(10)": ("Redefines packed user input", "REDEFINES overlays structured fields on raw input, so attacker-controlled bytes can alter meaning.", "Parse fields explicitly and validate each field."),
    "AUTHENTICATED-FLAG      PIC X VALUE 'N'": ("Security flag near unsafe data", "The lab models how adjacent flags can be corrupted when validation is missing.", "Keep security state server-side and separate from input storage."),
    "ADMIN-FLAG              PIC X VALUE 'N'": ("Admin flag corruption target", "An overflow payload can flip the simulated admin flag to Y.", "Never trust client-controlled or adjacent memory state for authorization."),
    "DEBUG-FLAG              PIC X VALUE 'N'": ("Debug backdoor flag", "If this flag is flipped, the vulnerable path exposes internal debug data.", "Disable debug paths in production and protect diagnostic functions."),
    "CUST-PIN                PIC X(4)": ("Tiny fixed PIN field", "A small sensitive field close to other data highlights fixed-field overwrite risk.", "Validate exact length and keep secrets out of overflowable records."),
    "SENSITIVE-TEMP          PIC X(100)": ("Uninitialised sensitive storage", "Temporary storage can leak previous values if displayed or copied without clearing.", "Initialise sensitive working storage and clear it after use."),
    "LOG-BUFFER              PIC X(256)": ("Sensitive logging sink", "The program later copies the customer record into a log buffer, exposing secrets.", "Log only minimal, redacted fields."),
    "DFHCOMMAREA": ("Exposed communication area", "COMMAREA carries transaction data between programs and must not be trusted blindly.", "Validate COMMAREA length and content before use."),
    "GET CONTAINER('USERDATA')": ("Unsafe CICS container read", "The example omits a strong MAXFLENGTH-style guard before copying data.", "Use MAXFLENGTH or equivalent bounded receive logic."),
    "MOVE USER-INPUT TO CUSTOMER-RECORD": ("Unchecked MOVE into smaller record", "This is the core simulated overflow: external input is copied into a structured record without bounds.", "Check length and move field-by-field."),
    "CUST-PIN = '9999' OR AUTHENTICATED-FLAG = 'Y'": ("Authentication bypass condition", "If a payload flips AUTHENTICATED-FLAG, the vulnerable branch grants access.", "Recalculate authorization from trusted session/RACF state."),
    "DEBUG-FLAG = 'Y'": ("Debug privilege escalation", "A corrupted debug flag exposes internal memory-like data.", "Require explicit privileged authorization for diagnostics."),
    "NUMVAL(TRANSACTION-AMOUNT)": ("Unsafe numeric conversion", "Unvalidated numeric conversion can cause logic errors or abends.", "Validate numeric format and range before conversion."),
    "MOVE CUSTOMER-RECORD TO LOG-BUFFER": ("Sensitive data logged", "Customer PIN/balance data can be copied into logs.", "Redact sensitive fields before logging."),
    "DISPLAY 'DEBUG DUMP: ' TEMP-STORAGE": ("Memory disclosure", "Debug output exposes sensitive temporary storage.", "Remove memory dumps or protect them with audited privileged access."),
}


def _load_code() -> str:
    here = Path(__file__).resolve()
    root = here.parents[2]
    asset = root / "assets" / "cobol_bo_vulnerable.cbl"
    try:
        return asset.read_text(encoding="utf-8")
    except Exception:
        return "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. VULNERABLE-BANK-UPDATE.\n"


def render_cobol_bo_annotation() -> str:
    code = _load_code().splitlines()
    rows = []
    issue_cards = []
    seen = set()
    for i, line in enumerate(code, 1):
        note = None
        for needle, data in VULN_NOTES.items():
            if needle in line:
                note = data; break
        cls = " class='vuln-line'" if note else ""
        title = f" title='{escape(note[0], quote=True)}'" if note else ""
        rows.append(f"<tr{cls}{title}><td class='ln'>{i}</td><td><code>{escape(line)}</code></td></tr>")
        if note and note[0] not in seen:
            seen.add(note[0])
            issue_cards.append(f"<article class='vuln-note'><h4>{escape(note[0])}</h4><p><strong>Why it matters:</strong> {escape(note[1])}</p><p><strong>Mitigation:</strong> {escape(note[2])}</p></article>")
    return """
<section class='panel cobol-annotated'>
  <style>
    .cobol-annotated .code-wrap{display:grid;grid-template-columns:2fr 1fr;gap:1rem;align-items:start}
    .cobol-annotated table{width:100%;border-collapse:collapse;background:#111827;color:#f9fafb;font-family:ui-monospace,monospace;font-size:.86rem}
    .cobol-annotated td{vertical-align:top;padding:.14rem .35rem;border-bottom:1px solid rgba(255,255,255,.05)}
    .cobol-annotated .ln{color:#9ca3af;text-align:right;width:3.5rem;user-select:none}
    .cobol-annotated .vuln-line code{text-decoration: underline wavy #ef4444 2px;text-underline-offset:3px;background:rgba(239,68,68,.15)}
    .cobol-annotated .vuln-note{border-left:4px solid #ef4444;background:#fff7ed;margin:0 0 .65rem 0;padding:.7rem;border-radius:.35rem}
    .cobol-annotated .vuln-note h4{margin:.1rem 0 .35rem 0}
  </style>
  <h2>Annotated COBOL/CICS source</h2>
  <p>The underlined lines are intentionally vulnerable training examples from <code>VULNERABLE-BANK-UPDATE</code>. Gibson models the effects safely; it does not corrupt real memory.</p>
  <div class='code-wrap'>
    <div class='code-scroll'><table><tbody>""" + "\n".join(rows) + """</tbody></table></div>
    <aside>""" + "\n".join(issue_cards) + """</aside>
  </div>
</section>
"""
