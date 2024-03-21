# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import json
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Mapping, NoReturn, Optional

import httpx

from promptflow._constants import DEFAULT_ENCODING, LINE_TIMEOUT_SEC
from promptflow._core._errors import NotSupported, UnexpectedError
from promptflow._sdk._constants import (
    DAG_FILE_NAME,
    FLOW_META_JSON,
    FLOW_META_JSON_GEN_TIMEOUT,
    FLOW_TOOLS_JSON,
    FLOW_TOOLS_JSON_GEN_TIMEOUT,
    PROMPT_FLOW_DIR_NAME,
)
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter
from promptflow._utils.flow_utils import is_flex_flow, read_json_content
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
    def dump_metadata(cls, flow_file: Path, working_dir: Path) -> NoReturn:
        """Generate metadata for a specific flow."""
        cls.generate_flow_tools_json(flow_file, working_dir, dump=True)
        cls.generate_flow_json(flow_file, working_dir, dump=True)

    @classmethod
    def generate_flow_tools_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_TOOLS_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> dict:
        """Generate flow.tools.json for the specified flow."""
        if is_flex_flow(file_path=flow_file, working_dir=working_dir):
            return {}
        else:
            return cls._generate_flow_tools_json(flow_file, working_dir, dump, timeout, load_in_subprocess)

    @classmethod
    def _generate_flow_tools_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_TOOLS_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> dict:
        raise NotImplementedError()

    @classmethod
    def generate_flow_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_META_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> Dict[str, Any]:
        """Generate metadata for a specific flow.

        :param flow_file: The path of the flow file.
        :type flow_file: Path
        :param working_dir: The working directory to generate the flow metadata. It will impact the packages to load
            and the location of generated flow.json file when dump is True.
        :type working_dir: Path
        :param dump: Whether to dump the metadata to .promptflow/flow.json.
        :type dump: bool
        :param timeout: The timeout for the flow execution. Default timeout is 60 seconds.
        :type timeout: int
        :param load_in_subprocess: Whether to load the flow in a subprocess. This parameter works for Python flow only.
        :type load_in_subprocess: bool
        :return: The metadata of the flow.
        :rtype: Dict[str, Any]
        """
        if is_flex_flow(file_path=flow_file, working_dir=working_dir):
            return cls._generate_flow_json(flow_file, working_dir, dump, timeout, load_in_subprocess)
        else:
            return {}

    @classmethod
    def _generate_flow_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_META_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def get_used_connection_names(cls, flow_file: Path, working_dir: Path) -> List[str]:
        """Get the used connection names in the flow."""
        raise NotImplementedError()

    def get_inputs_definition(self):
        """Get the inputs definition of an eager flow"""
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
    def __init__(
        self,
        *,
        working_dir: Path = None,
        enable_stream_output: bool = False,
    ):
        """Initialize the executor proxy with the working directory.

        :param working_dir: The working directory of the executor, usually the flow directory,
                where we can find metadata under .promptflow. Will use current working directory if not provided.
        :type working_dir: Path
        """
        self._working_dir = working_dir or Path.cwd()
        self._enable_stream_output = enable_stream_output

        # build-in integer is thread-safe in Python.
        # ref: https://stackoverflow.com/questions/6320107/are-python-ints-thread-safe
        self._active_generator_count = 0

    @property
    def enable_stream_output(self) -> bool:
        """Whether to enable the stream output."""
        return self._enable_stream_output

    @property
    def working_dir(self) -> Path:
        """
        The working directory of the executor, usually the flow directory,
        where we can find metadata under .promptflow.
        """
        return self._working_dir

    # region Service Lifecycle Control when Streaming Output is Enabled
    async def _activate_generator(self):
        """For streaming output, we will return a generator for the output, and the execution service
        should keep alive until the generator is exhausted.

        This method is used to increase the active generator count.
        """
        self._active_generator_count += 1

    async def _deactivate_generator(self):
        """For streaming output, we will return a generator for the output, and the execution service
        should keep alive until the generator is exhausted.

        This method is used to decrease the active generator count.
        """
        self._active_generator_count -= 1

    async def _all_generators_exhausted(self):
        """For streaming output, we will return a generator for the output, and the execution service
        should keep alive until the generator is exhausted.

        This method is to check if all generators are exhausted.
        """
        # the count should never be negative, but still check it here for safety
        return self._active_generator_count <= 0

    async def destroy_if_all_generators_exhausted(self):
        """
        client.stream api in exec_line function won't pass all response one time.
        For API-based streaming chat flow, if executor proxy is destroyed, it will kill service process
        and connection will close. this will result in subsequent getting generator content failed.

        Besides, external caller usually wait for the destruction of executor proxy before it can continue and iterate
        the generator content, so we can't keep waiting here.

        On the other hand, the subprocess for execution service is not started in detach mode;
        it wll exit when parent process exit. So we simply skip the destruction here.
        """

        # TODO 3033484: update this after executor service support graceful shutdown
        if not await self._all_generators_exhausted():
            raise UnexpectedError(
                message_format="The executor service is still handling a stream request "
                "whose response is not fully consumed yet."
            )
        await self.destroy()

    # endregion

    @classmethod
    def dump_metadata(cls, flow_file: Path, working_dir: Path) -> NoReturn:
        # In abstract class, dump_metadata may redirect to generate_tools_json and generate_flow_json
        # However, for APIBasedExecutorProxy, we can't get the meta in current process, so generate_tools_json
        # and generate_flow_json should rely on the metadata file dumped by dump_metadata instead.

        # for local, they should override this method and dump metadata, like via a subprocess command
        # for cloud, they will assume that metadata has already been dumped into the flow directory so do nothing here
        return

    def get_inputs_definition(self):
        """Get the inputs definition of an eager flow"""
        from promptflow.contracts.flow import FlowInputDefinition

        flow_meta = self.generate_flow_json(
            flow_file=self.working_dir / DAG_FILE_NAME,
            working_dir=self.working_dir,
            dump=False,
        )
        inputs = {}
        for key, value in flow_meta.get("inputs", {}).items():
            # TODO: update this after we determine whether to accept list here or now
            _type = value.get("type")
            if isinstance(_type, list):
                _type = _type[0]
            value["type"] = _type
            inputs[key] = FlowInputDefinition.deserialize(value)
        return inputs

    @classmethod
    def _generate_flow_tools_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_TOOLS_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> dict:
        flow_tools_json_path = working_dir / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        return read_json_content(flow_tools_json_path, "meta of tools")

    @classmethod
    def _generate_flow_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_META_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> Dict[str, Any]:
        flow_json_path = working_dir / PROMPT_FLOW_DIR_NAME / FLOW_META_JSON
        return read_json_content(flow_json_path, "meta of tools")

    @property
    def api_endpoint(self) -> str:
        """The basic API endpoint of the executor service.

        The executor proxy calls the executor service to get the
        line results and aggregation result through this endpoint.
        """
        raise NotImplementedError()

    @property
    def chat_output_name(self) -> Optional[str]:
        """The name of the chat output in the line result. Return None if the bonded flow is not a chat flow."""
        # TODO: implement this based on _generate_flow_json
        return None

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """Execute a line synchronously.

        For now, we add this method to support the streaming output; maybe we can remove this method after we
        figure out how to support streaming output in async mode.
        If enable_stream_output is False, this method will call exec_line_async to get the line result.

        :param inputs: The inputs of the line.
        :type inputs: Mapping[str, Any]
        :param index: The index of the line to execute.
        :type index: Optional[int]
        :param run_id: The id of the run.
        :type run_id: Optional[str]
        :return: The line result.
        :rtype: LineResult
        """
        if not self.enable_stream_output:
            return async_run_allowing_running_loop(
                self.exec_line_async,
                inputs=inputs,
                index=index,
                run_id=run_id,
            )

        start_time = datetime.utcnow()
        # call execution api to get line results
        url = self.api_endpoint + "/execution"
        payload = {"run_id": run_id, "line_number": index, "inputs": inputs}
        headers = {"Accept": "text/event-stream"}

        def generator():
            with httpx.Client() as client:
                with client.stream("POST", url, json=payload, timeout=LINE_TIMEOUT_SEC, headers=headers) as response:
                    if response.status_code != 200:
                        result = self._process_http_response(response)
                        run_info = FlowRunInfo.create_with_error(start_time, inputs, index, run_id, result)
                        yield LineResult(output={}, aggregation_inputs={}, run_info=run_info, node_run_infos={})
                    for line in response.iter_lines():
                        chunk_data = json.loads(line)
                        # only support one chat output for now
                        yield LineResult.deserialize(chunk_data)

        origin_generator = generator()

        line_result = next(origin_generator)
        async_run_allowing_running_loop(self._activate_generator)
        if self.chat_output_name is not None and self.chat_output_name in line_result.output:
            first_chat_output = line_result.output[self.chat_output_name]

            def final_generator():
                yield first_chat_output
                for output in origin_generator:
                    yield output.output[self.chat_output_name]
                async_run_allowing_running_loop(self._deactivate_generator)

            # Note: the generator output should be saved in both line_result.output and line_result.run_info.output
            line_result.output[self.chat_output_name] = final_generator()
            line_result.run_info.output[self.chat_output_name] = final_generator()

        # TODO: do we support streaming output for non-chat flow and what to return if so?
        return line_result

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        if self.enable_stream_output:
            # Todo: update to async, will get no result in "async for" of final_generator function in async mode
            raise NotSupported("Stream output is not supported in async mode for now")

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
            # use this instead of response.text to handle streaming response
            response_text = response.read().decode(DEFAULT_ENCODING)
            # if the status code is not 200, log the error
            message_format = "Unexpected error when executing a line, status code: {status_code}, error: {error}"
            bulk_logger.error(message_format.format(status_code=response.status_code, error=response_text))
            # if response can be parsed as json, return the error dict
            # otherwise, wrap the error in an UnexpectedError and return the error dict
            try:
                error_dict = json.loads(response_text)
                return error_dict["error"]
            except (JSONDecodeError, KeyError):
                unexpected_error = UnexpectedError(
                    message_format=message_format, status_code=response.status_code, error=response_text
                )
                return ExceptionPresenter.create(unexpected_error).to_dict()
