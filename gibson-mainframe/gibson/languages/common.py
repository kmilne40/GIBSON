from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class SourceLocation:
    line: int = 0
    column: int = 0

@dataclass
class LanguageDiagnostic:
    code: str
    message: str
    severity: str = "INFO"
    location: SourceLocation = field(default_factory=SourceLocation)

@dataclass
class LanguageListing:
    title: str
    sections: List[str] = field(default_factory=list)
    diagnostics: List[LanguageDiagnostic] = field(default_factory=list)

    def render(self, maxcc: int = 0) -> str:
        out = [self.title]
        out.extend(self.sections)
        if self.diagnostics:
            out.append("DIAGNOSTICS")
            for d in self.diagnostics:
                loc = f" LINE {d.location.line}" if d.location.line else ""
                out.append(f"{d.code}-{d.severity[0]}{loc} {d.message}")
        out.append(f"MAXIMUM CONDITION CODE WAS {maxcc}")
        return "\n".join(out)

@dataclass
class LanguageRuntimeResult:
    rc: int = 0
    maxcc: int = 0
    stdout: List[str] = field(default_factory=list)
    diagnostics: List[LanguageDiagnostic] = field(default_factory=list)
    listing: str = ""
    created_datasets: List[str] = field(default_factory=list)
    updated_datasets: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)

    def text(self) -> str:
        parts = []
        if self.listing:
            parts.append(self.listing)
        if self.stdout:
            parts.append("\n".join(self.stdout))
        return "\n".join(parts)

class BoundedRuntimeError(RuntimeError):
    pass
