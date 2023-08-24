# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import sys
from typing import Optional


class LoggerFactory:
    @staticmethod
    def get_logger(name: str, verbosity: int = logging.INFO, target_stdout: bool = False):
        logger = logging.getLogger(name)
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        if not LoggerFactory._find_handler(logger, logging.StreamHandler):
            LoggerFactory._add_handler(logger, verbosity, target_stdout)
        # TODO: Find a more elegant way to set the logging level for azure.core.pipeline.policies._universal
        azure_logger = logging.getLogger("azure.core.pipeline.policies._universal")
        azure_logger.setLevel(logging.DEBUG)
        LoggerFactory._add_handler(azure_logger, logging.DEBUG, target_stdout)
        return logger

    @staticmethod
    def _find_handler(logger: logging.Logger, handler_type: type) -> Optional[logging.Handler]:
        for log_handler in logger.handlers:
            if isinstance(log_handler, handler_type):
                return log_handler
        return None

    @staticmethod
    def _add_handler(logger: logging.Logger, verbosity: int, target_stdout: bool = False) -> None:
        # set target_stdout=True can log data into sys.stdout instead of default sys.stderr, in this way
        # logger info and python print result can be synchronized
        handler = logging.StreamHandler(stream=sys.stdout) if target_stdout else logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s][%(name)s][%(levelname)s] - %(message)s")
        handler.setFormatter(formatter)
        handler.setLevel(verbosity)
        logger.addHandler(handler)
