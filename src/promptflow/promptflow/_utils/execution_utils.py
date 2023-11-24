# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import AbstractSet, Any, Dict, List, Mapping

from promptflow._utils.logger_utils import logger
from promptflow.contracts.flow import Flow, FlowInputDefinition, InputValueType
from promptflow.contracts.run_info import FlowRunInfo, Status


def apply_default_value_for_input(inputs: Dict[str, FlowInputDefinition], line_inputs: Mapping) -> Dict[str, Any]:
    updated_inputs = dict(line_inputs or {})
    for key, value in inputs.items():
        if key not in updated_inputs and (value and value.default is not None):
            updated_inputs[key] = value.default
    return updated_inputs


def handle_line_failures(run_infos: List[FlowRunInfo], raise_on_line_failure: bool = False):
    """Handle line failures in batch run"""
    failed = [i for i, r in enumerate(run_infos) if r.status == Status.Failed]
    failed_msg = None
    if len(failed) > 0:
        failed_indexes = ",".join([str(i) for i in failed])
        first_fail_exception = run_infos[failed[0]].error["message"]
        if raise_on_line_failure:
            failed_msg = "Flow run failed due to the error: " + first_fail_exception
            raise Exception(failed_msg)

        failed_msg = (
            f"{len(failed)}/{len(run_infos)} flow run failed, indexes: [{failed_indexes}],"
            f" exception of index {failed[0]}: {first_fail_exception}"
        )
        logger.error(failed_msg)


def get_aggregation_inputs_properties(flow: Flow) -> AbstractSet[str]:
    """Return the serialized InputAssignment of the aggregation nodes inputs.

    For example, an aggregation node refers the outputs of a node named "grade",
    then this function will return set("${grade.output}").
    """
    normal_node_names = {node.name for node in flow.nodes if flow.is_normal_node(node.name)}
    properties = set()
    for node in flow.nodes:
        if node.name in normal_node_names:
            continue
        for value in node.inputs.values():
            if not value.value_type == InputValueType.NODE_REFERENCE:
                continue
            if value.value in normal_node_names:
                properties.add(value.serialize())
    return properties


def collect_lines(indexes: List[int], kvs: Mapping[str, List]) -> Mapping[str, List]:
    """Collect the values from the kvs according to the indexes."""
    return {k: [v[i] for i in indexes] for k, v in kvs.items()}
