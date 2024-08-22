import http
import os
import pathlib
from typing import Any, Iterator, MutableMapping, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from azure.core.exceptions import HttpResponseError
from azure.core.rest import AsyncHttpResponse, HttpRequest
from azure.identity import DefaultAzureCredential

from promptflow.evals._common.constants import EvaluationMetrics, HarmSeverityLevel, RAIService
from promptflow.evals._common.rai_service import (
    _get_service_discovery_url,
    ensure_service_availability,
    evaluate_with_rai_service,
    fetch_or_reuse_token,
    fetch_result,
    get_rai_svc_url,
    parse_response,
    submit_request,
)


@pytest.fixture
def data_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "evaluate_test_data.jsonl")


class MockAsyncHttpResponse(AsyncHttpResponse):
    """A mocked implementation of azure.core.rest.HttpResponse."""

    def __init__(
        self,
        status_code: int,
        *,
        text: Optional[str] = None,
        json: Optional[Any] = None,
        headers: Optional[MutableMapping[str, str]] = None,
        request: Optional[HttpRequest] = None,
        content_type: Optional[str] = None,
    ) -> None:
        self._status_code = status_code
        self._text = text or ""
        self._json = json
        self._request = request
        self._headers = headers or {}
        self._content_type = content_type

    def json(self) -> Any:
        return self._json

    def text(self, encoding: Optional[str] = None) -> str:
        return self._text

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def request(self) -> HttpRequest:
        return self._request

    @property
    def reason(self) -> str:
        return f"{self.status_code} {http.client.responses[self.status_code]}"

    @property
    def headers(self) -> MutableMapping[str, str]:
        return self._headers

    @property
    def content_type(self) -> Optional[str]:
        return self._content_type

    @property
    def is_closed(self) -> bool:
        return True

    @property
    def is_stream_consumed(self) -> bool:
        return True

    @property
    def encoding(self) -> Optional[str]:
        return None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HttpResponseError(response=self)

    async def close(self) -> None:
        pass

    async def __aenter__(self) -> object:
        raise NotImplementedError()

    async def __aexit__(self, *args) -> None:
        raise NotImplementedError()

    @property
    def url(self) -> str:
        raise NotImplementedError()

    @property
    def content(self) -> bytes:
        raise NotImplementedError()

    async def read(self) -> bytes:
        raise NotImplementedError()

    async def iter_bytes(self, **kwargs) -> Iterator[bytes]:
        raise NotImplementedError()

    async def iter_raw(self, **kwargs) -> Iterator[bytes]:
        raise NotImplementedError()


