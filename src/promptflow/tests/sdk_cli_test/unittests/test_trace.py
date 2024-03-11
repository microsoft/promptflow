# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import os
import uuid
from typing import Dict
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry.sdk.trace import TracerProvider

from promptflow._constants import SpanResourceAttributesFieldName, SpanResourceFieldName, TraceEnvironmentVariableName
from promptflow._sdk.entities._trace import Span
from promptflow.tracing._start_trace import _is_tracer_provider_set, setup_exporter_from_environ


@pytest.fixture
def reset_tracer_provider():
    from opentelemetry.util._once import Once

    with patch("opentelemetry.trace._TRACER_PROVIDER_SET_ONCE", Once()), patch(
        "opentelemetry.trace._TRACER_PROVIDER", None
    ):
        yield


@pytest.fixture
def mock_resource() -> Dict:
    return {
        SpanResourceFieldName.ATTRIBUTES: {
            SpanResourceAttributesFieldName.SERVICE_NAME: "promptflow",
            SpanResourceAttributesFieldName.SESSION_ID: str(uuid.uuid4()),
        },
        SpanResourceFieldName.SCHEMA_URL: "",
    }


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestStartTrace:
    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_setup_exporter_from_environ(self) -> None:
        assert not _is_tracer_provider_set()

        # set some required environment variables
        endpoint = "http://localhost:23333/v1/traces"
        session_id = str(uuid.uuid4())
        experiment = "test_experiment"
        with patch.dict(
            os.environ,
            {
                OTEL_EXPORTER_OTLP_ENDPOINT: endpoint,
                TraceEnvironmentVariableName.SESSION_ID: session_id,
                TraceEnvironmentVariableName.EXPERIMENT: experiment,
            },
            clear=True,
        ):
            setup_exporter_from_environ()

        assert _is_tracer_provider_set()
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        assert session_id == tracer_provider._resource.attributes[SpanResourceAttributesFieldName.SESSION_ID]
        assert experiment == tracer_provider._resource.attributes[SpanResourceAttributesFieldName.EXPERIMENT_NAME]

    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_local_to_cloud_resource(self) -> None:
        with patch.dict(
            os.environ,
            {
                TraceEnvironmentVariableName.SESSION_ID: str(uuid.uuid4()),
                TraceEnvironmentVariableName.SUBSCRIPTION_ID: "test_subscription_id",
                TraceEnvironmentVariableName.RESOURCE_GROUP_NAME: "test_resource_group_name",
                TraceEnvironmentVariableName.WORKSPACE_NAME: "test_workspace_name",
            },
            clear=True,
        ):
            setup_exporter_from_environ()
            tracer_provider: TracerProvider = trace.get_tracer_provider()
            res_attrs = dict(tracer_provider.resource.attributes)
            assert res_attrs[SpanResourceAttributesFieldName.SUBSCRIPTION_ID] == "test_subscription_id"
            assert res_attrs[SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME] == "test_resource_group_name"
            assert res_attrs[SpanResourceAttributesFieldName.WORKSPACE_NAME] == "test_workspace_name"

    def test_trace_without_attributes_collection(self, mock_resource: Dict) -> None:
        # generate a span without attributes
        # below magic numbers come from a real case from `azure-search-documents`
        pb_span = PBSpan()
        pb_span.trace_id = base64.b64decode("4WIgbhNyYmYKOWeAxbRm4g==")
        pb_span.span_id = base64.b64decode("lvxVSnvNhWo=")
        pb_span.name = "DocumentsOperations.search_post"
        pb_span.start_time_unix_nano = 1708420657948895100
        pb_span.end_time_unix_nano = 1708420659479925700
        pb_span.parent_span_id = base64.b64decode("C+++WS+OuxI=")
        pb_span.kind = PBSpan.SpanKind.SPAN_KIND_INTERNAL
        # below line should execute successfully
        span = Span._from_protobuf_object(pb_span, resource=mock_resource)
        # as the above span do not have any attributes, so the parsed span should not have any attributes
        attributes = span._content["attributes"]
        assert isinstance(attributes, dict)
        assert len(attributes) == 0
