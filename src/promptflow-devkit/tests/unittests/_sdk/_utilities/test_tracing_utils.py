import pytest
from pydash import partial

from promptflow._constants import SpanAttributeFieldName, SpanResourceAttributesFieldName, SpanResourceFieldName
from promptflow._sdk._utilities.tracing_utils import aggregate_trace_count
from promptflow._sdk.entities._trace import Span

# Mock definitions for Span, SpanResourceFieldName, SpanResourceAttributesFieldName, and SpanAttributeFieldName
# These should match the actual implementations you're using in your application.


@pytest.mark.unittest
class TestTraceTelemetry:
    def test_empty_span_list(self):
        """Test with an empty list of spans."""
        result = aggregate_trace_count([])
        assert result == {}

    def test_single_root_span(self):

        resource = {
            SpanResourceFieldName.ATTRIBUTES: {
                SpanResourceAttributesFieldName.SUBSCRIPTION_ID: "sub",
                SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME: "rg",
                SpanResourceAttributesFieldName.WORKSPACE_NAME: "ws",
            }
        }
        create_span = partial(
            Span,
            trace_id=None,
            span_id=None,
            name=None,
            context=None,
            kind=None,
            start_time=None,
            end_time=None,
            status=None,
            parent_id=None,
            resource=resource,
        )

        batch_root_span = create_span(
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
                SpanAttributeFieldName.BATCH_RUN_ID: "batch_run_id",
            },
        )
        line_root_span = create_span(
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
                SpanAttributeFieldName.LINE_RUN_ID: "line_run_id",
            },
        )

        flex_root_span = create_span(
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "flex",
            },
        )
        prompty_root_span = create_span(
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "prompty",
            },
        )
        script_root_span = create_span(
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
            },
        )
        none_ws_root_span = create_span(
            resource={},
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "prompty",
            },
        )
        non_root_span = create_span(
            parent_id=1,
            attributes={
                SpanAttributeFieldName.EXECUTION_TARGET: "code",
            },
        )
        result = aggregate_trace_count(
            [
                batch_root_span,
                line_root_span,
                script_root_span,
                flex_root_span,
                prompty_root_span,
                non_root_span,
                none_ws_root_span,
            ]
        )
        expected_result = {
            ("sub", "rg", "ws", "batch", "code"): 1,
            ("sub", "rg", "ws", "script", "code"): 1,
            ("sub", "rg", "ws", "script", "flex"): 1,
            ("sub", "rg", "ws", "script", "prompty"): 1,
            ("sub", "rg", "ws", "test", "code"): 1,
            (None, None, None, "script", "prompty"): 1,
        }
        assert result == expected_result
