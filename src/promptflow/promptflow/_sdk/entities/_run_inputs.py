# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from os import PathLike
from typing import Union

# TODO(2528165): remove this file when we deprecate Flow.run_bulk


class BaseInputs(object):
    def __init__(self, data: Union[str, PathLike], inputs_mapping: dict = None, **kwargs):
        self.data = data
        self.inputs_mapping = inputs_mapping


class BulkInputs(BaseInputs):
    """Bulk run inputs.
    data: pointer to test data for standard runs
    inputs_mapping: define a data flow logic to map input data, support:
        from data: data.col1:
        Example:
            {"question": "${data.question}", "context": "${data.context}"}
    """

    # TODO: support inputs_mapping for bulk run
    pass


class EvalInputs(BaseInputs):
    """Evaluation flow run inputs.
    data: pointer to test data (of variant bulk runs) for eval runs
    variant:
        variant run id or variant run
        keep lineage between current run and variant runs
        variant outputs can be referenced as ${batch_run.outputs.col_name} in inputs_mapping
    baseline:
        baseline run id or baseline run
        baseline bulk run for eval runs for pairwise comparison
    inputs_mapping: define a data flow logic to map input data, support:
        from data: data.col1:
        from variant:
            [0].col1, [1].col2: if need different col from variant run data
            variant.output.col1: if all upstream runs has col1
        Example:
            {"ground_truth": "${data.answer}", "prediction": "${batch_run.outputs.answer}"}
    """

    def __init__(
        self,
        data: Union[str, PathLike],
        variant: Union[str, "BulkRun"] = None,  # noqa: F821
        baseline: Union[str, "BulkRun"] = None,  # noqa: F821
        inputs_mapping: dict = None,
        **kwargs
    ):
        super().__init__(data=data, inputs_mapping=inputs_mapping, **kwargs)
        self.variant = variant
        self.baseline = baseline
