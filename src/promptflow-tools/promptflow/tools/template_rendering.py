# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.tools.common import (
    render_jinja_template,
    PromptResult,
    Escaper,
    INPUTS_TO_ESCAPE_PARAM_KEY
)


@tool
def render_template_jinja2(template: str, **kwargs) -> PromptResult:
    # step 1: set original string of prompt result.
    rendered_template = render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **kwargs)
    prompt_result = PromptResult(rendered_template)
    # step 2: build escape dict from prompt results and flow inputs.
    prompt_result.merge_escape_mapping_of_prompt_results(**kwargs)
    inputs_to_escape = kwargs.pop(INPUTS_TO_ESCAPE_PARAM_KEY, None)
    prompt_result.merge_escape_mapping_of_flow_inputs(inputs_to_escape, **kwargs)

    if prompt_result.need_to_escape():
        updated_kwargs = Escaper.escape_kwargs(prompt_result.get_escape_mapping(), inputs_to_escape, **kwargs)
        # step 3: escape prompt result string.
        escaped_rendered_template = render_jinja_template(
            template,
            trim_blocks=True,
            keep_trailing_newline=True,
            escape_dict=prompt_result.get_escape_mapping(),
            **updated_kwargs
        )
        prompt_result.set_escape_string(escaped_rendered_template)
    return prompt_result
