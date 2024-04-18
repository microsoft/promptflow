# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Iterable

from promptflow.executor._result import LineResult
from promptflow.integrations.parallel_run._config.model import ParallelRunConfig
from promptflow.integrations.parallel_run._executor.bulk_executor import BulkRunExecutor
from promptflow.integrations.parallel_run._model import DebugInfo, Result
from promptflow.integrations.parallel_run._processor.base import AbstractParallelRunProcessor


class BulkRunProcessor(AbstractParallelRunProcessor):
    def _build_results(self, line_results: Iterable[LineResult]) -> Iterable[Result]:
        debug_infos = []

        for line_result in line_results:
            if self._executor.is_debug_enabled:
                debug_infos.append(
                    DebugInfo(
                        run_info=line_result.run_info,
                    )
                )

    def _create_executor(self, config: ParallelRunConfig):
        return BulkRunExecutor(self._working_dir, config)
