# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT

from promptflow._sdk._configuration import ConfigFileNotFound, Configuration
from promptflow._utils.context_utils import _change_working_dir

CONFIG_DATA_ROOT = Path(__file__).parent.parent.parent / "test_configs" / "configs"


@pytest.fixture
def config():
    return Configuration.get_instance()


@pytest.mark.unittest
class TestConfig:
    def test_set_config(self, config):
        config.set_config("a.b.c.test_key", "test_value")
        assert config.get_config("a.b.c.test_key") == "test_value"
        # global config may contain other keys
        assert config.config["a"] == {"b": {"c": {"test_key": "test_value"}}}

    def test_get_config(self, config):
        config.set_config("test_key", "test_value")
        assert config.get_config("test_key") == "test_value"

    def test_get_or_set_installation_id(self, config):
        user_id = config.get_or_set_installation_id()
        assert user_id is not None

    def test_config_instance(self, config):
        new_config = Configuration.get_instance()
        assert new_config is config

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
