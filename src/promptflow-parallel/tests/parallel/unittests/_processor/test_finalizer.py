# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from unittest.mock import Mock, patch

from promptflow.parallel._metrics.metrics import Metrics
from promptflow.parallel._model import Row
from promptflow.parallel._processor.aggregation_finalizer import AggregationFinalizer
from promptflow.parallel._processor.finalizer import CompositeFinalizer


def test_composite_finalizer_enabled():
    finalizer = CompositeFinalizer([Mock(process_enabled=False), Mock(process_enabled=True)])
    assert finalizer.process_enabled


def test_composite_finalizer_process():
    disabled = Mock(process_enabled=False, process=Mock())
    enabled = Mock(process_enabled=True, process=Mock())
    finalizer = CompositeFinalizer([disabled, enabled])

    row = Mock()
    finalizer.process(row)

    assert not disabled.process.called
    assert enabled.process.called_once_with(row)


def test_aggregation_finalizer():
    rows = [Row.from_dict({"inputs": {"a": i}, "aggregation_inputs": {"b": i}}, i) for i in range(10)]

    def exec_agg(inputs: dict, aggregation_inputs: dict, **_):
        assert inputs == {"a": list(range(10))}
        assert aggregation_inputs == {"b": list(range(10))}
        return Mock()

    executor = Mock(execute_aggregation=exec_agg)
    with patch.object(Metrics, "send"), AggregationFinalizer(True, executor) as finalizer:
        for row in rows:
            finalizer.process(row)
