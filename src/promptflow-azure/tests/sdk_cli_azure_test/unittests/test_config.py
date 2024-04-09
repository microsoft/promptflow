# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._configuration import ConfigFileNotFound, Configuration, InvalidConfigFile
from promptflow._utils.context_utils import _change_working_dir

AZUREML_RESOURCE_PROVIDER = "Microsoft.MachineLearningServices"
RESOURCE_ID_FORMAT = "/subscriptions/{}/resourceGroups/{}/providers/{}/workspaces/{}"


CONFIG_DATA_ROOT = PROMPTFLOW_ROOT / "tests/test_configs/configs"


@pytest.fixture
def config():
    return Configuration.get_instance()


@pytest.mark.unittest
class TestConfig:
    def test_get_workspace_from_config(self):
        # New instance instead of get_instance() to avoid side effect
        conf = Configuration(overrides={"connection.provider": "azureml"})
        # Test config within flow folder
        target_folder = CONFIG_DATA_ROOT / "mock_flow1"
        with _change_working_dir(target_folder):
            config1 = conf.get_connection_provider()
        assert config1 == "azureml:" + RESOURCE_ID_FORMAT.format("sub1", "rg1", AZUREML_RESOURCE_PROVIDER, "ws1")
        # Test config using flow parent folder
        target_folder = CONFIG_DATA_ROOT / "mock_flow2"
        with _change_working_dir(target_folder):
            config2 = conf.get_connection_provider()
        assert config2 == "azureml:" + RESOURCE_ID_FORMAT.format(
            "sub_default", "rg_default", AZUREML_RESOURCE_PROVIDER, "ws_default"
        )
        # Test config not found
        with pytest.raises(ConfigFileNotFound):
            Configuration._get_workspace_from_config(path=CONFIG_DATA_ROOT.parent)
        # Test empty config
        target_folder = CONFIG_DATA_ROOT / "mock_flow_empty_config"
        with pytest.raises(InvalidConfigFile):
            with _change_working_dir(target_folder):
                conf.get_connection_provider()
