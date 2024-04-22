# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import AbstractSet, Any, Dict, List, Mapping

from promptflow._utils.logger_utils import logger
from promptflow.contracts.flow import Flow, FlowInputDefinition, InputAssignment, InputValueType
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.executor import _input_assignment_parser
from promptflow.tracing._operation_context import OperationContext


def apply_default_value_for_input(inputs: Dict[str, FlowInputDefinition], line_inputs: Mapping) -> Dict[str, Any]:
    updated_inputs = dict(line_inputs or {})
    for key, value in inputs.items():
        if key not in updated_inputs and (value and value.default is not None):
            updated_inputs[key] = value.default
    return updated_inputs


def handle_line_failures(run_infos: List[FlowRunInfo], raise_on_line_failure: bool = False):
    """Handle line failures in batch run"""
    failed_run_infos = [r for r in run_infos if r.status == Status.Failed]
    failed_msg = None
    if len(failed_run_infos) > 0:
        failed_indexes = ",".join([str(r.index) for r in failed_run_infos])
        first_fail_exception = failed_run_infos[0].error["message"]
        if raise_on_line_failure:
            failed_msg = "Flow run failed due to the error: " + first_fail_exception
            raise Exception(failed_msg)

        failed_msg = (
            f"{len(failed_run_infos)}/{len(run_infos)} flow run failed, indexes: [{failed_indexes}],"
            f" exception of index {failed_run_infos[0].index}: {first_fail_exception}"
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


def extract_aggregation_inputs(flow: Flow, nodes_outputs: dict) -> Dict[str, Any]:
    """Extract the aggregation inputs of a flow from the nodes outputs."""
    _aggregation_inputs_references = get_aggregation_inputs_properties(flow)
    return {prop: _parse_aggregation_input(nodes_outputs, prop) for prop in _aggregation_inputs_references}


def _parse_aggregation_input(nodes_outputs: dict, aggregation_input_property: str):
    """Parse the value of the aggregation input from the nodes outputs."""
    assign = InputAssignment.deserialize(aggregation_input_property)
    return _input_assignment_parser.parse_value(assign, nodes_outputs, {})


def set_batch_input_source_from_inputs_mapping(inputs_mapping):
    """Infer the batch input source from the input mapping and set it in the OperationContext instance.

    This method analyzes the `inputs_mapping` to ascertain the origin of the inputs for a batch operation.
    The `inputs_mapping` should be a dictionary with keys representing input names and values specifying the sources
    of these inputs. Inputs can originate from direct data or from the outputs of a previous run.

    The `inputs_mapping` is dictated entirely by the external caller. For more details on column mapping, refer to
    https://aka.ms/pf/column-mapping. The mapping can include references to both the inputs and outputs of previous
    runs, using a reserved source name 'run' to indicate such references. However, this method specifically checks
    for references to outputs of previous runs, which are denoted by values starting with "${run.outputs". When such
    a reference is found, the `batch_input_source` attribute of the OperationContext instance is set to "Run" to
    reflect that the batch operation is utilizing outputs from a prior run.

    If no values in the `inputs_mapping` start with "${run.outputs", it is inferred that the inputs do not derive
    from a previous run, and the `batch_input_source` is set to "Data".

    Examples of `inputs_mapping`:
        - Referencing a previous run's output:
            {'input1': '${run.outputs.some_output}', 'input2': 'direct_data'}
          In this case, 'input1' is sourced from a prior run's output, and 'input2' is from direct data.
          The `batch_input_source` would be set to "Run".

        - Sourcing directly from data:
            {'input1': 'data_source1', 'input2': 'data_source2'}
          Since no values start with "${run.outputs", the `batch_input_source` is set to "Data".

    Args:
        inputs_mapping (Mapping[str, str]): A dictionary mapping input names to their sources, where the sources
        can be either direct data or outputs from a previous run. The structure and content of this mapping are
        entirely under the control of the external caller.

    Returns:
        None
    """

    if inputs_mapping and any(
        isinstance(value, str) and value.startswith("${run.outputs") for value in inputs_mapping.values()
    ):
        batch_input_source = "Run"
    else:
        batch_input_source = "Data"
    OperationContext.get_instance()["batch_input_source"] = batch_input_source
