# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
from typing import Callable


class MetricLoggerManager:
    _instance = None

    def __init__(self):
        self._metric_loggers = []

    @staticmethod
    def get_instance() -> "MetricLoggerManager":
        if MetricLoggerManager._instance is None:
            MetricLoggerManager._instance = MetricLoggerManager()
        return MetricLoggerManager._instance

    def log_metric(self, key, value, variant_id=None):
        for logger in self._metric_loggers:
            if len(inspect.signature(logger).parameters) == 2:
                logger(key, value)  # If the logger only accepts two parameters, we don't pass variant_id
            else:
                logger(key, value, variant_id)

    def add_metric_logger(self, logger_func: Callable):
        existing_logger = next((logger for logger in self._metric_loggers if logger is logger_func), None)
        if existing_logger:
            return
        if not callable(logger_func):
            return
        sign = inspect.signature(logger_func)
        # We accept two kinds of metric loggers:
        # def log_metric(k, v)
        # def log_metric(k, v, variant_id)
        if len(sign.parameters) not in [2, 3]:
            return
        self._metric_loggers.append(logger_func)

    def remove_metric_logger(self, logger_func: Callable):
        self._metric_loggers.remove(logger_func)


def log_metric(key, value, variant_id=None):
    """Log a metric for current promptflow run.

    :param key: Metric name.
    :type key: str
    :param value: Metric value.
    :type value: float
    :param variant_id: Variant id for the metric.
    :type variant_id: str
    """
    MetricLoggerManager.get_instance().log_metric(key, value, variant_id)


def add_metric_logger(logger_func: Callable):
    MetricLoggerManager.get_instance().add_metric_logger(logger_func)


def remove_metric_logger(logger_func: Callable):
    MetricLoggerManager.get_instance().remove_metric_logger(logger_func)
