# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.contracts.types import PromptTemplate
from promptflow.tools.common import render_jinja_template


@tool
def render_template_jinja2(template: PromptTemplate, **kwargs) -> str:
    return render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **kwargs)
