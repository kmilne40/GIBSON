# Gibson Mainframe Simulator — Master Documentation Index

---

## Project Overview

| File | Description |
|------|-------------|
| [CHANGELOG.md](CHANGELOG.md) | Project-wide changelog |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | High-level summary of what has been implemented |
| [IMPLEMENTATION_SCOPE_AND_NON_SCOPE.md](IMPLEMENTATION_SCOPE_AND_NON_SCOPE.md) | What is and is not in scope for the simulator |
| [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | Known limitations and gaps |
| [PORT_OWNERSHIP_REPORT.md](PORT_OWNERSHIP_REPORT.md) | Which service owns each port |
| [Gibson_Code_Remediation_Report_v2.md](Gibson_Code_Remediation_Report_v2.md) | Code remediation findings and fixes v2 |
| [FULL_REGRESSION_TEST_REPORT.md](FULL_REGRESSION_TEST_REPORT.md) | Full regression test results |
| [MANUAL_VALIDATION_SCRIPT.md](MANUAL_VALIDATION_SCRIPT.md) | Script used for manual validation runs |

---

## Technical Manual (`docs/manual/`)

| File | Description |
|------|-------------|
| [docs/manual/index.md](docs/manual/index.md) | Full technical manual (source-backed, all chapters) |
| [docs/manual/front-matter.md](docs/manual/front-matter.md) | Front matter, conventions, audience |
| [docs/manual/quick-start-guide.md](docs/manual/quick-start-guide.md) | Quick start — install, start, connect |
| [docs/manual/chapter-1-mainframe-and.md](docs/manual/chapter-1-mainframe-and.md) | Chapter 1: Mainframe architecture overview |
| [docs/manual/chapter-2-installation-startup.md](docs/manual/chapter-2-installation-startup.md) | Chapter 2: Installation and startup |
| [docs/manual/chapter-3-application.md](docs/manual/chapter-3-application.md) | Chapter 3: Application layer |
| [docs/manual/chapter-4-access-logon-mfa.md](docs/manual/chapter-4-access-logon-mfa.md) | Chapter 4: Access, logon, and MFA |
| [docs/manual/chapter-5-tso-ready.md](docs/manual/chapter-5-tso-ready.md) | Chapter 5: TSO READY prompt and commands |
| [docs/manual/chapter-6-racf-administration.md](docs/manual/chapter-6-racf-administration.md) | Chapter 6: RACF administration |
| [docs/manual/chapter-7-ispf-and-editor.md](docs/manual/chapter-7-ispf-and-editor.md) | Chapter 7: ISPF and the editor |
| [docs/manual/chapter-8-sdsf-jes-jcl-and.md](docs/manual/chapter-8-sdsf-jes-jcl-and.md) | Chapter 8: SDSF, JES, and JCL |
| [docs/manual/chapter-9-master-console-and.md](docs/manual/chapter-9-master-console-and.md) | Chapter 9: Master Console and OPERLOG |
| [docs/manual/chapter-10-cics-and-banking.md](docs/manual/chapter-10-cics-and-banking.md) | Chapter 10: CICS and banking transactions |
| [docs/manual/chapter-11-db2-and-sql.md](docs/manual/chapter-11-db2-and-sql.md) | Chapter 11: Db2 and SQL |
| [docs/manual/chapter-12-omvs-uss-and.md](docs/manual/chapter-12-omvs-uss-and.md) | Chapter 12: OMVS/USS shell |
| [docs/manual/chapter-13-ftp-tcp-ip-and.md](docs/manual/chapter-13-ftp-tcp-ip-and.md) | Chapter 13: FTP and TCP/IP |
| [docs/manual/chapter-14-rest-api.md](docs/manual/chapter-14-rest-api.md) | Chapter 14: REST API |
| [docs/manual/chapter-15-security-training.md](docs/manual/chapter-15-security-training.md) | Chapter 15: Security training labs |
| [docs/manual/chapter-16-instructor-guide.md](docs/manual/chapter-16-instructor-guide.md) | Chapter 16: Instructor guide |
| [docs/manual/acf2-security-model-and-gibson.md](docs/manual/acf2-security-model-and-gibson.md) | ACF2 security model as it relates to Gibson |
| [docs/manual/code-interpreters.md](docs/manual/code-interpreters.md) | REXX, JCL, COBOL, HLASM interpreter reference |
| [docs/manual/expanded-racf-security-labs.md](docs/manual/expanded-racf-security-labs.md) | Extended RACF lab exercises |

---

## Installation & Release Notes

| File | Description |
|------|-------------|
| [docs/installation.md](docs/installation.md) | v17 installation notes |
| [docs/release_v18.md](docs/release_v18.md) | v18 release — client, RACF, IND$FILE updates |
| [docs/release_v19_secure_vuln_modes.md](docs/release_v19_secure_vuln_modes.md) | v19 release — secure/vulnerable mode |
| [docs/release_v20_secure_tn3270_ansi_merged.md](docs/release_v20_secure_tn3270_ansi_merged.md) | v20 release — TN3270/ANSI merged |
| [docs/release_v20_tn3270_stability.md](docs/release_v20_tn3270_stability.md) | v20 TN3270 stability notes |
| [docs/release_v21_secure_entrypoint_interpreters.md](docs/release_v21_secure_entrypoint_interpreters.md) | v21 release — secure entrypoint and interpreters |
| [docs/CHANGELOG_CICS_UI_OMVS_LOGGING_RSS_LYNX_V1.md](docs/CHANGELOG_CICS_UI_OMVS_LOGGING_RSS_LYNX_V1.md) | Changelog: CICS UI, OMVS logging, RSS, Lynx v1 |
| [docs/CHANGELOG_R05_GEO_MAP_FIX_V1.md](docs/CHANGELOG_R05_GEO_MAP_FIX_V1.md) | Changelog: R05 geolocation map fix |
| [docs/CHANGELOG_VTAM_OMVS_TOOLING_V1.md](docs/CHANGELOG_VTAM_OMVS_TOOLING_V1.md) | Changelog: VTAM/OMVS tooling v1 |

---

## Security Modes & MFA

| File | Description |
|------|-------------|
| [docs/security_modes.md](docs/security_modes.md) | Overview of Gibson secure/vulnerable modes |
| [docs/secure_mode_cis_mapping.md](docs/secure_mode_cis_mapping.md) | Mapping of secure mode controls to CIS benchmarks |
| [docs/tls_secure_services.md](docs/tls_secure_services.md) | TLS configuration for secure services |
| [docs/mfa_mode.md](docs/mfa_mode.md) | MFA mode overview |
| [docs/mfa_pin_time_token.md](docs/mfa_pin_time_token.md) | MFA PIN + HHMM time-token model |

---

## Terminal / TN3270 / VTAM

| File | Description |
|------|-------------|
| [docs/ansi_terminal_mode.md](docs/ansi_terminal_mode.md) | ANSI/ASCII live terminal mode |
| [docs/tn3270_vtam_frontend.md](docs/tn3270_vtam_frontend.md) | v17 TN3270/VTAM front-end design |
| [docs/tn3270_client_compatibility.md](docs/tn3270_client_compatibility.md) | v18 TN3270 client compatibility |
| [docs/tn3270_hang_fix.md](docs/tn3270_hang_fix.md) | c3270 hang fix |
| [TERMINAL_KEY_MAPPING_IMPLEMENTATION.md](TERMINAL_KEY_MAPPING_IMPLEMENTATION.md) | Terminal key mapping implementation |
| [TERMINAL_SESSION_STABILITY_HARDENING.md](TERMINAL_SESSION_STABILITY_HARDENING.md) | Terminal session stability hardening |
| [PANEL_INPUT_HELPER_IMPLEMENTATION.md](PANEL_INPUT_HELPER_IMPLEMENTATION.md) | Panel input helper implementation |
| [PANEL_INPUT_HELPER_HARDENING.md](PANEL_INPUT_HELPER_HARDENING.md) | Panel input helper hardening |
| [PF_KEY_AUTO_SUBMIT_IMPLEMENTATION.md](PF_KEY_AUTO_SUBMIT_IMPLEMENTATION.md) | PF key auto-submit implementation |
| [docs/examples/ncat-gibson-aid-keys.md](docs/examples/ncat-gibson-aid-keys.md) | Sending AID/PF keys with ncat |
| [BASELINE_TERMINAL_KEY_HANDLING_ANALYSIS.md](BASELINE_TERMINAL_KEY_HANDLING_ANALYSIS.md) | Baseline analysis of terminal key handling |
| [TERMINAL_KEY_HANDLING_TEST_REPORT.md](TERMINAL_KEY_HANDLING_TEST_REPORT.md) | Terminal key handling test report |
| [TERMINAL_CONNECTIVITY_STABILITY_TEST_REPORT.md](TERMINAL_CONNECTIVITY_STABILITY_TEST_REPORT.md) | Terminal connectivity stability test report |
| [PF_KEY_STABILITY_TEST_REPORT.md](PF_KEY_STABILITY_TEST_REPORT.md) | PF key stability test report |

---

## ISPF / DSLIST / Editor

| File | Description |
|------|-------------|
| [ISPF_COORDINATE_CONTRACT.md](ISPF_COORDINATE_CONTRACT.md) | ISPF coordinate system contract |
| [ISPF_RENDER_WIDTH_GUARDS.md](ISPF_RENDER_WIDTH_GUARDS.md) | Render width guard implementation |
| [ISPF_DSLIST_REGRESSION_FIX.md](ISPF_DSLIST_REGRESSION_FIX.md) | DSLIST regression fix in ISPF |
| [DSLIST_COMMAND_FIELD_FIX.md](DSLIST_COMMAND_FIELD_FIX.md) | DSLIST command field fix |
| [EDITOR_CURSOR_WRAP_FIX.md](EDITOR_CURSOR_WRAP_FIX.md) | Editor cursor / no-wrap fix |
| [docs/CHAPTER7_8_GIBSON_COMMAND_MAPPING.md](docs/CHAPTER7_8_GIBSON_COMMAND_MAPPING.md) | Chapter 7/8 ISPF command mapping reference |
| [docs/TSO_VIEW_IMPLEMENTATION_GUIDE.md](docs/TSO_VIEW_IMPLEMENTATION_GUIDE.md) | TSO VIEW command implementation guide |
| [ISPF_COORDINATE_BASELINE.md](ISPF_COORDINATE_BASELINE.md) | Baseline snapshot of ISPF coordinate system |
| [DSLIST_LAYOUT_BASELINE.md](DSLIST_LAYOUT_BASELINE.md) | DSLIST layout baseline |
| [EDITOR_WRAP_BASELINE.md](EDITOR_WRAP_BASELINE.md) | Editor wrap baseline |
| [ISPF_COORDINATE_TEST_REPORT.md](ISPF_COORDINATE_TEST_REPORT.md) | ISPF coordinate test report |
| [ISPF_STABILITY_TEST_REPORT.md](ISPF_STABILITY_TEST_REPORT.md) | ISPF stability test report |
| [DSLIST_STABILITY_TEST_REPORT.md](DSLIST_STABILITY_TEST_REPORT.md) | DSLIST stability test report |
| [EDITOR_WRAP_TEST_REPORT.md](EDITOR_WRAP_TEST_REPORT.md) | Editor wrap test report |

---

## IND$FILE Transfer

| File | Description |
|------|-------------|
| [INDFILE_IMPLEMENTATION_PLAN.md](INDFILE_IMPLEMENTATION_PLAN.md) | IND$FILE implementation plan |
| [INDFILE_COMMAND_MODE_IMPLEMENTATION.md](INDFILE_COMMAND_MODE_IMPLEMENTATION.md) | IND$FILE command-mode implementation |
| [INDFILE_COMMAND_MODE_HARDENING.md](INDFILE_COMMAND_MODE_HARDENING.md) | IND$FILE command-mode hardening |
| [INDFILE_NATIVE_TRANSFER_IMPLEMENTATION.md](INDFILE_NATIVE_TRANSFER_IMPLEMENTATION.md) | IND$FILE native transfer compatibility |
| [INDFILE_X3270_C3270_RESEARCH.md](INDFILE_X3270_C3270_RESEARCH.md) | x3270/c3270/s3270 IND$FILE research |
| [RACFDS_IND_FILE_BASELINE_ANALYSIS.md](RACFDS_IND_FILE_BASELINE_ANALYSIS.md) | RACFDS and IND$FILE baseline analysis |
| [TN3270_INDFILE_NATIVE_TRANSFER_DIAGNOSTICS.md](TN3270_INDFILE_NATIVE_TRANSFER_DIAGNOSTICS.md) | TN3270/IND$FILE native transfer diagnostics |
| [X3270_C3270_COMPATIBILITY_REPORT.md](X3270_C3270_COMPATIBILITY_REPORT.md) | x3270/c3270 compatibility report |
| [X3270_C3270_NATIVE_TRANSFER_LIMITATIONS.md](X3270_C3270_NATIVE_TRANSFER_LIMITATIONS.md) | x3270/c3270 native transfer limitations |
| [docs/indfile_transfer.md](docs/indfile_transfer.md) | v18 IND$FILE transfer overview |
| [BASELINE_INDFILE_COMMAND_MODE_ANALYSIS.md](BASELINE_INDFILE_COMMAND_MODE_ANALYSIS.md) | Baseline IND$FILE command-mode analysis |
| [INDFILE_COMMAND_MODE_TEST_REPORT.md](INDFILE_COMMAND_MODE_TEST_REPORT.md) | IND$FILE command-mode test report |
| [INDFILE_TEST_REPORT.md](INDFILE_TEST_REPORT.md) | IND$FILE test report |
| [TN3270_NATIVE_TRANSFER_DIAGNOSTICS_REPORT.md](TN3270_NATIVE_TRANSFER_DIAGNOSTICS_REPORT.md) | TN3270 native transfer diagnostics report |
| [S3270_SCRIPTED_INDFILE_VALIDATION.md](S3270_SCRIPTED_INDFILE_VALIDATION.md) | s3270 scripted IND$FILE validation |
| [S3270_VALIDATION_REPORT.md](S3270_VALIDATION_REPORT.md) | s3270 validation report |

---

## RACF / Security Database

| File | Description |
|------|-------------|
| [RACF_DATABASE_MATERIALISATION_IMPLEMENTATION.md](RACF_DATABASE_MATERIALISATION_IMPLEMENTATION.md) | RACF database materialisation implementation |
| [RACFDS_BASELINE_ANALYSIS.md](RACFDS_BASELINE_ANALYSIS.md) | RACFDS baseline analysis |
| [RACFDS_GACFDB_MAPPING_RESEARCH.md](RACFDS_GACFDB_MAPPING_RESEARCH.md) | GACF.DB to RACFDS field mapping research |
| [RACFDS_LEGACY_DES_POLICY_DESIGN.md](RACFDS_LEGACY_DES_POLICY_DESIGN.md) | Legacy DES policy design for RACFDS |
| [RACFDS_DES_MATERIALISATION_IMPLEMENTATION.md](RACFDS_DES_MATERIALISATION_IMPLEMENTATION.md) | RACFDS DES materialisation implementation |
| [RACFDS_LEGACY_DES_FIX_IMPLEMENTATION.md](RACFDS_LEGACY_DES_FIX_IMPLEMENTATION.md) | RACFDS legacy-DES fix implementation |
| [LEGACY_RACF_DES_HASH_RESEARCH.md](LEGACY_RACF_DES_HASH_RESEARCH.md) | Legacy RACF DES hash research |
| [LEGACY_RACF_DES_IMPLEMENTATION.md](LEGACY_RACF_DES_IMPLEMENTATION.md) | Legacy RACF DES implementation |
| [IRRDBU00_SIMULATION_IMPLEMENTATION.md](IRRDBU00_SIMULATION_IMPLEMENTATION.md) | IRRDBU00 unload simulation |
| [SYS1_HLQ_DATASET_CATALOG_IMPLEMENTATION.md](SYS1_HLQ_DATASET_CATALOG_IMPLEMENTATION.md) | SYS1 HLQ dataset catalog implementation |
| [docs/racf_dataset_access.md](docs/racf_dataset_access.md) | v18 RACF dataset access controls |
| [docs/racf_user_revocation.md](docs/racf_user_revocation.md) | RACF user revocation and deletion |
| [docs/network_fingerprinting.md](docs/network_fingerprinting.md) | Network fingerprinting enhancement |
| [docs/fingerprinting_removed.md](docs/fingerprinting_removed.md) | v20 runtime fingerprinting removal |
| [RACFDS_DES_MATERIALISATION_TEST_REPORT.md](RACFDS_DES_MATERIALISATION_TEST_REPORT.md) | RACFDS DES materialisation test report |
| [RACFDS_HASH_TEST_REPORT.md](RACFDS_HASH_TEST_REPORT.md) | RACFDS hash test report |
| [RACFDS_HASH_FORENSICS_TEST_REPORT.md](RACFDS_HASH_FORENSICS_TEST_REPORT.md) | RACFDS hash forensics test report |
| [RACFBLOCKER_REGRESSION_REPORT.md](RACFBLOCKER_REGRESSION_REPORT.md) | RACFBLOCKER regression report |

---

## racf2john / Password Cracking Simulation

| File | Description |
|------|-------------|
| [OMVS_RACF2JOHN_IMPLEMENTATION.md](OMVS_RACF2JOHN_IMPLEMENTATION.md) | OMVS racf2john implementation |
| [RACF2JOHN_JOHN_COMPATIBILITY_RESEARCH.md](RACF2JOHN_JOHN_COMPATIBILITY_RESEARCH.md) | racf2john / john compatibility research |
| [RACF2JOHN_JOHN_IMPLEMENTATION.md](RACF2JOHN_JOHN_IMPLEMENTATION.md) | racf2john / john implementation |
| [RACF2JOHN_ENRICHMENT_IMPLEMENTATION.md](RACF2JOHN_ENRICHMENT_IMPLEMENTATION.md) | racf2john enrichment implementation |
| [OMVS_JOHN_SIM_IMPLEMENTATION.md](OMVS_JOHN_SIM_IMPLEMENTATION.md) | OMVS john simulator implementation |
| [JOHN_SIM_ENRICHMENT_IMPLEMENTATION.md](JOHN_SIM_ENRICHMENT_IMPLEMENTATION.md) | john simulator enrichment implementation |
| [RACF2JOHN_JOHN_TEST_REPORT.md](RACF2JOHN_JOHN_TEST_REPORT.md) | racf2john / john test report |

---

## SMF / Forensics / zSecure

| File | Description |
|------|-------------|
| [SMF_SCHEMA_REFERENCE.md](SMF_SCHEMA_REFERENCE.md) | SMF record schema reference |
| [SMF_CORE_ENGINE_IMPLEMENTATION.md](SMF_CORE_ENGINE_IMPLEMENTATION.md) | SMF core engine implementation |
| [SMF_RECORDING_MODE_IMPLEMENTATION.md](SMF_RECORDING_MODE_IMPLEMENTATION.md) | SMF recording mode implementation |
| [SMF_DATA_SOURCE_CONSISTENCY_IMPLEMENTATION.md](SMF_DATA_SOURCE_CONSISTENCY_IMPLEMENTATION.md) | SMF data-source consistency implementation |
| [SMF_DB2_API_NETWORK_IMPLEMENTATION.md](SMF_DB2_API_NETWORK_IMPLEMENTATION.md) | SMF Db2/API/network record implementation |
| [SMF80_RACF_IMPLEMENTATION.md](SMF80_RACF_IMPLEMENTATION.md) | SMF type 80 RACF record implementation |
| [SMF80_PASSTICKET_IMPLEMENTATION.md](SMF80_PASSTICKET_IMPLEMENTATION.md) | SMF type 80 PassTicket implementation |
| [SMF110_CICS_IMPLEMENTATION.md](SMF110_CICS_IMPLEMENTATION.md) | SMF type 110 CICS implementation |
| [ICSF_MASTER_KEY_REFRESH_SMF_IMPLEMENTATION.md](ICSF_MASTER_KEY_REFRESH_SMF_IMPLEMENTATION.md) | ICSF master key refresh SMF implementation |
| [RACFDS_SMF_FORENSICS_IMPLEMENTATION.md](RACFDS_SMF_FORENSICS_IMPLEMENTATION.md) | RACFDS SMF forensics implementation |
| [RACFDS_SMF_MASTER_CONSOLE_CTI_IMPLEMENTATION.md](RACFDS_SMF_MASTER_CONSOLE_CTI_IMPLEMENTATION.md) | RACFDS SMF / Master Console / CTI implementation |
| [M4M_SMF_FORENSIC_SCENARIOS_IMPLEMENTATION.md](M4M_SMF_FORENSIC_SCENARIOS_IMPLEMENTATION.md) | M4M SMF forensic scenario implementation |
| [SECURITY_PERIOD_SUMMARY_IMPLEMENTATION.md](SECURITY_PERIOD_SUMMARY_IMPLEMENTATION.md) | Security period summary implementation |
| [ZSECURE_REALISM_UPLIFT.md](ZSECURE_REALISM_UPLIFT.md) | zSecure realism uplift |
| [ZSECURE_SMF_INTEGRATION_IMPLEMENTATION.md](ZSECURE_SMF_INTEGRATION_IMPLEMENTATION.md) | zSecure SMF integration implementation |
| [ZSEC_HANDLER_SEPARATION_IMPLEMENTATION.md](ZSEC_HANDLER_SEPARATION_IMPLEMENTATION.md) | zSecure handler separation implementation |
| [ZSEC_COMMAND_OWNERSHIP_MATRIX.md](ZSEC_COMMAND_OWNERSHIP_MATRIX.md) | zSecure command ownership matrix |
| [RACFDS_ZSECURE_IMPLEMENTATION.md](RACFDS_ZSECURE_IMPLEMENTATION.md) | RACFDS zSecure implementation |
| [IBM_SMF_ZSECURE_RESEARCH.md](IBM_SMF_ZSECURE_RESEARCH.md) | IBM SMF and zSecure research notes |
| [SMF_MANX_LOGSTREAM_RESEARCH.md](SMF_MANX_LOGSTREAM_RESEARCH.md) | SMF MANx and logstream research |
| [BASELINE_ZSEC_SMF_OUTPUT_AUDIT.md](BASELINE_ZSEC_SMF_OUTPUT_AUDIT.md) | Baseline zSecure/SMF output audit |
| [SMF_FORENSICS_BASELINE_ANALYSIS.md](SMF_FORENSICS_BASELINE_ANALYSIS.md) | SMF forensics baseline analysis |
| [docs/OMVS_SECURITY_TOOL_LOGGING_IMPLEMENTATION.md](docs/OMVS_SECURITY_TOOL_LOGGING_IMPLEMENTATION.md) | OMVS security tool event logging implementation |
| [SMF_FORENSICS_TEST_REPORT.md](SMF_FORENSICS_TEST_REPORT.md) | SMF forensics test report |
| [SMF_MANX_LOGSTREAM_TEST_REPORT.md](SMF_MANX_LOGSTREAM_TEST_REPORT.md) | SMF MANx / logstream test report |
| [ZSEC_SMF_CORRECTNESS_TEST_REPORT.md](ZSEC_SMF_CORRECTNESS_TEST_REPORT.md) | zSecure / SMF correctness test report |
| [ZSECURE_RACFDS_TEST_REPORT.md](ZSECURE_RACFDS_TEST_REPORT.md) | zSecure RACFDS test report |
| [ZSECURE_TEST_REPORT.md](ZSECURE_TEST_REPORT.md) | zSecure test report |
| [SMF_ZSECURE_CTI_MASTER_CONSOLE_EVIDENCE.md](SMF_ZSECURE_CTI_MASTER_CONSOLE_EVIDENCE.md) | SMF, zSecure, CTI, and Master Console evidence |

---

## CTI / Alerting / Master Console

| File | Description |
|------|-------------|
| [CTI_AUTH_IMPLEMENTATION.md](CTI_AUTH_IMPLEMENTATION.md) | CTI authentication implementation |
| [CTI_MANAGEMENT_IMPLEMENTATION.md](CTI_MANAGEMENT_IMPLEMENTATION.md) | CTI management implementation |
| [CTI_SMF_TIMELINE_INTEGRATION.md](CTI_SMF_TIMELINE_INTEGRATION.md) | CTI / SMF timeline integration |
| [RACFDS_CTI_ALERTING_IMPLEMENTATION.md](RACFDS_CTI_ALERTING_IMPLEMENTATION.md) | RACFDS CTI alerting implementation |
| [RACFDS_MASTER_CONSOLE_ALERTING_IMPLEMENTATION.md](RACFDS_MASTER_CONSOLE_ALERTING_IMPLEMENTATION.md) | RACFDS Master Console alerting implementation |
| [CTI_AUTH_MANAGEMENT_TEST_REPORT.md](CTI_AUTH_MANAGEMENT_TEST_REPORT.md) | CTI auth and management test report |

---

## OMVS / USS Security Tools

| File | Description |
|------|-------------|
| [docs/OMVS_NMAP_IMPLEMENTATION_GUIDE.md](docs/OMVS_NMAP_IMPLEMENTATION_GUIDE.md) | OMVS nmap implementation guide |
| [docs/OMVS_NIKTO_GUIDE.md](docs/OMVS_NIKTO_GUIDE.md) | OMVS Nikto guide |
| [docs/OMVS_CICSPWN_IMPLEMENTATION_GUIDE.md](docs/OMVS_CICSPWN_IMPLEMENTATION_GUIDE.md) | OMVS CICSPWN implementation guide |
| [docs/OMVS_DB2CONNECT_GUIDE.md](docs/OMVS_DB2CONNECT_GUIDE.md) | OMVS Db2 Connect guide |
| [docs/OMVS_FTP_JES_ANON_GUIDE.md](docs/OMVS_FTP_JES_ANON_GUIDE.md) | OMVS FTP/JES anonymous access guide |
| [docs/OMVS_OSINT_TOOLS_GUIDE.md](docs/OMVS_OSINT_TOOLS_GUIDE.md) | OMVS OSINT tools guide |
| [docs/OMVS_TASK_MANAGER_GUIDE.md](docs/OMVS_TASK_MANAGER_GUIDE.md) | OMVS task manager guide |
| [docs/OMVS_TSHOCKER_CATSO_GUIDE.md](docs/OMVS_TSHOCKER_CATSO_GUIDE.md) | OMVS TShOcker/CATSO guide |
| [docs/UPLOADED_TOOLS_ANALYSIS_SUMMARY.md](docs/UPLOADED_TOOLS_ANALYSIS_SUMMARY.md) | Uploaded tools analysis summary |
| [docs/VTAM_OMVS_TOOLING_CODE_ANALYSIS.md](docs/VTAM_OMVS_TOOLING_CODE_ANALYSIS.md) | VTAM/OMVS tooling code analysis |
| [docs/VTAM_OMVS_TOOLING_IMPACT_MATRIX.md](docs/VTAM_OMVS_TOOLING_IMPACT_MATRIX.md) | VTAM/OMVS tooling impact matrix |
| [docs/VTAM_OMVS_TOOLING_RESEARCH_MATRIX.md](docs/VTAM_OMVS_TOOLING_RESEARCH_MATRIX.md) | VTAM/OMVS tooling research matrix |
| [docs/VTAM_OMVS_TOOLING_RESEARCH_REVALIDATION.md](docs/VTAM_OMVS_TOOLING_RESEARCH_REVALIDATION.md) | VTAM/OMVS tooling research revalidation |
| [docs/VTAM_OMVS_TOOLING_TEST_PLAN.md](docs/VTAM_OMVS_TOOLING_TEST_PLAN.md) | VTAM/OMVS tooling test plan |
| [docs/OMVS_TOOLING_STATIC_SECURITY_CHECKS.md](docs/OMVS_TOOLING_STATIC_SECURITY_CHECKS.md) | OMVS tooling static security checks |

---

## Language Runtimes (REXX, JCL, COBOL, HLASM)

| File | Description |
|------|-------------|
| [REXX_IMPLEMENTATION_NOTES.md](REXX_IMPLEMENTATION_NOTES.md) | REXX implementation notes |
| [JCL_JES_IMPLEMENTATION_NOTES.md](JCL_JES_IMPLEMENTATION_NOTES.md) | JCL/JES implementation notes |
| [COBOL_IMPLEMENTATION_NOTES.md](COBOL_IMPLEMENTATION_NOTES.md) | COBOL implementation notes |
| [HLASM_IMPLEMENTATION_NOTES.md](HLASM_IMPLEMENTATION_NOTES.md) | HLASM implementation notes |
| [IBM_LANGUAGE_RUNTIME_RESEARCH.md](IBM_LANGUAGE_RUNTIME_RESEARCH.md) | IBM language runtime research notes |
| [LANGUAGE_COMMON_RUNTIME_IMPLEMENTATION.md](LANGUAGE_COMMON_RUNTIME_IMPLEMENTATION.md) | Common runtime implementation (shared layer) |
| [LANGUAGE_INTEGRATION_IMPLEMENTATION.md](LANGUAGE_INTEGRATION_IMPLEMENTATION.md) | Language integration implementation |
| [CURRENT_INTERPRETER_CAPABILITY_MATRIX.md](CURRENT_INTERPRETER_CAPABILITY_MATRIX.md) | Current interpreter capability matrix |
| [docs/interpreters_rexx_jcl_cobol.md](docs/interpreters_rexx_jcl_cobol.md) | REXX, JCL/JES, and COBOL simulation reference |
| [LANGUAGE_RUNTIME_BASELINE_ANALYSIS.md](LANGUAGE_RUNTIME_BASELINE_ANALYSIS.md) | Language runtime baseline analysis |
| [LANGUAGE_RUNTIME_TEST_REPORT.md](LANGUAGE_RUNTIME_TEST_REPORT.md) | Language runtime test report |

---

## z/VM CP/CMS Simulation

| File | Description |
|------|-------------|
| [docs/zvm_simulation.md](docs/zvm_simulation.md) | z/VM CP/CMS simulator — connecting, screen flow, all CP and CMS commands, PF key map, logging |

---

## RSS / Lynx / ICSF / Network Features

| File | Description |
|------|-------------|
| [RSS_PERFORMANCE_IMPLEMENTATION.md](RSS_PERFORMANCE_IMPLEMENTATION.md) | RSS performance implementation |
| [RSS_SECURITY_REVIEW.md](RSS_SECURITY_REVIEW.md) | RSS security review |
| [docs/TSO_RSS_READER_IMPLEMENTATION.md](docs/TSO_RSS_READER_IMPLEMENTATION.md) | TSO RSS reader — live feed via CTI/RSS backend |
| [docs/LYNX_BROWSER_IMPLEMENTATION.md](docs/LYNX_BROWSER_IMPLEMENTATION.md) | Gibson Lynx text browser implementation |
| [docs/icsf_simulation.md](docs/icsf_simulation.md) | ICSF (cryptographic services) simulation |
| [docs/HOSTS_TXT_TARGET_MODEL.md](docs/HOSTS_TXT_TARGET_MODEL.md) | HOSTS.TXT scoping/target model |
| [docs/HOME_NETWORK_LIVINGSTON_OVERRIDE_IMPLEMENTATION.md](docs/HOME_NETWORK_LIVINGSTON_OVERRIDE_IMPLEMENTATION.md) | Livingston home network override implementation |
| [docs/PUBLIC_IP_4_180_9_35_GEO_FIX.md](docs/PUBLIC_IP_4_180_9_35_GEO_FIX.md) | Public IP geolocation fix for 4.180.9.35 |
| [docs/R05_GEO_MAP_FIX_IMPLEMENTATION_TRACEABILITY.md](docs/R05_GEO_MAP_FIX_IMPLEMENTATION_TRACEABILITY.md) | R05 geo map fix implementation traceability |
| [docs/R05_GEO_MAP_FIX_STATIC_SECURITY_CHECKS.md](docs/R05_GEO_MAP_FIX_STATIC_SECURITY_CHECKS.md) | R05 geo map fix static security checks |
| [RSS_PERFORMANCE_TEST_REPORT.md](RSS_PERFORMANCE_TEST_REPORT.md) | RSS performance test report |

---

## Traceability & Static Security Checks

| File | Description |
|------|-------------|
| [docs/CICS_UI_OMVS_LOGGING_RSS_LYNX_IMPLEMENTATION_TRACEABILITY.md](docs/CICS_UI_OMVS_LOGGING_RSS_LYNX_IMPLEMENTATION_TRACEABILITY.md) | Traceability: CICS, OMVS logging, RSS, Lynx |
| [docs/STATIC_SECURITY_CHECKS_CICS_UI_OMVS_LOGGING_RSS_LYNX.md](docs/STATIC_SECURITY_CHECKS_CICS_UI_OMVS_LOGGING_RSS_LYNX.md) | Static security checks: CICS, OMVS, RSS, Lynx |
| [docs/OMVS_TOOLING_STATIC_SECURITY_CHECKS.md](docs/OMVS_TOOLING_STATIC_SECURITY_CHECKS.md) | OMVS tooling static security checks |
