# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor.
import contextlib
import logging
from pathlib import Path
from types import GeneratorType
from typing import Any, Mapping, Optional, Tuple, Union

from colorama import Fore, init

from promptflow._constants import LINE_NUMBER_KEY, FlowLanguage
from promptflow._core._errors import NotSupported
from promptflow._internal import ConnectionManager
from promptflow._proxy import ProxyFactory
from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME
from promptflow._sdk._utilities.general_utils import get_flow_name, get_flow_path
from promptflow._sdk.entities._flows import Flow, FlowContext, Prompty
from promptflow._sdk.operations._local_storage_operations import LoggerOperations
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.dataclass_serializer import convert_eager_flow_output_to_dict
from promptflow._utils.exception_utils import ErrorResponse
from promptflow._utils.flow_utils import dump_flow_result, parse_variant
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.flow import PromptyFlow as ExecutablePromptyFlow
from promptflow.contracts.run_info import RunInfo, Status
from promptflow.exceptions import UserErrorException
from promptflow.executor._result import LineResult
from promptflow.storage._run_storage import DefaultRunStorage
from promptflow.tracing._start_trace import is_collection_writeable, start_trace

from ..entities._flows import FlexFlow
from .utils import (
    SubmitterHelper,
    flow_overwrite_context,
    print_chat_output,
    resolve_generator,
    show_node_log_and_output,
)

logger = get_cli_sdk_logger()


