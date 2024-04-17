from typing import Dict

from opentelemetry import trace

from promptflow.tracing._trace import serialize_attribute


def enrich_prompt_template(template: str, variables: Dict[str, object]):
    span = trace.get_current_span()
    prompt_info = {"prompt.template": template, "prompt.variables": serialize_attribute(variables)}
    span.set_attributes(prompt_info)
    span.add_event("promptflow.prompt.template", {"payload": serialize_attribute(prompt_info)})
