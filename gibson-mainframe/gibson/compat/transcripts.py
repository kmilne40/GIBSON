"""Stable externally-visible strings used by legacy tooling.

Security-testing tools such as the supplied nmap-sim.py enumerate users by
matching exact strings. Keep these constants stable even when internal code is
refactored.
"""
PROMPT_LOGON_TYPE = "Logon Type: "
PROMPT_ENTER_USERID = "IKJ56700A ENTER USERID : "
PROMPT_PASSWORD = "ENTER CURRENT PASSWORD FOR {user}-"
PROMPT_READY = "READY"
PROMPT_TSO = ""
MSG_BAD_LOGON_TYPE = "Invalid logon type. Please try again."
MSG_NO_TSO = "IKJ56420I USERID ({user}) NOT AUTHORIZED FOR TSO:- RE-ENTER -"
MSG_PASSWORD_INCORRECT = "PASSWORD INCORRECT"
MSG_GOODBYE = "Goodbye!"
MSG_INSUFFICIENT = "INSUFFICIENT ACCESS."
