# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""
This file can generate a meta file for the given prompt template or a python file.
"""
import importlib.util
import inspect
import json
import logging
import multiprocessing
import os
import re
import types
from pathlib import Path
from traceback import TracebackException
from typing import Mapping

from jinja2 import TemplateSyntaxError
from jinja2.environment import COMMENT_END_STRING, COMMENT_START_STRING

from promptflow._constants import PF_MAIN_MODULE_NAME
from promptflow._core._errors import (
    GenerateMetaTimeout,
    MetaFileNotFound,
    MetaFileReadError,
    NoToolTypeDefined,
    NotSupported,
)
from promptflow._core.tool import ToolProvider
from promptflow._core.tool_settings_parser import _parser_tool_icon, _parser_tool_input_settings
from promptflow._core.tool_validation import _validate_tool_function, _validate_tool_schema
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow._utils.exception_utils import (
    ADDITIONAL_INFO_USER_CODE_STACKTRACE,
    ExceptionPresenter,
    get_tb_next,
    last_frame_info,
)
from promptflow._utils.process_utils import block_terminate_signal_to_parent
from promptflow._utils.tool_utils import asdict_without_none, function_to_interface, get_inputs_for_prompt_template
from promptflow.contracts.tool import Tool, ToolType
from promptflow.exceptions import ErrorTarget, UserErrorException


def generate_prompt_tool(name, content, prompt_only=False, source=None):
    """Generate meta for a single jinja template file."""
    # Get all the variable name from a jinja template
    tool_type = ToolType.PROMPT if prompt_only else ToolType.LLM
    try:
        inputs = get_inputs_for_prompt_template(content)
    except TemplateSyntaxError as e:
        error_type_and_message = f"({e.__class__.__name__}) {e}"
        raise JinjaParsingError(
            message_format=(
                "Generate tool meta failed for {tool_type} tool. Jinja parsing failed at line {line_number}: "
                "{error_type_and_message}"
            ),
            tool_type=tool_type.value,
            line_number=e.lineno,
            error_type_and_message=error_type_and_message,
        ) from e
    except Exception as e:
        error_type_and_message = f"({e.__class__.__name__}) {e}"
        raise JinjaParsingError(
            message_format=(
                "Generate tool meta failed for {tool_type} tool. Jinja parsing failed: {error_type_and_message}"
            ),
            tool_type=tool_type.value,
            error_type_and_message=error_type_and_message,
        ) from e

    pattern = f"{COMMENT_START_STRING}(((?!{COMMENT_END_STRING}).)*){COMMENT_END_STRING}"
    match_result = re.match(pattern, content)
    description = match_result.groups()[0].strip() if match_result else None
    # Construct the Tool structure
    tool = Tool(
        name=name,
        description=description,
        type=tool_type,
        inputs=inputs,
        outputs={},
    )
    if source is None:
        tool.code = content
    else:
        tool.source = source
    return tool


def generate_prompt_meta_dict(name, content, prompt_only=False, source=None):
    return asdict_without_none(generate_prompt_tool(name, content, prompt_only, source))


def is_tool(f):
    if not isinstance(f, types.FunctionType):
        return False
    if not hasattr(f, "__tool"):
        return False
    return True


def collect_tool_functions_in_module(m):
    tools = []
    for _, obj in inspect.getmembers(m):
        if is_tool(obj):
            # Note that the tool should be in defined in exec but not imported in exec,
            # so it should also have the same module with the current function.
            if getattr(obj, "__module__", "") != m.__name__:
                continue
            tools.append(obj)
    return tools


def collect_flow_entry_in_module(m, entry):
    func_name = entry.split(":")[-1]
    func = getattr(m, func_name, None)
    if isinstance(func, types.FunctionType):
        return func
    raise PythonLoadError(
        message_format="Failed to collect flow entry '{entry}' in module '{module}'.",
        entry=entry,
        module=m.__name__,
    )


def collect_tool_methods_in_module(m):
    tools = []
    for _, obj in inspect.getmembers(m):
        if isinstance(obj, type) and issubclass(obj, ToolProvider) and obj.__module__ == m.__name__:
            for _, method in inspect.getmembers(obj):
                if is_tool(method):
                    tools.append(method)
    return tools


def collect_tool_methods_with_init_inputs_in_module(m):
    tools = []
    for _, obj in inspect.getmembers(m):
        if isinstance(obj, type) and issubclass(obj, ToolProvider) and obj.__module__ == m.__name__:
            for _, method in inspect.getmembers(obj):
                if is_tool(method):
                    tools.append((method, obj.get_initialize_inputs()))
    return tools


def _parse_tool_from_function(
    f, initialize_inputs=None, gen_custom_type_conn=False, skip_prompt_template=False, include_outputs=False
):
    try:
        tool_type = getattr(f, "__type", None) or ToolType.PYTHON
    except Exception as e:
        raise e
    tool_name = getattr(f, "__name", None)
    description = getattr(f, "__description", None)
    if hasattr(f, "__tool") and isinstance(f.__tool, Tool):
        return f.__tool
    if hasattr(f, "__original_function"):
        f = f.__original_function
    try:
        inputs, outputs, _, enable_kwargs = function_to_interface(
            f,
            initialize_inputs=initialize_inputs,
            gen_custom_type_conn=gen_custom_type_conn,
            skip_prompt_template=skip_prompt_template,
        )
    except Exception as e:
        error_type_and_message = f"({e.__class__.__name__}) {e}"
        raise BadFunctionInterface(
            message_format="Parse interface for tool '{tool_name}' failed: {error_type_and_message}",
            tool_name=f.__name__,
            error_type_and_message=error_type_and_message,
        ) from e
    class_name = None
    if "." in f.__qualname__:
        class_name = f.__qualname__.replace(f".{f.__name__}", "")
    # Construct the Tool structure
    return Tool(
        name=tool_name or f.__qualname__,
        description=description or inspect.getdoc(f),
        inputs=inputs,
        outputs=outputs if include_outputs else None,
        type=tool_type,
        class_name=class_name,
        function=f.__name__,
        module=f.__module__,
        enable_kwargs=enable_kwargs,
    )


def _serialize_tool(tool, input_settings, extra_info):
    """
    Serialize tool obj to dict.

    :param tool: Tool object
    :type tool: promptflow.contracts.tool.Tool
    :param input_settings: Input settings of the tool
    :type input_settings: Dict[str, obj]
    :param extra_info: Extra settings of the tool
    :type extra_info: Dict[str, obj]
    :return: serialized tool, validation result
    :rtype: Dict[str, str], List[str]
    """
    validation_result = _validate_tool_function(tool, input_settings, extra_info)
    if not validation_result:
        construct_tool = asdict_without_none(tool)
        if extra_info:
            _parser_tool_icon(extra_info)
            construct_tool.update(extra_info)

        # Update tool input settings
        if input_settings:
            tool_inputs = construct_tool.get("inputs", {})
            _parser_tool_input_settings(tool_inputs, input_settings)
        schema_validation_result = _validate_tool_schema(construct_tool)
        if schema_validation_result:
            validation_result.append(schema_validation_result)
        return construct_tool, validation_result
    else:
        return {}, validation_result


def generate_python_tools_in_module(module):
    tool_functions = collect_tool_functions_in_module(module)
    tool_methods = collect_tool_methods_in_module(module)
    return [_parse_tool_from_function(f) for f in tool_functions + tool_methods]


def generate_python_tools_in_module_as_dict(module):
    tools = generate_python_tools_in_module(module)
    return {f"{t.module}.{t.name}": asdict_without_none(t) for t in tools}


def load_python_module_from_file(src_file: Path):
    # Here we hard code the module name as __pf_main__ since it is invoked as a main script in pf.
    src_file = Path(src_file).resolve()  # Make sure the path is absolute to align with python import behavior.
    spec = importlib.util.spec_from_file_location(PF_MAIN_MODULE_NAME, location=src_file)
    if spec is None or spec.loader is None:
        raise PythonLoaderNotFound(
            message_format="Failed to load python file '{src_file}'. Please make sure it is a valid .py file.",
            src_file=src_file,
        )
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        # TODO: add stacktrace to additional info
        error_type_and_message = f"({e.__class__.__name__}) {e}"
        raise PythonLoadError(
            message_format="Failed to load python module from file '{src_file}': {error_type_and_message}",
            src_file=src_file,
            error_type_and_message=error_type_and_message,
        ) from e
    return m


def load_python_module_from_entry(entry: str):
    try:
        module_name = entry.split(":")[0]
        return importlib.import_module(module_name)
    except Exception as e:
        error_type_and_message = f"({e.__class__.__name__}) {e}"
        raise PythonLoadError(
            message_format="Failed to load python module '{module_name}' from entry '{entry}': "
            "{error_type_and_message}",
            module_name=module_name,
            entry=entry,
            error_type_and_message=error_type_and_message,
        ) from e


def load_python_module(content, source=None):
    # Source represents code first experience.
    if source is not None and Path(source).exists():
        return load_python_module_from_file(Path(source))
    try:
        m = types.ModuleType(PF_MAIN_MODULE_NAME)
        exec(content, m.__dict__)
        return m
    except Exception as e:
        error_type_and_message = f"({e.__class__.__name__}) {e}"
        raise PythonParsingError(
            message_format="Failed to load python module. Python parsing failed: {error_type_and_message}",
            error_type_and_message=error_type_and_message,
        ) from e


def collect_tool_function_in_module(m):
    tool_functions = collect_tool_functions_in_module(m)
    tool_methods = collect_tool_methods_with_init_inputs_in_module(m)
    num_tools = len(tool_functions) + len(tool_methods)
    if num_tools == 0:
        raise NoToolDefined(
            message_format=(
                "No tool found in the python script. "
                "Please make sure you have one and only one tool definition in your script."
            )
        )
    elif num_tools > 1:
        tool_names = ", ".join(t.__name__ for t in tool_functions + tool_methods)
        raise MultipleToolsDefined(
            message_format=(
                "Expected 1 but collected {tool_count} tools: {tool_names}. "
                "Please make sure you have one and only one tool definition in your script."
            ),
            tool_count=num_tools,
            tool_names=tool_names,
        )
    if tool_functions:
        return tool_functions[0], None
    else:
        return tool_methods[0]


def generate_python_tool_meta_dict(name, content, source=None):
    m = load_python_module(content, source)
    f, initialize_inputs = collect_tool_function_in_module(m)
    tool = _parse_tool_from_function(f, initialize_inputs=initialize_inputs)
    extra_info = getattr(f, "__extra_info")
    input_settings = getattr(f, "__input_settings")
    tool.module = None
    if name is not None:
        tool.name = name
    if source is None:
        tool.code = content
    else:
        tool.source = source
    construct_tool, is_invlid_result = _serialize_tool(tool, input_settings, extra_info)
    if is_invlid_result:
        raise UserErrorException(f"Tool validation failed: {';'.join(is_invlid_result)}")
    # Handle string enum in tool dict
    construct_tool = json.loads(json.dumps(construct_tool))
    return construct_tool


# Only used in non-code first experience.
def generate_python_meta(name, content, source=None):
    return json.dumps(generate_python_tool_meta_dict(name, content, source), indent=2)


def generate_prompt_meta(name, content, prompt_only=False, source=None):
    return json.dumps(generate_prompt_meta_dict(name, content, prompt_only, source), indent=2)


def generate_tool_meta_dict_by_file(path: str, tool_type: ToolType):
    """Generate meta for a single tool file, which can be a python file or a jinja template file,
    note that if a python file is passed, correct working directory must be set and should be added to sys.path.
    """
    tool_type = ToolType(tool_type)
    file = Path(path)
    if not file.is_file():
        raise MetaFileNotFound(
            message_format="Generate tool meta failed for {tool_type} tool. Meta file '{file_path}' can not be found.",
            tool_type=tool_type.value,
            file_path=path,  # Use a relative path here to make the error message more readable.
        )
    try:
        content = file.read_text(encoding="utf-8")
    except Exception as e:
        error_type_and_message = f"({e.__class__.__name__}) {e}"
        raise MetaFileReadError(
            message_format=(
                "Generate tool meta failed for {tool_type} tool. "
                "Read meta file '{file_path}' failed: {error_type_and_message}"
            ),
            tool_type=tool_type.value,
            file_path=path,
            error_type_and_message=error_type_and_message,
        ) from e

    name = file.stem
    if tool_type == ToolType.PYTHON:
        return generate_python_tool_meta_dict(name, content, path)
    elif tool_type == ToolType.LLM:
        return generate_prompt_meta_dict(name, content, source=path)
    elif tool_type == ToolType.PROMPT:
        return generate_prompt_meta_dict(name, content, prompt_only=True, source=path)
    else:
        raise NotSupported(
            message_format=(
                "Generate tool meta failed. "
                "The type '{tool_type}' is currently unsupported. "
                "Please choose from available types: {supported_tool_types} and try again."
            ),
            tool_type=tool_type.value,
            supported_tool_types=",".join([ToolType.PYTHON, ToolType.LLM, ToolType.PROMPT]),
        )


def generate_tool_meta(
    working_dir: Path,
    tools: Mapping[str, Mapping[str, str]],
):
    """
    Generate tool meta for a list of tools.
    Sample input tools:
    {
        "filename.py": { "tool_type": "python" },
    }

    Note: this function is referred in pf utils, so it should be kept as is.
    :param working_dir: The working directory where the tools are located.
    :type working_dir: Path
    :param tools: A dictionary of tool sources and their configurations.
    :type tools: Mapping[str, Mapping[str, str]]
    :return: A tuple of dictionaries, containing generated metadata and exceptions on generation.
    :rtype: Tuple[dict, dict]
    """
    tool_dict, exception_dict = {}, {}

    with _change_working_dir(working_dir), inject_sys_path(working_dir):
        for source, config in tools.items():
            try:
                if "tool_type" not in config:
                    raise NoToolTypeDefined(
                        message_format="Tool type not defined for source '{source}'.",
                        source=source,
                    )
                tool_type = ToolType(config.get("tool_type"))
                tool_dict[source] = generate_tool_meta_dict_by_file(source, tool_type)
            except Exception as e:
                exception_dict[source] = ExceptionPresenter.create(e).to_dict()
    return tool_dict, exception_dict


def _generate_tool_meta_and_update_dict(
    working_dir: Path,
    tools: Mapping[str, Mapping[str, str]],
    tool_dict: dict,
    exception_dict: dict,
    prevent_terminate_signal_propagation: bool = False,
):
    if prevent_terminate_signal_propagation:
        block_terminate_signal_to_parent()

    _tool_dict, _exception_dict = generate_tool_meta(working_dir, tools)
    tool_dict.update(_tool_dict)
    exception_dict.update(_exception_dict)


def generate_tool_meta_in_subprocess(
    working_dir: Path,
    tools: Mapping[str, Mapping[str, str]],
    input_logger: logging.Logger,
    timeout: int = 10,
    prevent_terminate_signal_propagation: bool = False,
):
    """
    :param working_dir: The working directory where the tools are located.
    :type working_dir: Path
    :param tools: A dictionary of tool sources and their configurations.
    :type tools: Mapping[str, Mapping[str, str]]
    :param input_logger: The logger to log the input.
    :type input_logger: logging.Logger
    :param timeout: The timeout in seconds for the subprocess to generate the tool meta.
    :type timeout: int
    :param prevent_terminate_signal_propagation: If True, the termination signal of the child process will not be
    propagated to the parent process. This is to avoid the main process being terminated when the child process is
    terminated, which is a default behavior within an uvicorn app.
    :type prevent_terminate_signal_propagation: bool
    :return: A tuple of dictionaries, containing generated metadata and exceptions on generation.
    :rtype: Tuple[dict, dict]
    """
    manager = multiprocessing.Manager()
    process_tool_dict = manager.dict()
    process_exception_dict = manager.dict()

    p = multiprocessing.Process(
        target=_generate_tool_meta_and_update_dict,
        args=(working_dir, tools, process_tool_dict, process_exception_dict, prevent_terminate_signal_propagation),
    )
    p.start()
    input_logger.info(f"[{os.getpid()}--{p.pid}] Start process to generate tool meta.")

    p.join(timeout=timeout)

    if p.is_alive():
        input_logger.warning(f"Generate meta timeout after {timeout} seconds, terminate the process.")
        p.terminate()
        p.join()

    # These dict was created by manager.dict(), so convert to normal dict here.
    tool_dict = {source: tool for source, tool in process_tool_dict.items()}
    exception_dict = {source: exception for source, exception in process_exception_dict.items()}

    # For not processed tools, treat as timeout error.
    for source in tools.keys():
        if source not in tool_dict and source not in exception_dict:
            exception_dict[source] = ExceptionPresenter.create(GenerateMetaTimeout(source=source)).to_dict()

    return tool_dict, exception_dict


def generate_flow_meta_dict_by_file(entry: str, source: str = None, path: str = None):
    if path:
        m = load_python_module_from_file(Path(path))
    else:
        m = load_python_module_from_entry(entry)

    f = collect_flow_entry_in_module(m, entry)
    # Since the flow meta is generated from the entry function, we leverage the function
    # _parse_tool_from_function to parse the interface of the entry function to get the inputs and outputs.
    tool = _parse_tool_from_function(f, include_outputs=True)

    flow_meta = {"entry": entry, "function": f.__name__}
    if source:
        flow_meta["source"] = source
    if tool.inputs:
        flow_meta["inputs"] = {}
        for k, v in tool.inputs.items():
            # We didn't support specifying multiple types for inputs, so we only take the first one.
            flow_meta["inputs"][k] = {"type": v.type[0].value}
            if v.default is not None:
                flow_meta["inputs"][k]["default"] = v.default
    if tool.outputs:
        flow_meta["outputs"] = {}
        for k, v in tool.outputs.items():
            # We didn't support specifying multiple types for outputs, so we only take the first one.
            flow_meta["outputs"][k] = {"type": v.type[0].value}
    return flow_meta


class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.TOOL, **kwargs)


class JinjaParsingError(ToolValidationError):
    pass


class ReservedVariableCannotBeUsed(JinjaParsingError):
    pass


class PythonParsingError(ToolValidationError):
    pass


class PythonLoaderNotFound(ToolValidationError):
    pass


class NoToolDefined(PythonParsingError):
    pass


class MultipleToolsDefined(PythonParsingError):
    pass


class BadFunctionInterface(PythonParsingError):
    pass


class PythonLoadError(PythonParsingError):
    @property
    def python_load_traceback(self):
        """Return the traceback inside user's source code scope.

        The traceback inside the promptflow's internal code will be taken off.
        """
        exc = self.inner_exception
        if exc and exc.__traceback__ is not None:
            tb = exc.__traceback__
            # The first three frames are always the code in tool.py who invokes the tool.
            # We do not want to dump it to user code's traceback.
            tb = get_tb_next(tb, next_cnt=3)
            if tb is not None:
                te = TracebackException(type(exc), exc, tb)
                formatted_tb = "".join(te.format())

                return formatted_tb
        return None

    @property
    def additional_info(self):
        """Set the python load exception details as additional info."""
        if not self.inner_exception:
            return None

        info = {
            "type": self.inner_exception.__class__.__name__,
            "message": str(self.inner_exception),
            "traceback": self.python_load_traceback,
        }

        info.update(last_frame_info(self.inner_exception))

        return {
            ADDITIONAL_INFO_USER_CODE_STACKTRACE: info,
        }
