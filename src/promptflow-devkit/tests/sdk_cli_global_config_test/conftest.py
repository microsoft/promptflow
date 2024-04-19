# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os

import pytest
from _constants import DEFAULT_RESOURCE_GROUP_NAME, DEFAULT_SUBSCRIPTION_ID, DEFAULT_WORKSPACE_NAME

from promptflow._sdk._configuration import Configuration
from promptflow.client import PFClient

AZUREML_RESOURCE_PROVIDER = "Microsoft.MachineLearningServices"
RESOURCE_ID_FORMAT = "/subscriptions/{}/resourceGroups/{}/providers/{}/workspaces/{}"


# region pfazure constants
@pytest.fixture(scope="session")
def subscription_id() -> str:
    return os.getenv("PROMPT_FLOW_SUBSCRIPTION_ID", DEFAULT_SUBSCRIPTION_ID)


@pytest.fixture(scope="session")
def resource_group_name() -> str:
    return os.getenv("PROMPT_FLOW_RESOURCE_GROUP_NAME", DEFAULT_RESOURCE_GROUP_NAME)


@pytest.fixture(scope="session")
def workspace_name() -> str:
    return os.getenv("PROMPT_FLOW_WORKSPACE_NAME", DEFAULT_WORKSPACE_NAME)


# endregion


@pytest.fixture
def pf() -> PFClient:
    return PFClient()


@pytest.fixture
def global_config(subscription_id: str, resource_group_name: str, workspace_name: str) -> None:
    config = Configuration.get_instance()
    if Configuration.CONNECTION_PROVIDER in config._config:
        return
    config.set_config(
        Configuration.CONNECTION_PROVIDER,
        "azureml:"
        + RESOURCE_ID_FORMAT.format(subscription_id, resource_group_name, AZUREML_RESOURCE_PROVIDER, workspace_name),
    )
