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
from promptflow._trace._start_trace import (
    _create_resource,
    _is_tracer_provider_configured,
    _provision_session_id,
    setup_exporter_from_environ,
)


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
    def test_create_resource(self) -> None:
        session_id = str(uuid.uuid4())
        resource1 = _create_resource(session_id=session_id)
        assert resource1.attributes[SpanResourceAttributesFieldName.SESSION_ID] == session_id
        assert SpanResourceAttributesFieldName.EXPERIMENT_NAME not in resource1.attributes

        experiment = "test_experiment"
        resource2 = _create_resource(session_id=session_id, experiment=experiment)
        assert resource2.attributes[SpanResourceAttributesFieldName.SESSION_ID] == session_id
        assert resource2.attributes[SpanResourceAttributesFieldName.EXPERIMENT_NAME] == experiment

    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_setup_exporter_from_environ(self) -> None:
        assert not _is_tracer_provider_configured()

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

        assert _is_tracer_provider_configured()
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        assert session_id == tracer_provider._resource.attributes[SpanResourceAttributesFieldName.SESSION_ID]
        assert experiment == tracer_provider._resource.attributes[SpanResourceAttributesFieldName.EXPERIMENT_NAME]

    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_provision_session_id(self) -> None:
        # no specified, session id should be a valid UUID
        session_id = _provision_session_id(specified_session_id=None)
        # below assert applys a UUID type check for `session_id`
        assert session_id == str(uuid.UUID(session_id, version=4))

        # specified session id
        specified_session_id = str(uuid.uuid4())
        session_id = _provision_session_id(specified_session_id=specified_session_id)
        assert session_id == specified_session_id

        # within a configured tracer provider
        endpoint = "http://localhost:23333/v1/traces"
        configured_session_id = str(uuid.uuid4())
        with patch.dict(
            os.environ,
            {
                OTEL_EXPORTER_OTLP_ENDPOINT: endpoint,
                TraceEnvironmentVariableName.SESSION_ID: configured_session_id,
            },
            clear=True,
        ):
            setup_exporter_from_environ()

            # no specified
            session_id = _provision_session_id(specified_session_id=None)
            assert configured_session_id == session_id

            # specified, but still honor the configured one
            session_id = _provision_session_id(specified_session_id=str(uuid.uuid4()))
            assert configured_session_id == session_id

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
            tracer_provider = trace.get_tracer_provider()
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
