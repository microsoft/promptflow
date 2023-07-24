import json

from promptflow._constants import PromptflowEdition
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow.core import RunTracker
from promptflow.exceptions import ErrorResponse
from promptflow.runtime.runtime_config import RuntimeConfig
from promptflow.utils._runtime_contract_util import normalize_dict_keys_camel_to_snake

from . import logger
from ._utils import get_storage_from_config


def mark_runs_as_failed_in_runhistory(
    config: RuntimeConfig, flow_request: SubmitFlowRequest, payload: dict, ex: Exception
):
    if not flow_request:
        payload = normalize_dict_keys_camel_to_snake(payload)
    run_mode = flow_request.run_mode if flow_request else RunMode(payload.get("run_mode", 0))
    if (run_mode in (RunMode.BulkTest, RunMode.Eval)) and config.storage.storage_account:
        from promptflow.storage.azureml_run_storage import MlflowHelper

        mlflow_tracking_uri = config.set_mlflow_tracking_uri()
        mlflow_helper = MlflowHelper(mlflow_tracking_uri=mlflow_tracking_uri)
        _, root_run_ids, bulk_test_id = get_run_ids(flow_request, payload)

        for run_id in root_run_ids:
            try:
                logger.info(f"Start to update run {run_id} status to Failed.")
                mlflow_helper.start_run(run_id)
                mlflow_run = mlflow_helper.get_run(run_id=run_id)
                error_response = ErrorResponse.from_exception(ex).to_dict()
                mlflow_helper.write_error_message(mlflow_run=mlflow_run, error_response=error_response)
                mlflow_helper.end_run(run_id, Status.Failed.value)
                logger.info(f"End to update run {run_id} status to Failed.")
            except Exception as exception:
                logger.warning(
                    "Hit exception when update run %s status to Failed in run history, exception: %s",
                    run_id,
                    exception,
                )

        # TODO: revisit this logic when have a final decision about bulk test run
        if run_mode == RunMode.BulkTest and bulk_test_id:
            logger.info(f"Start to update bulk_test_run {bulk_test_id} status to Completed in run history.")
            mlflow_helper.start_run(bulk_test_id)
            mlflow_helper.end_run(bulk_test_id, Status.Completed.value)
            logger.info(f"End to update bulk_test_run {bulk_test_id} status to Completed in run history.")


def mark_runs_as_failed_in_storage_and_runhistory(
    config: RuntimeConfig, flow_request: SubmitFlowRequest, payload: dict, ex: Exception
):
    storage = get_storage_from_config(config)
    run_tracker = RunTracker(storage)
    if not flow_request:
        payload = normalize_dict_keys_camel_to_snake(payload)
    run_tracker._run_mode = flow_request.run_mode if flow_request else RunMode(payload.get("run_mode", 0))

    flow_id, root_run_ids, bulk_test_id = get_run_ids(flow_request, payload)
    run_tracker.mark_notstarted_runs_as_failed(flow_id, root_run_ids, ex)

    # TODO: revisit this logic when have a final decision about bulk test run
    if run_tracker._run_mode == RunMode.BulkTest and storage._edition == PromptflowEdition.ENTERPRISE:
        run_tracker.end_bulk_test_aml_run(bulk_test_id)


def get_run_ids(flow_request: SubmitFlowRequest, payload: dict):
    flow_id = None
    root_run_ids = None
    bulk_test_id = None
    if flow_request:
        logger.info("Flow request is None.")
        flow_id = flow_request.flow_id
        root_run_ids = flow_request.get_root_run_ids()
        if flow_request.run_mode == RunMode.BulkTest:
            bulk_test_id = flow_request.submission_data.bulk_test_id
    else:
        # Try to get all the run ids directly from payload
        flow_id = payload.get("flow_id", "")
        flow_run_id = payload.get("flow_run_id", "")
        root_run_ids = [flow_run_id]
        run_mode = RunMode(payload.get("run_mode", 0))
        if run_mode == RunMode.Flow or run_mode == RunMode.BulkTest:
            submission_data = payload.get("submission_data", {})
            if isinstance(submission_data, str):
                # submission data is a json string
                submission_data = json.loads(submission_data)

            if isinstance(submission_data, dict):
                variants_runs = submission_data.get("variants_runs", {})
                if variants_runs:
                    root_run_ids += list(variants_runs.values())

                eval_flow_run_id = submission_data.get("eval_flow_run_id", None)
                if eval_flow_run_id:
                    root_run_ids.append(eval_flow_run_id)

                bulk_test_id = submission_data.get("bulk_test_id", None)

    return flow_id, root_run_ids, bulk_test_id
