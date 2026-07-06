# Gibson AID/PF Keys with Ncat

Ncat is not a 3270 emulator. It can connect to Gibson and can use TLS with
`--ssl`, but it does not synthesize IBM 3270 AID keys by itself. Gibson v23
therefore supports typed AID aliases for Ncat, netcat, telnet, and TLS diagnostic
clients.

Plain vulnerable-mode connection:

```bash
ncat 192.168.0.203 2023
```

Secure-mode TLS connection:

```bash
ncat --ssl --ssl-verify=false 192.168.0.203 1023
```

Inside the session, type aliases such as:

```text
PF1    -> HELP
PF3    -> END
PF7    -> UP
PF8    -> DOWN
PF10   -> LEFT
PF11   -> RIGHT
PF12   -> CANCEL
/PF3   -> END
:PF3   -> END
AID PF3 -> END
CLEAR
PA1
PA2
PA3
```

If your local terminal sends ANSI function-key escape sequences through Ncat,
Gibson also recognises common xterm forms such as F1 `ESC OP`, F3 `ESC OR`,
F7 `ESC [18~`, F8 `ESC [19~`, F10 `ESC [21~`, F11 `ESC [23~`, and F12
`ESC [24~`.
