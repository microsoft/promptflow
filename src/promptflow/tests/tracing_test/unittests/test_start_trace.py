# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uuid

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from pytest_mock import MockerFixture

import promptflow.tracing._start_trace
from promptflow.tracing import start_trace
from promptflow.tracing._constants import (
    PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON,
    RESOURCE_ATTRIBUTES_SERVICE_NAME,
    ResourceAttributesFieldName,
)


@pytest.mark.unittest
class TestStartTrace:
    def test_tracer_provider_after_start_trace(self) -> None:
        start_trace()
        tracer_provider = trace.get_tracer_provider()
        assert isinstance(tracer_provider, TracerProvider)
        attrs = tracer_provider.resource.attributes
        assert attrs[ResourceAttributesFieldName.SERVICE_NAME] == RESOURCE_ATTRIBUTES_SERVICE_NAME
        assert ResourceAttributesFieldName.SESSION_ID not in attrs

    def test_tracer_provider_overwritten(self) -> None:
        trace.set_tracer_provider(TracerProvider())
        old_tracer_provider = trace.get_tracer_provider()
        start_trace()
        new_tracer_provider = trace.get_tracer_provider()
        assert id(old_tracer_provider) != id(new_tracer_provider)

    def test_tracer_provider_resource_attributes(self) -> None:
        session_id = str(uuid.uuid4())
        res_attrs = {"attr1": "value1", "attr2": "value2"}
        start_trace(resource_attributes=res_attrs, session=session_id)
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        attrs = tracer_provider.resource.attributes
        assert attrs[ResourceAttributesFieldName.SESSION_ID] == session_id
        assert attrs["attr1"] == "value1"
        assert attrs["attr2"] == "value2"

    def test_skip_tracing_local_setup(self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
        spy = mocker.spy(promptflow.tracing._start_trace, "_is_devkit_installed")
        # configured environ to skip local setup
        with monkeypatch.context() as m:
            m.setenv(PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON, "true")
            start_trace()
            assert spy.call_count == 0
        # no environ, should call local setup once
        start_trace()
        assert spy.call_count == 1
