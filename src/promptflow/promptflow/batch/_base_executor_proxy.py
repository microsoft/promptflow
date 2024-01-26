# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Mapping, Optional

import httpx

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow._core._errors import UnexpectedError
from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter
from promptflow._utils.logger_utils import bulk_logger
from promptflow._utils.utils import load_json
from promptflow.batch._errors import ExecutorServiceUnhealthy
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.exceptions import ErrorTarget, ValidationException
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.storage._run_storage import AbstractRunStorage

EXECUTOR_UNHEALTHY_MESSAGE = "The executor service is currently not in a healthy state"


class AbstractExecutorProxy:
    @classmethod
    def get_tool_metadata(cls, flow_file: Path, working_dir: Optional[Path] = None) -> dict:
        """Generate tool metadata file for the specified flow."""
        return cls._get_tool_metadata(flow_file, working_dir or flow_file.parent)

    @classmethod
    def _get_tool_metadata(cls, flow_file: Path, working_dir: Path) -> dict:
        raise NotImplementedError()

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "AbstractExecutorProxy":
        """Create a new executor"""
        raise NotImplementedError()

    async def destroy(self):
        """Destroy the executor"""
        pass

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """Execute a line"""
        raise NotImplementedError()

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        """Execute aggregation nodes"""
        raise NotImplementedError()

    async def ensure_executor_health(self):
        """Ensure the executor service is healthy before execution"""
        pass


class APIBasedExecutorProxy(AbstractExecutorProxy):
    @property
    def api_endpoint(self) -> str:
        """The basic API endpoint of the executor service.

        The executor proxy calls the executor service to get the
        line results and aggregation result through this endpoint.
        """
        raise NotImplementedError()

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        start_time = datetime.utcnow()
        # call execution api to get line results
        url = self.api_endpoint + "/execution"
        payload = {"run_id": run_id, "line_number": index, "inputs": inputs}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=LINE_TIMEOUT_SEC)
        # process the response
        result = self._process_http_response(response)
        if response.status_code != 200:
            run_info = FlowRunInfo.create_with_error(start_time, inputs, index, run_id, result)
            return LineResult(output={}, aggregation_inputs={}, run_info=run_info, node_run_infos={})
        return LineResult.deserialize(result)

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        # call aggregation api to get aggregation result
        async with httpx.AsyncClient() as client:
            url = self.api_endpoint + "/aggregation"
            payload = {"run_id": run_id, "batch_inputs": batch_inputs, "aggregation_inputs": aggregation_inputs}
            response = await client.post(url, json=payload, timeout=LINE_TIMEOUT_SEC)
        result = self._process_http_response(response)
        return AggregationResult.deserialize(result)

    async def ensure_executor_startup(self, error_file):
        """Ensure the executor service is initialized before calling the API to get the results"""
        try:
            await self.ensure_executor_health()
        except ExecutorServiceUnhealthy as ex:
            # raise the init error if there is any
            startup_ex = self._check_startup_error_from_file(error_file) or ex
            bulk_logger.error(f"Failed to start up the executor due to an error: {str(startup_ex)}")
            await self.destroy()
            raise startup_ex

    async def ensure_executor_health(self):
        """Ensure the executor service is healthy before calling the API to get the results

        During testing, we observed that the executor service started quickly on Windows.
        However, there is a noticeable delay in booting on Linux.

        So we set a specific waiting period. If the executor service fails to return to normal
        within the allocated timeout, an exception is thrown to indicate a potential problem.
        """
        retry_count = 0
        max_retry_count = 20
        while retry_count < max_retry_count:
            if not self._is_executor_active():
                bulk_logger.error("The executor service is not active. Please check the logs for more details.")
                break
            if await self._check_health():
                return
            # wait for 1s to prevent calling the API too frequently
            await asyncio.sleep(1)
            retry_count += 1
        raise ExecutorServiceUnhealthy(f"{EXECUTOR_UNHEALTHY_MESSAGE}. Please resubmit your flow and try again.")

    def _is_executor_active(self):
        """The interface function to check if the executor service is active"""
        return True

    async def _check_health(self):
        try:
            health_url = self.api_endpoint + "/health"
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url)
            if response.status_code != 200:
                bulk_logger.warning(f"{EXECUTOR_UNHEALTHY_MESSAGE}. Response: {response.status_code} - {response.text}")
                return False
            return True
        except Exception as e:
            bulk_logger.warning(f"{EXECUTOR_UNHEALTHY_MESSAGE}. Error: {str(e)}")
            return False

    def _check_startup_error_from_file(self, error_file) -> Exception:
        error_dict = load_json(error_file)
        if error_dict:
            error_response = ErrorResponse.from_error_dict(error_dict)
            bulk_logger.error(
                "Error when starting the executor service: "
                f"[{error_response.innermost_error_code}] {error_response.message}"
            )
            return ValidationException(error_response.message, target=ErrorTarget.BATCH)
        return None

    def _process_http_response(self, response: httpx.Response):
        if response.status_code == 200:
            # if the status code is 200, the response is the json dict of a line result
            return response.json()
        else:
            # if the status code is not 200, log the error
            message_format = "Unexpected error when executing a line, status code: {status_code}, error: {error}"
            bulk_logger.error(message_format.format(status_code=response.status_code, error=response.text))
            # if response can be parsed as json, return the error dict
            # otherwise, wrap the error in an UnexpectedError and return the error dict
            try:
                error_dict = response.json()
                return error_dict["error"]
            except (JSONDecodeError, KeyError):
                unexpected_error = UnexpectedError(
                    message_format=message_format, status_code=response.status_code, error=response.text
                )
                return ExceptionPresenter.create(unexpected_error).to_dict()
