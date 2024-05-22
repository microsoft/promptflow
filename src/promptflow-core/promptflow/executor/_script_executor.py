import contextlib
import dataclasses
import importlib
import inspect
import os.path
import uuid
from collections.abc import Iterator
from dataclasses import is_dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from promptflow._constants import LINE_NUMBER_KEY, FlowType, MessageFormatType
from promptflow._core.log_manager import NodeLogManager
from promptflow._core.run_tracker import RunTracker
from promptflow._core.tool_meta_generator import PythonLoadError
from promptflow._utils.async_utils import async_to_sync, sync_to_async
from promptflow._utils.dataclass_serializer import convert_eager_flow_output_to_dict
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.execution_utils import apply_default_value_for_input
from promptflow._utils.logger_utils import logger
from promptflow._utils.multimedia_utils import BasicMultimediaProcessor
from promptflow._utils.tool_utils import function_to_interface
from promptflow._utils.yaml_utils import load_yaml
from promptflow.connections import ConnectionProvider
from promptflow.contracts.flow import FlexFlow, Flow
from promptflow.contracts.tool import ConnectionType
from promptflow.core import log_metric
from promptflow.core._connection_provider._dict_connection_provider import DictConnectionProvider
from promptflow.core._model_configuration import (
    MODEL_CONFIG_NAME_2_CLASS,
    AzureOpenAIModelConfiguration,
    OpenAIModelConfiguration,
)
from promptflow.exceptions import ErrorTarget
from promptflow.executor._errors import InvalidFlexFlowEntry, InvalidModelConfigValueType
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.storage import AbstractRunStorage
from promptflow.storage._run_storage import DefaultRunStorage
from promptflow.tracing._trace import _traced
from promptflow.tracing._tracer import Tracer
from promptflow.tracing.contracts.trace import TraceType

from ._errors import FlowEntryInitializationError, InvalidAggregationFunction, ScriptExecutionError
from .flow_executor import FlowExecutor
from .flow_validator import FlowValidator


