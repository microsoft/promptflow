import typing

from promptflow._constants import SpanAttributeFieldName, SpanResourceAttributesFieldName, SpanResourceFieldName
from promptflow._sdk.entities._trace import Span


def aggregate_trace_count(all_spans: typing.List[Span]):
    """
    Aggregate the trace count based on workspace info, scenario, and execution target.
    """
    trace_count_summary = {}

    if not all_spans:
        return trace_count_summary

    # Iterate over all spans
    for span in all_spans:
        # Only count for root span, ignore span count telemetry for now.
        if span.parent_id is None:
            resource_attributes = span.resource.get(SpanResourceFieldName.ATTRIBUTES, {})
            subscription_id = resource_attributes.get(SpanResourceAttributesFieldName.SUBSCRIPTION_ID, None)
            resource_group = resource_attributes.get(SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME, None)
            workspace_name = resource_attributes.get(SpanResourceAttributesFieldName.WORKSPACE_NAME, None)
            # We may need another field to indicate the language in the future, e.g. python, csharp.
            execution_target = span.attributes.get(SpanAttributeFieldName.EXECUTION_TARGET, "code")

            scenario = "script"
            if SpanAttributeFieldName.BATCH_RUN_ID in span.attributes:
                scenario = "batch"
            elif SpanAttributeFieldName.LINE_RUN_ID in span.attributes:
                scenario = "test"

            key = (subscription_id, resource_group, workspace_name, scenario, execution_target)
            trace_count_summary[key] = trace_count_summary.get(key, 0) + 1

    return trace_count_summary
