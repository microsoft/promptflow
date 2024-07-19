# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os

from promptflow._sdk._constants import PF_FLOW_ENTRY_IN_TMP, PF_FLOW_META_LOAD_IN_SUBPROCESS
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.tracing._integrations._openai_injector import inject_openai_api, recover_openai_api

from ..._user_agent import USER_AGENT
from .._utils import set_event_loop_policy
from .code_client import CodeClient
from .proxy_client import ProxyClient


class BatchRunContext:
    """Context manager for batch run clients.

    :param client: The client to run in the context.
    :type client: Union[
        ~promptflow.evals.evaluate.code_client.CodeClient,
        ~promptflow.evals.evaluate.proxy_client.ProxyClient
    ]
    """
    def __init__(self, client) -> None:
        self.client = client

    def __enter__(self):
        if isinstance(self.client, CodeClient):
            ClientUserAgentUtil.append_user_agent(USER_AGENT)
            inject_openai_api()

        if isinstance(self.client, ProxyClient):
            os.environ[PF_FLOW_ENTRY_IN_TMP] = "true"
            os.environ[PF_FLOW_META_LOAD_IN_SUBPROCESS] = "false"

            # For addressing the issue of asyncio event loop closed on Windows
            set_event_loop_policy()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(self.client, CodeClient):
            recover_openai_api()

        if isinstance(self.client, ProxyClient):
            os.environ.pop(PF_FLOW_ENTRY_IN_TMP, None)
            os.environ.pop(PF_FLOW_META_LOAD_IN_SUBPROCESS, None)
