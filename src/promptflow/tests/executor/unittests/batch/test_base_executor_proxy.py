import json
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from promptflow._proxy._base_executor_proxy import APIBasedExecutorProxy
from promptflow._proxy._errors import ExecutorServiceUnhealthy
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget, ValidationException
from promptflow.executor._errors import GetConnectionError
from promptflow.storage._run_storage import AbstractRunStorage

from ...mock_execution_server import _get_aggr_result_dict, _get_line_result_dict


@pytest.mark.unittest
class TestAPIBasedExecutorProxy:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "has_error",
        [False, True],
    )
    async def test_exec_line_async(self, has_error):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        run_id = "test_run_id"
        index = 1
        inputs = {"question": "test"}
        with patch("httpx.Response.raise_for_status"):
            line_result_dict = _get_line_result_dict(run_id, index, inputs, has_error=has_error)
            status_code = 400 if has_error else 200
            response = httpx.Response(status_code=status_code, json=line_result_dict)
            with patch("httpx.AsyncClient.post", return_value=response):
                line_result = await mock_executor_proxy.exec_line_async(inputs, index, run_id)
                assert line_result.output == {} if has_error else {"answer": "Hello world!"}
                assert line_result.run_info.run_id == f"{run_id}_{index}"
                assert line_result.run_info.root_run_id == run_id
                assert line_result.run_info.index == index
                assert line_result.run_info.status == Status.Failed if has_error else Status.Completed
                assert line_result.run_info.inputs == inputs
                assert (line_result.run_info.error is not None) == has_error

    @pytest.mark.asyncio
    async def test_exec_aggregation_async(self):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        run_id = "test_run_id"
        batch_inputs = {"question": ["test", "error"]}
        aggregation_inputs = {"${get_answer.output}": ["Incorrect", "Correct"]}
        with patch("httpx.Response.raise_for_status"):
            aggr_result_dict = _get_aggr_result_dict(run_id, aggregation_inputs)
            response = httpx.Response(200, json=aggr_result_dict)
            with patch("httpx.AsyncClient.post", return_value=response):
                aggr_result = await mock_executor_proxy.exec_aggregation_async(batch_inputs, aggregation_inputs, run_id)
                assert aggr_result.metrics == {"accuracy": 0.5}
                assert len(aggr_result.node_run_infos) == 1
                assert aggr_result.node_run_infos["aggregation"].flow_run_id == run_id
                assert aggr_result.node_run_infos["aggregation"].inputs == aggregation_inputs
                assert aggr_result.node_run_infos["aggregation"].status == Status.Completed

    @pytest.mark.asyncio
    async def test_ensure_executor_startup_when_no_error(self):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        with patch.object(APIBasedExecutorProxy, "ensure_executor_health", new_callable=AsyncMock) as mock:
            with patch.object(APIBasedExecutorProxy, "_check_startup_error_from_file") as mock_check_startup_error:
                await mock_executor_proxy.ensure_executor_startup("")
                mock_check_startup_error.assert_not_called()
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_executor_startup_when_not_healthy(self):
        # empty error file
        error_file = Path(mkdtemp()) / "error.json"
        error_file.touch()

        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        with patch.object(APIBasedExecutorProxy, "ensure_executor_health", new_callable=AsyncMock) as mock:
            mock.side_effect = ExecutorServiceUnhealthy("executor unhealthy")
            with pytest.raises(ExecutorServiceUnhealthy) as ex:
                await mock_executor_proxy.ensure_executor_startup(error_file)
            assert ex.value.message == "executor unhealthy"
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_executor_startup_when_existing_validation_error(self):
        # prepare the error file
        error_file = Path(mkdtemp()) / "error.json"
        error_dict = ExceptionPresenter.create(
            GetConnectionError(connection="aoai_conn", node_name="mock", error=Exception("mock"))
        ).to_dict()
        with open(error_file, "w") as file:
            json.dump(error_dict, file, indent=4)

        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        with patch.object(APIBasedExecutorProxy, "ensure_executor_health", new_callable=AsyncMock) as mock:
            mock.side_effect = ExecutorServiceUnhealthy("executor unhealthy")
            with pytest.raises(ValidationException) as ex:
                await mock_executor_proxy.ensure_executor_startup(error_file)
            assert "Get connection 'aoai_conn' for node 'mock' error: mock" in ex.value.message
            assert ex.value.target == ErrorTarget.BATCH

    @pytest.mark.asyncio
    async def test_ensure_executor_health_when_healthy(self):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        with patch.object(APIBasedExecutorProxy, "_check_health", return_value=True) as mock:
            await mock_executor_proxy.ensure_executor_health()
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_executor_health_when_unhealthy(self):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        with patch.object(APIBasedExecutorProxy, "_check_health", return_value=False) as mock:
            with pytest.raises(ExecutorServiceUnhealthy):
                await mock_executor_proxy.ensure_executor_health()
            assert mock.call_count == 20

    @pytest.mark.asyncio
    async def test_ensure_executor_health_when_not_active(self):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        with patch.object(APIBasedExecutorProxy, "_check_health", return_value=False) as mock:
            with patch.object(APIBasedExecutorProxy, "_is_executor_active", return_value=False):
                with pytest.raises(ExecutorServiceUnhealthy):
                    await mock_executor_proxy.ensure_executor_health()
            mock.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mock_value, expected_result",
        [
            (httpx.Response(200), True),
            (httpx.Response(500), False),
            (Exception("error"), False),
        ],
    )
    async def test_check_health(self, mock_value, expected_result):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock:
            mock.return_value = mock_value
            assert await mock_executor_proxy._check_health() is expected_result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response, expected_result",
        [
            (
                httpx.Response(500, json={"error": "test error"}),
                "test error",
            ),
            (
                httpx.Response(400, json={"detail": "test"}),
                {
                    "message": 'Unexpected error when executing a line, status code: 400, error: {"detail":"test"}',
                    "messageFormat": (
                        "Unexpected error when executing a line, " "status code: {status_code}, error: {error}"
                    ),
                    "messageParameters": {
                        "status_code": "400",
                        "error": '{"detail":"test"}',
                    },
                    "referenceCode": "Unknown",
                    "code": "SystemError",
                    "innerError": {
                        "code": "UnexpectedError",
                        "innerError": None,
                    },
                },
            ),
            (
                httpx.Response(502, text="test"),
                {
                    "message": "Unexpected error when executing a line, status code: 502, error: test",
                    "messageFormat": (
                        "Unexpected error when executing a line, " "status code: {status_code}, error: {error}"
                    ),
                    "messageParameters": {
                        "status_code": "502",
                        "error": "test",
                    },
                    "referenceCode": "Unknown",
                    "code": "SystemError",
                    "innerError": {
                        "code": "UnexpectedError",
                        "innerError": None,
                    },
                },
            ),
        ],
    )
    async def test_process_error_response(self, response, expected_result):
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        assert mock_executor_proxy._process_error_response(response) == expected_result


class MockAPIBasedExecutorProxy(APIBasedExecutorProxy):
    @property
    def api_endpoint(self) -> str:
        return "http://localhost:8080"

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "MockAPIBasedExecutorProxy":
        return MockAPIBasedExecutorProxy()
