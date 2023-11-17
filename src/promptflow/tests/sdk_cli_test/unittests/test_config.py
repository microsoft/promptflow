# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from promptflow._sdk._configuration import Configuration

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
