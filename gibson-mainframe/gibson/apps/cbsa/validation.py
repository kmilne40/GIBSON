from decimal import Decimal, InvalidOperation

def valid_amount(v):
    try: return Decimal(str(v))
    except Exception: raise ValueError("INVALID AMOUNT")

def require(value, name):
    if value is None or str(value).strip()=="": raise ValueError(f"{name} REQUIRED")
    return str(value).strip()
