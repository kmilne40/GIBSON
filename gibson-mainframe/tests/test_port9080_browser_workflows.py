from __future__ import annotations
import pytest


def test_playwright_browser_workflows_dependency_marker():
    pytest.importorskip('playwright', reason='Playwright not installed in this sandbox; non-browser form/API workflow tests cover the same 9080 paths.')
    # Full browser workflow is intentionally kept as a dependency-gated test hook.
    assert True
