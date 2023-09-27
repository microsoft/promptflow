# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT

from promptflow import PFClient
from promptflow._sdk._configuration import Configuration


@pytest.fixture(scope="session")
def pf() -> PFClient:
    return PFClient()


@pytest.fixture(scope="session")
def global_config():
    config = Configuration.get_instance()
    if Configuration.CONNECTION_PROVIDER in config._config:
        return
    config.set_config(
        Configuration.CONNECTION_PROVIDER,
        "azureml:"
        + RESOURCE_ID_FORMAT.format(
            "96aede12-2f73-41cb-b983-6d11a904839b", "promptflow", AZUREML_RESOURCE_PROVIDER, "promptflow-eastus2euap"
        ),
    )
