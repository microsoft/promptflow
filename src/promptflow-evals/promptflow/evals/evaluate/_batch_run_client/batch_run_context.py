# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os

from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.tracing._integrations._openai_injector import inject_openai_api, recover_openai_api

from ..._user_agent import USER_AGENT
from .code_client import CodeClient


class BatchRunContext:
    def __init__(self, client):
        self.client = client

    def __enter__(self):
        if isinstance(self.client, CodeClient):
            ClientUserAgentUtil.append_user_agent(USER_AGENT)
            inject_openai_api()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(self.client, CodeClient):
            recover_openai_api()
