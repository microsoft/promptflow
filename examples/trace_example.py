# TODO: this file targets to demonstrate our tracing support, not expected to be checked in

# below is the expected experience, we will support this after we are full ready
# import promptflow as pf
# pf.start_trace()

from promptflow._sdk._start_trace import start_trace

# start_trace() will print a url for trace detail visualization
start_trace()

...

# ==================================================
# below is what is happening in our @trace decorator
from opentelemetry import trace  # noqa: E402

tracer = trace.get_tracer(__name__)
# the span spec follows the contract in pull request:
# https://github.com/microsoft/promptflow/pull/1835
with tracer.start_as_current_span("hello") as span:
    span.set_attribute("framework", "promptflow")
    # Function/Tool/Flow/LLM/LangChain...
    span.set_attribute("span_type", "Function")
    # The module_name.qual_name of the function
    span.set_attribute("function", "promptflow.tools.template_rendering.render_template_jinja2")
    span.set_attribute("inputs", '{\n "name": "world"\n}')
    span.set_attribute("output", '"Hello world"')
    span.set_attribute("run.id", "<run-id>")
    span.set_attribute("run.line_id", "<run-line-id>")
    # Test/Batch/etc.
    span.set_attribute("run.mode", "Batch")
    span.set_attribute("context.user_agent", "promptflow/1.4.1")
