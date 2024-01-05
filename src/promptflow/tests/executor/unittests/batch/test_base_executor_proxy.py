from pathlib import Path
from tempfile import mkdtemp
from typing import Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.storage._run_storage import AbstractRunStorage


@pytest.mark.unittest
class TestAPIBasedExecutorProxy:
    @pytest.mark.asyncio
    async def test_check_health(self, mocker):
        mock_executor_proxy = MockAPIBasedExecutorProxy()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # case 1: assume executor proxy is healthy
            mock_get.return_value = httpx.Response(200)
            assert await mock_executor_proxy._check_health() is True
            # case 1: assume executor proxy is not healthy
            mock_get.return_value = httpx.Response(500)
            assert await mock_executor_proxy._check_health() is False
            mock_get.side_effect = Exception("error")
            assert await mock_executor_proxy._check_health() is False

    @pytest.mark.asyncio
    async def test_ensure_executor_startup(self):
        error_file = Path(mkdtemp()) / "error.json"
        mock_executor_proxy = await MockAPIBasedExecutorProxy.create("")
        mock_executor_proxy.ensure_executor_startup(error_file)
        pass


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
