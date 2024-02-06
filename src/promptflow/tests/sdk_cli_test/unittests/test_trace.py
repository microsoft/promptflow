# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import uuid
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry.sdk.trace import TracerProvider

from promptflow._constants import ResourceAttributeFieldName, TraceEnvironmentVariableName
from promptflow._trace._start_trace import (
    _create_resource,
    _is_tracer_provider_configured,
    _provision_session_id,
    setup_exporter_from_environ,
)


@pytest.fixture
def reset_tracer_provider() -> None:
    from opentelemetry.util._once import Once

    with patch("opentelemetry.trace._TRACER_PROVIDER_SET_ONCE", Once()), patch(
        "opentelemetry.trace._TRACER_PROVIDER", None
    ):
        yield


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestStartTrace:
    def test_create_resource(self) -> None:
        session_id = str(uuid.uuid4())
        resource1 = _create_resource(session_id=session_id)
        assert resource1.attributes[ResourceAttributeFieldName.SESSION_ID] == session_id
        assert ResourceAttributeFieldName.EXPERIMENT_NAME not in resource1.attributes

        experiment = "test_experiment"
        resource2 = _create_resource(session_id=session_id, experiment=experiment)
        assert resource2.attributes[ResourceAttributeFieldName.SESSION_ID] == session_id
        assert resource2.attributes[ResourceAttributeFieldName.EXPERIMENT_NAME] == experiment

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
        assert session_id == tracer_provider._resource.attributes[ResourceAttributeFieldName.SESSION_ID]
        assert experiment == tracer_provider._resource.attributes[ResourceAttributeFieldName.EXPERIMENT_NAME]

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
