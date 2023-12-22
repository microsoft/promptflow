# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.

import datetime
import shutil
from pathlib import Path

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import FlowRunProperties, JobType
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
from ..._utils.utils import dump_list_to_jsonl
from ..entities._orchestration import Orchestration
from .utils import SubmitterHelper, variant_overwrite_context

logger = LoggerFactory.get_logger(name=__name__)


class RunSubmitter:
    """Submit run to executor."""

    def __init__(self, run_operations: RunOperations):
        self.run_operations = run_operations

    def submit(self, run: Run, stream=False, **kwargs):
        if isinstance(run.flow, Orchestration):
            self._run_orchestration(run, orchestration=run.flow)
            return self.run_operations.get(name=run.name)
        self._run_bulk(run=run, stream=stream, **kwargs)
        return self.run_operations.get(name=run.name)

    def _resolve_job_inputs(self, flow_job_results, job, base_path):
        # TODO: Fill the default value to column mapping
        job_inputs = []
        results_lines = []
        for job_name, result_list in flow_job_results.items():  # {data: [{url:xx}], main: [{answer:xx}]}
            for i, result in enumerate(result_list):
                if len(results_lines) <= i:
                    results_lines.append({})
                for key, value in flow_job_results.items():
                    results_lines[i][key] = value[i]  # [{data: {url}, main: {answer}}], []
        column_mapping = job.column_mapping if job.type == JobType.FLOW else job.inputs
        for i, results_line in enumerate(results_lines):
            inputs_line = SubmitterHelper.resolve_single_job_inputs(results_line, column_mapping)
            job_inputs.append(inputs_line)
        target = Path(base_path) / ".temp" / "data"
        target.mkdir(exist_ok=True, parents=True)
        target = target / f"{job.name}_input_data.jsonl"
        dump_list_to_jsonl(target, job_inputs)
        return target

    def _run_orchestration(self, run, orchestration: Orchestration):
        # Make data as the first job inputs
        run.flow = SubmitterHelper.build_flow_for_orchestration(orchestration)
        flow_inputs = run.data
        # TODO: Refine data handling logic
        flow_job_results = {"data": SubmitterHelper.load_jsonl(flow_inputs)}
        child_runs = {}
        # TODO: Change this to a real orchestrator with multi-process
        for job in orchestration.jobs:
            flow = None
            job_inputs = self._resolve_job_inputs(flow_job_results, job, orchestration._base_path)
            if job.type == JobType.FLOW:
                flow = Path(job.flow)
                child_run = Run(
                    # Fix this name?
                    # name=job.name,
                    display_name=job.display_name,
                    tags=job.tags,
                    data=job_inputs,
                    # Colum mapping can't be used here.
                    # column_mapping=job.column_mapping,
                    variant=job.variant,
                    flow=flow,
                    connections=job.connections,
                    environment_variables=job.environment_variables,
                    config=run._config,
                )
            elif job.type == JobType.AGGREGATION:
                flow = SubmitterHelper.extend_aggregation_job_to_flow(job=job, base_path=orchestration._base_path)
                child_run = Run(
                    # Fix this name?
                    # name=job.name,
                    display_name=job.display_name,
                    # tags=job.tags,
                    data=job_inputs,
                    # Colum mapping can't be used here.
                    # column_mapping=job.column_mapping,
                    # variant=job.variant,
                    flow=flow,
                    environment_variables=job.environment_variables,
                )
            child_run = self.run_operations.create_or_update(run=child_run)
            if child_run.status != Status.Completed.value:
                raise ValueError(
                    f"Referenced run {child_run.name} is not completed, got status {child_run.status}, please check"
                    f" {child_run._output_path} for details."
                )
            child_runs.update({job.name: child_run})
            flow_job_results.update({job.name: SubmitterHelper.load_jsonl(child_run._output_path / "outputs.jsonl")})
        # create run to db when fully prepared to run in executor, otherwise won't create it
        run._dump()  # pylint: disable=protected-access
        # Update status to completed
        self.run_operations.update(
            name=run.name,
            status=Status.Completed.value,
            end_time=datetime.datetime.now(),
            # TODO: Finalize the things needs to be pop up to parent run, use last child run for now
            # system_metrics=child_run.properties.get("system_metrics"),
        )
        self._post_process_orchestration(run, child_runs)
        return self.run_operations.get(name=run.name)

    def _post_process_orchestration(self, run, child_runs):
        # TODO: Remove this. Copy metrics to parent run for now.
        base_output_path = Path(run.properties.get("output_path"))
        flow_output_path = base_output_path / "flow_outputs"
        flow_output_path.mkdir(exist_ok=True, parents=True)
        # Copy the last run's metrics
        target = Path(list(child_runs.values())[-1]._output_path)
        logger.debug(f"Copying metrics from {target} metrics to {flow_output_path}")
        shutil.copy2(target / "metrics.json", base_output_path / "metrics.json")
        # Copy the main run's output
        target = Path(child_runs["main"]._output_path)
        logger.debug(f"Copying outputs from {target} metrics to {flow_output_path}")
        shutil.copy2(target / "flow_outputs" / "output.jsonl", flow_output_path / "output.jsonl")
        shutil.copy2(target / "outputs.jsonl", base_output_path / "outputs.jsonl")
        # Copy flow runs
        shutil.copytree(target / "flow_artifacts", base_output_path / "flow_artifacts")
        # Copy snapshot
        shutil.copytree(run.flow, base_output_path / "snapshot")

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

            if batch_result.failed_lines > 0:
                # Log warning message when there are failed line run in bulk run.
                error_log = f"{batch_result.failed_lines} out of {batch_result.total_lines} runs failed in batch run."
                if run.properties.get(FlowRunProperties.OUTPUT_PATH, None):
                    error_log = (
                        error_log
                        + f" Please check out {run.properties[FlowRunProperties.OUTPUT_PATH]} for more details."
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
