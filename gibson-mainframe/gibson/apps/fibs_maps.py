from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class FibsField:
    id: str
    label: str
    row: int
    col: int
    length: int
    value: str = ""
    protected: bool = False
    hidden: bool = False
    numericOnly: bool = False
    mandatory: bool = False
    source: str = "screen"
    role: str = "input"

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id, "label": self.label, "row": self.row,
            "col": self.col, "length": self.length, "value": self.value,
            "protected": self.protected, "hidden": self.hidden,
            "numericOnly": self.numericOnly, "mandatory": self.mandatory,
            "source": self.source, "role": self.role,
            "editableNormal": not self.protected,
            "editableWhenHack": True,
        }

@dataclass
class FibsMap:
    name: str
    title: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    fields: list[FibsField] = field(default_factory=list)
    message: str = ""
    pfkeys: list[dict[str,str]] = field(default_factory=lambda: [
        {"key":"PF1","label":"HELP"}, {"key":"PF3","label":"MENU"},
        {"key":"PF5","label":"REFRESH"}, {"key":"PF7","label":"UP"},
        {"key":"PF8","label":"DOWN"}, {"key":"PF12","label":"SIGNOFF"},
        {"key":"ENTER","label":"EXECUTE"}])

    def as_json(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "rows": self.rows,
                "fields": [f.as_json() for f in self.fields],
                "message": self.message, "pfkeys": self.pfkeys,
                "cursor": {"row":22,"col":15}, "commandLine": True}

def txt(row:int,col:int,text:str,color:str="green") -> dict[str, Any]:
    return {"row":row,"col":col,"text":str(text),"color":color}

def fld(id,label,row,col,length,value="",**kw):
    return FibsField(id,label,row,col,length,str(value),**kw)

def render_text(m: FibsMap) -> str:
    lines=[f"{m.message[:79]:<79}", f"{m.name[:8]:<8} {m.title[:68]:<68}", ""]
    for r in sorted(m.rows, key=lambda x:(x.get('row',0),x.get('col',0))):
        lines.append(str(r.get('text',''))[:79])
    if m.fields:
        lines.append("")
        for f in m.fields:
            if f.hidden: continue
            val=f.value or ("_"*min(f.length,12))
            prot="" if not f.protected else "  (PROT)"
            lines.append(f"{f.label:<22} {val}{prot}"[:79])
    while len(lines)<20: lines.append("")
    lines.append("COMMAND ===>")
    lines.append("PF1=HELP PF3=MENU PF5=REFRESH PF7=UP PF8=DOWN PF12=SIGNOFF")
    return "\n".join(lines)
