# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from pytest_mock import MockerFixture

import promptflow.tracing._start_trace
from promptflow.tracing import start_trace
from promptflow.tracing._constants import (
    PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON,
    RESOURCE_ATTRIBUTES_SERVICE_NAME,
    ResourceAttributesFieldName,
)
from promptflow.tracing._start_trace import _get_collection_from_cwd, _kwargs_in_func, is_collection_writeable


@pytest.fixture
def mock_devkit_not_installed(mocker: MockerFixture):
    """Mock environment without promptflow-devkit installed."""
    with mocker.patch("promptflow.tracing._start_trace._is_devkit_installed", return_value=False):
        yield


@pytest.fixture
def reset_tracer_provider():
    """Force reset tracer provider."""
    with patch("opentelemetry.trace._TRACER_PROVIDER", None), patch(
        "opentelemetry.trace._TRACER_PROVIDER_SET_ONCE._done", False
    ):
        yield


def get_collection_from_tracer_provider() -> str:
    tracer_provider: TracerProvider = trace.get_tracer_provider()
    return tracer_provider.resource.attributes[ResourceAttributesFieldName.COLLECTION]


@pytest.mark.unittest
@pytest.mark.usefixtures("mock_devkit_not_installed", "reset_tracer_provider")
class TestStartTrace:
    def test_tracer_provider_after_start_trace(self) -> None:
        start_trace()
        tracer_provider = trace.get_tracer_provider()
        assert isinstance(tracer_provider, TracerProvider)
        attrs = tracer_provider.resource.attributes
        assert attrs[ResourceAttributesFieldName.SERVICE_NAME] == RESOURCE_ATTRIBUTES_SERVICE_NAME
        assert ResourceAttributesFieldName.COLLECTION in attrs

    def test_tracer_provider_resource_attributes(self) -> None:
        collection = str(uuid.uuid4())
        res_attrs = {"attr1": "value1", "attr2": "value2"}
        start_trace(resource_attributes=res_attrs, collection=collection)
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        attrs = tracer_provider.resource.attributes
        assert attrs[ResourceAttributesFieldName.COLLECTION] == collection
        assert attrs["attr1"] == "value1"
        assert attrs["attr2"] == "value2"

    def test_tracer_provider_resource_merge(self) -> None:
        existing_res = {"existing_attr": "existing_value"}
        trace.set_tracer_provider(TracerProvider(resource=Resource(existing_res)))
        start_trace()
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        assert "existing_attr" in tracer_provider.resource.attributes
        assert ResourceAttributesFieldName.SERVICE_NAME in tracer_provider.resource.attributes

    def test_tracer_provider_collection_overwrite(self) -> None:
        old_collection = str(uuid.uuid4())
        existing_res = {ResourceAttributesFieldName.COLLECTION: old_collection}
        trace.set_tracer_provider(TracerProvider(resource=Resource(existing_res)))
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        assert tracer_provider.resource.attributes[ResourceAttributesFieldName.COLLECTION] == old_collection
        # specify `collection` with `start_trace`
        new_collection = str(uuid.uuid4())
        start_trace(collection=new_collection)
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        assert tracer_provider.resource.attributes[ResourceAttributesFieldName.COLLECTION] == new_collection

    def test_collection_override(self) -> None:
        start_trace()
        collection_from_cwd = get_collection_from_tracer_provider()
        user_specified_collection1 = str(uuid.uuid4())
        # user specifies, will override
        start_trace(collection=user_specified_collection1)
        assert get_collection_from_tracer_provider() != collection_from_cwd
        assert get_collection_from_tracer_provider() == user_specified_collection1
        # user does not specify, collection will not change
        start_trace()
        assert get_collection_from_tracer_provider() == user_specified_collection1
        user_specified_collection2 = str(uuid.uuid4())
        # user specifies another, will override
        start_trace(collection=user_specified_collection2)
        assert get_collection_from_tracer_provider() != user_specified_collection1
        assert get_collection_from_tracer_provider() == user_specified_collection2

    def test_collection_internal_override(self) -> None:
        start_trace()
        # internal collection can override when no user specified
        internal_collection = str(uuid.uuid4())
        start_trace(_collection=internal_collection)
        assert get_collection_from_tracer_provider() == internal_collection
        # user specified will override internal collection
        user_specified_collection = str(uuid.uuid4())
        start_trace(collection=user_specified_collection)
        assert get_collection_from_tracer_provider() == user_specified_collection
        # internal collection cannot override user specified
        start_trace(_collection=internal_collection)
        assert get_collection_from_tracer_provider() == user_specified_collection

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

    def test_get_collection_from_cwd(self, tmpdir) -> None:
        with tmpdir.as_cwd():
            collection = _get_collection_from_cwd()
            assert collection == Path(tmpdir).resolve().name

    def test_kwargs_in_func(self) -> None:
        def func_with_kwargs1(**kwargs):
            ...

        def func_with_kwargs2(param1, param2, **kwargs):
            ...

        def func_without_kwargs1():
            ...

        def func_without_kwargs2(param1, param2):
            ...

        def func_without_kwargs3(param1, param2, *args):
            ...

        def func_without_kwargs4(param1, param2, *, keyword_param1, keyword_param2):
            ...

        assert _kwargs_in_func(func_with_kwargs1) is True
        assert _kwargs_in_func(func_with_kwargs2) is True
        assert _kwargs_in_func(func_without_kwargs1) is False
        assert _kwargs_in_func(func_without_kwargs2) is False
        assert _kwargs_in_func(func_without_kwargs3) is False
        assert _kwargs_in_func(func_without_kwargs4) is False

    def test_protected_collection(self) -> None:
        start_trace(collection=str(uuid.uuid4()))
        assert is_collection_writeable() is False

    def test_writeable_collection(self) -> None:
        start_trace()
        assert is_collection_writeable() is True
