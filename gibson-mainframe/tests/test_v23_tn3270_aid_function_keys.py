from __future__ import annotations

import socket
import threading

from gibson.net.telnet3270 import normalise_client_input
from gibson.render.aid_keys import command_from_key, extract_ansi_function_key, normalise_aid_alias
from gibson.render.input import SocketInputDriver


def test_textual_aid_aliases_map_to_gibson_commands():
    cases = {
        "PF1": ("PF1", "HELP"),
        "PF3": ("PF3", "END"),
        "F3": ("F3", "END"),
        "/PF3": ("PF3", "END"),
        ":PF3": ("PF3", "END"),
        "AID PF3": ("PF3", "END"),
        "PF7": ("PF7", "UP"),
        "PF8": ("PF8", "DOWN"),
        "PF10": ("PF10", "LEFT"),
        "PF11": ("PF11", "RIGHT"),
        "PF12": ("PF12", "CANCEL"),
        "ENTER": ("ENTER", "ENTER"),
        "CLEAR": ("CLEAR", "CLEAR"),
        "PA1": ("PA1", "PA1"),
        "PA2": ("PA2", "PA2"),
        "PA3": ("PA3", "PA3"),
    }
    for text, expected in cases.items():
        mapped = normalise_aid_alias(text)
        assert mapped is not None
        assert (mapped.aid, mapped.command) == expected


def test_ansi_function_sequences_map_to_commands():
    cases = {
        b"\x1bOP": ("F1", "HELP"),
        b"\x1bOR": ("F3", "END"),
        b"\x1b[18~": ("F7", "UP"),
        b"\x1b[19~": ("F8", "DOWN"),
        b"\x1b[21~": ("F10", "LEFT"),
        b"\x1b[23~": ("F11", "RIGHT"),
        b"\x1b[24~": ("F12", "CANCEL"),
    }
    for seq, expected in cases.items():
        key = extract_ansi_function_key(seq)
        assert key == expected[0]
        assert command_from_key(key) == expected[1]


def test_tn3270_aid_frames_map_without_ebcdic():
    assert normalise_client_input(b"\xf1\x40\x40\xff\xef") == "HELP"
    assert normalise_client_input(b"\xf3\x40\x40\xff\xef") == "END"
    assert normalise_client_input(b"\xf7\x40\x40\xff\xef") == "UP"
    assert normalise_client_input(b"\xf8\x40\x40\xff\xef") == "DOWN"
    assert normalise_client_input(b"\x7a\x40\x40\xff\xef") == "LEFT"
    assert normalise_client_input(b"\x7b\x40\x40\xff\xef") == "RIGHT"
    assert normalise_client_input(b"\x7c\x40\x40\xff\xef") == "CANCEL"
    assert normalise_client_input(b"\x6d\x40\x40\xff\xef") == "CLEAR"
    assert normalise_client_input(b"\x6c\x40\x40\xff\xef") == "PA1"


def test_tn3270_enter_frame_with_text_still_returns_text():
    assert normalise_client_input(b"\x7d\x40\x40\x11\x00\x00L CICS\xff\xef") == "L CICS"
    assert normalise_client_input(b"L TSO\r\n") == "L TSO"
    assert normalise_client_input("L TSO".encode("cp037")) != "L TSO"


def _driver_result(payload: bytes):
    a, b = socket.socketpair()
    try:
        b.sendall(payload)
        b.shutdown(socket.SHUT_WR)
        return SocketInputDriver(a, echo=False).read_line()
    finally:
        a.close(); b.close()


def test_socket_input_driver_maps_aliases_and_ansi_sequences():
    res = _driver_result(b"/PF3\r\n")
    assert res.key == "PF3"
    assert res.text == "END"
    res = _driver_result(b"\x1b[18~")
    assert res.key == "F7"
    assert res.text == "UP"


def test_socket_input_driver_maps_c3270_high_and_low_aid_frames():
    res = _driver_result(b"\xf3\x40\x40\xff\xef")
    assert res.key == "PF3"
    assert res.text == "END"
    res = _driver_result(b"\x7c\x40\x40\xff\xef")
    assert res.key == "PF12"
    assert res.text == "CANCEL"


def test_socket_input_driver_does_not_mis_map_plain_ascii_commands():
    res = _driver_result(b"L TSO\r\n")
    assert res.key is None
    assert res.text == "L TSO"
    res = _driver_result(b"zoo\r\n")
    assert res.key is None
    assert res.text == "zoo"
