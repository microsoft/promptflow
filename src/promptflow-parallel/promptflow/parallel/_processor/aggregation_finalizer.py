# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from typing import Any, Dict, List

from promptflow.parallel._executor.base import ParallelRunExecutor
from promptflow.parallel._metrics.metrics import Metrics
from promptflow.parallel._model import Row
from promptflow.parallel._processor.finalizer import Finalizer


class AggregationFinalizer(Finalizer):
    def __init__(self, has_aggregation_node, executor: ParallelRunExecutor):
        self._has_aggregation_node = has_aggregation_node
        self._executor = executor
        self._columned_aggregation_inputs = {}
        self._columned_inputs = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def process_enabled(self) -> bool:
        return self._has_aggregation_node

    def process(self, row: Row):
        self._row2col(self._columned_inputs, row["inputs"])
        self._row2col(self._columned_aggregation_inputs, row["aggregation_inputs"])

    @staticmethod
    def _row2col(target: Dict[str, List[Any]], row: Dict[str, Any]):
        """Convert row to column."""
        for k, v in row.items():
            target.setdefault(k, []).append(v)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._has_aggregation_node:
            self.do_aggregation()

    def do_aggregation(self):
        self._logger.info("Executing aggregation.")
        result = self._executor.execute_aggregation(
            inputs=self._columned_inputs, aggregation_inputs=self._columned_aggregation_inputs
        )

        Metrics(result.metrics).send()
