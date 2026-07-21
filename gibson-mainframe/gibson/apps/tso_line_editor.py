from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from gibson.render.input import InputResult, SocketInputDriver


@dataclass
class LineEditorState:
    dataset: str
    lines: list[str]
    mode: str = "EDIT"
    dirty: bool = False
    saved_once: bool = False


class TsoLineEditorSession:
    """TSO/E EDIT line-mode approximation.

    This intentionally remains distinct from the full-screen ISPF editor.
    Behaviour modelled here is the classic line editor flow: enter EDIT,
    switch to INPUT to add lines with 00010/00020 numbering, terminate INPUT by
    pressing Enter on a blank line, then SAVE and END from EDIT mode.
    """

    def __init__(
        self,
        dataset: str,
        text: str,
        *,
        exists: bool,
        save_callback: Callable[[str], None],
        type_prompt_callback: Optional[Callable[[], InputResult]] = None,
    ):
        self.state = LineEditorState(dataset=dataset, lines=text.splitlines(), mode="EDIT")
        self.exists = exists
        self.save_callback = save_callback
        self.type_prompt_callback = type_prompt_callback

    def text(self) -> str:
        return "\n".join(self.state.lines)

    def _line_label(self, index: int) -> str:
        return f"{(index + 1) * 10:05d}"

    def _resolve_line_ref(self, token: str) -> int:
        raw = (token or "").strip()
        if not raw:
            raise ValueError("missing line reference")
        value = int(raw)
        if value >= 10 and value % 10 == 0:
            return max(0, (value // 10) - 1)
        return max(0, value - 1)

    def _list(self, send: Callable[[str], None]) -> None:
        if not self.state.lines:
            send("END OF DATA\n")
            return
        for idx, line in enumerate(self.state.lines):
            send(f"{self._line_label(idx)} {line}\n")
        send("END OF DATA\n")

    def _save(self, send: Callable[[str], None]) -> None:
        try:
            self.save_callback(self.text())
            self.state.dirty = False
            self.state.saved_once = True
            send("EDIT\n")
        except Exception as exc:
            send(f"EDIT\nSAVE FAILED - {type(exc).__name__}: {exc}\n")

    def _enter_input(self, send: Callable[[str], None]) -> None:
        self.state.mode = "INPUT"
        send("INPUT\n")

    def _leave_input(self, send: Callable[[str], None]) -> None:
        self.state.mode = "EDIT"
        send("EDIT\n")

    def _prompt_type_if_needed(self, send: Callable[[str], None]) -> bool:
        if self.exists:
            return True
        send("ENTER DATASET TYPE-\n")
        type_res = self.type_prompt_callback() if self.type_prompt_callback is not None else InputResult("TEXT")
        if getattr(type_res, "key", "") == "EOF":
            return False
        _dtype = (type_res.text or "TEXT").strip().upper() or "TEXT"
        send("DATASET OR MEMBER NOT FOUND, ASSUMED TO BE NEW\n")
        self._enter_input(send)
        return True

    def _run_input_mode(self, driver: SocketInputDriver, send: Callable[[str], None]) -> bool:
        while self.state.mode == "INPUT":
            prompt = f"{self._line_label(len(self.state.lines))} "
            res = driver.read_line(prompt)
            if getattr(res, "key", "") == "EOF":
                return False
            text = res.text.rstrip("\r\n")
            if text == "":
                self._leave_input(send)
                return True
            self.state.lines.append(text)
            self.state.dirty = True
        return True

    def _delete(self, token: str, send: Callable[[str], None]) -> None:
        try:
            idx = self._resolve_line_ref(token)
            if 0 <= idx < len(self.state.lines):
                del self.state.lines[idx]
                self.state.dirty = True
            send("EDIT\n")
        except Exception:
            send("INVALID DELETE SUBCOMMAND\nEDIT\n")

    def _insert(self, token: str, driver: SocketInputDriver, send: Callable[[str], None]) -> bool:
        try:
            idx = min(max(0, self._resolve_line_ref(token)), len(self.state.lines))
        except Exception:
            send("INVALID INSERT SUBCOMMAND\nEDIT\n")
            return True

        insert_count = 0
        while True:
            prompt = f"{self._line_label(idx + insert_count)} "
            res = driver.read_line(prompt)
            if getattr(res, "key", "") == "EOF":
                return False
            insert_text = res.text.rstrip("\r\n")
            if insert_text == "":
                send("EDIT\n")
                return True
            self.state.lines.insert(idx + insert_count, insert_text)
            insert_count += 1
            self.state.dirty = True

    def run(self, driver: SocketInputDriver, send: Callable[[str], None]) -> None:
        if not self._prompt_type_if_needed(send):
            return
        if self.state.mode == "EDIT":
            send("EDIT\n")
            if self.state.lines:
                self._list(send)
                send("EDIT\n")
        while True:
            if self.state.mode == "INPUT":
                if not self._run_input_mode(driver, send):
                    return
                continue

            res = driver.read_line("")
            key = getattr(res, "key", "")
            if key == "EOF":
                return
            text = res.text.rstrip("\r\n")
            upper = text.strip().upper()

            if upper in {"", "EDIT"}:
                send("EDIT\n")
                continue
            if upper in {"INPUT", "I"}:
                self._enter_input(send)
                continue
            if upper in {"LIST", "L"}:
                self._list(send)
                send("EDIT\n")
                continue
            if upper == "SAVE":
                self._save(send)
                continue
            if upper == "END":
                if self.state.dirty and not self.state.saved_once:
                    self._save(send)
                return
            if upper in {"CANCEL", "CAN"}:
                return
            if upper.startswith("DELETE "):
                self._delete(text.split(None, 1)[1], send)
                continue
            if upper.startswith("INSERT "):
                if not self._insert(text.split(None, 1)[1], driver, send):
                    return
                continue
            send("INVALID EDIT SUBCOMMAND\nEDIT\n")
