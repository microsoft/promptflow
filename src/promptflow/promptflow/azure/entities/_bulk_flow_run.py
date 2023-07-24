# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

import pandas as pd
from azure.ai.ml._utils.utils import dump_yaml

from promptflow.azure._restclient.flow.models import FlowRunResult
from promptflow.azure._utils._url_utils import BulkRunURL, BulkRunId
from promptflow.azure.constants import FlowType


class BulkFlowRun:
    def __init__(self, flow_id: str, bulk_test_id: str, runtime: str=None,
                 experiment_id=None, bulk_test_flow_run_ids=None, workspace_name=None,
                 resource_group_name=None, subscription_id=None, flow_type: str = None, **kwargs):
        self._flow_id = flow_id
        self._run_id = kwargs.pop("run_id", None)
        self._bulk_test_id = bulk_test_id
        # TODO: use this as default value when not specified in submit_flow_run
        self._runtime = runtime

        # init flow job operations
        from .._configuration import _CLIENT
        from ..operations._flow_job_operations import FlowJobOperations

        self._flow_job_operations = FlowJobOperations(
            operation_scope=_CLIENT._operation_scope,
            operation_config=_CLIENT._operation_config,
            all_operations=_CLIENT._operation_container,
            credential=_CLIENT._credential
        )

        self.experiment_id = experiment_id
        self.bulk_test_flow_run_ids = bulk_test_flow_run_ids
        self.workspace_name = workspace_name
        self.resource_group_name = resource_group_name
        self.subscription_id = subscription_id

        self._flow_type = flow_type
        self._studio_url = kwargs.get("studio_url", None)
        self.id = kwargs.get("id", None)

    @staticmethod
    def from_bulk_test_id(bulk_test_id: str, flow_id: str) -> "BulkFlowRun":
        from .._configuration import _CLIENT
        from ..operations._flow_job_operations import FlowJobOperations

        flow_job_operations = FlowJobOperations(
            operation_scope=_CLIENT._operation_scope,
            operation_config=_CLIENT._operation_config,
            all_operations=_CLIENT._operation_container,
            credential=_CLIENT._credential
        )
        return flow_job_operations.get_bulk_flow_run(bulk_test_id=bulk_test_id, flow_id=flow_id)

    @classmethod
    def from_url(cls, url: str) -> "BulkFlowRun":
        if url.startswith("http"):
            run_url = BulkRunURL(url)
        elif url.startswith("azureml://"):
            run_url = BulkRunId(url)
        else:
            raise ValueError("Invalid URL: {}".format(url))
        return cls(
            flow_id=run_url.flow_id,
            bulk_test_id=run_url.bulk_test_id,
            experiment_id=run_url.experiment_id,
        )

    def __getitem__(self, key: str):
        if key == "run_id":
            return self.run_id
        elif key == "metrics":
            return self.metrics
        else:
            raise AttributeError(f"Attribute {key} is not supported.")

    @property
    def runtime(self) -> str:
        return self._runtime

    @property
    def run_id(self) -> str:
        return self._run_id or self._bulk_test_id

    @property
    def metrics(self) -> typing.Dict[str, typing.Any]:
        """Evaluation flow run id -> metrics dict"""
        # TODO: hide this or cache results to avoid it calculates every time
        # query metrics from mlflow every time to keep data fresh
        return self._flow_job_operations.get_metrics(self._bulk_test_id)

    @property
    def code(self) -> str:
        # TODO: return flow id for now
        return self._flow_id

    @property
    def details(self) -> typing.Optional[pd.DataFrame]:
        # TODO: hide this or cache results to avoid it calculates every time
        # query from Flow MT every time to keep data fresh
        child_run_infos = self._flow_job_operations.get_child_run_infos(self.run_id, self._flow_id, self._flow_type)
        return self._from_child_run_infos(child_run_infos)

    def _to_dict(self) -> typing.Dict:
        # TODO: add schema for this
        run_dict = {
            "runtime": self.runtime,
            "run_id": self.run_id,
            "flow_id": self._flow_id,
            "bulk_test_id": self._bulk_test_id,
        }
        # clear empty values
        run_dict = {k: v for k, v in run_dict.items() if v}
        if self._studio_url:
            run_dict["studio_url"] = self._studio_url
        if self.id:
            run_dict["id"] = self.id
        return run_dict

    def _to_yaml(self) -> str:
        return dump_yaml(self._to_dict(), sort_keys=False)

    def __str__(self):
        try:
            return self._to_yaml()
        except BaseException:  # pylint: disable=broad-except
            return super(BulkFlowRun, self).__str__()

    def wait_for_completion(self):
        self._flow_job_operations.stream(
            bulk_test_id=self._bulk_test_id, flow_id=self._flow_id, flow_type=self._flow_type
        )

    @staticmethod
    def _from_flow_run_result(
            flow_id: str, experiment_id: str, runtime: str, result: FlowRunResult,
            workspace_name, resource_group_name, subscription_id, flow_type: str,
            arm_id: str, run_id: str = None,
            **kwargs
    ):
        bulk_test_flow_run_ids = list(result.flow_run_logs.keys() - {result.bulk_test_id})
        return BulkFlowRun(
            id=arm_id,
            flow_id=flow_id,
            run_id=run_id,
            bulk_test_id=result.bulk_test_id,
            experiment_id=experiment_id,
            bulk_test_flow_run_ids=bulk_test_flow_run_ids,
            workspace_name=workspace_name,
            resource_group_name=resource_group_name,
            subscription_id=subscription_id,
            flow_type=flow_type,
            **kwargs
        )

    def _from_child_run_infos(self, child_run_infos: typing.List[typing.Dict[str, str]]) -> typing.Optional[pd.DataFrame]:
        processed_run_infos = []
        input_keys, output_keys = set(), set()
        add_index, add_variant_id = False, False
        for original_child_run_info in child_run_infos:
            processed_run_info = {}
            # we have some operations to DataFrame that does not support duplicate column name;
            # there won't be duplicate name within inputs and output, and currently we will add
            # one or two(depends on flow type) extra columns, index and variant_id.
            # so we need to check before we add it(them).
            _inputs, _outputs = original_child_run_info["inputs"], original_child_run_info["output"]
            if _inputs is None:
                _inputs = []
            if _outputs is None:
                _outputs = []
            if "index" not in _inputs and "index" not in _outputs:
                add_index = True
                processed_run_info["index"] = original_child_run_info["index"]
            # standard flow run might need variant_id
            # bulk test toward evaluation run does not need this - inputs will contain this.
            if self._flow_type == FlowType.STANDARD:
                if "variant_id" not in _inputs and "variant_id" not in _outputs:
                    add_variant_id = True
                    processed_run_info["variant_id"] = original_child_run_info["variant_id"]
            # add inputs
            nested_inputs = original_child_run_info.pop("inputs")
            if nested_inputs is not None:
                for k, v in nested_inputs.items():
                    k = f"inputs.{k}"
                    input_keys.add(k)
                    processed_run_info[k] = v
            # add output
            nested_output = original_child_run_info.pop("output")
            if nested_output is not None:
                for k, v in nested_output.items():
                    k = f"output.{k}"
                    output_keys.add(k)
                    processed_run_info[k] = v
            processed_run_infos.append(processed_run_info)

        if len(processed_run_infos) == 0:
            return None

        # create pandas DataFrame
        df = pd.DataFrame(processed_run_infos)
        # build expected columns order for DataFrame reindex
        expected_columns = ["index"] if add_index else []
        expected_columns += list(input_keys)
        expected_columns += ["variant_id"] if add_variant_id else []
        expected_columns += list(output_keys)
        df = df.reindex(columns=expected_columns)
        # rename to remove prefix "inputs." and "output."
        rename_args = {
            old_column: old_column.replace("inputs.", "").replace("output.", "")
            for old_column in df.columns.tolist()
        }
        df = df.rename(columns=rename_args)
        # sort by index and variant_id
        df = df.sort_values(["index", "variant_id"], ascending=[True, True])
        return df

    @staticmethod
    def visualize(arm_id: str):
        from promptflow.sdk._visualize_functions import visualize_cloud_output

        visualize_cloud_output(arm_id)
