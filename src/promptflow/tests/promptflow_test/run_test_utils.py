import json
from enum import Enum
from typing import Dict, List

import mlflow
import pytest
from azure.core.exceptions import ResourceNotFoundError
from mt_endpoint_test.mt_client import PromptflowResponse

from promptflow.contracts.run_mode import RunMode
from promptflow.storage.azureml_run_storage import MlflowHelper
from promptflow.storage.common import reconstruct_metrics_dict
from promptflow_test.utils import assert_success, count_reduce_eval_node, get_child_runs, get_root_runs


class FlowRequestService(Enum):
    MT = 1
    RUNTIME = 2


class FlowStatus(Enum):
    Completed = 1
    Failed = 2


def assert_result_valid(
    request,
    response,
    request_service: FlowRequestService,
    mode: RunMode,
    ml_client=None,
    azure_run_storage=None,
    expected_status=FlowStatus.Completed,
):
    if request_service == FlowRequestService.MT:
        assert_mt_result_valid(request, response, mode, ml_client, azure_run_storage, expected_status)
    elif request_service == FlowRequestService.RUNTIME:
        assert_runtime_result_valid(request, response, mode, ml_client, expected_status)
    else:
        raise Exception(f"FlowRequestService={request_service} not supported yet")


def assert_mt_result_valid(
    request, response: PromptflowResponse, mode: RunMode, ml_client, azure_run_storage, expected_status
):
    """
    Top level run valiation method for mt endpoint call
    """
    # Validate response key field
    if response.is_run_completed:
        assert expected_status == FlowStatus.Completed
        assert response.flow_run_error is None
    else:
        assert expected_status == FlowStatus.Failed
        assert response.flow_run_error is not None
        assert response.flow_run_error.get("code")
        assert response.flow_run_error.get("message")
        # Enable below util MT integrated
        # assert response.flow_run_error.get("referenceCode")

        # validate run numbers
    if mode == RunMode.Flow:
        flow_runs = response.flow_runs
        root_runs = get_root_runs(flow_runs)
        for root_run in root_runs:
            child_runs = get_child_runs(flow_runs, root_run["run_id"])
            print(f"Enter into regular flow run validation with flow_run_id={root_run.get('run_id')}")
            validate_single_flow_run_info(ml_client, root_run, child_runs)

        if response.is_run_completed:
            validate_runs_number(request, response.flow_runs, response.node_runs)
    elif mode == RunMode.BulkTest:
        flow_runs = response.flow_runs
        root_runs = get_root_runs(flow_runs)
        for root_run in root_runs:
            child_runs = get_child_runs(flow_runs, root_run["run_id"])
            print(f"Enter into bulk run validation with flow_run_id={root_run.get('run_id')}")
            validate_single_bulk_run_info(ml_client, root_run, child_runs)

        if response.is_run_completed:
            validate_runs_number(request, response.flow_runs, response.node_runs)

        has_eval = is_bulk_run_with_eval(request)

        if has_eval:
            print("Check eval flow part - mt")
            assert azure_run_storage is not None
            assert response.eval_flow_run_id is not None and len(response.eval_flow_run_id) > 0

            all_flow_runs = azure_run_storage.get_run_info_by_partition_key(
                partition_key=response.flow_id, is_node_run=False
            )
            eval_flow_runs = [run for run in all_flow_runs if run.get("run_id").startswith("evaluate_")]
            eval_node_runs = azure_run_storage.get_run_info_by_partition_key(
                partition_key=response.eval_flow_run_id, is_node_run=True
            )
            num_of_reduce_node = count_reduce_eval_node(request, mode)

            eval_root_runs = get_root_runs(eval_flow_runs)
            for eval_root_run in eval_root_runs:
                eval_child_runs = get_child_runs(eval_flow_runs, eval_root_run["run_id"])
                print(f"Enter into eval run of bulk test validation with flow_run_id={eval_root_run.get('run_id')}")
                validate_single_bulk_run_info(ml_client, eval_root_run, eval_child_runs, num_of_reduce_node)

            if response.is_run_completed:
                validate_runs_number_from_bulk_eval_flow(request, eval_flow_runs, eval_node_runs, mode)
    elif mode == RunMode.Eval:
        flow_runs = response.flow_runs
        root_runs = get_root_runs(flow_runs)
        for root_run in root_runs:
            child_runs = get_child_runs(flow_runs, root_run["run_id"])
            print(f"Enter into eval flow run validation with flow_run_id={root_run.get('run_id')}")
            validate_single_bulk_run_info(ml_client, root_run, child_runs)

        if response.is_run_completed:
            validate_runs_number_from_eval_flow(request, response.flow_runs, response.node_runs, mode)


