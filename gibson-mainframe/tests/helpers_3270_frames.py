from gibson.net.datastream3270 import encode_3270_address, aid_name_to_byte, encode_ebcdic_field

SBA=0x11
IAC_EOR=b"\xff\xef"

def frame_aid(aid_name: str) -> bytes:
    b = aid_name_to_byte(aid_name)
    assert b is not None
    return bytes([b]) + encode_3270_address(0) + IAC_EOR

def frame_pf3(): return frame_aid('PF3')
def frame_pf7(): return frame_aid('PF7')
def frame_pf8(): return frame_aid('PF8')
def frame_tab(): return b"\t"
def frame_cursor(row:int, col:int) -> bytes: return bytes([0x7d]) + encode_3270_address((row-1)*80+(col-1)) + IAC_EOR

def frame_enter_with_field(address:int, value:str, *, ebcdic: bool=False) -> bytes:
    return frame_enter_with_fields({address:value}, ebcdic=ebcdic)

def frame_enter_with_fields(mapping, *, ebcdic: bool=False) -> bytes:
    pkt=bytearray([0x7d])
    pkt.extend(encode_3270_address(0))
    for address, value in mapping.items():
        pkt.append(SBA); pkt.extend(encode_3270_address(int(address)))
        pkt.extend(encode_ebcdic_field(str(value)) if ebcdic else str(value).encode('ascii','ignore'))
    pkt.extend(IAC_EOR)
    return bytes(pkt)
