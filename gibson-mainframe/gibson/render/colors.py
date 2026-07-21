"""ANSI approximations of common 3270 colour conventions."""
import os as _os

RESET = "\x1b[0m"
BLUE = "\x1b[34m"
LIGHT_BLUE = "\x1b[94m"
GREEN = "\x1b[32m"
TURQUOISE = "\x1b[36m"
RED = "\x1b[31m"
WHITE = "\x1b[37;1m"
YELLOW = "\x1b[33m"
CLEAR = "\x1b[2J\x1b[H"
HLINE = BLUE + ("─" * 79) + RESET
ACTION_BAR = BLUE + "Menu  Utilities  Compilers  Options  Status  Help" + RESET

# --- Text attribute (SGR) codes -------------------------------------------
# These are honoured by the guacd telnet terminal that backs the Guacamole
# web client, as well as by xterm-class native clients.
BOLD = "\x1b[1m"
BOLD_OFF = "\x1b[22m"
BLINK = "\x1b[5m"          # the closest a terminal gets to a pulsing "glow"
BLINK_OFF = "\x1b[25m"
REVERSE = "\x1b[7m"        # swaps fg/bg -> highlighted "name-plate" block
REVERSE_OFF = "\x1b[27m"
BRIGHT_TURQUOISE = "\x1b[96m"
BRIGHT_GREEN = "\x1b[92m"
BRIGHT_YELLOW = "\x1b[93m"
BRIGHT_BLUE = "\x1b[94m"   # light blue

# Named presets for the configurable hostname highlight.  Each value is the
# opening SGR sequence; glow() always closes with RESET.
GLOW_STYLES = {
    "off": "",
    "bold": BOLD + BRIGHT_TURQUOISE,
    "color": BRIGHT_TURQUOISE,
    "reverse": REVERSE + BOLD,
    # Default for the master console SYSNAME: bright turquoise, bold, blinking.
    "glow": BOLD + BRIGHT_TURQUOISE + BLINK,
    # VTAM logon banner default: STEADY bold light blue -- it never blinks to
    # black.  The light-blue<->dark-blue "breathing" bloom is produced by the
    # animated pulse (GIBSON_HOSTNAME_PULSE, on by default) which cycles real
    # colours instead of toggling visibility.  Set GIBSON_HOSTNAME_GLOW=blink
    # for the old on/off blink, or =off to disable entirely.
    "banner": BOLD + BRIGHT_BLUE,
    "banner_steady": BOLD + BRIGHT_BLUE,
    "banner_blink": BOLD + BRIGHT_BLUE + BLINK,
    "blink": BOLD + BRIGHT_BLUE + BLINK,
    "banner_pulse": BOLD + BRIGHT_BLUE,
    "banner_cyan": BOLD + BRIGHT_TURQUOISE,
    "banner_green": BOLD + BRIGHT_GREEN,
}


def glow(text: str, style: str | None = None) -> str:
    """Wrap ``text`` in an attention-drawing highlight.

    The style can be supplied explicitly or via the ``GIBSON_HOSTNAME_GLOW``
    environment variable (one of: glow, bold, color, reverse, off).  Unknown
    or empty values fall back to the ``glow`` preset.  When the resolved style
    is ``off`` the text is returned untouched so plain terminals/log scrapes
    are unaffected.
    """
    if style is None:
        style = _os.environ.get("GIBSON_HOSTNAME_GLOW", "glow")
    opener = GLOW_STYLES.get((style or "glow").strip().lower())
    if opener is None:
        opener = GLOW_STYLES["glow"]
    if not opener:
        return text
    return opener + text + RESET
