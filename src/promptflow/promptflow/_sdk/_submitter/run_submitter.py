# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.

import datetime
from pathlib import Path

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import FlowRunProperties
from promptflow._sdk._utils import parse_variant
from promptflow._sdk.entities._flow import Flow
from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations
from promptflow._utils.context_utils import _change_working_dir
from promptflow.batch import BatchEngine
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import UserErrorException

from ..._utils.logger_utils import LoggerFactory
from .utils import SubmitterHelper, variant_overwrite_context

logger = LoggerFactory.get_logger(name=__name__)


class RunSubmitter:
    """Submit run to executor."""

    def __init__(self, run_operations: RunOperations):
        self.run_operations = run_operations

    def submit(self, run: Run, stream=False, **kwargs):
        self._run_bulk(run=run, stream=stream, **kwargs)
        return self.run_operations.get(name=run.name)

    def _run_bulk(self, run: Run, stream=False, **kwargs):
        # validate & resolve variant
        if run.variant:
            tuning_node, variant = parse_variant(run.variant)
        else:
            tuning_node, variant = None, None

        if run.run is not None:
            if isinstance(run.run, str):
                run.run = self.run_operations.get(name=run.run)
            elif not isinstance(run.run, Run):
                raise TypeError(f"Referenced run must be a Run instance, got {type(run.run)}")
            else:
                # get the run again to make sure it's status is latest
                run.run = self.run_operations.get(name=run.run.name)
            if run.run.status != Status.Completed.value:
                raise ValueError(f"Referenced run {run.run.name} is not completed, got status {run.run.status}")
            run.run.outputs = self.run_operations._get_outputs(run.run)
        if not run.run and not run.data:
            raise ValueError("Either run or data must be specified for flow run.")

        # running specified variant
        with variant_overwrite_context(run.flow, tuning_node, variant, connections=run.connections) as flow:
            local_storage = LocalStorageOperations(run, stream=stream, run_mode=RunMode.Batch)
            with local_storage.logger:
                self._submit_bulk_run(flow=flow, run=run, local_storage=local_storage)

    def _submit_bulk_run(self, flow: Flow, run: Run, local_storage: LocalStorageOperations) -> dict:
        run_id = run.name
        if flow.dag.get(LANGUAGE_KEY, FlowLanguage.Python) == FlowLanguage.CSharp:
            connections = []
        else:
            with _change_working_dir(flow.code):
                connections = SubmitterHelper.resolve_connections(flow=flow)
        column_mapping = run.column_mapping
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=run.environment_variables)
        SubmitterHelper.init_env(environment_variables=run.environment_variables)

        batch_engine = BatchEngine(
            flow.path,
            flow.code,
            connections=connections,
            storage=local_storage,
            log_path=local_storage.logger.file_path,
        )
        # prepare data
        input_dirs = self._resolve_input_dirs(run)
        self._validate_column_mapping(column_mapping)
        batch_result = None
        status = Status.Failed.value
        exception = None
        # create run to db when fully prepared to run in executor, otherwise won't create it
        run._dump()  # pylint: disable=protected-access
        try:
            batch_result = batch_engine.run(
                input_dirs=input_dirs,
                inputs_mapping=column_mapping,
                output_dir=local_storage.outputs_folder,
                run_id=run_id,
            )
            error_log = ""
            if batch_result.failed_lines > 0:
                # Log warning message when there are failed line run in bulk run.
                error_log = f"{batch_result.failed_lines} out of {batch_result.total_lines} runs failed in batch run."
            elif batch_result.error_summary.aggr_error_dict:
                # log warning message when there are failed aggregation nodes in bulk run.
                aggregation_nodes = list(batch_result.error_summary.aggr_error_dict.keys())
                error_log = f"aggregation nodes {aggregation_nodes} failed in batch run."
            # update error log
            if error_log and run.properties.get(FlowRunProperties.OUTPUT_PATH, None):
                error_log = (
                    error_log + f" Please check out {run.properties[FlowRunProperties.OUTPUT_PATH]} for more details."
                )
            logger.warning(error_log)
            # The bulk run is completed if the batch_engine.run successfully completed.
            status = Status.Completed.value
        except Exception as e:
            # when run failed in executor, store the exception in result and dump to file
            logger.warning(f"Run {run.name} failed when executing in executor.")
            exception = e
            # for user error, swallow stack trace and return failed run since user don't need the stack trace
            if not isinstance(e, UserErrorException):
                # for other errors, raise it to user to help debug root cause.
                raise e
            # won't raise the exception since it's already included in run object.
        finally:
            # persist snapshot and result
            # snapshot: flow directory
            local_storage.dump_snapshot(flow)
            # persist inputs, outputs and metrics
            local_storage.persist_result(batch_result)
            # exceptions
            local_storage.dump_exception(exception=exception, batch_result=batch_result)
            # system metrics: token related
            system_metrics = batch_result.system_metrics.to_dict() if batch_result else {}

            self.run_operations.update(
                name=run.name,
                status=status,
                end_time=datetime.datetime.now(),
                system_metrics=system_metrics,
            )

    def _resolve_input_dirs(self, run: Run):
        result = {"data": run.data if run.data else None}
        if run.run is not None:
            result.update(
                {
                    "run.outputs": self.run_operations._get_outputs_path(run.run),
                    # to align with cloud behavior, run.inputs should refer to original data
                    "run.inputs": self.run_operations._get_data_path(run.run),
                }
            )
        return {k: str(Path(v).resolve()) for k, v in result.items() if v is not None}

    @classmethod
    def _validate_column_mapping(cls, column_mapping: dict):
        if not column_mapping:
            return
        if not isinstance(column_mapping, dict):
            raise UserErrorException(f"Column mapping must be a dict, got {type(column_mapping)}.")
        all_static = True
        for v in column_mapping.values():
            if isinstance(v, str) and v.startswith("$"):
                all_static = False
                break
        if all_static:
            raise UserErrorException(
                "Column mapping must contain at least one mapping binding, "
                f"current column mapping contains all static values: {column_mapping}"
            )
