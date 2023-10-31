# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import io
import json
from dataclasses import asdict
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow._core.tool_meta_generator import is_tool, _parse_tool_from_function, asdict_without_none
from promptflow._core.tools_manager import collect_package_tools
from promptflow._utils.multimedia_utils import convert_multimedia_data_to_base64
from promptflow.contracts.multimedia import Image
from promptflow.exceptions import UserErrorException


class ToolOperations:
    """ToolOperations."""

    def generate_tool_meta(self, tool_module):
        tool_functions = self._collect_tool_functions_in_module(tool_module)
        tool_methods = self._collect_tool_class_methods_in_module(tool_module)
        construct_tools = {}
        for f in tool_functions:
            tool_name, construct_tool = self._serialize_tool(f)
            construct_tools[tool_name] = construct_tool
        for (f, initialize_inputs) in tool_methods:
            tool_name, construct_tool = self._serialize_tool(f, initialize_inputs)
            construct_tools[tool_name] = construct_tool
        # The generated dict cannot be dumped as yaml directly since yaml cannot handle string enum.
        return json.loads(json.dumps(construct_tools))

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

    def _validate_input_settings(self, tool_inputs, input_settings):
        for input_name, settings in input_settings.items():
            if input_name not in tool_inputs:
                raise UserErrorException(f"Cannot find {input_name} in tool inputs.")
            if settings.enabled_by and settings.enabled_by not in tool_inputs:
                raise UserErrorException(
                    f"Cannot find the input \"{settings.enabled_by}\" for the enabled_by of {input_name}.")
            if settings.dynamic_list:
                dynamic_func_inputs = inspect.signature(settings.dynamic_list._func_obj).parameters
                has_kwargs = any([param.kind == param.VAR_KEYWORD for param in dynamic_func_inputs.values()])
                required_inputs = [k for k, v in dynamic_func_inputs.items() if v.default is inspect.Parameter.empty]
                if settings.dynamic_list._input_mapping:
                    # Validate input mapping in dynamic_list
                    for func_input, reference_input in settings.dynamic_list._input_mapping.items():
                        # Check invalid input name of dynamic list function
                        if not has_kwargs and func_input not in dynamic_func_inputs:
                            raise UserErrorException(
                                f"Cannot find {func_input} in the inputs of "
                                f"dynamic_list func {settings.dynamic_list.func_path}"
                            )
                        # Check invalid input name of tool
                        if reference_input not in tool_inputs:
                            raise UserErrorException(f"Cannot find {reference_input} in the tool inputs.")
                        if func_input in required_inputs:
                            required_inputs.remove(func_input)
                # Check required input of dynamic_list function
                if len(required_inputs) != 0:
                    raise UserErrorException(f"Missing required input(s) of dynamic_list function: {required_inputs}")

    def _serialize_tool(self, tool_func, initialize_inputs=None):
        """
        Serialize tool obj to dict.

        :param tool_func: Package tool function
        :type tool_func: callable
        :param initialize_inputs: Initialize inputs of package tool
        :type initialize_inputs: Dict[str, obj]
        :return: package tool name, serialized tool
        :rtype: str, Dict[str, str]
        """
        tool = _parse_tool_from_function(tool_func, initialize_inputs=initialize_inputs, gen_custom_type_conn=True)
        extra_info = getattr(tool_func, "__extra_info")
        tool_name = (
            f"{tool.module}.{tool.class_name}.{tool.function}"
            if tool.class_name is not None
            else f"{tool.module}.{tool.function}"
        )
        construct_tool = asdict(tool, dict_factory=lambda x: {k: v for (k, v) in x if v})
        if extra_info:
            if "icon" in extra_info:
                if not Path(extra_info["icon"]).exists():
                    raise UserErrorException(f"Cannot find the icon path {extra_info['icon']}.")
                extra_info["icon"] = self._serialize_image_data(extra_info["icon"])
            construct_tool.update(extra_info)

        # Update tool input settings
        input_settings = getattr(tool_func, "__input_settings")
        if input_settings:
            tool_inputs = construct_tool.get("inputs", {})
            self._validate_input_settings(tool_inputs, input_settings)
            for input_name, settings in input_settings.items():
                tool_inputs[input_name].update(asdict_without_none(settings))
        return tool_name, construct_tool

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
