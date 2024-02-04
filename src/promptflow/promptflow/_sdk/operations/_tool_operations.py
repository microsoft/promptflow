# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import importlib.util
import inspect
import io
import json
import logging
import pkgutil
from dataclasses import asdict
from os import PathLike
from pathlib import Path
from types import ModuleType
from typing import Union

import jsonschema

from promptflow._core.tool_meta_generator import (
    ToolValidationError,
    _parse_tool_from_function,
    asdict_without_none,
    is_tool,
)
from promptflow._core.tools_manager import PACKAGE_TOOLS_ENTRY, collect_package_tools
from promptflow._sdk._constants import ICON, ICON_DARK, ICON_LIGHT, LOGGER_NAME, SKIP_FUNC_PARAMS, TOOL_SCHEMA
from promptflow._sdk._telemetry import ActivityType, monitor_operation
from promptflow._sdk.entities._validation import ValidationResult, ValidationResultBuilder
from promptflow._utils.multimedia_utils import convert_multimedia_data_to_base64
from promptflow.contracts.multimedia import Image
from promptflow.exceptions import UserErrorException

TOTAL_COUNT = "total_count"
INVALID_COUNT = "invalid_count"
logger = logging.getLogger(LOGGER_NAME)


class ToolOperations:
    """ToolOperations."""

    def __init__(self):
        self._tool_schema_dict = None

    @property
    def _tool_schema(self):
        if not self._tool_schema_dict:
            with open(TOOL_SCHEMA, "r") as f:
                self._tool_schema_dict = json.load(f)
        return self._tool_schema_dict

    def _merge_validate_result(self, target, source):
        target.merge_with(source)
        target._set_extra_info(
            TOTAL_COUNT,
            target._get_extra_info(TOTAL_COUNT, 0) + source._get_extra_info(TOTAL_COUNT, 0),
        )
        target._set_extra_info(
            INVALID_COUNT,
            target._get_extra_info(INVALID_COUNT, 0) + source._get_extra_info(INVALID_COUNT, 0),
        )

    def _list_tools_in_package(self, package_name: str, raise_error: bool = False):
        """
        List the meta of all tools in the package. Raise user error if raise_error=True and found incorrect tools.

        :param package_name: Package name
        :type package_name: str
        :param raise_error: Whether to raise the error.
        :type raise_error: bool
        :return: Dict of tools meta
        :rtype: Dict[str, Dict]
        """
        package_tools, validate_result = self._list_tool_meta_in_package(package_name=package_name)
        if not validate_result.passed:
            if raise_error:

                def tool_validate_error_func(msg, _):
                    return ToolValidationError(message=msg, validate_result=validate_result)

                validate_result.try_raise(raise_error=raise_error, error_func=tool_validate_error_func)
            else:
                logger.warning(f"Found invalid tool(s):\n {repr(validate_result)}")

        return package_tools

    def _list_tool_meta_in_package(self, package_name: str):
        """
        List the meta of all tools in the package.

        :param package_name: Package name
        :type package_name: str
        :return: Dict of tools meta, validation result
        :rtype: Dict[str, Dict], ValidationResult
        """
        package_tools = {}
        validate_result = ValidationResultBuilder.success()
        try:
            package = __import__(package_name)
            module_list = pkgutil.walk_packages(package.__path__, prefix=package.__name__ + ".")
            for module in module_list:
                module_tools, module_validate_result = self._generate_tool_meta(importlib.import_module(module.name))
                package_tools.update(module_tools)
                self._merge_validate_result(validate_result, module_validate_result)
        except ImportError as e:
            raise UserErrorException(f"Cannot find the package {package_name}, {e}.")
        return package_tools, validate_result

    def _generate_tool_meta(self, tool_module):
        """
        Generate tools meta in the module.

        :param tool_module: The module needs to generate tools meta
        :type tool_module: object
        :return: Dict of tools meta, validation result
        :rtype: Dict[str, Dict], ValidationResult
        """
        tool_functions = self._collect_tool_functions_in_module(tool_module)
        tool_methods = self._collect_tool_class_methods_in_module(tool_module)
        construct_tools = {}
        invalid_tool_count = 0
        tool_validate_result = ValidationResultBuilder.success()
        for f in tool_functions:
            tool, input_settings, extra_info = self._parse_tool_from_func(f)
            construct_tool, validate_result = self._serialize_tool(tool, input_settings, extra_info, f)
            if validate_result.passed:
                tool_name = self._get_tool_name(tool)
                construct_tools[tool_name] = construct_tool
            else:
                invalid_tool_count = invalid_tool_count + 1
                tool_validate_result.merge_with(validate_result)
        for f, initialize_inputs in tool_methods:
            tool, input_settings, extra_info = self._parse_tool_from_func(f, initialize_inputs)
            construct_tool, validate_result = self._serialize_tool(tool, input_settings, extra_info, f)
            if validate_result.passed:
                tool_name = self._get_tool_name(tool)
                construct_tools[tool_name] = construct_tool
            else:
                invalid_tool_count = invalid_tool_count + 1
                tool_validate_result.merge_with(validate_result)
        # The generated dict cannot be dumped as yaml directly since yaml cannot handle string enum.
        tools = json.loads(json.dumps(construct_tools))
        tool_validate_result._set_extra_info(TOTAL_COUNT, len(tool_functions) + len(tool_methods))
        tool_validate_result._set_extra_info(INVALID_COUNT, invalid_tool_count)
        return tools, tool_validate_result

    @staticmethod
    def _collect_tool_functions_in_module(tool_module):
        tools = []
        for _, obj in inspect.getmembers(tool_module):
            if is_tool(obj):
                # Note that the tool should be in defined in exec but not imported in exec,
                # so it should also have the same module with the current function.
                if getattr(obj, "__module__", "") != tool_module.__name__:
                    continue
                tools.append(obj)
        return tools

    @staticmethod
    def _collect_tool_class_methods_in_module(tool_module):
        from promptflow._core.tool import ToolProvider

        tools = []
        for _, obj in inspect.getmembers(tool_module):
            if isinstance(obj, type) and issubclass(obj, ToolProvider) and obj.__module__ == tool_module.__name__:
                for _, method in inspect.getmembers(obj):
                    if is_tool(method):
                        initialize_inputs = obj.get_initialize_inputs()
                        tools.append((method, initialize_inputs))
        return tools

    def _get_tool_name(self, tool):
        tool_name = (
            f"{tool.module}.{tool.class_name}.{tool.function}"
            if tool.class_name is not None
            else f"{tool.module}.{tool.function}"
        )
        return tool_name

    def _parse_tool_from_func(self, tool_func, initialize_inputs=None):
        """
        Parse tool from tool function

        :param tool_func: The tool function
        :type tool_func: callable
        :param initialize_inputs: Initialize inputs of tool
        :type initialize_inputs: Dict[str, obj]
        :return: tool object, tool input settings, extra info about the tool
        :rtype: Tool, Dict[str, InputSetting], Dict[str, obj]
        """
        tool = _parse_tool_from_function(
            tool_func, initialize_inputs=initialize_inputs, gen_custom_type_conn=True, skip_prompt_template=True
        )
        extra_info = getattr(tool_func, "__extra_info")
        input_settings = getattr(tool_func, "__input_settings")
        return tool, input_settings, extra_info

    def _validate_tool_function(self, tool, input_settings, extra_info, func_name=None, func_path=None):
        """
        Check whether the icon and input settings of the tool are legitimate.

        :param tool: The tool object
        :type tool: Tool
        :param input_settings: Input settings of the tool
        :type input_settings: Dict[str, InputSetting]
        :param extra_info: Extra info about the tool
        :type extra_info: Dict[str, obj]
        :param func_name: Function name of the tool
        :type func_name: str
        :param func_path: Script path of the tool
        :type func_path: str
        :return: Validation result of the tool
        :rtype: ValidationResult
        """
        validate_result = ValidationResultBuilder.success()

        if extra_info:
            if ICON in extra_info:
                if ICON_LIGHT in extra_info or ICON_DARK in extra_info:
                    validate_result.append_error(
                        yaml_path=None,
                        message=f"Cannot provide both `icon` and `{ICON_LIGHT}` or `{ICON_DARK}`.",
                        function_name=func_name,
                        location=func_path,
                        key="function_name",
                    )
        if input_settings:
            input_settings_validate_result = self._validate_input_settings(
                tool.inputs, input_settings, func_name, func_path
            )
            validate_result.merge_with(input_settings_validate_result)
        return validate_result

    def _validate_tool_schema(self, tool_dict, func_name=None, func_path=None):
        """
        Check whether the generated schema of the tool are legitimate.

        :param tool_dict: The generated tool dict
        :type tool_dict: Dict[str, obj]
        :param func_name: Function name of the tool
        :type func_name: str
        :param func_path: Script path of the tool
        :type func_path: str
        :return: Validation result of the tool
        :rtype: ValidationResult
        """
        validate_result = ValidationResultBuilder.success()
        try:
            jsonschema.validate(instance=tool_dict, schema=self._tool_schema)
        except jsonschema.exceptions.ValidationError as e:
            validate_result.append_error(
                message=str(e), yaml_path=None, function_name=func_name, location=func_path, key="function_name"
            )
        return validate_result

    def _validate_input_settings(self, tool_inputs, input_settings, func_name=None, func_path=None):
        """
        Check whether input settings of the tool are legitimate.

        :param tool_inputs: Tool inputs
        :type tool_inputs: Dict[str, obj]
        :param input_settings: Input settings of the tool
        :type input_settings: Dict[str, InputSetting]
        :param extra_info: Extra info about the tool
        :type extra_info: Dict[str, obj]
        :param func_name: Function name of the tool
        :type func_name: str
        :param func_path: Script path of the tool
        :type func_path: str
        :return: Validation result of the tool
        :rtype: ValidationResult
        """
        validate_result = ValidationResultBuilder.success()
        for input_name, settings in input_settings.items():
            if input_name not in tool_inputs:
                validate_result.append_error(
                    yaml_path=None,
                    message=f"Cannot find {input_name} in tool inputs.",
                    function_name=func_name,
                    location=func_path,
                    key="function_name",
                )
            if settings.enabled_by and settings.enabled_by not in tool_inputs:
                validate_result.append_error(
                    yaml_path=None,
                    message=f'Cannot find the input "{settings.enabled_by}" for the enabled_by of {input_name}.',
                    function_name=func_name,
                    location=func_path,
                    key="function_name",
                )
            if settings.dynamic_list:
                dynamic_func_inputs = inspect.signature(settings.dynamic_list._func_obj).parameters
                has_kwargs = any([param.kind == param.VAR_KEYWORD for param in dynamic_func_inputs.values()])
                required_inputs = [
                    k
                    for k, v in dynamic_func_inputs.items()
                    if v.default is inspect.Parameter.empty and v.kind != v.VAR_KEYWORD and k not in SKIP_FUNC_PARAMS
                ]
                if settings.dynamic_list._input_mapping:
                    # Validate input mapping in dynamic_list
                    for func_input, reference_input in settings.dynamic_list._input_mapping.items():
                        # Check invalid input name of dynamic list function
                        if not has_kwargs and func_input not in dynamic_func_inputs:
                            validate_result.append_error(
                                yaml_path=None,
                                message=f"Cannot find {func_input} in the inputs of "
                                f"dynamic_list func {settings.dynamic_list.func_path}",
                                function_name=func_name,
                                location=func_path,
                                key="function_name",
                            )
                        # Check invalid input name of tool
                        if reference_input not in tool_inputs:
                            validate_result.append_error(
                                yaml_path=None,
                                message=f"Cannot find {reference_input} in the tool inputs.",
                                function_name=func_name,
                                location=func_path,
                                key="function_name",
                            )
                        if func_input in required_inputs:
                            required_inputs.remove(func_input)
                # Check required input of dynamic_list function
                if len(required_inputs) != 0:
                    validate_result.append_error(
                        yaml_path=None,
                        message=f"Missing required input(s) of dynamic_list function: {required_inputs}",
                        function_name=func_name,
                        location=func_path,
                        key="function_name",
                    )
        return validate_result

    def _serialize_tool(self, tool, input_settings, extra_info, tool_func):
        """
        Serialize tool obj to dict.

        :param tool_func: Package tool function
        :type tool_func: callable
        :param initialize_inputs: Initialize inputs of package tool
        :type initialize_inputs: Dict[str, obj]
        :return: package tool name, serialized tool
        :rtype: str, Dict[str, str]
        """
        tool_func_name = tool_func.__name__
        tool_script_path = inspect.getsourcefile(getattr(tool_func, "__original_function", tool_func))
        validate_result = self._validate_tool_function(
            tool, input_settings, extra_info, tool_func_name, tool_script_path
        )
        if validate_result.passed:
            construct_tool = asdict(tool, dict_factory=lambda x: {k: v for (k, v) in x if v})
            if extra_info:
                if ICON in extra_info:
                    extra_info[ICON] = self._serialize_icon_data(extra_info["icon"])
                if ICON_LIGHT in extra_info:
                    icon = extra_info.get("icon", {})
                    icon["light"] = self._serialize_icon_data(extra_info[ICON_LIGHT])
                    extra_info[ICON] = icon
                if ICON_DARK in extra_info:
                    icon = extra_info.get("icon", {})
                    icon["dark"] = self._serialize_icon_data(extra_info[ICON_DARK])
                    extra_info[ICON] = icon
                construct_tool.update(extra_info)

            # Update tool input settings
            if input_settings:
                tool_inputs = construct_tool.get("inputs", {})
                generated_by_inputs = {}
                for input_name, settings in input_settings.items():
                    tool_inputs[input_name].update(asdict_without_none(settings))
                    kwargs = settings._kwargs or {}
                    for k, v in kwargs.items():
                        if k in tool_inputs[input_name]:
                            if isinstance(v, dict):
                                tool_inputs[input_name][k].update(v)
                            elif isinstance(v, list):
                                tool_inputs[input_name][k].append(v)
                            else:
                                logger.debug(
                                    f"InputSetting {k} of {input_name} will be overwrite from"
                                    f" {tool_inputs[input_name][k]} to {v}."
                                )
                                tool_inputs[input_name][k] = v
                        else:
                            tool_inputs[input_name][k] = v
                    if settings.generated_by:
                        generated_by_inputs.update(settings.generated_by._input_settings)
                tool_inputs.update(generated_by_inputs)
            schema_validate_result = self._validate_tool_schema(construct_tool, tool_func_name, tool_script_path)
            validate_result.merge_with(schema_validate_result)
            return construct_tool, validate_result
        else:
            return {}, validate_result

    def _serialize_icon_data(self, icon):
        if not Path(icon).exists():
            raise UserErrorException(f"Cannot find the icon path {icon}.")
        return self._serialize_image_data(icon)

    @staticmethod
    def _serialize_image_data(image_path):
        """Serialize image to base64."""
        from PIL import Image as PIL_Image

        with open(image_path, "rb") as image_file:
            # Create a BytesIO object from the image file
            image_data = io.BytesIO(image_file.read())

        # Open the image and resize it
        img = PIL_Image.open(image_data)
        if img.size != (16, 16):
            img = img.resize((16, 16), PIL_Image.Resampling.LANCZOS)
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        icon_image = Image(buffered.getvalue(), mime_type="image/png")
        image_url = convert_multimedia_data_to_base64(icon_image, with_type=True)
        return image_url

    @staticmethod
    def _is_package_tool(package) -> bool:
        import pkg_resources

        try:
            distribution = pkg_resources.get_distribution(package.__name__)
            entry_points = distribution.get_entry_map()
            return PACKAGE_TOOLS_ENTRY in entry_points
        except Exception as e:
            logger.debug(f"Failed to check {package.__name__} is a package tool, raise {e}")
            return False

    @monitor_operation(activity_name="pf.tools.list", activity_type=ActivityType.PUBLICAPI)
    def list(
        self,
        flow: Union[str, PathLike] = None,
    ):
        """
        List all package tools in the environment and code tools in the flow.

        :param flow: path to the flow directory
        :type flow: Union[str, PathLike]
        :return: Dict of package tools and code tools info.
        :rtype: Dict[str, Dict]
        """
        from promptflow._sdk._pf_client import PFClient

        local_client = PFClient()
        package_tools = collect_package_tools()
        if flow:
            tools, _ = local_client.flows._generate_tools_meta(flow)
        else:
            tools = {"package": {}, "code": {}}
        tools["package"].update(package_tools)
        return tools

    @monitor_operation(activity_name="pf.tools.validate", activity_type=ActivityType.PUBLICAPI)
    def validate(
        self, source: Union[str, callable, PathLike], *, raise_error: bool = False, **kwargs
    ) -> ValidationResult:
        """
        Validate tool.

        :param source: path to the package tool directory or tool script
        :type source: Union[str, callable, PathLike]
        :param raise_error: whether raise error when validation failed
        :type raise_error: bool
        :return: a validation result object
        :rtype: ValidationResult
        """

        def validate_tool_function(tool_func, init_inputs=None):
            tool, input_settings, extra_info = self._parse_tool_from_func(tool_func, init_inputs)
            _, validate_result = self._serialize_tool(tool, input_settings, extra_info, source)
            validate_result._set_extra_info(TOTAL_COUNT, 1)
            validate_result._set_extra_info(INVALID_COUNT, 0 if validate_result.passed else 1)
            return validate_result

        if callable(source):
            from promptflow._core.tool import ToolProvider

            if isinstance(source, type) and issubclass(source, ToolProvider):
                # Validate tool class
                validate_result = ValidationResultBuilder.success()
                for _, method in inspect.getmembers(source):
                    if is_tool(method):
                        initialize_inputs = source.get_initialize_inputs()
                        func_validate_result = validate_tool_function(method, initialize_inputs)
                        self._merge_validate_result(validate_result, func_validate_result)
            else:
                # Validate tool function
                validate_result = validate_tool_function(source)
        elif isinstance(source, (str, PathLike)):
            # Validate tool script
            if not Path(source).exists():
                raise UserErrorException(f"Cannot find the tool script {source}")
            # Load the module from the file path
            module_name = Path(source).stem
            spec = importlib.util.spec_from_file_location(module_name, source)
            module = importlib.util.module_from_spec(spec)

            # Load the module's code
            spec.loader.exec_module(module)
            _, validate_result = self._generate_tool_meta(module)
        elif isinstance(source, ModuleType):
            # Validate package tool
            if not self._is_package_tool(source):
                raise UserErrorException("Invalid package tool.")
            _, validate_result = self._list_tool_meta_in_package(package_name=source.__name__)
        else:
            raise UserErrorException(
                "Provide invalid source, tool validation source supports script tool, "
                "package tool and tool script path."
            )

        def tool_validate_error_func(msg, _):
            return ToolValidationError(message=msg)

        validate_result.try_raise(raise_error=raise_error, error_func=tool_validate_error_func)
        return validate_result
