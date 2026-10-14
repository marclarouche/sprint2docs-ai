import socket
import subprocess
import urllib.request

import pytest


@pytest.fixture(autouse=True)
def no_network_or_shell(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("external operation attempted")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(urllib.request, "urlopen", deny)
    monkeypatch.setattr(subprocess, "Popen", deny)
