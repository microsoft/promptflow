# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT

from promptflow._sdk._configuration import ConfigFileNotFound, Configuration

CONFIG_DATA_ROOT = Path(__file__).parent.parent.parent / "test_configs" / "configs"


@pytest.fixture
def config():
    return Configuration.get_instance()


@pytest.mark.unittest
class TestConfig:
    def test_set_config(self, config):
        config.set_config("a.b.c.test_key", "test_value")
        assert config.get_config("a.b.c.test_key") == "test_value"
        assert config.config == {"a": {"b": {"c": {"test_key": "test_value"}}}}

    def test_get_config(self, config):
        config.set_config("test_key", "test_value")
        assert config.get_config("test_key") == "test_value"

    def test_get_telemetry_consent(self, config):
        config.set_telemetry_consent(True)
        assert config.get_telemetry_consent() is True

    def test_set_telemetry_consent(self, config):
        config.set_telemetry_consent(True)
        assert config.get_telemetry_consent() is True

    def test_get_or_set_installation_id(self, config):
        user_id = config.get_or_set_installation_id()
        assert user_id is not None

    def test_config_instance(self, config):
        new_config = Configuration.get_instance()
        assert new_config is config

    def test_get_workspace_from_config(self):
        # Test config within flow folder
        config1 = Configuration._get_workspace_from_config(path=CONFIG_DATA_ROOT / "mock_flow1")
        assert config1 == RESOURCE_ID_FORMAT.format("sub1", "rg1", AZUREML_RESOURCE_PROVIDER, "ws1")
        # Test config using flow parent folder
        config2 = Configuration._get_workspace_from_config(path=CONFIG_DATA_ROOT / "mock_flow2")
        assert config2 == RESOURCE_ID_FORMAT.format(
            "sub_default", "rg_default", AZUREML_RESOURCE_PROVIDER, "ws_default"
        )
        # Test config not found
        with pytest.raises(ConfigFileNotFound):
            config1 = Configuration._get_workspace_from_config(path=CONFIG_DATA_ROOT.parent)
