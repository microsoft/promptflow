# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import List, Dict

from promptflow.azure._configuration import _get_flow_job_operations
from promptflow.azure.constants import FlowType
from promptflow.azure.entities import BulkFlowRun


class BulkFlowRunInput:
    """Bulk flow run input.
    data: pointer to test data (of variant bulk runs) for eval runs (optional), pointer to test data for standard runs (mandatory)
    variants:
        list of bulk runs of variants (optional for standard runs)
        keep lineage between current run and variant runs
        variant outputs can be referenced as variants.output.col_name in inputs_mapping
    inputs_mapping: define a data flow logic to map input data, support:
        from data: data.col1:
        from variants:
            [0].col1, [1].col2: if need different col from variant runs data
            variants.output.col1: if all upstream runs has col1
        Example:
            {ground_truth: "data.answer", context: "variants.output.context", answer: "variants.output.answer"}
    """

    def __init__(
            self,
            data,
            variants: List[BulkFlowRun],
            inputs_mapping: Dict[str, str],
            **kwargs,
    ):
        self.data = data
        if len(variants) > 1:
            raise ValueError("Only one variant is supported for flow evaluation currently.")
        bulk_flow_run = variants[0]
        self.flow_id = bulk_flow_run._flow_id
        self.bulk_test_id = bulk_flow_run._bulk_test_id
        self.experiment_id = bulk_flow_run.experiment_id
        self.bulk_test_flow_run_ids = self._get_bulk_test_flow_run_ids(bulk_flow_run)
        if not inputs_mapping:
            inputs_mapping = {}
        self.inputs_mapping = {k: v.replace("variants.output.", "output.") for k, v in inputs_mapping.items()}

    @classmethod
    def _get_bulk_test_flow_run_ids(cls, bulk_flow_run: BulkFlowRun) -> List[str]:
        """Get bulk test flow run ids from bulk flow run."""
        if bulk_flow_run.bulk_test_flow_run_ids:
            return bulk_flow_run.bulk_test_flow_run_ids
        # get from remote
        flow_job_ops = _get_flow_job_operations()
        run_ids = flow_job_ops.get_child_run_ids(
            run_id=bulk_flow_run._bulk_test_id,
            flow_type=FlowType.STANDARD
        )
        return run_ids
