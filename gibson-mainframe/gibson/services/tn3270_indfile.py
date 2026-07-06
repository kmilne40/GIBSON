from __future__ import annotations

"""Placeholder service facade for future full native IND$FILE state handling."""

from typing import Any
from gibson.core.indfile_protocol import detect_transfer_command, handle_typed_transfer


def maybe_handle_indfile(state: Any, userid: str, text: str) -> str | None:
    if not detect_transfer_command(text):
        return None
    return handle_typed_transfer(state, userid, text)
