# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import time

import pytest

from promptflow._cli._user_agent import USER_AGENT
from promptflow._telemetry.logging_handler import get_appinsights_log_handler


@pytest.mark.e2etest
class TestTelemetry:
    def test_logging_handler(self):
        logger = logging.getLogger("test_logging_handler")
        handler = get_appinsights_log_handler(
            user_agent=USER_AGENT,
        )
        logger.addHandler(handler)
        logger.info("test_logging_handler")
        logger.warning("test_logging_handler")
        time.sleep(10)
