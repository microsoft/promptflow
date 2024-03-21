# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from promptflow._sdk._configuration import Configuration, InvalidConfigValue
from promptflow._sdk._constants import FLOW_DIRECTORY_MACRO_IN_CONFIG
from promptflow._utils.user_agent_utils import ClientUserAgentUtil

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
        user_id1 = config.get_or_set_installation_id()
        assert user_id1 is not None

        user_id2 = config.get_or_set_installation_id()
        assert user_id1 == user_id2

    def test_config_instance(self, config):
        new_config = Configuration.get_instance()
        assert new_config is config

    def test_set_invalid_run_output_path(self, config: Configuration) -> None:
        expected_error_message = (
            "Cannot specify flow directory as run output path; "
            "if you want to specify run output path under flow directory, "
            "please use its child folder, e.g. '${flow_directory}/.runs'."
        )
        # directly set
        with pytest.raises(InvalidConfigValue) as e:
            config.set_config(key=Configuration.RUN_OUTPUT_PATH, value=FLOW_DIRECTORY_MACRO_IN_CONFIG)
        assert expected_error_message in str(e)
        # override
        with pytest.raises(InvalidConfigValue) as e:
            Configuration(overrides={Configuration.RUN_OUTPUT_PATH: FLOW_DIRECTORY_MACRO_IN_CONFIG})
        assert expected_error_message in str(e)

    def test_ua_set_load(self, config: Configuration) -> None:
        config.set_config(key=Configuration.USER_AGENT, value="test/1.0.0")
        user_agent = config.get_user_agent()
        assert user_agent == "PFCustomer_test/1.0.0"
        # load empty ua won't break
        config.set_config(key=Configuration.USER_AGENT, value="")
        user_agent = config.get_user_agent()
        assert user_agent == ""
        # empty ua won't add to context
        ClientUserAgentUtil.update_user_agent_from_config()
        user_agent = ClientUserAgentUtil.get_user_agent()
        # in test environment, user agent may contain promptflow-local-serving/0.0.1 test-user-agent
        assert "test/1.0.0" not in user_agent
