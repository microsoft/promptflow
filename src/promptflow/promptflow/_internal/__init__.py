# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

# flake8: noqa

"""Put some imports here for internal packages to minimize the effort of refactoring."""
from promptflow._core.cache_manager import enable_cache
from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.tool import ToolProvider, tool
from promptflow._core.tools_manager import (
    collect_package_tools,
    register_apis,
    register_builtins,
    register_connections,
    reserved_keys,
)
from promptflow._utils.generate_tool_meta_utils import generate_tool_meta_dict_by_file