def assert_runtime_result_valid(request, result, mode: RunMode, ml_client, expected_status):
    """
    Top level run valiation method for runtime endpoint call
    """
    # Step 1: Validate run status
    if expected_status == FlowStatus.Completed:
        assert_success(result)

    # Step 2: Validate runs number & run info
    validate_run_info(ml_client, result.get("flow_runs"), mode, num_of_reduce_node=0)
    if result.get("status") == "Completed" and mode != RunMode.Eval:
        validate_runs_number(request, result.get("flow_runs"), result.get("node_runs"))

    # Step 3: Validate runs number & run info from eval flow, if any
    has_eval = is_bulk_run_with_eval(request) or mode == RunMode.Eval
    if has_eval:
        print("Check eval flow part - runtime")
        assert result.get("evaluation") is not None

        num_of_reduce_node = count_reduce_eval_node(request, mode)
        validate_run_info(ml_client, result["evaluation"].get("flow_runs"), mode, num_of_reduce_node)
        if result.get("status") == "Completed":
            validate_runs_number_from_bulk_eval_flow(
                request, result["evaluation"].get("flow_runs"), result["evaluation"].get("node_runs"), mode
            )


def validate_runs_number(request, flow_runs: List, node_runs: List):
    assert "flow" in request and "nodes" in request["flow"]
    assert isinstance(request["flow"]["nodes"], List)
    num_of_bulk_run_nodes = len(request["flow"]["nodes"])
    batch_size = 1
    if "batch_inputs" in request:
        assert isinstance(request["batch_inputs"], List)
        batch_size = len(request["batch_inputs"])
    num_of_variants = 1
    if "variants" in request:
        assert isinstance(request["variants"], Dict)
        num_of_variants += len(request["variants"])

    # Check bulk run "node_runs" number
    assert isinstance(node_runs, List)
    expected_node_run_num = num_of_bulk_run_nodes * num_of_variants * batch_size

    assert len(node_runs) == expected_node_run_num, (
        f"Bulk run 'node_runs' number={len(node_runs)} not match expected={expected_node_run_num} with "
        f"num_of_bulk_run_nodes= {num_of_bulk_run_nodes}, "
        f"num_of_variants={num_of_variants}, batch_size={batch_size}"
    )

    # Check bulk run "flow_runs" number
    assert isinstance(flow_runs, List)
    expected_flow_run_num = (batch_size + 1) * num_of_variants
    assert len(flow_runs) == (batch_size + 1) * num_of_variants, (
        f"Bulk run 'flow_runs' number ={len(flow_runs)} not match expected={expected_flow_run_num} "
        f"with batch_size={batch_size}, "
        f"num_of_variants={num_of_variants}"
    )


def validate_run_info(ml_client, flow_runs: List, mode: RunMode, num_of_reduce_node: int = 0):
    root_runs = get_root_runs(flow_runs)
    for root_run in root_runs:
        child_runs = get_child_runs(flow_runs, root_run["run_id"])
        if mode == RunMode.Flow:
            print(f"Enter into regular flow run validation with flow_run_id={root_run.get('run_id')}")
            validate_single_flow_run_info(ml_client, root_run, child_runs)
        elif mode == RunMode.BulkTest or mode == RunMode.Eval:
            print(f"Enter into bulk run validation with flow_run_id={root_run.get('run_id')}")
            validate_single_bulk_run_info(ml_client, root_run, child_runs, num_of_reduce_node)
        else:
            raise Exception(f"RunMode={mode} is not supported yet")


