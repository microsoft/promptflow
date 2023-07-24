from typing import Callable, Mapping, Tuple

from promptflow.contracts.flow import Flow
from promptflow.contracts.tool import ToolType
from promptflow.core.tools_manager import BuiltinsManager
from promptflow.exceptions import ValidationException
from promptflow.executor.error_codes import ToolLoadError, ToolNotFoundInFlow, ToolTypeNotSupported


def _load_tools_and_update_node_inputs(flow: Flow) -> Mapping[str, Callable]:
    loaded_tools = {}
    tool_metas = {tool.name: tool for tool in flow.tools}
    for node in flow.nodes:
        if node.tool not in tool_metas:
            msg = f"Node '{node.name}' references tool '{node.tool}' which is not in the flow '{flow.name}'."
            raise ToolNotFoundInFlow(message=msg)
        # We may also load other non python tools here
        tool = tool_metas[node.tool]
        if BuiltinsManager.is_custom_python(tool):
            continue  # Here we skip custom python tools, they will be loaded later

        api_name = f"{node.provider}.{node.api}"
        try:
            # There are some class init input in node inputs so we need to pass them
            loaded_tool, init_inputs = _load_tool(tool, api_name, node.inputs)
            loaded_tools[node.name] = loaded_tool
        except ValidationException as e:
            raise e
        except Exception as e:
            raise ToolLoadError(
                message=f"Failed to load tool '{tool.name}' for node '{node.name}' due to '{e}'."
            ) from e
        # Remove init inputs from node inputs, keep function inputs only
        node.inputs = {k: v for k, v in node.inputs.items() if k not in init_inputs}
    return loaded_tools


def _load_tool(tool, api_name, node_inputs) -> Tuple[Callable, dict]:
    builtins_manager = BuiltinsManager()
    if BuiltinsManager.is_builtin(tool) or tool.type is ToolType._ACTION:
        return builtins_manager.load_builtin(tool, node_inputs)
    elif tool.type is ToolType.LLM:
        api = BuiltinsManager.load_api_or_tool_by_name(api_name, tool_func_name=None)
        return builtins_manager.load_prompt_with_api(tool, api, node_inputs)
    elif tool.type is ToolType.PROMPT:
        return builtins_manager.load_prompt_rendering(tool), {}
    else:
        raise ToolTypeNotSupported(message=f"Unsupported tool {tool.name}.")
