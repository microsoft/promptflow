# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import base64
import io
import inspect
import json
from pathlib import Path
from dataclasses import asdict
from os import PathLike
from typing import Union

from promptflow._core.tool_meta_generator import is_tool
from promptflow._core.tools_manager import collect_package_tools
from promptflow._utils.tool_utils import function_to_interface
from promptflow.contracts.tool import Tool, ToolType
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
        from promptflow import ToolProvider

        tools = []
        for _, obj in inspect.getmembers(tool_module):
            if isinstance(obj, type) and issubclass(obj, ToolProvider) and obj.__module__ == tool_module.__name__:
                for _, method in inspect.getmembers(obj):
                    if is_tool(method):
                        initialize_inputs = obj.get_initialize_inputs()
                        tools.append((method, initialize_inputs))
        return tools

    @staticmethod
    def _parse_tool_from_function(f, initialize_inputs=None):
        tool_type = getattr(f, "__type") or ToolType.PYTHON
        tool_name = getattr(f, "__name")
        description = getattr(f, "__description")
        extra_info = getattr(f, "__extra_info")
        if getattr(f, "__tool", None) and isinstance(f.__tool, Tool):
            return getattr(f, "__tool")
        if hasattr(f, "__original_function"):
            f = getattr(f, "__original_function")
        try:
            inputs, _, _ = function_to_interface(f, initialize_inputs=initialize_inputs)
        except Exception as e:
            raise UserErrorException(f"Failed to parse interface for tool {f.__name__}, reason: {e}") from e
        class_name = None
        if "." in f.__qualname__:
            class_name = f.__qualname__.replace(f".{f.__name__}", "")
        # Construct the Tool structure
        tool = Tool(
            name=tool_name or f.__qualname__,
            description=description or inspect.getdoc(f),
            inputs=inputs,
            type=tool_type,
            class_name=class_name,
            function=f.__name__,
            module=f.__module__,
        )
        return tool, extra_info

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
        tool, extra_info = self._parse_tool_from_function(tool_func, initialize_inputs)
        tool_name = f"{tool.module}.{tool.class_name}.{tool.function}" \
            if tool.class_name is not None else f"{tool.module}.{tool.function}"
        construct_tool = asdict(tool, dict_factory=lambda x: {k: v for (k, v) in x if v})
        if extra_info:
            if "icon" in extra_info:
                if not Path(extra_info["icon"]).exists():
                    raise UserErrorException(f"Cannot find the icon path {extra_info['icon']}.")
                extra_info["icon"] = self._serialize_image_data(extra_info["icon"])
            construct_tool.update(extra_info)
        return tool_name, construct_tool

    @staticmethod
    def _serialize_image_data(image_path):
        """Serialize image to base64."""
        from PIL import Image

        with open(image_path, "rb") as image_file:
            # Create a BytesIO object from the image file
            image_data = io.BytesIO(image_file.read())

        # Open the image and resize it
        img = Image.open(image_data)
        if img.size != (16, 16):
            img = img.resize((16, 16), Image.Resampling.LANCZOS)

        # Save the resized image to a data URL
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue())
        data_url = 'data:image/png;base64,' + img_str.decode('utf-8')
        return data_url

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
