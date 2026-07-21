from gibson.services.telnet_server import _colourize_vtam_screen
from gibson.render import colors


def test_colourize_vtam_screen_applies_requested_palette():
    screen = "GIBSON PRODUCTION LPAR\nTHIS SYSTEM CONTAINS RESTRICTED INFORMATION\nGGGGG\nLU NAME: LU320\n"
    out = _colourize_vtam_screen(screen)
    assert colors.LIGHT_BLUE in out
    assert colors.RED in out
    assert colors.GREEN in out


def test_colourize_vtam_screen_preserves_content():
    screen = "  GIBSON PRODUCTION LPAR  \nLOGON using L TSO\n"
    out = _colourize_vtam_screen(screen)
    assert "GIBSON PRODUCTION LPAR" in out
    assert "LOGON using L TSO" in out
