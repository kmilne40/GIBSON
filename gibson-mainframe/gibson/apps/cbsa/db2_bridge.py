from .store import get_cbsa_store
from .vuln_sql import sqli_search

def catalog(state): return get_cbsa_store(state).tables()
def metadata(state): return get_cbsa_store(state).metadata()
def call_vuln_account_search(state, arg): return sqli_search(get_cbsa_store(state), arg, "DB2")
