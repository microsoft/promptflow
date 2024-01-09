import socket

import pytest

from promptflow.batch import CSharpExecutorProxy


@pytest.mark.unittest
class TestCSharpExecutorProxy:
    def test_find_available_port(self):
        port = CSharpExecutorProxy.find_available_port()
        assert isinstance(port, str)
        assert int(port) > 0, "Port number should be greater than 0"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", int(port)))
        except OSError:
            pytest.fail("Port is not actually available")
