# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import logging
import os
import time

import pytest

from promptflow._cli._configuration import Configuration
from promptflow._cli._pf._run import show_run
from promptflow._telemetry.logging_handler import AzureMLSDKLogHandler, get_appinsights_log_handler


@contextlib.contextmanager
def environment_variable_overwrite(key, val):
    if key in os.environ.keys():
        backup_value = os.environ[key]
    else:
        backup_value = None
    os.environ[key] = val

    try:
        yield
    finally:
        if backup_value:
            os.environ[key] = backup_value
        else:
            os.environ.pop(key)


@contextlib.contextmanager
def cli_consent_config_overwrite(val):
    config = Configuration.get_instance()
    config.set_telemetry_consent(val)
    try:
        yield
    finally:
        if os.path.exists(Configuration.CONFIG_PATH):
            os.remove(Configuration.CONFIG_PATH)


@pytest.mark.e2etest
class TestTelemetry:
    def test_logging_handler(self):
        logger = logging.getLogger("test_logging_handler")
        # override environment variable
        with environment_variable_overwrite("TELEMETRY_ENABLED", "true"):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, AzureMLSDKLogHandler)
            assert handler._is_telemetry_collection_disabled is False
            logger.addHandler(handler)
            logger.info("test_logging_handler")
            logger.warning("test_logging_handler")
            time.sleep(10)

        with environment_variable_overwrite("TELEMETRY_ENABLED", "false"):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, AzureMLSDKLogHandler)
            assert handler._is_telemetry_collection_disabled is True

        # write config
        with cli_consent_config_overwrite(True):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, AzureMLSDKLogHandler)
            assert handler._is_telemetry_collection_disabled is False

        with cli_consent_config_overwrite(False):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, AzureMLSDKLogHandler)
            assert handler._is_telemetry_collection_disabled is True

    def test_cli_telemetry(self):
        with cli_consent_config_overwrite(True):
            try:
                show_run(name="not_exist")
            except Exception:
                pass
        time.sleep(1000)

    def test_sdk_telemetry(self, pf):
        with cli_consent_config_overwrite(True):
            try:
                pf.run.get("not_exist")
            except Exception:
                pass
        time.sleep(1000)
