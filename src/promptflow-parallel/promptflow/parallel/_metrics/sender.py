# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import sys
from typing import Any, Dict


class MetricsSender:
    def __init__(self, to_parent_run=False):
        self._run_context = None
        self._to_parent_run = to_parent_run
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def run_context(self):
        if self._run_context is not None:
            return self._run_context

        from azureml.core import Run

        self._run_context = Run.get_context(allow_offline=False)
        self._logger.info(f"Run context: {self._run_context.id}")
        if self._to_parent_run:
            self._run_context = self._run_context.parent
            if not self._run_context:
                raise ValueError(f"The current run {self._run_context.id} has no parent run.")
        return self._run_context

    def send(self, metrics: Dict[str, Any]):
        try:
            self._logger.info("Start to push metrics to remote.")
            if metrics is not None:
                for k, v in metrics.items():
                    self._send_metric(k, v)
            self.run_context.flush()
            self._logger.info("End to push metrics successfully.")
        except BaseException as e:
            sys.stderr.write(f"Failed to push metrics. {e}")

    def _send_metric(self, metric_name, metric_value):
        self.run_context.log(metric_name, metric_value)
