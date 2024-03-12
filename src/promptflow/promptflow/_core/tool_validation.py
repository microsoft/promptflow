# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import json

import jsonschema

from promptflow._constants import ICON, ICON_DARK, ICON_LIGHT, SKIP_FUNC_PARAMS, TOOL_SCHEMA


def _validate_tool_function(tool, input_settings, extra_info):
    """
    Check whether the icon and input settings of the tool are legitimate.

    :param tool: The tool object
    :type tool: Tool
    :param input_settings: Input settings of the tool
    :type input_settings: Dict[str, InputSetting]
    :param extra_info: Extra info about the tool
    :type extra_info: Dict[str, obj]
    :return: Validation result of the tool
    :rtype: List[str]
    """
    validate_result = []

    if extra_info:
        if ICON in extra_info:
            if ICON_LIGHT in extra_info or ICON_DARK in extra_info:
                validate_result.append(f"Cannot provide both `icon` and `{ICON_LIGHT}` or `{ICON_DARK}`.")
    if input_settings:
        input_settings_validate_result = _validate_input_settings(tool.inputs, input_settings)
        validate_result.extend(input_settings_validate_result)
    return validate_result


def _validate_tool_schema(tool_dict):
    """
    Check whether the generated schema of the tool are legitimate.

    :param tool_dict: The generated tool dict
    :type tool_dict: Dict[str, obj]
    :return: Validation result of the tool
    :rtype: str
    """
    try:
        with open(TOOL_SCHEMA, "r") as f:
            tool_schema = json.load(f)

        jsonschema.validate(instance=tool_dict, schema=tool_schema)
    except jsonschema.exceptions.ValidationError as e:
        return str(e)


def _validate_input_settings(tool_inputs, input_settings):
    """
    Check whether input settings of the tool are legitimate.

    :param tool_inputs: Tool inputs
    :type tool_inputs: Dict[str, obj]
    :param input_settings: Input settings of the tool
    :type input_settings: Dict[str, InputSetting]
    :param extra_info: Extra info about the tool
    :type extra_info: Dict[str, obj]
    :return: Validation result of the tool
    :rtype: List[str]
    """
    validate_result = []
    for input_name, settings in input_settings.items():
        if input_name not in tool_inputs:
            validate_result.append(
                f"Cannot find {input_name} in tool inputs.",
            )
        if settings.enabled_by and settings.enabled_by not in tool_inputs:
            validate_result.append(f'Cannot find the input "{settings.enabled_by}" for the enabled_by of {input_name}.')
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
                        validate_result.append(
                            f"Cannot find {func_input} in the inputs of "
                            f"dynamic_list func {settings.dynamic_list.func_path}"
                        )
                    # Check invalid input name of tool
                    if reference_input not in tool_inputs:
                        validate_result.append(f"Cannot find {reference_input} in the tool inputs.")
                    if func_input in required_inputs:
                        required_inputs.remove(func_input)
            # Check required input of dynamic_list function
            if len(required_inputs) != 0:
                validate_result.append(f"Missing required input(s) of dynamic_list function: {required_inputs}")
    return validate_result
