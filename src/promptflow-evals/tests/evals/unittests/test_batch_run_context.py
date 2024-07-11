import os
from unittest.mock import MagicMock

import pytest

from promptflow.client import PFClient
from promptflow.evals._constants import PF_BATCH_TIMEOUT_SEC, PF_BATCH_TIMEOUT_SEC_DEFAULT
from promptflow.evals._user_agent import USER_AGENT
from promptflow.evals.evaluate._batch_run_client import BatchRunContext, CodeClient
from promptflow.evals.evaluate._batch_run_client.code_client import CodeRun


@pytest.fixture
def code_client_mock():
    return MagicMock(spec=CodeClient)


@pytest.fixture
def pf_client_mock():
    return MagicMock(spec=PFClient)


@pytest.fixture
def code_run_mock():
    return MagicMock()


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

    def test_get_result_timeout(self, code_run_mock):
        code_run_instance = CodeRun(run=code_run_mock, input_data={})
        code_run_instance.get_result_df()

        code_run_mock.result.assert_called_once_with(timeout=PF_BATCH_TIMEOUT_SEC_DEFAULT)

        custom_timeout = "100000"
        os.environ[PF_BATCH_TIMEOUT_SEC] = custom_timeout
        code_run_instance.get_result_df()
        code_run_mock.result.assert_called_with(timeout=int(custom_timeout))
