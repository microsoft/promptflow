# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.tools.common import render_jinja_template, ExtendedStr, escape_roles_for_prompt_tool_input


# do not need to store the escape dict for prompt, since prompt will have the original string and the escaped string.
def _update_kwargs(kwargs: dict) -> dict:
    input_escape_list = kwargs.get("input_escape_list", [])
    for k, v in kwargs.items():
        if k in input_escape_list:
            kwargs[k] = escape_roles_for_prompt_tool_input(v)
    return kwargs


@tool
def render_template_jinja2(template: str, **kwargs) -> ExtendedStr:
    updated_kwargs = _update_kwargs(kwargs)
    # check if need to put the update logic within render, since it seems all the place have render need to do update.
    # or use a wrapper?
    rendered_origin = render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **kwargs)
    rendered_escape = render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **updated_kwargs)
    res = ExtendedStr(rendered_origin)
    res.escaped_string = rendered_escape

    return res
