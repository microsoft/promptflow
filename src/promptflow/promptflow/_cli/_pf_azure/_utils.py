# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._cli._user_agent import USER_AGENT
from promptflow._cli._utils import get_client_for_cli
from promptflow.azure import PFClient


def _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=False):
    ml_client = get_client_for_cli(
        subscription_id=subscription_id, resource_group_name=resource_group, workspace_name=workspace_name
    )
    client = PFClient(ml_client=ml_client, user_agent=USER_AGENT, logging_enable=debug)
    return client