@pytest.mark.usefixtures("mock_project_scope")
@pytest.mark.unittest
class TestContentSafetyEvaluator:
    def test_rai_subscript_functions(self):
        # ensure_service_availability()

        """
        evaluate_with_rai_service()
        fetch_or_reuse_token()
        get_rai_svc_url()
        _get_service_discovery_url()
        parse_response()
        fetch_result()
        submit_request()
        ensure_service_availability()"""

    @pytest.mark.asyncio
    @patch("promptflow.evals._http_utils.AsyncHttpPipeline.get", return_value=MockAsyncHttpResponse(200, json={}))
    async def test_ensure_service_availability(self, client_mock):
        _ = await ensure_service_availability("dummy_url", "dummy_token")
        assert client_mock._mock_await_count == 1

    @pytest.mark.asyncio
    @patch("promptflow.evals._http_utils.AsyncHttpPipeline.get", return_value=MockAsyncHttpResponse(9001, json={}))
    async def test_ensure_service_availability_service_unavailable(self, client_mock):
        with pytest.raises(Exception) as exc_info:
            _ = await ensure_service_availability("dummy_url", "dummy_token")
        assert "RAI service is not available in this region. Status Code: 9001" in str(exc_info._excinfo[1])
        assert client_mock._mock_await_count == 1

    @pytest.mark.asyncio
    @patch("promptflow.evals._http_utils.AsyncHttpPipeline.get", return_value=MockAsyncHttpResponse(200, json={}))
    async def test_ensure_service_availability_exception_capability_unavailable(self, client_mock):
        with pytest.raises(Exception) as exc_info:
            _ = await ensure_service_availability("dummy_url", "dummy_token", capability="does not exist")
        assert "Capability 'does not exist' is not available in this region" in str(exc_info._excinfo[1])
        assert client_mock._mock_await_count == 1

    @pytest.mark.asyncio
    @patch(
        "promptflow.evals._http_utils.AsyncHttpPipeline.post",
        return_value=MockAsyncHttpResponse(
            202,
            json={"location": "this/is/the/dummy-operation-id"},
        ),
    )
    async def test_submit_request(self, client_mock):
        result = await submit_request(
            question="What is the meaning of life",
            answer="42",
            metric="points",
            rai_svc_url="www.notarealurl.com",
            token="dummy",
        )
        assert result == "dummy-operation-id"

    @pytest.mark.asyncio
    @patch(
        "promptflow.evals._http_utils.AsyncHttpPipeline.post",
        return_value=MockAsyncHttpResponse(
            404,
            json={"location": "this/is/the/dummy-operation-id"},
            content_type="application/json",
        ),
    )
    async def test_submit_request_not_found(self, client_mock):
        with pytest.raises(HttpResponseError) as exc_info:
            _ = await submit_request(
                question="What is the meaning of life",
                answer="42",
                metric="points",
                rai_svc_url="www.notarealurl.com",
                token="dummy",
            )
        assert "Operation returned an invalid status '404 Not Found'" in str(exc_info._excinfo[1])

    @pytest.mark.usefixtures("mock_token")
    @pytest.mark.usefixtures("mock_expired_token")
    @pytest.mark.asyncio
    async def test_fetch_or_reuse_token(self, mock_token, mock_expired_token):
        mock_cred = MagicMock(Spec=DefaultAzureCredential)
        mock_cred.get_token.return_value = type("", (object,), {"token": 100})()

        res = await fetch_or_reuse_token(credential=mock_cred, token=mock_token)
        assert res == mock_token

        res = await fetch_or_reuse_token(credential=mock_cred, token=mock_expired_token)
        assert res == 100

        res = await fetch_or_reuse_token(credential=mock_cred, token="not-a-token")
        assert res == 100

    @patch(
        "promptflow.evals._http_utils.AsyncHttpPipeline.get",
        return_value=MockAsyncHttpResponse(200, json={"result": "stuff"}),
    )
    @patch("promptflow.evals._common.constants.RAIService.TIMEOUT", 1)
    @patch("promptflow.evals._common.constants.RAIService.SLEEP_TIME", 1.2)
    @pytest.mark.usefixtures("mock_token")
    @pytest.mark.asyncio
    async def test_fetch_result(self, client_mock, mock_token):
        # These asserts aren't necessary, but given the scarcity of constant patches,
        # it's nice to include an obvious example.
        assert RAIService.TIMEOUT == 1
        assert RAIService.SLEEP_TIME == 1.2
        res = await fetch_result(
            operation_id="op-id", rai_svc_url="www.notarealurl.com", credential=None, token=mock_token
        )
        assert client_mock._mock_await_count == 1
        assert res["result"] == "stuff"

    @patch(
        "promptflow.evals._http_utils.AsyncHttpPipeline.get",
        return_value=MockAsyncHttpResponse(404, json={"result": "stuff"}),
    )
    @patch("promptflow.evals._common.constants.RAIService.TIMEOUT", 1)
    @patch("promptflow.evals._common.constants.RAIService.SLEEP_TIME", 1.2)
    @pytest.mark.usefixtures("mock_token")
    @pytest.mark.asyncio
    async def test_fetch_result_timeout(self, client_mock, mock_token):
        with pytest.raises(TimeoutError) as exc_info:
            _ = await fetch_result(
                operation_id="op-id", rai_svc_url="www.notarealurl.com", credential=None, token=mock_token
            )
        # We expect 2 calls; the initial call, then one more ~2 seconds later.
        assert client_mock._mock_await_count == 2
        # Don't bother checking exact time beyond seconds, that's never going to be consistent across machines.
        assert "Fetching annotation result 2 times out after 1" in str(exc_info._excinfo[1])

    def test_parse_response(self):
        batch_response = [{"not-a-metric": "not-a-value"}]
        metric_name = EvaluationMetrics.HATE_FAIRNESS
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert np.isnan(result[EvaluationMetrics.HATE_UNFAIRNESS])
        assert np.isnan(result[EvaluationMetrics.HATE_UNFAIRNESS + "_score"])
        assert result[EvaluationMetrics.HATE_UNFAIRNESS + "_reason"] == ""

        metric_name = EvaluationMetrics.VIOLENCE
        response_value = {
            "label": 0,
            "reasoning": "This is a sample reasoning.",
            "version": "0.3",
        }

        # The parse_response function has a TON of conditional logic that depends
        # on the exact structure of batch_response[0][metric_name].
        # This tests ALL of it.
        batch_response[0] = {metric_name: str(response_value)}

        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert result[metric_name] == HarmSeverityLevel.VeryLow.value
        assert result[metric_name + "_score"] == 0
        assert result[metric_name + "_reason"] == response_value["reasoning"]

        response_value["output"] = {
            "valid": True,
            "reason": "This is a sample reason.",
        }
        batch_response[0] = {metric_name: str(response_value)}
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert result[metric_name] == HarmSeverityLevel.VeryLow.value
        assert result[metric_name + "_score"] == 0
        assert result[metric_name + "_reason"] == response_value["output"]["reason"]

        response_value.pop("output")
        response_value.pop("reasoning")
        response_value.pop("label")
        batch_response[0] = {metric_name: str(response_value)}
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert np.isnan(result[metric_name])
        assert np.isnan(result[metric_name + "_score"])
        assert result[metric_name + "_reason"] == ""

        batch_response[0] = {metric_name: 5}
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert result[metric_name] == HarmSeverityLevel.Medium.value
        assert result[metric_name + "_score"] == 5
        assert result[metric_name + "_reason"] == ""

        batch_response[0] = {metric_name: 8}
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert np.isnan(result[metric_name])
        assert np.isnan(result[metric_name + "_score"])

        batch_response[0] = {metric_name: "value is 7"}
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert result[metric_name] == HarmSeverityLevel.High.value
        assert result[metric_name + "_score"] == 7
        assert result[metric_name + "_reason"] == "value is 7"

        batch_response[0] = {metric_name: "not a number"}
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert np.isnan(result[metric_name])
        assert np.isnan(result[metric_name + "_score"])

        batch_response[0] = {metric_name: ["still not a number"]}
        result = parse_response(batch_response=batch_response, metric_name=metric_name)
        assert np.isnan(result[metric_name])
        assert np.isnan(result[metric_name + "_score"])

    @pytest.mark.asyncio
    @patch(
        "promptflow.evals._http_utils.AsyncHttpPipeline.get",
        return_value=MockAsyncHttpResponse(
            200, json={"properties": {"discoveryUrl": "https://www.url.com:123/thePath"}}
        ),
    )
    async def test_get_service_discovery_url(self, client_mock):

        token = "fake-token"
        azure_ai_project = {
            "subscription_id": "fake-id",
            "project_name": "fake-name",
            "resource_group_name": "fake-group",
        }

        url = await _get_service_discovery_url(azure_ai_project=azure_ai_project, token=token)
        assert url == "https://www.url.com:123"

    @pytest.mark.asyncio
    @patch(
        "promptflow.evals._http_utils.AsyncHttpPipeline.get",
        return_value=MockAsyncHttpResponse(
            201, json={"properties": {"discoveryUrl": "https://www.url.com:123/thePath"}}
        ),
    )
    async def test_get_service_discovery_url_exception(self, client_mock):
        token = "fake-token"
        azure_ai_project = {
            "subscription_id": "fake-id",
            "project_name": "fake-name",
            "resource_group_name": "fake-group",
        }

        with pytest.raises(Exception) as exc_info:
            _ = await _get_service_discovery_url(azure_ai_project=azure_ai_project, token=token)
        assert "Failed to retrieve the discovery service URL" in str(exc_info._excinfo[1])

    @pytest.mark.asyncio
    @patch(
        "promptflow.evals._http_utils.AsyncHttpPipeline.get",
        return_value=MockAsyncHttpResponse(
            200, json={"properties": {"discoveryUrl": "https://www.url.com:123/thePath"}}
        ),
    )
    @patch(
        "promptflow.evals._common.rai_service._get_service_discovery_url",
        return_value="https://www.url.com:123",
    )
    async def test_get_rai_svc_url(self, client_mock, discovery_mock):
        token = "fake-token"
        project_scope = {
            "subscription_id": "fake-id",
            "project_name": "fake-name",
            "resource_group_name": "fake-group",
        }
        rai_url = await get_rai_svc_url(project_scope=project_scope, token=token)
        assert rai_url == (
            "https://www.url.com:123/raisvc/v1.0/subscriptions/fake-id/"
            + "resourceGroups/fake-group/providers/Microsoft.MachineLearningServices/workspaces/fake-name"
        )

    @pytest.mark.asyncio
    @patch(
        "promptflow.evals._common.rai_service.fetch_or_reuse_token",
        return_value="dummy-token",
    )
    @patch(
        "promptflow.evals._common.rai_service.get_rai_svc_url",
        return_value="www.rai_url.com",
    )
    @patch(
        "promptflow.evals._common.rai_service.ensure_service_availability",
        return_value=None,
    )
    @patch(
        "promptflow.evals._common.rai_service.submit_request",
        return_value="op_id",
    )
    @patch(
        "promptflow.evals._common.rai_service.fetch_result",
        return_value="response_object",
    )
    @patch(
        "promptflow.evals._common.rai_service.parse_response",
        return_value="wow-that's-a-lot-of-patches",
    )
    @patch("azure.identity.DefaultAzureCredential")
    async def test_evaluate_with_rai_service(
        self, cred_mock, fetch_token_mock, scv_mock, avail_mock, submit_mock, fetch_result_mock, parse_mock
    ):
        result = await evaluate_with_rai_service(
            "what is the weather outside?",
            "raining cats and dogs",
            "points",
            {"subscription_id": "fake-id", "project_name": "fake-name", "resource_group_name": "fake-group"},
            None,
        )
        assert result == "wow-that's-a-lot-of-patches"
        assert fetch_token_mock._mock_call_count == 1
        assert scv_mock._mock_call_count == 1
        assert avail_mock._mock_call_count == 1
        assert submit_mock._mock_call_count == 1
        assert fetch_result_mock._mock_call_count == 1
        assert parse_mock._mock_call_count == 1
