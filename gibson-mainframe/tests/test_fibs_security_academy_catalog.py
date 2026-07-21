from gibson.apps.fibs_training.lab_catalog import list_labs, get_lab


def test_security_academy_catalog_has_complete_labs():
    labs = list_labs()
    assert len(labs) >= 11
    slugs = {l.slug for l in labs}
    assert {"sqli","idor","mass-assignment","weak-auth","verbose-errors","business-logic","method-override","excessive-data","jwt","oauth","cobol-buffer-overflow"} <= slugs
    original = {"sqli","idor","mass-assignment","weak-auth","verbose-errors","business-logic","method-override","excessive-data","jwt","oauth","cobol-buffer-overflow"}
    for lab in labs:
        assert lab.title and lab.summary and lab.category
        assert len(lab.learning_objectives) >= 3
        assert len(lab.hints) >= 3
        if lab.slug in original:
            assert len(lab.knowledge_checks) >= 3
            assert "CICS" in " ".join(lab.architecture_nodes + list(lab.backend_mapping.values()))
            assert any("SMF" in e for e in lab.evidence_targets) or lab.slug in {"excessive-data"}
            assert lab.solution.get("payload")


def test_sqli_lab_has_mainframe_mapping():
    lab = get_lab("sqli")
    assert lab is not None
    text = " ".join(lab.backend_mapping.values())
    assert "FIBS-TELLER-SEARCH" in text
    assert "CBSA.ACCOUNT" in text
    assert "SMF102" in text
