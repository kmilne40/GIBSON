from gibson.apps.fibs_training.lab_catalog import list_labs


def test_every_lab_has_beginner_educational_sections():
    for lab in list_labs():
        assert len(lab.beginner_explanation) > 40
        assert len(lab.why_it_matters) > 40
        assert lab.attacker_goal
        assert lab.defender_view
        assert 'CICS transaction' in lab.glossary
        assert len(lab.instructor_notes) >= 3
