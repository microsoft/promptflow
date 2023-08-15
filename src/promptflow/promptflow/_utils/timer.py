# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from time import perf_counter


class Timer:
    def __init__(self, logger: logging.Logger, funcDescription: str):
        self.logger = logger
        self.funcDescription = funcDescription
        self.start = None
        self.end = None

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, *args):
        self.end = perf_counter()
        self.logger.info(
            f"{self.funcDescription} finished in {self.end - self.start} seconds"
        )
