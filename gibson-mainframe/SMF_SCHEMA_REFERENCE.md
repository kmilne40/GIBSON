# SMF Schema Reference

Every structured record contains:

- record_id
- record_type
- subtype
- version
- timestamp
- system_id
- sysplex
- lpar
- userid
- jobname
- subsystem
- source_component
- correlation_id
- summary
- raw_fields

Supported initial record families:

- Type 7: SMF data lost / evidence gap training
- Type 30: job, TSO, JES and step activity
- Type 80: RACF and PassTicket security evidence
- Type 92: USS file/process activity
- Type 101/102: Db2 accounting/audit-style evidence
- Type 110: CICS transaction monitoring evidence
- Type 119: TCP/IP, TN3270, FTP and network evidence
- Type 123: API / z/OS Connect-style request evidence
- ICSF simulated structured record: master key refresh evidence
