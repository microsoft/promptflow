# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.

import datetime
from pathlib import Path
from typing import Union

from promptflow._constants import SystemMetricKeys
from promptflow._proxy import ProxyFactory
from promptflow._sdk._constants import REMOTE_URI_PREFIX, ContextAttributeKey, FlowRunProperties
from promptflow._sdk.entities._flows import Flow, Prompty
from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.flow_utils import parse_variant
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.batch import BatchEngine
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import UserErrorException, ValidationException
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._start_trace import is_collection_writeable, start_trace

from .._load_functions import load_flow
from ..entities._flows import FlexFlow
from .utils import SubmitterHelper, variant_overwrite_context

logger = LoggerFactory.get_logger(name=__name__)


class RunSubmitter:
    """Submit run to executor."""

    def __init__(self, client):
        self._client = client
        self._config = self._client._config
        self.run_operations = self._client.runs

    def submit(self, run: Run, stream=False, **kwargs):
        self._run_bulk(run=run, stream=stream, **kwargs)
        return self.run_operations.get(name=run.name)

    def resume(self, resume_from: str, **kwargs):
        resume_from_run = self._ensure_run_completed(resume_from)
        run = resume_from_run._copy(resume_from=resume_from_run.name, **kwargs)
        self._run_bulk(run=run, **kwargs)
        return self.run_operations.get(name=run.name)

    def _ensure_run_completed(self, required_run: Union[str, Run]):
        """Ensure the required run is completed and return the run object."""
        if isinstance(required_run, str):
            required_run = self.run_operations.get(name=required_run)
        elif not isinstance(required_run, Run):
            error = TypeError(f"Referenced run must be a Run instance, got {type(required_run)}")
            raise UserErrorException(message=str(error), error=error)
        else:
            # get the run again to make sure it's status is latest
            required_run = self.run_operations.get(name=required_run.name)
        if required_run.status != Status.Completed.value:
            error = ValueError(f"Referenced run {required_run.name} is not completed, got status {required_run.status}")
            raise UserErrorException(message=str(error), error=error)
        required_run.outputs = self.run_operations._get_outputs(required_run)
        return required_run

    def _run_bulk(self, run: Run, stream=False, **kwargs):
        attributes: dict = kwargs.get("attributes", {})
        # validate & resolve variant
        if run.variant:
            tuning_node, variant = parse_variant(run.variant)
        else:
            tuning_node, variant = None, None

        # always remove reference.batch_run_id from operation context to avoid mis-inheritance
        operation_context = OperationContext.get_instance()
        operation_context._remove_otel_attributes(ContextAttributeKey.REFERENCED_BATCH_RUN_ID)
        if run.run is not None:
            # Set for flow test against run and no experiment scenario
            if ContextAttributeKey.REFERENCED_BATCH_RUN_ID not in attributes:
                referenced_batch_run_id = run.run.name if isinstance(run.run, Run) else run.run
                attributes[ContextAttributeKey.REFERENCED_BATCH_RUN_ID] = referenced_batch_run_id
            run.run = self._ensure_run_completed(run.run)
        if run._resume_from is not None:
            logger.debug(f"Resume from run {run._resume_from!r}...")
            run._resume_from = self._ensure_run_completed(run._resume_from)
        print("@@@", run)
        print("@@@", run.init)
        # start trace
        logger.debug("start trace for flow run...")
        flow_path = run._get_flow_dir().resolve()
        logger.debug("flow path for run.start_trace: %s", flow_path)
        if is_collection_writeable():
            logger.debug("trace collection is writeable, will use flow name as collection...")
            collection_for_run = run._flow_name
            logger.debug("collection for run: %s", collection_for_run)
            # pass with internal parameter `_collection`
            start_trace(
                attributes=attributes,
                run=run,
                _collection=collection_for_run,
                path=flow_path,
            )
        else:
            logger.debug("trace collection is protected, will honor existing collection.")
            start_trace(attributes=attributes, run=run, path=flow_path)

        self._validate_inputs(run=run)

        local_storage = LocalStorageOperations(run, stream=stream, run_mode=RunMode.Batch)
        with local_storage.logger:
            flow_obj = load_flow(source=run.flow)
            with variant_overwrite_context(flow_obj, tuning_node, variant, connections=run.connections) as flow:
                self._submit_bulk_run(flow=flow, run=run, local_storage=local_storage)

    @classmethod
    def _validate_inputs(cls, run: Run):
        if not run.run and not run.data and not run._resume_from:
            error = ValidationException("Either run or data or resume from run must be specified for flow run.")
            raise UserErrorException(message=str(error), error=error)

    def _submit_bulk_run(
        self, flow: Union[Flow, FlexFlow, Prompty], run: Run, local_storage: LocalStorageOperations
    ) -> dict:
        logger.info(f"Submitting run {run.name}, log path: {local_storage.logger.file_path}")
        run_id = run.name
        # TODO: unify the logic for prompty and other flows
        if not isinstance(flow, Prompty):
            # variants are resolved in the context, so we can't move this logic to Operations for now
            ProxyFactory().create_inspector_proxy(flow.language).prepare_metadata(
                flow_file=Path(flow.path), working_dir=Path(flow.code), init_kwargs=run.init
            )

        with _change_working_dir(flow.code):
            # resolve connections with environment variables overrides to avoid getting unused connections
            logger.debug(
                f"Resolving connections for flow {flow.path} with environment variables {run.environment_variables}."
            )
            connections = SubmitterHelper.resolve_connections(
                flow=flow, environment_variables_overrides=run.environment_variables
            )
        column_mapping = run.column_mapping
        # resolve environment variables
        run.environment_variables = SubmitterHelper.load_and_resolve_environment_variables(
            flow=flow, environment_variable_overrides=run.environment_variables
        )
        SubmitterHelper.init_env(environment_variables=run.environment_variables)

        # prepare data
        input_dirs = self._resolve_input_dirs(run)
        self._validate_column_mapping(column_mapping)
        batch_result = None
        status = Status.Failed.value
        exception = None
        # create run to db when fully prepared to run in executor, otherwise won't create it
        run._status = Status.Running.value
        run._start_time = datetime.datetime.now()
        run._dump()  # pylint: disable=protected-access

        resume_from_run_storage = (
            LocalStorageOperations(run._resume_from, run_mode=RunMode.Batch) if run._resume_from else None
        )
        try:
            batch_engine = BatchEngine(
                run._dynamic_callable or flow.path,
                flow.code,
                connections=connections,
                entry=flow.entry if isinstance(flow, FlexFlow) else None,
                storage=local_storage,
                log_path=local_storage.logger.file_path,
                init_kwargs=run.init,
            )
            batch_result = batch_engine.run(
                input_dirs=input_dirs,
                inputs_mapping=column_mapping,
                output_dir=local_storage.outputs_folder,
                run_id=run_id,
                resume_from_run_storage=resume_from_run_storage,
                resume_from_run_output_dir=resume_from_run_storage.outputs_folder if resume_from_run_storage else None,
            )
            error_logs = []
            if batch_result.failed_lines > 0:
                # Log warning message when there are failed line run in bulk run.
                error_logs.append(
                    f"{batch_result.failed_lines} out of {batch_result.total_lines} runs failed in batch run."
                )
            if batch_result.error_summary.aggr_error_dict:
                # log warning message when there are failed aggregation nodes in bulk run.
                aggregation_nodes = list(batch_result.error_summary.aggr_error_dict.keys())
                error_logs.append(f"aggregation nodes {aggregation_nodes} failed in batch run.")
            # update error log
            if error_logs and run.properties.get(FlowRunProperties.OUTPUT_PATH, None):
                error_logs.append(
                    f" Please check out {run.properties[FlowRunProperties.OUTPUT_PATH]} for more details."
                )
            if error_logs:
                logger.warning("\n".join(error_logs))
            # The bulk run is completed if the batch_engine.run successfully completed.
            status = Status.Completed.value
        except Exception as e:
            # when run failed in executor, store the exception in result and dump to file
            logger.warning(f"Run {run.name} failed when executing in executor with exception {e}.")
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
            # system metrics
            system_metrics = {}
            if batch_result:
                system_metrics.update(batch_result.system_metrics.to_dict())  # token related
                system_metrics.update(
                    {f"{SystemMetricKeys.NODE_PREFIX}.{k}": v for k, v in batch_result.node_status.items()}
                )
                system_metrics.update(
                    {
                        SystemMetricKeys.LINES_COMPLETED: batch_result.completed_lines,
                        SystemMetricKeys.LINES_FAILED: batch_result.failed_lines,
                    }
                )

            run = self.run_operations.update(
                name=run.name,
                status=status,
                end_time=datetime.datetime.now(),
                system_metrics=system_metrics,
            )

            # upload run to cloud if the trace destination is set to cloud
            trace_destination = self._config.get_trace_destination(path=run._get_flow_dir().resolve())
            if trace_destination and trace_destination.startswith(REMOTE_URI_PREFIX):
                logger.debug(f"Trace destination set to {trace_destination!r}, uploading run to cloud...")
                self._upload_run_to_cloud(run=run)

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
            raise ValidationException(f"Column mapping must be a dict, got {type(column_mapping)}.")
        all_static = True
        for v in column_mapping.values():
            if isinstance(v, str) and v.startswith("$"):
                all_static = False
                break
        if all_static:
            raise ValidationException(
                "Column mapping must contain at least one mapping binding, "
                f"current column mapping contains all static values: {column_mapping}"
            )

    @classmethod
    def _upload_run_to_cloud(cls, run: Run):
        error_msg_prefix = f"Failed to upload run {run.name!r} to cloud."
        try:
            from promptflow._sdk._tracing import _get_ws_triad_from_pf_config
            from promptflow.azure._cli._utils import _get_azure_pf_client

            ws_triad = _get_ws_triad_from_pf_config(path=run._get_flow_dir().resolve(), config=run._config)
            pf = _get_azure_pf_client(
                subscription_id=ws_triad.subscription_id,
                resource_group=ws_triad.resource_group_name,
                workspace_name=ws_triad.workspace_name,
            )
            pf.runs._upload(run=run)
        except ImportError as e:
            error_message = (
                f'{error_msg_prefix}. "promptflow[azure]" is required for local to cloud tracing experience, '
                f'please install it by running "pip install promptflow[azure]". Original error: {str(e)}'
            )
            raise UserErrorException(message=error_message) from e
