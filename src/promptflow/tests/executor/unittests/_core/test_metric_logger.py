import pytest

from promptflow._core.metric_logger import MetricLoggerManager, add_metric_logger, log_metric, remove_metric_logger


@pytest.mark.unittest
class TestMetricLogger:
    def test_add_and_remove_metric_logger(self):
        # define log metric function
        metrics = {}

        def _log_metric(key, value):
            metrics[key] = value

        def _log_metric_invalid(key, value, variant_id, extra_param):
            metrics[key] = {variant_id: {value: extra_param}}

        add_metric_logger(_log_metric)
        assert MetricLoggerManager.get_instance()._metric_loggers == [_log_metric]
        add_metric_logger(_log_metric)
        assert MetricLoggerManager.get_instance()._metric_loggers == [_log_metric]
        add_metric_logger(_log_metric_invalid)
        assert MetricLoggerManager.get_instance()._metric_loggers == [_log_metric]
        add_metric_logger("test")
        assert MetricLoggerManager.get_instance()._metric_loggers == [_log_metric]
        remove_metric_logger(_log_metric)
        assert MetricLoggerManager.get_instance()._metric_loggers == []

    def test_log_metric(self):
        # define log metric function
        metrics = {}

        def _log_metric(key, value):
            metrics[key] = value

        def _log_metric_with_variant_id(key, value, variant_id):
            metrics[key] = {variant_id: value}

        add_metric_logger(_log_metric)
        log_metric("test1", 1)
        assert metrics == {"test1": 1}

        add_metric_logger(_log_metric_with_variant_id)
        log_metric("test2", 1, "line_0")
        assert metrics == {"test1": 1, "test2": {"line_0": 1}}
