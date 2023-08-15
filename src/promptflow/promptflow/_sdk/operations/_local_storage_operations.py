# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
import json
import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, NewType, Optional, Tuple, Union

import pandas as pd
import yaml

from promptflow._sdk._constants import (
    DEFAULT_ENCODING,
    LINE_NUMBER,
    LocalStorageFilenames,
    get_run_output_path,
)
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._flow import Flow
from promptflow.exceptions import BulkRunException

RunInputs = NewType("RunInputs", Dict[str, List[Any]])
RunOutputs = NewType("RunOutputs", Dict[str, List[Any]])
RunMetrics = NewType("RunMetrics", Dict[str, Any])


class LoggerOperations:
    def __init__(self, log_path: str):
        self._log_path = Path(log_path)

    @property
    def log_path(self) -> str:
        return str(self._log_path)

    def get_logs(self) -> str:
        with open(self._log_path, "r") as f:
            return f.read()

    @contextmanager
    def setup_logger(self, stream=False):
        # avoid circular import
        from promptflow._utils.logger_utils import (
            FileHandler,
            FileHandlerConcurrentWrapper,
            bulk_logger,
            flow_logger,
            logger,
        )

        executor_loggers = [logger, flow_logger, bulk_logger]
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.touch(exist_ok=True)
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
        self._detail_path = self.path / LocalStorageFilenames.DETAIL
        self._exception_path = self.path / LocalStorageFilenames.EXCEPTION
        self.logger = LoggerOperations(log_path=self.path / LocalStorageFilenames.LOG)

    def dump_snapshot(self, flow: Flow) -> None:
        """Dump flow directory to snapshot folder, input file will be dumped after the run."""
        shutil.copytree(
            flow.code.as_posix(),
            self._snapshot_folder_path,
            # ignore .promptflow/ and .runs, otherwise will raise RecursionError
            ignore=shutil.ignore_patterns(".*"),
            dirs_exist_ok=True,
        )
        # replace DAG file with the overwrite one
        self._dag_path.unlink()
        shutil.copy(flow.path, self._dag_path)

    def load_io_spec(
        self,
    ) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
        """Load input/output spec from DAG."""
        with open(self._dag_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            flow_dag = yaml.safe_load(f)
        return flow_dag["inputs"], flow_dag["outputs"]

    def dump_inputs(self, inputs: RunInputs) -> None:
        df = pd.DataFrame(inputs)
        with open(self._inputs_path, mode="w", encoding=DEFAULT_ENCODING) as f:
            # policy: http://policheck.azurewebsites.net/Pages/TermInfo.aspx?LCID=9&TermID=203588
            df.to_json(f, "records", lines=True)

    def load_inputs(self) -> RunInputs:
        with open(self._inputs_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            df = pd.read_json(f, "records", lines=True)
            return df.to_dict("list")

    def dump_outputs(self, outputs: RunOutputs) -> None:
        df = pd.DataFrame(outputs)
        with open(self._outputs_path, mode="w", encoding=DEFAULT_ENCODING) as f:
            df.to_json(f, "records", lines=True)

    def load_outputs(self) -> RunOutputs:
        with open(self._outputs_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            df = pd.read_json(f, "records", lines=True)
            # for legacy runs, there is no line_number in output
            if LINE_NUMBER in df:
                df = df.set_index(LINE_NUMBER)
            return df.to_dict("list")

    def dump_metrics(self, metrics: Optional[RunMetrics]) -> None:
        metrics = metrics or dict()
        with open(self._metrics_path, mode="w", encoding=DEFAULT_ENCODING) as f:
            json.dump(metrics, f)

    def dump_detail(self, detail: Dict[str, Any]) -> None:
        with open(self._detail_path, mode="w", encoding=DEFAULT_ENCODING) as f:
            json.dump(detail, f)

    def dump_exception(self, exception: Exception) -> None:
        if not exception:
            return
        if not isinstance(exception, BulkRunException):
            # If other errors raised, pass it into PromptflowException
            try:
                errors = len(self.get_error_messages())
                total = len(self._get_line_runs())
            except Exception:
                errors = "unknown"
                total = "unknown"
            exception = BulkRunException(
                message=str(exception),
                error=exception,
                failed_lines=errors,
                total_lines=total,
            )
        with open(self._exception_path, mode="w", encoding=DEFAULT_ENCODING) as f:
            json.dump(exception.to_dict(include_debug_info=True), f)

    def load_exception(self) -> Dict:
        try:
            with open(self._exception_path, mode="r", encoding=DEFAULT_ENCODING) as f:
                return json.load(f)
        except Exception:
            return {}

    def load_detail(self) -> Dict[str, Any]:
        with open(self._detail_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            return json.load(f)

    def load_metrics(self) -> Dict[str, Union[int, float, str]]:
        with open(self._metrics_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            metrics = json.load(f)
        return metrics

    def get_error_messages(self) -> List[Tuple[int, dict]]:
        error_messages = []
        with open(self._detail_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            detail = json.load(f)
            for run in detail["flow_runs"]:
                if run["error"] is not None:
                    error_messages.append((run["index"], copy.deepcopy(run["error"])))
        return error_messages

    def _get_line_runs(self):
        with open(self._detail_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            detail = json.load(f)
        return detail["flow_runs"]
