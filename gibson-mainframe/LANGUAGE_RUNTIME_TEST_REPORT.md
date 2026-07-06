# Language Runtime Test Report

## Static compile

`python -m compileall -q gibson` passed.

## Targeted language/runtime tests

`pytest -q tests/test_core.py tests/test_language_cobol_runtime.py tests/test_language_jcl_parser.py tests/test_language_jcl_jes_execution.py tests/test_language_rexx_core.py tests/test_language_hlasm_runtime.py tests/test_language_integration_tso_jes.py`

Result: `14 passed`.

## Broader targeted regression suite

`pytest -q tests/test_core.py tests/test_book_enhancements.py tests/test_racfblocker_command_ownership.py tests/test_v5_pin_autotick_dvcapin_welcome.py tests/test_master_console.py tests/test_app8080_dvca_router.py tests/test_cbsa_integration.py tests/test_no_removed_port_resurrection.py tests/test_port_3270_removed.py tests/test_cti_rss_article_reader.py tests/test_dvca_cics_hack_commands.py tests/test_language_cobol_runtime.py tests/test_language_jcl_parser.py tests/test_language_jcl_jes_execution.py tests/test_language_rexx_core.py tests/test_language_hlasm_runtime.py tests/test_language_integration_tso_jes.py`

Result: `41 passed`.

## Full pytest

A full `pytest -q -x` was attempted. It did not reach a failure before sandbox timeout after progressing beyond the previously identified stale DVCA legacy test failure. The full suite is large and still requires an unconstrained local run.