class ScriptExecutor(FlowExecutor):
    def __init__(
        self,
        flow_file: Union[Path, str, Callable],
        connections: Optional[Union[dict, ConnectionProvider]] = None,
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
    ):
        logger.debug(f"Start initializing the executor with {flow_file}.")
        logger.debug(f"Init params for script executor: {init_kwargs}")

        if connections and isinstance(connections, dict):
            connections = DictConnectionProvider(connections)
        self._connections = connections

        self._flow_file = flow_file
        entry = flow_file  # Entry could be both a path or a callable
        self._entry = entry
        if isinstance(entry, (str, Path)):
            self._working_dir = Flow._resolve_working_dir(entry, working_dir)
        else:
            self._working_dir = working_dir or Path.cwd()

        # load flow if possible
        try:
            flow_file = os.path.join(self._working_dir, self._flow_file)
            with open(flow_file, "r", encoding="utf-8") as fin:
                flow_data = load_yaml(fin)
            flow = FlexFlow.deserialize(flow_data)
        except Exception as e:
            logger.debug(f"Failed to load flow from file {self._flow_file} with error: {e}")
            flow = None
        self._flow = flow

        self._init_kwargs = self._apply_sample_init(init_kwargs=init_kwargs)
        self._init_input_sign()
        self._initialize_function()
        self._storage = storage or DefaultRunStorage()
        self._flow_id = "default_flow_id"
        self._log_interval = 60
        self._line_timeout_sec = 600
        self._message_format = MessageFormatType.BASIC
        self._multimedia_processor = BasicMultimediaProcessor()

    @classmethod
    def _get_func_name(cls, func: Callable):
        try:
            original_func = getattr(func, "__original_function")
            if isinstance(original_func, partial):
                original_func = original_func.func
            return original_func.__qualname__
        except AttributeError:
            return func.__qualname__

    @contextlib.contextmanager
    def _exec_line_context(self, run_id, line_number):
        # TODO: refactor NodeLogManager, for script executor, we don't have node concept.
        log_manager = NodeLogManager()
        # No need to clear node context, log_manger will be cleared after the with block.
        log_manager.set_node_context(run_id, "Flex", line_number)
        with log_manager, self._update_operation_context(run_id, line_number):
            yield

    _execution_target = FlowType.FLEX_FLOW

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        allow_generator_output: bool = False,
        **kwargs,
    ) -> LineResult:
        if self._is_async:
            from promptflow._utils.async_utils import async_run_allowing_running_loop

            return async_run_allowing_running_loop(
                self.exec_line_async,
                inputs=inputs,
                index=index,
                run_id=run_id,
                allow_generator_output=allow_generator_output,
                **kwargs,
            )
        run_id = run_id or str(uuid.uuid4())
        inputs = self._apply_sample_inputs(inputs=inputs)
        inputs = apply_default_value_for_input(self._inputs_sign, inputs)
        with self._exec_line_context(run_id, index):
            return self._exec_line(inputs, index, run_id, allow_generator_output=allow_generator_output)

    def _exec_line_preprocess(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        allow_generator_output: bool = False,
    ):
        line_run_id = run_id if index is None else f"{run_id}_{index}"
        run_tracker = RunTracker(self._storage)
        run_tracker.allow_generator_types = allow_generator_output
        run_info = run_tracker.start_flow_run(
            flow_id=self._flow_id,
            root_run_id=run_id,
            run_id=line_run_id,
            parent_run_id=run_id,
            inputs=inputs,
            index=index,
            message_format=self._message_format,
        )
        # Executor will add line_number to batch inputs if there is no line_number in the original inputs,
        # which should be removed, so, we only preserve the inputs that are contained in self._inputs.
        inputs = {k: inputs[k] for k in self._inputs if k in inputs}
        inputs = FlowValidator._ensure_flow_inputs_type_inner(self._inputs_sign, inputs)
        return run_info, inputs, run_tracker, None, []

    def _exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        allow_generator_output: bool = False,
    ) -> LineResult:
        run_info, inputs, run_tracker, output, traces = self._exec_line_preprocess(
            inputs,
            index,
            run_id,
            allow_generator_output,
        )
        line_run_id = run_info.run_id
        try:
            Tracer.start_tracing(line_run_id)
            output = self._func(**inputs)
            output = self._stringify_generator_output(output) if not allow_generator_output else output
            traces = Tracer.end_tracing(line_run_id)
            # Should convert output to dict before storing it to run info, since we will add key 'line_number' to it,
            # so it must be a dict.
            output_dict = convert_eager_flow_output_to_dict(output)
            run_info.api_calls = traces
            run_tracker.set_openai_metrics(line_run_id)
            run_tracker.end_run(line_run_id, result=output_dict)
        except Exception as e:
            # We assume the error comes from user's code.
            # For these cases, raise ScriptExecutionError, which is classified as UserError
            # and shows stack trace in the error message to make it easy for user to troubleshoot.
            error_type_and_message = f"({e.__class__.__name__}) {e}"
            ex = ScriptExecutionError(
                message_format="Execution failure in '{func_name}': {error_type_and_message}",
                func_name=self._func_name,
                error_type_and_message=error_type_and_message,
                error=e,
            )
            if not traces:
                traces = Tracer.end_tracing(line_run_id)
            run_tracker.end_run(line_run_id, ex=ex, traces=traces)
        finally:
            run_tracker.persist_flow_run(run_info)
        return self._construct_line_result(output, run_info)

    def _construct_line_result(self, output, run_info):
        line_result = LineResult(output, {}, run_info, {})
        #  Return line result with index
        if run_info.index is not None and isinstance(line_result.output, dict):
            line_result.output[LINE_NUMBER_KEY] = run_info.index
        return line_result

    @property
    def has_aggregation_node(self):
        return hasattr(self, "_aggr_func")

    def exec_aggregation(
        self,
        inputs: Mapping[str, Any],
        aggregation_inputs: List[Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        if not self._aggr_func:
            return AggregationResult({}, {}, {})
        # Similar to dag flow, add a prefix "reduce" for run id of aggregation function.
        run_id = f"{run_id}_reduce" if run_id is not None else f"{str(uuid.uuid4())}_reduce"
        with self._update_operation_context_for_aggregation(run_id):
            return self._exec_aggregation(aggregation_inputs)

    def _exec_aggregation(
        self,
        inputs: List[Any],
    ) -> AggregationResult:
        output, metrics = None, {}
        try:
            output = self._aggr_func(**{self._aggr_input_name: inputs})
            if isinstance(output, dict):
                metrics = output
                for k, v in metrics.items():
                    log_metric(k, v)
            else:
                logger.warning("The output of aggregation function isn't a dictionary, skip the metrices update.")
        except Exception as e:
            error_type_and_message = f"({e.__class__.__name__}) {e}"
            e = ScriptExecutionError(
                message_format="Execution failure in '{func_name}': {error_type_and_message}",
                func_name=self._aggr_func.__name__,
                error_type_and_message=error_type_and_message,
            )
            error = ExceptionPresenter.create(e).to_dict(include_debug_info=True)
            logger.warning(f"Failed to execute aggregation function with error: {error}")
            logger.warning("The flow will have empty metrics.")
        return AggregationResult(output, metrics, {})

    async def exec_aggregation_async(
        self,
        inputs: Mapping[str, Any],
        aggregation_inputs: List[Any],
        run_id: Optional[str] = None,
    ):
        if not self._aggr_func:
            return AggregationResult({}, {}, {})
        # Similar to dag flow, add a prefix "reduce" for run id of aggregation function.
        run_id = f"{run_id}_reduce" if run_id is not None else f"{str(uuid.uuid4())}_reduce"
        with self._update_operation_context_for_aggregation(run_id):
            return await self._exec_aggregation_async(aggregation_inputs)

    async def _exec_aggregation_async(self, inputs):
        output, metrics = None, {}
        try:
            output = await self._aggr_func_async(**{self._aggr_input_name: inputs})
            if isinstance(output, dict):
                metrics = output
                for k, v in metrics.items():
                    log_metric(k, v)
            else:
                logger.warning("The output of aggregation function isn't a dictionary, skip the metrices update.")
        except Exception as e:
            error_type_and_message = f"({e.__class__.__name__}) {e}"
            e = ScriptExecutionError(
                message_format="Execution failure in '{func_name}': {error_type_and_message}",
                func_name=self._aggr_func.__name__,
                error_type_and_message=error_type_and_message,
            )
            error = ExceptionPresenter.create(e).to_dict(include_debug_info=True)
            logger.warning(f"Failed to execute aggregation function with error: {error}")
            logger.warning("The flow will have empty metrics.")
        return AggregationResult(output, metrics, {})

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        allow_generator_output: bool = False,
        **kwargs,
    ) -> LineResult:
        run_id = run_id or str(uuid.uuid4())
        inputs = self._apply_sample_inputs(inputs=inputs)
        inputs = apply_default_value_for_input(self._inputs_sign, inputs)
        with self._exec_line_context(run_id, index):
            return await self._exec_line_async(inputs, index, run_id, allow_generator_output=allow_generator_output)

    async def _exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        allow_generator_output: bool = False,
    ) -> LineResult:
        run_info, inputs, run_tracker, output, traces = self._exec_line_preprocess(
            inputs,
            index,
            run_id,
            allow_generator_output,
        )
        line_run_id = run_info.run_id
        try:
            Tracer.start_tracing(line_run_id)
            output = self._func_async(**inputs)
            # Get the result of the output if it is an awaitable.
            # Note that if it is an async generator, it would not be awaitable.
            if inspect.isawaitable(output):
                output = await output
            output = await self._stringify_generator_output_async(output) if not allow_generator_output else output
            traces = Tracer.end_tracing(line_run_id)
            output_dict = convert_eager_flow_output_to_dict(output)
            run_info.api_calls = traces
            run_tracker.set_openai_metrics(line_run_id)
            run_tracker.end_run(line_run_id, result=output_dict)
        except Exception as e:
            if not traces:
                traces = Tracer.end_tracing(line_run_id)
            run_tracker.end_run(line_run_id, ex=e, traces=traces)
        finally:
            run_tracker.persist_flow_run(run_info)
        return self._construct_line_result(output, run_info)

    async def _stringify_generator_output_async(self, output):
        if isinstance(output, dict):
            return await super()._stringify_generator_output_async(output)
        if is_dataclass(output):
            kv = {field.name: getattr(output, field.name) for field in dataclasses.fields(output)}
            updated_kv = await super()._stringify_generator_output_async(kv)
            return dataclasses.replace(output, **updated_kv)
        kv = {"output": output}
        updated_kv = await super()._stringify_generator_output_async(kv)
        return updated_kv["output"]

    def _stringify_generator_output(self, output):
        if isinstance(output, dict):
            return super()._stringify_generator_output(output)
        elif is_dataclass(output):
            fields = dataclasses.fields(output)
            for field in fields:
                if isinstance(getattr(output, field.name), Iterator):
                    consumed_values = "".join(str(chuck) for chuck in getattr(output, field.name))
                    setattr(output, field.name, consumed_values)
        else:
            if isinstance(output, Iterator):
                output = "".join(str(chuck) for chuck in output)
        return output

    def enable_streaming_for_llm_flow(self, stream_required: Callable[[], bool]):
        # no need to inject streaming here, user can directly pass the param to the function
        return

    def get_inputs_definition(self):
        return self._inputs

    def _resolve_init_kwargs(self, c: type, init_kwargs: dict):
        """Resolve init kwargs, the connection names will be resolved to connection objects."""
        logger.debug(f"Resolving init kwargs: {init_kwargs.keys()}.")
        init_kwargs = apply_default_value_for_input(self._init_sign, init_kwargs)
        sig = inspect.signature(c.__init__)
        connection_params = []
        model_config_param_name_2_cls = {}
        # TODO(3117908): support connection & model config from YAML signature.
        for key, param in sig.parameters.items():
            if ConnectionType.is_connection_class_name(param.annotation.__name__):
                connection_params.append(key)
            elif param.annotation.__name__ in MODEL_CONFIG_NAME_2_CLASS.keys():
                model_config_param_name_2_cls[key] = MODEL_CONFIG_NAME_2_CLASS[param.annotation.__name__]
        if not connection_params and not model_config_param_name_2_cls:
            return init_kwargs
        resolved_init_kwargs = {k: v for k, v in init_kwargs.items()}
        if connection_params:
            self._resolve_connection_params(
                connection_params=connection_params, init_kwargs=init_kwargs, resolved_init_kwargs=resolved_init_kwargs
            )
        if model_config_param_name_2_cls:
            self._resolve_model_config_params(
                model_config_param_name_2_cls=model_config_param_name_2_cls,
                init_kwargs=init_kwargs,
                resolved_init_kwargs=resolved_init_kwargs,
            )

        return resolved_init_kwargs

    def _resolve_connection_params(self, connection_params: list, init_kwargs: dict, resolved_init_kwargs: dict):
        provider = self._connections or ConnectionProvider.get_instance()
        # parse connection
        logger.debug(f"Resolving connection params: {connection_params}")
        for key in connection_params:
            resolved_init_kwargs[key] = provider.get(init_kwargs[key])

    @classmethod
    def _resolve_model_config_params(
        cls, model_config_param_name_2_cls: dict, init_kwargs: dict, resolved_init_kwargs: dict
    ):
        # parse model config
        logger.debug(f"Resolving model config params: {model_config_param_name_2_cls}")
        for key, model_config_cls in model_config_param_name_2_cls.items():
            model_config_val = init_kwargs[key]
            if isinstance(model_config_val, dict):
                logger.debug(f"Recovering model config object from dict: {model_config_val}.")
                model_config_val = model_config_cls(**model_config_val)
            if not isinstance(model_config_val, model_config_cls):
                raise InvalidModelConfigValueType(
                    message_format="Model config value is not an instance of {model_config_cls}, got {value_type}",
                    model_config_cls=model_config_cls,
                    value_type=type(model_config_val),
                )
            if getattr(model_config_val, "connection", None):
                logger.debug(f"Getting connection {model_config_val.connection} for model config.")
                provider = ConnectionProvider.get_instance()
                connection_obj = provider.get(model_config_val.connection)

                if isinstance(model_config_val, AzureOpenAIModelConfiguration):
                    model_config_val = AzureOpenAIModelConfiguration.from_connection(
                        connection=connection_obj, azure_deployment=model_config_val.azure_deployment
                    )
                elif isinstance(model_config_val, OpenAIModelConfiguration):
                    model_config_val = OpenAIModelConfiguration.from_connection(
                        connection=connection_obj, model=model_config_val.model
                    )
            resolved_init_kwargs[key] = model_config_val

    @property
    def is_function_entry(self):
        return hasattr(self._entry, "__call__") or inspect.isfunction(self._entry)

    def _parse_entry_func(self):
        if self.is_function_entry:
            if inspect.isfunction(self._entry):
                return self._entry
            self._initialize_aggr_function(self._entry)
            return self._entry.__call__
        module_name, func_name = self._parse_flow_file()
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            error_type_and_message = f"({e.__class__.__name__}) {e}"
            raise PythonLoadError(
                message_format="Failed to load python module for {entry_file}: {error_type_and_message}",
                entry_file=self._flow_file,
                error_type_and_message=error_type_and_message,
            ) from e
        func = getattr(module, func_name, None)
        # check if func is a callable class
        if inspect.isclass(func):
            if hasattr(func, "__call__"):
                logger.debug(
                    f"Python class entry '{func_name}' has __call__ method, initializing it with {self._init_kwargs}"
                )
                try:
                    resolved_init_kwargs = self._resolve_init_kwargs(func, self._init_kwargs)
                    obj = func(**resolved_init_kwargs)
                except Exception as e:
                    # TODO: scrub secrets in init kwarg values
                    raise FlowEntryInitializationError(init_kwargs=self._init_kwargs, ex=e) from e
                func = getattr(obj, "__call__")
                self._initialize_aggr_function(obj)
            else:
                raise PythonLoadError(
                    message_format="Python class entry '{func_name}' does not have __call__ method.",
                    func_name=func_name,
                    module_name=module_name,
                )
        elif func is None or not inspect.isfunction(func):
            raise PythonLoadError(
                message_format="Failed to load python function '{func_name}' from file '{module_name}', got {func}.",
                func_name=func_name,
                module_name=module_name,
                func=func,
            )
        return func

    def _initialize_function(self):
        func = self._parse_entry_func()
        original_func = getattr(func, "__original_function", func)

        # If the function is not decorated with trace, add trace for it.
        if not hasattr(func, "__original_function"):
            func = _traced(func, trace_type=TraceType.FLOW)
        else:
            if inspect.ismethod(func):
                # For class method, the original function is a function reference that not bound to any object,
                # so we need to pass the instance to it.
                name = name[: -len(".__call__")] if (name := func.__qualname__).endswith(".__call__") else name
                func = _traced(
                    partial(getattr(func, "__original_function"), self=func.__self__),
                    trace_type=TraceType.FLOW,
                    name=name,
                )
            else:
                func = _traced(getattr(func, "__original_function"), trace_type=TraceType.FLOW)
        inputs, _, _, _ = function_to_interface(func)
        self._inputs = {k: v.to_flow_input_definition() for k, v in inputs.items()}
        if inspect.iscoroutinefunction(original_func) or inspect.isasyncgenfunction(original_func):
            self._is_async = True
            self._func = async_to_sync(func)
            self._func_async = func
        else:
            self._is_async = False
            self._func = func
            self._func_async = sync_to_async(func)
        self._func_name = self._get_func_name(func=func)
        return func

    def _initialize_aggr_function(self, flow_obj: object):
        aggr_func = getattr(flow_obj, "__aggregate__", None)
        if aggr_func is not None:
            sign = inspect.signature(aggr_func)
            if len(sign.parameters) != 1:
                raise InvalidAggregationFunction(
                    message_format="The __aggregate__ method should have only one parameter.",
                )
            if not hasattr(aggr_func, "__original_function"):
                aggr_func = _traced(aggr_func)
            if inspect.iscoroutinefunction(aggr_func):
                self._aggr_func = async_to_sync(aggr_func)
                self._aggr_func_async = aggr_func
            else:
                self._aggr_func = aggr_func
                self._aggr_func_async = sync_to_async(aggr_func)
            self._aggr_input_name = list(sign.parameters.keys())[0]

    def _parse_flow_file(self):
        with open(self._working_dir / self._flow_file, "r", encoding="utf-8") as fin:
            flow_dag = load_yaml(fin)
        entry = flow_dag.get("entry", "")
        try:
            module_name, func_name = entry.split(":")
        except Exception as e:
            raise InvalidFlexFlowEntry(
                message_format="Invalid entry '{entry}'.The entry should be in the format of '<module>:<function>'.",
                entry=entry,
                target=ErrorTarget.EXECUTOR,
            ) from e
        return module_name, func_name

    def _init_input_sign(self):
        if not self.is_function_entry and self._flow is not None:
            # In the yaml file, user can define the inputs and init signature for the flow, also SDK may create
            # the signature and add them to the yaml file. We need to get the signature from the yaml file and
            # used for applying default value and ensuring input type.
            # If the default value is an empty string, we will assume user has defined the default value as None
            # in python script. We will exclude it from signature.
            self._inputs_sign = {k: v for k, v in self._flow.inputs.items() if v.default != ""}
            self._init_sign = {k: v for k, v in self._flow.init.items() if v.default != ""}
        else:
            # TODO(3194196): support input signature for function entry.
            # Since there is no yaml file for function entry, we set the inputs and init signature to empty dict.
            self._inputs_sign = {}
            self._init_sign = {}

    def _apply_sample_init(self, init_kwargs: Mapping[str, Any]):
        """Apply sample init if init_kwargs not provided."""
        if not init_kwargs and self._flow:
            sample_init = self._flow.sample.get("init")
            if sample_init:
                logger.debug(f"Init kwargs are not provided, applying sample init: {sample_init}.")
                return sample_init
        return init_kwargs or {}

    def _apply_sample_inputs(self, inputs: Mapping[str, Any]):
        """Apply sample inputs if inputs not provided."""
        if not inputs and self._flow:
            sample_inputs = self._flow.sample.get("inputs")
            if sample_inputs:
                logger.debug(f"Inputs are not provided, applying sample inputs: {sample_inputs}.")
                return sample_inputs
        return inputs or {}
