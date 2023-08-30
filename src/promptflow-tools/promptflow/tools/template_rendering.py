# Importing from promptflow._internal is necessary as this module is promptflow internal.
from promptflow._internal import tool
from promptflow.tools.common import render_jinja_template


@tool
def render_template_jinja2(template: str, **kwargs) -> str:
    return render_jinja_template(template, trim_blocks=True, keep_trailing_newline=True, **kwargs)
