# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import time
from promptflow import PFClient


class FlowRunWrapper(object):
    def __init__(self, flow_run, prefix=None, **kwargs):
        self.flow_run = flow_run
        self.column_mapping = flow_run.column_mapping
        self.prefix = prefix if prefix is not None else ""
        self.client = PFClient()

    def get_result_df(self, all_results=True, exclude_inputs=False):
        self._wait_for_completion()
        result_df = self.client.get_details(self.flow_run.name, all_results=all_results)
        if exclude_inputs:
            result_df = result_df.drop(
                columns=[col for col in result_df.columns if col.startswith("inputs.")]
            )
        result_df.rename(columns={col: col.replace("outputs", self.prefix) for col in [col for col in result_df.columns if col.startswith("outputs.")]}, inplace=True)
        return result_df

    def _wait_for_completion(self):
        from promptflow._sdk._constants import RunStatus
        while True:
            if self.run.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED]:
                break
            time.sleep(2)
