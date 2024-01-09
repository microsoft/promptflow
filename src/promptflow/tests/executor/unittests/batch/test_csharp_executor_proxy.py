import socket
from unittest.mock import MagicMock, patch

import pytest

from promptflow.batch import CSharpExecutorProxy

from ...utils import get_flow_folder, get_yaml_file


@pytest.mark.unittest
class TestCSharpExecutorProxy:
    @pytest.mark.asyncio
    async def test_create(self):
        flow_file = get_yaml_file("csharp_flow")
        working_dir = get_flow_folder("csharp_flow")

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            with patch.object(CSharpExecutorProxy, "ensure_executor_startup", return_value=None):
                executor_proxy = await CSharpExecutorProxy.create(flow_file, working_dir)
            mock_popen.assert_called_once()
            assert executor_proxy is not None
            assert executor_proxy._process is not None
            assert executor_proxy._port is not None
            assert executor_proxy.api_endpoint == f"http://localhost:{executor_proxy._port}"

    def test_find_available_port(self):
        port = CSharpExecutorProxy.find_available_port()
        assert isinstance(port, str)
        assert int(port) > 0, "Port number should be greater than 0"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", int(port)))
        except OSError:
            pytest.fail("Port is not actually available")
