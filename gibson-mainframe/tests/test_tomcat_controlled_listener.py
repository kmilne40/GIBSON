from __future__ import annotations
import socket, time
from gibson.core.config import GibsonConfig
from gibson.core.state import GibsonState
from gibson.apps.tomcat_sim.config import TomcatSimConfig
from gibson.apps.tomcat_sim.state import create_session
from gibson.apps.tomcat_sim.session import start_listener


def _free_port():
    s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p


def _recv_until(sock, needle, limit=4096):
    data = b""
    while len(data) < limit and needle.encode() not in data:
        data += sock.recv(1024)
    return data.decode(errors='ignore')

def test_controlled_listener_accepts_only_safe_commands(tmp_path):
    port=_free_port()
    state=GibsonState.create(GibsonConfig(host='127.0.0.1', sim_root=tmp_path))
    state.tomcat_sim_config=TomcatSimConfig(pseudo_bind_port=port)
    create_session(state,'/shell_exploit','tomcat')
    assert start_listener(state, port)
    with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
        sock.settimeout(2)
        banner=sock.recv(1024).decode(errors='ignore')
        assert 'Gibson controlled Tomcat training shell' in banner
        sock.sendall(b'id\n')
        data=_recv_until(sock, 'uid=12345')
        assert 'uid=12345(tomcat)' in data
        sock.sendall(b'sh -i\n')
        data=_recv_until(sock, 'denied')
        assert 'denied' in data.lower()
        sock.sendall(b'exit\n')
    try:
        state.tomcat_sim_state.listener_server.shutdown()
        state.tomcat_sim_state.listener_server.server_close()
    except Exception:
        pass
