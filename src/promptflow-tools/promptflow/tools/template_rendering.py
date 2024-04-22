# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.tools.common import (
    render_jinja_template,
    PromptResult,
    build_escape_dict,
    escape_roles_for_flow_inputs_and_prompt_output,
    INPUTS_TO_ESCAPE_PARAM_KEY
)


@tool
def render_template_jinja2(template: str, **kwargs) -> PromptResult:
    rendered_template = render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **kwargs)
    prompt_result = PromptResult(rendered_template)

    inputs_to_escape = kwargs.pop(INPUTS_TO_ESCAPE_PARAM_KEY, None)
    escape_dict = build_escape_dict(inputs_to_escape=inputs_to_escape, **kwargs)
    updated_kwargs = escape_roles_for_flow_inputs_and_prompt_output(escape_dict, inputs_to_escape, **kwargs)
    if escape_dict:
        escaped_rendered_template = render_jinja_template(
            template, trim_blocks=True, keep_trailing_newline=True, escape_dict=escape_dict, **updated_kwargs
        )
        prompt_result.escaped_string = escaped_rendered_template
        prompt_result.escaped_mapping = escape_dict
    return prompt_result
