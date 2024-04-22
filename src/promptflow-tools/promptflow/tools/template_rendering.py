# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.tools.common import render_jinja_template, PromptResult, escape_roles_for_flow_inputs_and_prompt_output


@tool
def render_template_jinja2(template: str, **kwargs) -> PromptResult:
    rendered_template = render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **kwargs)
    prompt_result = PromptResult(rendered_template)

    updated_kwargs = escape_roles_for_flow_inputs_and_prompt_output(kwargs.copy())
    if kwargs != updated_kwargs:
        escaped_rendered_template = render_jinja_template(
            template, trim_blocks=True, keep_trailing_newline=True, **updated_kwargs
        )
        prompt_result.escaped_string = escaped_rendered_template
    return prompt_result
