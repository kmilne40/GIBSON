from gibson.screens.vtam_model import VtamScreenModel
from gibson.render.vtam_renderer import render_plain, render_ansi, render_3270
from gibson.core.terminal_compat import compact_vtam_screen


def test_canonical_vtam_preserves_logo_and_ports():
    model = VtamScreenModel(client_ip="192.0.2.10", client_port=41194, service_port=2023)
    text = render_plain(model)
    assert "####" in text
    assert "▇" not in text
    assert "SERVICE PORT: 2023" in text
    assert "CLIENT PORT: 41194" in text
    assert "PORT:41194" not in text
    assert "GTSOv0.3.3" not in text


def test_canonical_vtam_renderers_work():
    model = VtamScreenModel(client_ip="192.0.2.10", client_port=41194)
    assert "\x1b[" in render_ansi(model)
    compact = compact_vtam_screen(ip_address="192.0.2.10", port=41194)
    assert "SERVICE PORT" in compact and "CLIENT PORT" in compact
    screen = render_3270(model)
    assert screen.rows == 24 and screen.cols == 80
