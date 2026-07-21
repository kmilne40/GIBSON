from __future__ import annotations

import html
from typing import Iterable

from gibson.apps.dvca.models import Field, Screen


def _classes(f: Field, reveal_hidden: bool, show_sfe: bool) -> str:
    classes = ["field"]
    classes.append("field-protected" if f.protected else "field-unprotected")
    if f.hidden:
        classes.append("field-hidden-revealed" if reveal_hidden else "field-hidden")
    if f.numeric:
        classes.append("field-numeric")
    if f.mdt:
        classes.append("field-mdt")
    if f.fset:
        classes.append("field-fset")
    if f.modified:
        classes.append("field-modified")
    if show_sfe:
        classes.append("field-sfe")
    return " ".join(classes)


def field_badges(f: Field) -> list[str]:
    badges: list[str] = []
    if f.protected:
        badges.append("PROT")
    if f.hidden:
        badges.append("HIDDEN")
    if f.numeric:
        badges.append("NUM")
    if f.mdt:
        badges.append("MDT")
    if f.fset:
        badges.append("FSET")
    if f.modified:
        badges.append("MOD")
    return badges


def render_terminal_html(screen: Screen, *, reveal_hidden: bool = False, show_fields: bool = False, show_sfe: bool = False) -> str:
    plain = screen.render(reveal_hidden=reveal_hidden, show_fields=show_fields)
    rows = plain.splitlines()
    field_by_row: dict[int, list[Field]] = {}
    for f in screen.fields:
        field_by_row.setdefault(f.row, []).append(f)
    output: list[str] = []
    for row_no, row in enumerate(rows, 1):
        fields = sorted(field_by_row.get(row_no, []), key=lambda x: x.col)
        cursor = 1
        pieces: list[str] = []
        for f in fields:
            start = max(1, f.col)
            end = start + max(0, f.length)
            if start > cursor:
                pieces.append(html.escape(row[cursor - 1:start - 1]))
            val = f.render_value(reveal_hidden=reveal_hidden)
            label = ",".join(field_badges(f))
            title = f"{f.name} row={f.row} col={f.col} len={f.length} {label}"
            if f.hidden and not reveal_hidden:
                span_text = html.escape(row[start - 1:end - 1])
            else:
                span_text = html.escape(val)
            pieces.append(
                f"<span class='{_classes(f, reveal_hidden, show_sfe)}' "
                f"data-field='{html.escape(f.name)}' data-row='{f.row}' "
                f"data-col='{f.col}' data-length='{f.length}' title='{html.escape(title)}'>"
                f"{span_text}</span>"
            )
            cursor = max(cursor, end)
        if cursor <= len(row):
            pieces.append(html.escape(row[cursor - 1:]))
        output.append("".join(pieces))
    return "\n".join(output)


def field_table_rows(fields: Iterable[Field], *, reveal_hidden: bool = False) -> str:
    rows: list[str] = []
    for f in fields:
        attrs = " ".join(f"<span class='badge'>{html.escape(b)}</span>" for b in field_badges(f))
        value = f.render_value(reveal_hidden=reveal_hidden)
        rows.append(
            "<tr>"
            f"<td>{html.escape(f.name)}</td><td>{f.row}</td><td>{f.col}</td>"
            f"<td>{f.length}</td><td><code>{html.escape(value)}</code></td>"
            f"<td>{attrs}</td><td>{html.escape(f.source)}</td>"
            "</tr>"
        )
    return "".join(rows)
