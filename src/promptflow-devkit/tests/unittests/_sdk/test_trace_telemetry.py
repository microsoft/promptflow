import pytest

from promptflow._constants import SpanAttributeFieldName, SpanResourceAttributesFieldName, SpanResourceFieldName
from promptflow._sdk._trace_telemetry import aggregate_trace_count

# Mock definitions for Span, SpanResourceFieldName, SpanResourceAttributesFieldName, and SpanAttributeFieldName
# These should match the actual implementations you're using in your application.


class MockSpan:
    def __init__(self, parent_id, resource, attributes):
        self.parent_id = parent_id
        self.resource = resource
        self.attributes = attributes


@pytest.mark.unittest
class TestTraceTelemetry:
    def test_empty_span_list(self):
        """Test with an empty list of spans."""
        result = aggregate_trace_count([])
        assert result == {}

    def test_single_root_span(self):
        """Test with a single root span."""
        resource = {
            SpanResourceFieldName.ATTRIBUTES: {
                SpanResourceAttributesFieldName.SUBSCRIPTION_ID: "sub",
                SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME: "rg",
                SpanResourceAttributesFieldName.WORKSPACE_NAME: "ws",
            }
        }
        batch_root_span = MockSpan(
            parent_id=None,
            resource=resource,
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
                SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id",
            },
        )
        line_root_span = MockSpan(
            parent_id=None,
            resource=resource,
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
                SpanAttributeFieldName.LINE_RUN_ID: "line_run_id",
            },
        )

        flex_root_span = MockSpan(
            parent_id=None,
            resource=resource,
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "flex",
            },
        )
        prompty_root_span = MockSpan(
            parent_id=None,
            resource=resource,
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "prompty",
            },
        )
        script_root_span = MockSpan(
            parent_id=None,
            resource=resource,
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
            },
        )
        non_root_span = MockSpan(
            parent_id=1,
            resource=resource,
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
            },
        )
        result = aggregate_trace_count(
            [batch_root_span, line_root_span, script_root_span, flex_root_span, prompty_root_span, non_root_span]
        )
        expected_result = {
            ("sub", "rg", "ws", "batch", "code"): 1,
            ("sub", "rg", "ws", "script", "code"): 1,
            ("sub", "rg", "ws", "script", "flex"): 1,
            ("sub", "rg", "ws", "script", "prompty"): 1,
            ("sub", "rg", "ws", "test", "code"): 1,
        }
        assert result == expected_result
