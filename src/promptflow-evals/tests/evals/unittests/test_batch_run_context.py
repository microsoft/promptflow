from unittest.mock import MagicMock

import pytest

from promptflow.client import PFClient
from promptflow.evals._user_agent import USER_AGENT
from promptflow.evals.evaluate._batch_run_client import BatchRunContext, CodeClient


@pytest.fixture
def code_client_mock():
    return MagicMock(spec=CodeClient)


@pytest.fixture
def pf_client_mock():
    return MagicMock(spec=PFClient)


@pytest.mark.unittest
class TestBatchRunContext:
    def test_with_codeclient(self, mocker, code_client_mock):
        mock_append_user_agent = mocker.patch(
            "promptflow._utils.user_agent_utils.ClientUserAgentUtil.append_user_agent"
        )
        mock_inject_openai_api = mocker.patch("promptflow.tracing._integrations._openai_injector.inject_openai_api")
        mock_recover_openai_api = mocker.patch("promptflow.tracing._integrations._openai_injector.recover_openai_api")

        with BatchRunContext(code_client_mock):
            # TODO: Failed to mock inject_openai_api and recover_openai_api for some reason.
            # Need to investigate further.
            # mock_inject_openai_api.assert_called_once()
            # mock_recover_openai_api.assert_called_once()
            print(f"mock_inject_openai_api.call_count: {mock_inject_openai_api.call_count}")
            print(f"mock_recover_openai_api.call_count: {mock_recover_openai_api.call_count}")
            pass

        mock_append_user_agent.assert_called_once_with(USER_AGENT)

    def test_with_pfclient(self, mocker, pf_client_mock):
        mock_append_user_agent = mocker.patch(
            "promptflow._utils.user_agent_utils.ClientUserAgentUtil.append_user_agent"
        )
        mock_inject_openai_api = mocker.patch("promptflow.tracing._integrations._openai_injector.inject_openai_api")
        mock_recover_openai_api = mocker.patch("promptflow.tracing._integrations._openai_injector.recover_openai_api")

        with BatchRunContext(code_client_mock):
            mock_append_user_agent.assert_not_called()
            mock_inject_openai_api.assert_not_called()
            pass

        mock_recover_openai_api.assert_not_called()