class TestSubmitter:
    """
    Submitter for testing flow/node.

    A submitter will be bonded to a test run (including whether this is a node test or a flow test) after __init__,
    and will be bonded to a specific executor proxy within an init context:
    1) we will occupy some resources like a temporary folder to save flow with variant resolved, or an execution
      service process if applicable;
    2) output path will also be fixed within an init context;

    Dependent resources like execution service will be created and released within the init context:
    with TestSubmitter(...).init(...) as submitter:
        # dependent resources are created, e.g., we may assume that an execution service is started here if applicable
        ...
    # dependent resources are released
    ...
    """

    def __init__(
        self,
        flow: Union[Flow, FlexFlow],
        flow_context: FlowContext,
        client=None,
    ):
        self._flow = flow
        self.entry = flow.entry if isinstance(flow, FlexFlow) else None
        self._origin_flow = flow
        self._dataplane_flow = None
        self.flow_context = flow_context
        # TODO: remove this
        self._variant = flow_context.variant
        from .._pf_client import PFClient

        self._client = client if client else PFClient()

        # below attributes will be set within init context
        # TODO: try to minimize the attribute count
        self._output_base: Optional[Path] = None
        self._relative_flow_output_path: Optional[Path] = None
        self._connections: Optional[dict] = None
        self._target_node = None
        self._storage = None
        self._enable_stream_output = None
        self._executor_proxy = None
        self._within_init_context = False

    @property
    def executor_proxy(self):
        self._raise_if_not_within_init_context()
        return self._executor_proxy

    def _raise_if_not_within_init_context(self):
        if not self._within_init_context:
            raise UserErrorException("This method should be called within the init context.")

    @property
    def enable_stream_output(self) -> bool:
        self._raise_if_not_within_init_context()
        return self._enable_stream_output

    @property
    def flow(self):
        self._raise_if_not_within_init_context()
        return self._flow

    @property
    def dataplane_flow(self):
        # TODO: test submitter shouldn't interact with dataplane flow directly
        if not self._dataplane_flow:
            if isinstance(self.flow, Prompty):
                self._dataplane_flow = ExecutablePromptyFlow.deserialize(self.flow._data)
            else:
                self._dataplane_flow = ExecutableFlow.from_yaml(flow_file=self.flow.path, working_dir=self.flow.code)
        return self._dataplane_flow

    @property
    def output_base(self) -> Path:
        self._raise_if_not_within_init_context()
        return self._output_base

    @property
    def relative_flow_output_path(self) -> Path:
        self._raise_if_not_within_init_context()
        return self._relative_flow_output_path

    @property
    def target_node(self) -> Optional[str]:
        self._raise_if_not_within_init_context()
        return self._target_node

    @contextlib.contextmanager
    def _resolve_variant(self, init_kwargs=None):
        if self.flow_context.variant:
            tuning_node, node_variant = parse_variant(self.flow_context.variant)
        else:
            tuning_node, node_variant = None, None

        with flow_overwrite_context(
            flow=self._origin_flow,
            tuning_node=tuning_node,
            variant=node_variant,
            connections=self.flow_context.connections,
            overrides=self.flow_context.overrides,
            init_kwargs=init_kwargs,
        ) as temp_flow:
            # TODO execute flow test in a separate process.

            with _change_working_dir(temp_flow.code):
                self._flow = temp_flow
                self._tuning_node = tuning_node
                self._node_variant = node_variant
                yield self
                self._flow = None
                self._dataplane_flow = None
                self._tuning_node = None
                self._node_variant = None

    @classmethod
    def _resolve_environment_variables(cls, environment_variable_overrides, flow: Flow, client):
        return SubmitterHelper.load_and_resolve_environment_variables(
            flow=flow, environment_variable_overrides=environment_variable_overrides, client=client
        )

    @classmethod
    def _resolve_output_path(
        cls, *, output_base: Optional[str], default: Path, target_node: str
    ) -> Tuple[Path, Path, Path]:
        if output_base:
            output_base, output_sub = Path(output_base), Path(".")
        else:
            output_base, output_sub = Path(default), Path(PROMPT_FLOW_DIR_NAME)

        output_base.mkdir(parents=True, exist_ok=True)

        log_path = output_base / output_sub / (f"{target_node}.node.log" if target_node else "flow.log")
        return output_base, log_path, output_sub

    @contextlib.contextmanager
    def init(
        self,
        *,
        connections: Optional[dict] = None,
        target_node: Optional[str] = None,
        environment_variables: Optional[dict] = None,
        stream_log: bool = True,
        output_path: Optional[str] = None,
        session: Optional[str] = None,
        collection: Optional[str] = None,
        stream_output: bool = True,
        init_kwargs: Optional[dict] = None,
    ):
        """
        Create/Occupy dependent resources to execute the test within the context.
        Resources will be released after exiting the context.

        :param connections: connection overrides.
        :type connections: dict
        :param target_node: target node name for node test, may only do node_test if specified.
        :type target_node: str
        :param environment_variables: environment variable overrides.
        :type environment_variables: dict
        :param stream_log: whether to stream log to stdout.
        :type stream_log: bool
        :param output_path: output path.
        :type output_path: str
        :param session: session id. If None, a new session id will be generated with _provision_session.
        :type session: str
        :param collection: collection.
        :type collection: str
        :param stream_output: whether to return a generator for streaming output.
        :type stream_output: bool
        :param init_kwargs: Initialization parameters for flex flow, only supported when flow is callable class.
        :type init: init_kwargs
        :return: TestSubmitter instance.
        :rtype: TestSubmitter
        """
        with self._resolve_variant(init_kwargs=init_kwargs):
            # temp flow is generated, will use self.flow instead of self._origin_flow in the following context
            self._within_init_context = True
            self._target_node = target_node
            self._enable_stream_output = stream_output

            SubmitterHelper.init_env(
                environment_variables=self._resolve_environment_variables(
                    environment_variable_overrides=environment_variables,
                    flow=self.flow,
                    client=self._client,
                )
                or {},
            )

            # do not enable trace when test single node, as we have not determined this behavior
            if target_node is None:
                logger.debug("start trace for flow test...")
                flow_path = get_flow_path(self._origin_flow)
                logger.debug("flow path for test.start_trace: %s", flow_path)
                if collection is not None:
                    logger.debug("collection is user specified: %s, will use it...", collection)
                    start_trace(collection=collection, session=session, path=flow_path)
                else:
                    if is_collection_writeable():
                        logger.debug("trace collection is writeable, will use flow name as collection...")
                        collection_for_test = get_flow_name(self._origin_flow)
                        logger.debug("collection for test: %s", collection_for_test)
                        # pass with internal parameter `_collection`
                        start_trace(session=session, _collection=collection_for_test, path=flow_path)
                    else:
                        logger.debug("trace collection is protected, will honor existing collection.")
                        start_trace(session=session, path=flow_path)

            self._output_base, log_path, output_sub = self._resolve_output_path(
                output_base=output_path,
                default=self.flow.code,
                target_node=target_node,
            )
            self._relative_flow_output_path = output_sub / "output"

            # use flow instead of origin_flow here, as flow can be incomplete before resolving additional includes
            self._connections = connections or SubmitterHelper.resolve_connections(
                self.flow,
                self._client,
            )
            credential_list = ConnectionManager(self._connections).get_secret_list()

            with LoggerOperations(
                file_path=log_path.as_posix(),
                stream=stream_log,
                credential_list=credential_list,
            ):
                # storage must be created within the LoggerOperations context to shadow credentials
                self._storage = DefaultRunStorage(
                    base_dir=self.output_base,
                    sub_dir=output_sub / "intermediate",
                )

                self._executor_proxy = ProxyFactory().create_executor_proxy(
                    self.flow.path,
                    self.flow.code,
                    connections=self._connections,
                    storage=self._storage,
                    log_path=log_path,
                    enable_stream_output=stream_output,
                    language=self.flow.language,
                    init_kwargs=init_kwargs,
                    logging_level=logging.INFO,
                )

                try:
                    yield self
                finally:
                    if self.executor_proxy:
                        async_run_allowing_running_loop(self.executor_proxy.destroy)

            self._within_init_context = False

    def resolve_data(
        self, node_name: str = None, inputs: dict = None, chat_history_name: str = None, dataplane_flow=None
    ):
        """
        Resolve input to flow/node test inputs.
        Raise user error when missing required inputs. And log warning when unknown inputs appeared.

        :param node_name: Node name.
        :type node_name: str
        :param inputs: Inputs of flow/node test.
        :type inputs: dict
        :param chat_history_name: Chat history name.
        :type chat_history_name: str
        :return: Dict of flow inputs, Dict of reference node output.
        :rtype: dict, dict
        """
        from promptflow.contracts.flow import InputValueType

        # TODO: only store dataplane flow in context resolver
        dataplane_flow = dataplane_flow or self.dataplane_flow
        inputs = (inputs or {}).copy()
        flow_inputs, dependency_nodes_outputs, merged_inputs = {}, {}, {}
        missing_inputs = []
        # Using default value of inputs as flow input
        if node_name:
            node = next(filter(lambda item: item.name == node_name, dataplane_flow.nodes), None)
            if not node:
                raise UserErrorException(f"Cannot find {node_name} in the flow.")
            for name, value in node.inputs.items():
                if value.value_type == InputValueType.NODE_REFERENCE:
                    input_name = (
                        f"{value.value}.{value.section}.{value.property}"
                        if value.property
                        else f"{value.value}.{value.section}"
                    )
                    if input_name in inputs:
                        dependency_input = inputs.pop(input_name)
                    elif name in inputs:
                        dependency_input = inputs.pop(name)
                    else:
                        missing_inputs.append(name)
                        continue
                    if value.property:
                        dependency_nodes_outputs[value.value] = dependency_nodes_outputs.get(value.value, {})
                        if isinstance(dependency_input, dict) and value.property in dependency_input:
                            dependency_nodes_outputs[value.value][value.property] = dependency_input[value.property]
                        elif dependency_input:
                            dependency_nodes_outputs[value.value][value.property] = dependency_input
                    else:
                        dependency_nodes_outputs[value.value] = dependency_input
                    merged_inputs[name] = dependency_input
                elif value.value_type == InputValueType.FLOW_INPUT:
                    input_name = f"{value.prefix}{value.value}"
                    if input_name in inputs:
                        flow_input = inputs.pop(input_name)
                    elif name in inputs:
                        flow_input = inputs.pop(name)
                    else:
                        flow_input = dataplane_flow.inputs[value.value].default
                        if flow_input is None:
                            missing_inputs.append(name)
                            continue
                    flow_inputs[value.value] = flow_input
                    merged_inputs[name] = flow_input
                else:
                    flow_inputs[name] = inputs.pop(name) if name in inputs else value.value
                    merged_inputs[name] = flow_inputs[name]
        else:
            for name, value in dataplane_flow.inputs.items():
                if name in inputs:
                    flow_inputs[name] = inputs.pop(name)
                    merged_inputs[name] = flow_inputs[name]
                else:
                    if value.default is None:
                        # When the flow is a chat flow and chat_history has no default value, set an empty list for it
                        if chat_history_name and name == chat_history_name:
                            flow_inputs[name] = []
                        else:
                            missing_inputs.append(name)
                    else:
                        flow_inputs[name] = value.default
                        merged_inputs[name] = flow_inputs[name]
        prefix = node_name or "flow"
        if missing_inputs:
            raise UserErrorException(f'Required input(s) {missing_inputs} are missing for "{prefix}".')
        if inputs:
            logger.warning(f"Unknown input(s) of {prefix}: {inputs}")
            flow_inputs.update(inputs)
            merged_inputs.update(inputs)
        logger.info(f"{prefix} input(s): {merged_inputs}")
        return flow_inputs, dependency_nodes_outputs

    def _get_output_path(self, kwargs) -> Tuple[Path, Path]:
        """Return the output path and sub dir path of the output."""
        # Note that the different relative path in LocalRunStorage will lead to different image reference
        if kwargs.get("output_path"):
            return Path(kwargs["output_path"]), Path(".")
        return Path(self.flow.code), Path(PROMPT_FLOW_DIR_NAME)

    def flow_test(
        self,
        inputs: Mapping[str, Any],
        allow_generator_output: bool = False,  # TODO: remove this
        run_id: str = None,
        init_kwargs: Optional[dict] = None,
    ) -> LineResult:
        """
        Submit a flow test.
        Note that you will get an error if you call this method with target_node specified in the init context.

        We have separate interface for flow test and node test as they have different input and output.
        However, target node will determine log path, which should be specified in the init context, e.g.,
        it is required for starting an execution service.

        :param inputs: Inputs of the flow.
        :type inputs: dict
        :param allow_generator_output: Allow generator output.
        :type allow_generator_output: bool
        :param stream_output: Stream output.
        :type stream_output: bool
        :param run_id: Run id will be set in operation context and used for session
        :type run_id: str
        :param init_kwargs: Initialization parameters for flex flow, only supported when flow is callable class.
        :type init_kwargs: dict
        """
        self._raise_if_not_within_init_context()
        if self.target_node:
            raise UserErrorException("target_node is not allowed for flow test.")

        if self.flow.language == FlowLanguage.Python:
            # TODO: replace with implementation based on PythonExecutorProxy
            from promptflow.executor.flow_executor import execute_flow

            line_result = execute_flow(
                flow_file=self.flow.path,
                working_dir=self.flow.code,
                output_dir=self.output_base / self.relative_flow_output_path,
                connections=self._connections,
                inputs=inputs,
                enable_stream_output=self.enable_stream_output,
                allow_generator_output=allow_generator_output,
                entry=self.entry,
                storage=self._storage,
                run_id=run_id,
                init_kwargs=init_kwargs,
            )
        else:
            from promptflow._utils.multimedia_utils import BasicMultimediaProcessor

            # TODO: support run_id for non-python
            # TODO: most of below code is duplicate to flow_executor.execute_flow
            line_result: LineResult = self.executor_proxy.exec_line(inputs, index=0)
            # csharp flow does not support multimedia contract currently, just use the default multimedia processor
            line_result.output = BasicMultimediaProcessor().persist_multimedia_data(
                line_result.output, base_dir=self.output_base, sub_dir=self.relative_flow_output_path
            )
            if line_result.aggregation_inputs:
                # Convert inputs of aggregation to list type
                flow_inputs = {k: [v] for k, v in inputs.items()}
                aggregation_inputs = {k: [v] for k, v in line_result.aggregation_inputs.items()}

                aggregation_results = async_run_allowing_running_loop(
                    self.executor_proxy.exec_aggregation_async, flow_inputs, aggregation_inputs
                )

                line_result.node_run_infos.update(aggregation_results.node_run_infos)
                line_result.run_info.metrics = aggregation_results.metrics
            if isinstance(line_result.output, dict):
                # remove line_number from output
                line_result.output.pop(LINE_NUMBER_KEY, None)

        self._get_generator_outputs(line_result.output)
        return line_result

    def node_test(
        self,
        flow_inputs: Mapping[str, Any],
        dependency_nodes_outputs: Mapping[str, Any],
    ) -> RunInfo:
        self._raise_if_not_within_init_context()
        if self.target_node is None:
            raise UserErrorException("target_node is required for node test.")

        if self.flow.language == FlowLanguage.CSharp:
            raise NotSupported("Node test is not supported for CSharp flow for now.")

        from promptflow.executor.flow_executor import FlowExecutor

        return FlowExecutor.load_and_exec_node(
            self.flow.path,
            self.target_node,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=self._connections,
            working_dir=self.flow.code,
            storage=self._storage,
        )

    def _chat_flow(self, inputs, chat_history_name, show_step_output=False):
        """
        Interact with Chat Flow. Do the following:
            1. Combine chat_history and user input as the input for each round of the chat flow.
            2. Each round of chat is executed once flow test.
            3. Prefix the output for distinction.
        """

        @contextlib.contextmanager
        def change_logger_level(level):
            origin_level = logger.level
            logger.setLevel(level)
            yield
            logger.setLevel(origin_level)

        init(autoreset=True)
        default_chat_history = list(self.dataplane_flow.inputs.get(chat_history_name).default or [])
        chat_history = inputs.get[chat_history_name] if chat_history_name in inputs else default_chat_history
        # TODO: test submitter should not interact with dataplane flow directly
        input_name = next(
            filter(lambda key: self.dataplane_flow.inputs[key].is_chat_input, self.dataplane_flow.inputs.keys())
        )
        output_name = next(
            filter(
                lambda key: self.dataplane_flow.outputs[key].is_chat_output,
                self.dataplane_flow.outputs.keys(),
            ),
            None,
        )

        while True:
            # generator record should be reset for each round of chat
            generator_record = {}
            try:
                print(f"{Fore.GREEN}User: ", end="")
                input_value = input()
                if not input_value.strip():
                    continue
            except (KeyboardInterrupt, EOFError):
                print("Terminate the chat.")
                break
            inputs = inputs or {}
            inputs[input_name] = input_value
            inputs[chat_history_name] = chat_history
            with change_logger_level(level=logging.WARNING):
                chat_inputs, _ = self.resolve_data(inputs=inputs)

            init_kwargs = None
            if isinstance(self.flow, Prompty):
                # Override prompt output format configuration and only return first choice in interactive mode.
                init_kwargs = {"model": {"response": "first"}}
            flow_result = self.flow_test(
                inputs=chat_inputs,
                allow_generator_output=True,
                init_kwargs=init_kwargs,
            )
            self._raise_error_when_test_failed(flow_result, show_trace=True)
            show_node_log_and_output(flow_result.node_run_infos, show_step_output, generator_record)

            print(f"{Fore.YELLOW}Bot: ", end="")
            # For prompty flow, if outputs are not specified, prompty output will be treated as chat output.
            chat_output = flow_result.output[output_name] if output_name else flow_result.output
            print_chat_output(
                chat_output,
                generator_record,
                generator_key=f"run.outputs.{output_name or 'output'}",
            )
            flow_result = resolve_generator(flow_result, generator_record)
            custom_path = None
            if isinstance(self.flow, (Prompty, FlexFlow)):
                # For prompty and flex flow, the format of chat history is consistent with openai.
                # [{"role": "role_name", "content": "content_vale"}]
                resolved_chat_output = flow_result.output[output_name] if output_name else flow_result.output
                history = [
                    {"role": "user", "content": input_value},
                    {"role": "assistant", "content": resolved_chat_output},
                ]
                chat_history.extend(history)
                if isinstance(self.flow, Prompty):
                    custom_path = (
                        Path(self._origin_flow.code) / PROMPT_FLOW_DIR_NAME / Path(self._origin_flow.path).stem
                    )
            else:
                # TODO: In order not to break the original dag flow, the original chat history format is maintained.
                # Compatibility with older format will be done in the future.
                flow_outputs = {k: v for k, v in flow_result.output.items()}
                history = {"inputs": {input_name: input_value}, "outputs": flow_outputs}
                chat_history.append(history)
            dump_flow_result(
                flow_folder=self._origin_flow.code, flow_result=flow_result, prefix="chat", custom_path=custom_path
            )

    @staticmethod
    def _raise_error_when_test_failed(test_result, show_trace=False):
        from promptflow.executor._result import LineResult

        test_status = test_result.run_info.status if isinstance(test_result, LineResult) else test_result.status

        if test_status == Status.Failed:
            error_dict = test_result.run_info.error if isinstance(test_result, LineResult) else test_result.error
            error_response = ErrorResponse.from_error_dict(error_dict)
            user_execution_error = error_response.get_user_execution_error_info()
            error_message = error_response.message
            # sdk will wrap exception here, so we need get user code stacktrace or recursively get debug info
            # stacktrace as inner exception here
            stack_trace = user_execution_error.get("traceback", "") or TestSubmitter._recursively_get_stacktrace(
                error_dict.get("debugInfo", {})
            )
            error_type = user_execution_error.get("type", "Exception")
            if show_trace:
                print(stack_trace)
            raise UserErrorException(f"{error_type}: {error_message}", error=stack_trace)

    @staticmethod
    def _get_generator_outputs(outputs):
        # covert output to dict to unify the log
        outputs = convert_eager_flow_output_to_dict(outputs)
        if isinstance(outputs, dict):
            generator_outputs = {key: output for key, output in outputs.items() if isinstance(output, GeneratorType)}
            if generator_outputs:
                logger.info(f"Some streaming outputs in the result, {generator_outputs.keys()}")

    @staticmethod
    def _recursively_get_stacktrace(debug_info: dict):
        if not debug_info:
            return ""
        stack_trace = debug_info.get("stackTrace", "") + debug_info.get("message", "")
        inner_exception = debug_info.get("innerException", {})
        stack_trace = TestSubmitter._recursively_get_stacktrace(inner_exception) + stack_trace
        return stack_trace
