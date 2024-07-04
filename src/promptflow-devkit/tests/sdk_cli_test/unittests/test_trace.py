# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import datetime
import json
import logging
import os
import uuid
from typing import Dict
from unittest.mock import MagicMock, patch

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
from promptflow._sdk._constants import (
    HOME_PROMPT_FLOW_DIR,
    PF_SERVICE_HOST,
    PF_TRACE_CONTEXT,
    PF_TRACE_CONTEXT_ATTR,
    TRACE_DEFAULT_COLLECTION,
    TRACE_LIST_DEFAULT_LIMIT,
    ContextAttributeKey,
)
from promptflow._sdk._tracing import setup_exporter_to_pfs, start_trace_with_devkit
from promptflow._sdk._utilities.tracing_utils import (
    TraceCountKey,
    TraceTelemetryHelper,
    WorkspaceKindLocalCache,
    append_conditions,
    parse_protobuf_span,
)
from promptflow.client import PFClient
from promptflow.exceptions import UserErrorException
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._start_trace import setup_exporter_from_environ

MOCK_PROMPTFLOW_SERVICE_PORT = "23333"
MOCK_PROMPTFLOW_SERVICE_HOST = PF_SERVICE_HOST


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
    with mock.patch(
        "promptflow._sdk._tracing._invoke_pf_svc",
        return_value=(MOCK_PROMPTFLOW_SERVICE_PORT, MOCK_PROMPTFLOW_SERVICE_HOST),
    ):
        yield


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestImports:
    def test_imports_in_tracing(self):
        # promptflow-tracing has imports from promptflow-devkit
        # this test guards against breaking changes in imports
        from promptflow._sdk._tracing import setup_exporter_to_pfs, start_trace_with_devkit

        assert callable(setup_exporter_to_pfs)
        assert callable(start_trace_with_devkit)

    def test_process_otlp_trace_request(self):
        from promptflow._internal import process_otlp_trace_request

        assert callable(process_otlp_trace_request)


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestStartTrace:
    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_setup_exporter_from_environ(self) -> None:
        from promptflow._sdk._service.utils.utils import get_pfs_host, get_pfs_host_after_check_wildcard

        def is_tracer_provider_set() -> bool:
            return isinstance(trace.get_tracer_provider(), TracerProvider)

        assert not is_tracer_provider_set()
        service_host = get_pfs_host()
        service_host = get_pfs_host_after_check_wildcard(service_host)
        # set some required environment variables
        endpoint = f"http://{service_host}:23333/v1/traces"
        collection = str(uuid.uuid4())
        experiment = "test_experiment"
        with patch.dict(
            os.environ,
            {
                OTEL_EXPORTER_OTLP_ENDPOINT: endpoint,
                TraceEnvironmentVariableName.COLLECTION: collection,
                TraceEnvironmentVariableName.EXPERIMENT: experiment,
            },
            clear=True,
        ):
            setup_exporter_from_environ()

        assert is_tracer_provider_set()
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        assert collection == tracer_provider._resource.attributes[SpanResourceAttributesFieldName.COLLECTION]
        assert experiment == tracer_provider._resource.attributes[SpanResourceAttributesFieldName.EXPERIMENT_NAME]

    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_local_to_cloud_resource(self) -> None:
        with patch.dict(
            os.environ,
            {
                TraceEnvironmentVariableName.COLLECTION: str(uuid.uuid4()),
                TraceEnvironmentVariableName.SUBSCRIPTION_ID: "test_subscription_id",
                TraceEnvironmentVariableName.RESOURCE_GROUP_NAME: "test_resource_group_name",
                TraceEnvironmentVariableName.WORKSPACE_NAME: "test_workspace_name",
                OTEL_EXPORTER_OTLP_ENDPOINT: "https://dummy-endpoint",
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
        span = parse_protobuf_span(pb_span, resource=mock_resource, logger=logging.getLogger(__name__))
        # as the above span do not have any attributes, so the parsed span should not have any attributes
        assert isinstance(span.attributes, dict)
        assert len(span.attributes) == 0

    @pytest.mark.usefixtures("mock_promptflow_service_invocation")
    def test_experiment_test_lineage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # experiment orchestrator will help set this context in environment
        referenced_line_run_id = str(uuid.uuid4())
        ctx = {PF_TRACE_CONTEXT_ATTR: {ContextAttributeKey.REFERENCED_LINE_RUN_ID: referenced_line_run_id}}
        with monkeypatch.context() as m:
            m.setenv(PF_TRACE_CONTEXT, json.dumps(ctx))
            start_trace_with_devkit(collection=str(uuid.uuid4()))
            # lineage is stored in context
            op_ctx = OperationContext.get_instance()
            otel_attrs = op_ctx._get_otel_attributes()
            assert otel_attrs[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID] == referenced_line_run_id

    @pytest.mark.usefixtures("mock_promptflow_service_invocation")
    def test_experiment_test_lineage_cleanup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # in previous code, context may be set with lineage
        op_ctx = OperationContext.get_instance()
        op_ctx._add_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID, str(uuid.uuid4()))
        with monkeypatch.context() as m:
            m.setenv(PF_TRACE_CONTEXT, json.dumps({PF_TRACE_CONTEXT_ATTR: dict()}))
            start_trace_with_devkit(collection=str(uuid.uuid4()))
            # lineage will be reset
            otel_attrs = op_ctx._get_otel_attributes()
            assert SpanAttributeFieldName.REFERENCED_LINE_RUN_ID not in otel_attrs

    def test_setup_exporter_in_executor(self, monkeypatch: pytest.MonkeyPatch):
        with monkeypatch.context() as m:
            m.delenv(OTEL_EXPORTER_OTLP_ENDPOINT, raising=False)
            original_proivder = trace.get_tracer_provider()
            setup_exporter_from_environ()
            new_provider: TracerProvider = trace.get_tracer_provider()
            # Assert the provider without exporter is not the one with exporter
            assert original_proivder == new_provider

    def test_pfs_invocation_failed_in_start_trace(self):
        with mock.patch(
            "promptflow._sdk._tracing._invoke_pf_svc",
            return_value=(MOCK_PROMPTFLOW_SERVICE_PORT, MOCK_PROMPTFLOW_SERVICE_HOST),
        ), mock.patch("promptflow._sdk._tracing.is_pfs_service_healthy", return_value=False), mock.patch(
            "promptflow._sdk._tracing._inject_res_attrs_to_environ"
        ) as monitor_func:
            start_trace_with_devkit(collection=str(uuid.uuid4()))
            assert monitor_func.call_count == 0

    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_no_op_tracer_provider(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
        # logger with "promptflow." prefix cannot be captured by caplog, so patch the logger for this test
        with patch("promptflow._sdk._tracing._logger", logging.getLogger(__name__)):
            with caplog.at_level(level=logging.WARNING):
                monkeypatch.setenv(OTEL_EXPORTER_OTLP_ENDPOINT, "http://dummy-endpoint")
                trace.set_tracer_provider(trace.NoOpTracerProvider())
                setup_exporter_to_pfs()
                monkeypatch.delenv(OTEL_EXPORTER_OTLP_ENDPOINT)
            assert (
                "tracer provider is set to NoOpTracerProvider, skip setting exporter to prompt flow service."
                in caplog.text
            )


@pytest.mark.unittest
@pytest.mark.sdk_test
class TestTraceOperations:
    def test_validate_delete_query_params(self, pf: PFClient) -> None:
        expected_error_message = (
            'Valid delete queries: 1) specify `run`; 2) specify `collection` (not "default"); '
            "3) specify `collection` and `started_before` (ISO 8601)."
        )

        def _validate_invalid_params(kwargs: Dict):
            with pytest.raises(UserErrorException) as e:
                pf.traces._validate_delete_query_params(**kwargs)
            assert expected_error_message in str(e)

        _validate_invalid_params({"run": str(uuid.uuid4()), "started_before": datetime.datetime.now().isoformat()})
        _validate_invalid_params({"collection": TRACE_DEFAULT_COLLECTION})
        _validate_invalid_params({"collection": str(uuid.uuid4()), "started_before": "invalid isoformat"})

    def test_append_conditions(self) -> None:
        orig_expr = "name == 'web_classification'"
        expr = append_conditions(
            expression=orig_expr,
            collection="test-collection",
            runs="run",
            session_id="test-session-id",
        )
        expected_expr = (
            "name == 'web_classification' and collection == 'test-collection' and "
            "run == 'run' and session_id == 'test-session-id'"
        )
        assert expr == expected_expr

    def test_append_conditions_multiple_runs(self) -> None:
        orig_expr = "name == 'web_classification'"
        expr = append_conditions(
            expression=orig_expr,
            collection="test-collection",
            runs=["run1", "run2"],
            session_id="test-session-id",
        )
        expected_expr = (
            "name == 'web_classification' and collection == 'test-collection' and "
            "(run == 'run1' or run == 'run2') and session_id == 'test-session-id'"
        )
        assert expr == expected_expr

    def test_search_default_limit(self, pf: PFClient) -> None:
        # mock ORM search to assert the default limit is applied
        def mock_orm_line_run_search(expression, limit):
            assert limit == TRACE_LIST_DEFAULT_LIMIT
            return []  # return an empty list to ensure test passed

        from promptflow._sdk._orm.trace import LineRun

        with patch.object(LineRun, "search", side_effect=mock_orm_line_run_search):
            pf.traces._search_line_runs(expression="name == 'web_classification'")


@pytest.mark.unittest
@pytest.mark.sdk_test
class TestWorkspaceKindLocalCache:
    def test_no_cache(self):
        sub, rg, ws = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        ws_local_cache = WorkspaceKindLocalCache(subscription_id=sub, resource_group_name=rg, workspace_name=ws)
        assert not ws_local_cache.is_cache_exists
        # mock `WorkspaceKindLocalCache._get_workspace_kind_from_azure`
        mock_kind = str(uuid.uuid4())
        with patch(
            "promptflow._sdk._utilities.tracing_utils.WorkspaceKindLocalCache._get_workspace_kind_from_azure"
        ) as mock_get_kind:
            mock_get_kind.return_value = mock_kind
            assert ws_local_cache.get_kind() == mock_kind

    def test_valid_cache(self):
        sub, rg, ws = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        # manually create a valid local cache
        kind = str(uuid.uuid4())
        with open(HOME_PROMPT_FLOW_DIR / WorkspaceKindLocalCache.PF_DIR_TRACING / f"{sub}_{rg}_{ws}.json", "w") as f:
            cache = {
                WorkspaceKindLocalCache.SUBSCRIPTION_ID: sub,
                WorkspaceKindLocalCache.RESOURCE_GROUP_NAME: rg,
                WorkspaceKindLocalCache.WORKSPACE_NAME: ws,
                WorkspaceKindLocalCache.KIND: kind,
                WorkspaceKindLocalCache.TIMESTAMP: datetime.datetime.now().isoformat(),
            }
            f.write(json.dumps(cache))
        ws_local_cache = WorkspaceKindLocalCache(subscription_id=sub, resource_group_name=rg, workspace_name=ws)
        assert ws_local_cache.is_cache_exists is True
        assert not ws_local_cache.is_expired
        assert ws_local_cache.get_kind() == kind

    def test_expired_cache(self):
        sub, rg, ws = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        # manually create an expired local cache
        with open(HOME_PROMPT_FLOW_DIR / WorkspaceKindLocalCache.PF_DIR_TRACING / f"{sub}_{rg}_{ws}.json", "w") as f:
            cache = {
                WorkspaceKindLocalCache.SUBSCRIPTION_ID: sub,
                WorkspaceKindLocalCache.RESOURCE_GROUP_NAME: rg,
                WorkspaceKindLocalCache.WORKSPACE_NAME: ws,
                WorkspaceKindLocalCache.KIND: str(uuid.uuid4()),  # this value is not important as it will be refreshed
                WorkspaceKindLocalCache.TIMESTAMP: (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(),
            }
            f.write(json.dumps(cache))
        ws_local_cache = WorkspaceKindLocalCache(subscription_id=sub, resource_group_name=rg, workspace_name=ws)
        assert ws_local_cache.is_cache_exists is True
        assert ws_local_cache.is_expired is True
        # mock `WorkspaceKindLocalCache._get_workspace_kind_from_azure`
        kind = str(uuid.uuid4())
        with patch(
            "promptflow._sdk._utilities.tracing_utils.WorkspaceKindLocalCache._get_workspace_kind_from_azure"
        ) as mock_get_kind:
            mock_get_kind.return_value = kind
            assert ws_local_cache.get_kind() == kind
        assert not ws_local_cache.is_expired


@pytest.mark.unittest
@pytest.mark.sdk_test
class TestTraceTelemetry:
    def test_user_agent_in_custom_dimensions(self):
        def mock_info(*args, **kwargs):
            extra: dict = kwargs.get("extra")
            custom_dimensions: dict = extra.get("custom_dimensions")
            assert "user_agent" in custom_dimensions.keys()
            assert "promptflow-sdk/" in custom_dimensions["user_agent"]

        mock_telemetry_logger = MagicMock()
        mock_telemetry_logger.info = mock_info
        with patch("promptflow._sdk._utilities.tracing_utils.get_telemetry_logger", return_value=mock_telemetry_logger):
            telemetry_helper = TraceTelemetryHelper()
            summary = dict()
            k = TraceCountKey(None, None, None, "script", "code")
            summary[k] = 1
            # append the mock summary and log
            telemetry_helper.append(summary)
            telemetry_helper.log_telemetry()
