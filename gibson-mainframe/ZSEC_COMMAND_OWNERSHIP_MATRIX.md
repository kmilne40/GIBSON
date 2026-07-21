# zSecure command ownership matrix

| Command | Owner | Data source | Output |
|---|---|---|---|
| ZSEC EVENTS | zsecure_engine._zsec_events | SMF + audit | recent security events |
| ZSEC RARE | zsecure_engine._zsec_rare | SMF + audit filtered by rare terms | high-risk/rare events |
| ZSEC SUMMARY | zsecure_engine._zsec_summary | SMF + audit | counts by category |
| ZSEC SMF/SMF80 | zsecure_engine._zsec_smf_review | structured SMF writer | SMF list/filter |
| ZSEC RACFDS | zsecure_engine._zsec_racfds | RACFDB + events | RACFDS exposure |
| ZSEC OFFLINEHASH/HASHCRACK | zsecure_engine._zsec_offlinehash | RACFDS + events | hash extraction/cracking |
| ZSEC IND$FILE | zsecure_engine._zsec_indfile | indfile_history | IND$FILE transfers |
| ZSEC TRANSFERS | zsecure_engine._zsec_indfile(broad) | transfer/security events | transfer/exfil review |
