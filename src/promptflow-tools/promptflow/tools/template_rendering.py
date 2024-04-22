# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.tools.common import render_jinja_template, ExtendedStr, escape_roles


@tool
def render_template_jinja2(template: str, **kwargs) -> ExtendedStr:
    flow_input_list = kwargs.pop("flow_inputs", None)
    updated_kwargs = kwargs
    if flow_input_list:
        # Use escape/unescape to avoid unintended parsing of role in user inputs.
        updated_kwargs = {
            key: escape_roles(value) if key in flow_input_list else value for key, value in kwargs.items()
        }

    original_str = render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **kwargs)
    escape_str = render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **updated_kwargs)
    res = ExtendedStr(original_str)
    res.escaped_string = escape_str
    return res
