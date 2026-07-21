from pathlib import Path


def test_removed_ports_not_reintroduced_in_runtime_sources():
    bad = []
    for path in Path("gibson").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "listen(('0.0.0.0', 3270" in text or "port=3270" in text:
            bad.append(str(path))
        if "React8999" in text or "/api/v1/ui8999" in text:
            bad.append(str(path))
    assert not bad