def validate_runs_number_from_bulk_eval_flow(request, flow_runs, node_runs, mode: RunMode):
    # Check eval flow run number
    if "eval_flow" in request and request["eval_flow"] is not None:
        batch_size = 1
        if "batch_inputs" in request:
            assert isinstance(request["batch_inputs"], List)
            batch_size = len(request["batch_inputs"])

        num_of_variants = 1
        if "variants" in request:
            assert isinstance(request["variants"], Dict)
            num_of_variants += len(request["variants"])

        num_of_reduce_node = count_reduce_eval_node(request, mode)

        assert "nodes" in request["eval_flow"]
        assert isinstance(request["eval_flow"]["nodes"], List)
        num_of_eval_flow_nodes = len(request["eval_flow"]["nodes"])

        # Eval Flow use 'line_number'/'variant_id'/'variant_ids' to divide input data into different batch
        # We need to decide its cut criteria to decide the batch_size_for_eval_flow
        assert "eval_flow" in request and "inputs" in request["eval_flow"]
        use_line_number = "line_number" in request["eval_flow"]["inputs"]
        use_variant_ids = "variant_ids" in request["eval_flow"]["inputs"]
        use_variant_id = "variant_id" in request["eval_flow"]["inputs"]

        # We could not use both input as the same time
        assert sum([use_variant_ids, use_variant_id]) <= 1

        eval_batch_size = 1
        if use_line_number:
            eval_batch_size *= batch_size
        if use_variant_id:
            eval_batch_size *= num_of_variants

        # Check eval run "node_runs" number
        assert isinstance(node_runs, List)
        expected_eval_node_run_num = (
            num_of_eval_flow_nodes - num_of_reduce_node
        ) * eval_batch_size + num_of_reduce_node

        assert len(node_runs) == expected_eval_node_run_num, (
            f"eval flow 'node_runs' number = {len(node_runs)} "
            f"not match expected={expected_eval_node_run_num} with num_of_eval_flow_nodes={num_of_eval_flow_nodes},"
            f" eval_batch_size={eval_batch_size}, "
            f"num_of_reduce_node={num_of_reduce_node}"
        )

        # Check eval run "flow_runs" number
        assert isinstance(flow_runs, List)
        expected_eval_flow_run_num = eval_batch_size + 1

        assert len(flow_runs) == expected_eval_flow_run_num, (
            f"eval flow 'flow_runs' number {len(flow_runs)} "
            f"not match expected={expected_eval_flow_run_num} with eval_batch_size={eval_batch_size}"
        )


def validate_runs_number_from_eval_flow(request, flow_runs, node_runs, mode: RunMode):
    # Check eval flow run number
    assert request.get("flow") is not None
    batch_size = 1

    assert request.get("bulk_test_inputs")
    batch_size = 1
    if isinstance(request["bulk_test_inputs"], List):
        batch_size = len(request["bulk_test_inputs"])

    num_of_variants = 1
    if "variants" in request:
        assert isinstance(request["variants"], Dict)
        num_of_variants += len(request["variants"])

    num_of_reduce_node = count_reduce_eval_node(request, mode)

    assert "nodes" in request["flow"]
    assert isinstance(request["flow"]["nodes"], List)
    num_of_eval_flow_nodes = len(request["flow"]["nodes"])

    # Eval Flow use 'line_number'/'variant_id'/'variant_ids' to divide input data into different batch
    # We need to decide its cut criteria to decide the batch_size_for_eval_flow
    assert "flow" in request and "inputs" in request["flow"]
    use_line_number = "line_number" in request["flow"]["inputs"]
    use_variant_ids = "variant_ids" in request["flow"]["inputs"]
    use_variant_id = "variant_id" in request["flow"]["inputs"]

    # We could not use both input as the same time
    assert sum([use_variant_ids, use_variant_id]) <= 1

    eval_batch_size = 1
    if use_line_number:
        eval_batch_size *= batch_size
    if use_variant_id:
        eval_batch_size *= num_of_variants

    # Check eval run "node_runs" number
    assert isinstance(node_runs, List)
    expected_eval_node_run_num = (num_of_eval_flow_nodes - num_of_reduce_node) * eval_batch_size + num_of_reduce_node

    assert len(node_runs) == expected_eval_node_run_num, (
        f"eval flow 'node_runs' number = {len(node_runs)} "
        f"not match expected={expected_eval_node_run_num} with num_of_eval_flow_nodes={num_of_eval_flow_nodes},"
        f" eval_batch_size={eval_batch_size}, "
        f"num_of_reduce_node={num_of_reduce_node}"
    )

    # Check eval run "flow_runs" number
    assert isinstance(flow_runs, List)
    expected_eval_flow_run_num = eval_batch_size + 1

    assert len(flow_runs) == expected_eval_flow_run_num, (
        f"eval flow 'flow_runs' number {len(flow_runs)} "
        f"not match expected={expected_eval_flow_run_num} with eval_batch_size={eval_batch_size}"
    )


