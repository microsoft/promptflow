# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest

from promptflow._cli.configuration import Configuration


@pytest.fixture
def config():
    return Configuration.get_instance()


@pytest.mark.unittest
class TestConfig:
    def test_set_config(self, config):
        config.set_config("test_key", "test_value")
        assert config.get_config("test_key") == "test_value"

    def test_get_config(self, config):
        config.set_config("test_key", "test_value")
        assert config.get_config("test_key") == "test_value"

    def test_get_telemetry_consent(self, config):
        config.set_telemetry_consent(True)
        assert config.get_telemetry_consent() is True

    def test_set_telemetry_consent(self, config):
        config.set_telemetry_consent(True)
        assert config.get_telemetry_consent() is True

    def test_get_or_set_user_id(self, config):
        user_id = config.get_or_set_user_id()
        assert user_id is not None
