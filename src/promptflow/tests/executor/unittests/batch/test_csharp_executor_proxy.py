import socket
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from promptflow.batch import CSharpExecutorProxy
from promptflow.executor._result import AggregationResult

from ...utils import get_flow_folder, get_yaml_file


async def get_executor_proxy():
    flow_file = get_yaml_file("csharp_flow")
    working_dir = get_flow_folder("csharp_flow")
    with patch.object(CSharpExecutorProxy, "ensure_executor_startup", return_value=None):
        return await CSharpExecutorProxy.create(flow_file, working_dir)


@pytest.mark.unittest
class TestCSharpExecutorProxy:
    @pytest.mark.asyncio
    async def test_create(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            executor_proxy = await get_executor_proxy()
            mock_popen.assert_called_once()
            assert executor_proxy is not None
            assert executor_proxy._process is not None
            assert executor_proxy._port is not None
            assert executor_proxy.api_endpoint == f"http://localhost:{executor_proxy._port}"

    @pytest.mark.asyncio
    async def test_destroy_with_already_terminated(self):
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        executor_proxy = await get_executor_proxy()
        executor_proxy._process = mock_process

        await executor_proxy.destroy()

        mock_process.poll.assert_called_once()
        mock_process.terminate.assert_not_called()

    @pytest.mark.asyncio
    async def test_destroy_with_terminates_gracefully(self):
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        executor_proxy = await get_executor_proxy()
        executor_proxy._process = mock_process

        await executor_proxy.destroy()

        mock_process.poll.assert_called_once()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        mock_process.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_destroy_with_force_kill(self):
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="cmd", timeout=5)
        executor_proxy = await get_executor_proxy()
        executor_proxy._process = mock_process

        await executor_proxy.destroy()

        mock_process.poll.assert_called_once()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_exec_aggregation_async(self):
        executor_proxy = await get_executor_proxy()
        aggr_result = await executor_proxy.exec_aggregation_async("", "", "")
        assert isinstance(aggr_result, AggregationResult)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exit_code, expected_result",
        [
            (None, True),
            (0, False),
            (1, False),
        ],
    )
    async def test_is_executor_active(self, exit_code, expected_result):
        executor_proxy = await get_executor_proxy()
        executor_proxy._process = MagicMock()
        executor_proxy._process.poll.return_value = exit_code
        assert executor_proxy._is_executor_active() == expected_result

    def test_get_tool_metadata(self):
        flow_file = get_yaml_file("csharp_flow")
        working_dir = get_flow_folder("csharp_flow")
        with pytest.raises(FileNotFoundError):
            CSharpExecutorProxy.get_tool_metadata(flow_file, working_dir)

    def test_find_available_port(self):
        port = CSharpExecutorProxy.find_available_port()
        assert isinstance(port, str)
        assert int(port) > 0, "Port number should be greater than 0"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", int(port)))
        except OSError:
            pytest.fail("Port is not actually available")
