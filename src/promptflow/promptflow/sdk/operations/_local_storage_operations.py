# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import logging
import shutil
from contextlib import contextmanager
from typing import Any, Dict, List, NewType, Optional, Tuple

import pandas as pd
import yaml

from promptflow.sdk._constants import LocalStorageFilenames, get_run_output_path
from promptflow.sdk.entities import Run
from promptflow.sdk.entities._flow import Flow

RunInputs = NewType("RunInputs", Dict[str, List[Any]])
RunOutputs = NewType("RunOutputs", Dict[str, List[Any]])
RunMetrics = NewType("RunMetrics", Dict[str, Any])


class LocalStorageOperations:
    """LocalStorageOperations."""

    def __init__(self, run: Run):
        self._run = run
        self.path = get_run_output_path(self._run)
        if not self.path.is_dir():
            self.path.mkdir(parents=True, exist_ok=True)

        self._snapshot_folder_path = self.path / LocalStorageFilenames.SNAPSHOT_FOLDER
        self._snapshot_folder_path.mkdir(exist_ok=True)
        self._dag_path = self._snapshot_folder_path / LocalStorageFilenames.DAG
        self._inputs_path = self._snapshot_folder_path / LocalStorageFilenames.INPUTS
        self._outputs_path = self.path / LocalStorageFilenames.OUTPUTS
        self._metrics_path = self.path / LocalStorageFilenames.METRICS
        self._details_path = self.path / LocalStorageFilenames.DETAIL
        self._log_path = self.path / LocalStorageFilenames.LOG

    @property
    def log_path(self) -> str:
        return str(self._log_path)

    @contextmanager
    def setup_logger(self, stream=False):
        # avoid circular import
        from promptflow.utils.logger_utils import (
            FileHandler,
            FileHandlerConcurrentWrapper,
            bulk_logger,
            flow_logger,
            logger,
        )

        executor_loggers = [logger, flow_logger, bulk_logger]
        # set log path
        for _logger in executor_loggers:
            for handler in _logger.handlers:
                if isinstance(handler, FileHandlerConcurrentWrapper):
                    handler.handler = FileHandler(self.log_path)
                if stream is False and isinstance(handler, logging.StreamHandler):
                    handler.setLevel(logging.CRITICAL)
        try:
            yield

        finally:
            # clear log path config
            for _logger in executor_loggers:
                for handler in _logger.handlers:
                    if isinstance(handler, FileHandlerConcurrentWrapper):
                        handler.clear()
                    if stream is False and isinstance(handler, logging.StreamHandler):
                        handler.setLevel(logging.INFO)

    def dump_snapshot(self, flow: Flow) -> None:
        """Dump flow directory to snapshot folder, input file will be dumped after the run."""
        shutil.copytree(
            self._run.flow.as_posix(),
            self._snapshot_folder_path,
            # ignore .promptflow/ and .runs, otherwise will raise RecursionError
            ignore=shutil.ignore_patterns(".*"),
            dirs_exist_ok=True,
        )
        # replace DAG file with the overwrite one
        self._dag_path.unlink()
        shutil.copy(flow.path, self._dag_path)

    def load_io_spec(self) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
        """Load input/output spec from DAG."""
        with open(self._dag_path, "r") as f:
            flow_dag = yaml.safe_load(f)
        return flow_dag["inputs"], flow_dag["outputs"]

    def dump_inputs(self, inputs: RunInputs) -> None:
        df = pd.DataFrame(inputs)
        df.to_json(self._inputs_path, orient="records", lines=True)

    def dump_eval_inputs_from_legacy_executor_result(self, details: Dict[str, Any]) -> None:
        # workaround during the switch of executor
        # we need to extra record line number for eval runs
        # variant id will be set during visualization
        inputs = []
        flow_runs = details["flow_runs"]
        # start from the second run, as the first one is the root run
        for run in flow_runs[1:]:
            current_inputs = copy.deepcopy(run["inputs"])
            current_inputs["line_number"] = run["index"]
            inputs.append(copy.deepcopy(current_inputs))
        df = pd.DataFrame(inputs)
        df.to_json(self._inputs_path, orient="records", lines=True)

    def load_inputs(self) -> RunInputs:
        df = pd.read_json(self._inputs_path, orient="records", lines=True)
        return df.to_dict(orient="list")

    def dump_outputs(self, outputs: RunOutputs) -> None:
        df = pd.DataFrame(outputs)
        df.to_json(self._outputs_path, orient="records", lines=True)

    def load_outputs(self) -> RunOutputs:
        df = pd.read_json(self._outputs_path, orient="records", lines=True)
        return df.to_dict(orient="list")

    def dump_metrics(self, metrics: Optional[RunMetrics]) -> None:
        metrics = metrics or dict()
        with open(self._metrics_path, "w") as f:
            json.dump(metrics, f)

    def dump_details(self, details: Dict[str, Any]) -> None:
        with open(self._details_path, "w") as f:
            json.dump(details, f)

    def load_metrics(self) -> RunMetrics:
        with open(self._metrics_path, "r") as f:
            return json.load(f)

    def get_logs(self) -> str:
        with open(self._log_path, "r") as f:
            return f.read()

    def get_error_message(self) -> dict:
        with open(self._details_path, "r") as f:
            details = json.load(f)
            return details["flow_runs"][0]["error"]
