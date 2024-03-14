# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import json
import os
import uuid
from typing import Dict
from unittest.mock import patch

import pytest
from mock import mock
from opentelemetry import trace
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry.sdk.trace import TracerProvider

from promptflow._constants import (
    SpanAttributeFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
    TraceEnvironmentVariableName,
)
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._constants import PF_TRACE_CONTEXT, PF_TRACE_CONTEXT_ATTR, ContextAttributeKey
from promptflow._sdk._tracing import start_trace_with_devkit
from promptflow._sdk.entities._trace import Span
from promptflow.tracing._start_trace import _is_tracer_provider_set, setup_exporter_from_environ, start_trace

MOCK_PROMPTFLOW_SERVICE_PORT = "23333"


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


@pytest.fixture
def mock_promptflow_service_invocation():
    """Mock `_invoke_pf_svc` as we don't expect to invoke PFS during unit test."""
    with mock.patch("promptflow._sdk._tracing._invoke_pf_svc") as mock_func:
        mock_func.return_value = MOCK_PROMPTFLOW_SERVICE_PORT
        yield


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

    def test_experiment_test_lineage(self, monkeypatch: pytest.MonkeyPatch, mock_promptflow_service_invocation) -> None:
        # experiment orchestrator will help set this context in environment
        referenced_line_run_id = str(uuid.uuid4())
        ctx = {PF_TRACE_CONTEXT_ATTR: {ContextAttributeKey.REFERENCED_LINE_RUN_ID: referenced_line_run_id}}
        with monkeypatch.context() as m:
            m.setenv(PF_TRACE_CONTEXT, json.dumps(ctx))
            start_trace_with_devkit(session_id=None)
            # lineage is stored in context
            op_ctx = OperationContext.get_instance()
            otel_attrs = op_ctx._get_otel_attributes()
            assert otel_attrs[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID] == referenced_line_run_id

    def test_experiment_test_lineage_cleanup(
        self, monkeypatch: pytest.MonkeyPatch, mock_promptflow_service_invocation
    ) -> None:
        # in previous code, context may be set with lineage
        op_ctx = OperationContext.get_instance()
        op_ctx._add_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID, str(uuid.uuid4()))
        with monkeypatch.context() as m:
            m.setenv(PF_TRACE_CONTEXT, json.dumps({PF_TRACE_CONTEXT_ATTR: dict()}))
            start_trace_with_devkit(session_id=None)
            # lineage will be reset
            otel_attrs = op_ctx._get_otel_attributes()
            assert SpanAttributeFieldName.REFERENCED_LINE_RUN_ID not in otel_attrs

    def test_setup_exporter_in_executor(self, monkeypatch: pytest.MonkeyPatch):
        with monkeypatch.context() as m:
            m.delenv(OTEL_EXPORTER_OTLP_ENDPOINT, raising=False)
            setup_exporter_from_environ()
            tracer_provider: TracerProvider = trace.get_tracer_provider()
            assert len(tracer_provider._active_span_processor._span_processors) == 0

    def test_setup_exporter_in_executor_with_preview_flag(self, mock_promptflow_service_invocation):
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True

            start_trace()
            setup_exporter_from_environ()
            tracer_provider: TracerProvider = trace.get_tracer_provider()
            assert len(tracer_provider._active_span_processor._span_processors) == 1
            assert (
                tracer_provider._active_span_processor._span_processors[0].span_exporter._endpoint
                == f"http://localhost:{MOCK_PROMPTFLOW_SERVICE_PORT}/v1/traces"
            )