def validate_single_flow_run_info(ml_client, root_run: Dict, child_runs: List[Dict]):
    # -----CheckPoint-0: input validation-----
    assert ml_client is not None

    # -----CheckPoint-1: Assert regular flow run does not have RH record-----
    with pytest.raises(ResourceNotFoundError):
        ml_client.jobs._runs_operations.get_run(run_id=root_run["run_id"])

    # -----CheckPoint-2: check the status vs error field at root run-----
    if root_run["status"] == "Completed":
        assert root_run.get("error") is None
    else:
        assert root_run.get("error") is not None
        assert root_run["error"].get("code")
        assert root_run["error"].get("message")
        # Enable below util MT integrated
        # assert root_run["error"].get("referenceCode")

    # -----CheckPoint-3: check the status vs error field at child run-----
    for child_run in child_runs:
        assert root_run["status"] == child_run["status"]
        if child_run["status"] == "Completed":
            assert child_run.get("error") is None
        else:
            assert child_run.get("error")
            assert child_run["error"].get("code")
            assert child_run["error"].get("message")
            # Enable below util MT integrated
            # assert child_run["error"].get("referenceCode")


def validate_single_bulk_run_info(ml_client, root_run: Dict, child_runs: List[Dict], num_of_reduce_node: int = 0):
    # Method to ensure the run stats are consistently between root_run, child_runs, run_dto

    # -----CheckPoint-0: input validation-----
    assert ml_client is not None

    # -----CheckPoint-1: run_dto only exist for root runs, not for child_runs-----
    assert "run_id" in root_run
    run_dto = ml_client.jobs._runs_operations.get_run(run_id=root_run["run_id"])
    assert run_dto is not None
    # [Skip this part]: check no run dto for child runs

    # ------CheckPoint-2: status + error message check------
    # Currently, we set root_run always 'completed" even if child run failure
    assert root_run["status"] == run_dto.status
    assert "error" in root_run
    if root_run["error"] is not None:
        assert root_run["error"].get("code") == run_dto.error.error.code
        assert root_run["error"].get("message") == run_dto.error.error.message
        assert root_run["error"].get("referenceCode") == run_dto.error.error.referenceCode

    # Check root run details
    assert root_run["status"] == "Completed"
    # Check child run details
    for child_run in child_runs:
        if "Completed" == child_run["status"]:
            assert "error" in child_run and child_run["error"] is None
        else:
            assert child_run["error"]["code"]
            assert child_run["error"]["message"]
            # Enable below util MT integrated
            # assert child_run["error"]["referenceCode"]
        assert root_run["run_id"] == child_run["parent_run_id"]
        assert root_run["variant_id"] == child_run["variant_id"]
        assert root_run["flow_id"] == child_run["flow_id"]

    # ------CheckPoint-3: Check Properties------
    assert hasattr(run_dto, "properties")
    # Check Property "azureml.promptflow.total_tokens"
    assert MlflowHelper.RUN_HISTORY_TOTAL_TOKENS_PROPERTY_NAME in run_dto.properties
    total_tokens_from_run_dto = int(run_dto.properties[MlflowHelper.RUN_HISTORY_TOTAL_TOKENS_PROPERTY_NAME])
    assert "system_metrics" in root_run and "total_tokens" in root_run["system_metrics"]
    total_tokens_from_root_run = root_run["system_metrics"]["total_tokens"]
    total_tokens_from_child_runs = 0
    for child_run in child_runs:
        if "system_metrics" in child_run and "total_tokens" in child_run["system_metrics"]:
            total_tokens_from_child_runs += child_run["system_metrics"]["total_tokens"]
    assert total_tokens_from_run_dto == total_tokens_from_root_run
    assert total_tokens_from_root_run == total_tokens_from_child_runs

    # ------CheckPoint-4: Check Metrics------
    # Step-1: Check bulk run metrics
    # Step-2: Check eval flow metrics: only enable metrics for reduce node
    if num_of_reduce_node > 0:
        run_dto_with_metrics = mlflow.get_run(root_run["run_id"])
        assert run_dto_with_metrics.data.metrics is not None
        assert "metrics" in root_run
        expected_metrics = reconstruct_metrics_dict(root_run["metrics"])
        remove_inner_metrics(run_dto_with_metrics.data.metrics)
        print(f"metrics: {json.dumps(run_dto_with_metrics.data.metrics)}")
        assert expected_metrics == run_dto_with_metrics.data.metrics


# This validation shall be replaced  Task 2486209: Enrich the metrics validation part
def remove_inner_metrics(metrics: dict):
    for key in list(metrics.keys()):
        if key.endswith(".completed") or key.endswith(".failed") or key.endswith(".is_completed"):
            del metrics[key]


def is_bulk_run_with_eval(request) -> bool:
    return (
        request.get("eval_flow") is not None
        and isinstance(request["eval_flow"], Dict)
        and len(request["eval_flow"]) > 0
    )
