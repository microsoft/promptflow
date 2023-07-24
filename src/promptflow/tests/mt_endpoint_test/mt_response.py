import json
import logging
import re
from pathlib import Path

from promptflow.utils.dict_utils import get_value_by_key_path
from promptflow.utils.str_utils import remove_prefix


class PromptflowResponse:
    """This class represents the response from MT endpoint when a flow run is submitted."""

    def __init__(self, dct, workspace=None, is_eval_run=False):
        self._dct = dct
        self._ws = workspace
        self._is_eval_run = is_eval_run
        self._flow_id, self._flow_run_id = self.resolve_flow_run_resource_id()

    @property
    def flow_id(self):
        return self._flow_id

    @property
    def flow_run_id(self):
        return self._flow_run_id

    @property
    def flow_name(self):
        return self._dct.get("flowName")

    @property
    def bulk_test_id(self):
        return self._dct.get("bulkTestId")

    @property
    def flow_run_logs(self):
        return self._dct.get("flowRunLogs", {})

    @property
    def flow_run_link(self):
        if not self._ws:
            raise ValueError("Cannot generate the flow run url since the workspace is unknown.")

        run_id = None
        if self.bulk_test_id:
            run_id = f"bulktest/{self.bulk_test_id}"
        elif self.flow_run_id:
            run_id = f"run/{self.flow_run_id}"

        return (
            (
                f"https://ml.azure.com/prompts/flow/5fbfda62-4e3d-43da-b908-8b8feca82b17/{self.flow_id}/"
                f"{run_id}/details?wsid={self._ws.id}&tid=72f988bf-86f1-41af-91ab-2d7cd011db47"
            )
            if run_id
            else None
        )

    @property
    def flow_run_error(self):
        return self._dct.get("error") or self._dct.get("errorResponse", {}).get("error")

    @property
    def operation_id(self):
        return get_value_by_key_path(self._dct, "correlation/operation")

    @property
    def is_run_completed(self):
        if self.flow_run_error:
            return False
        flow_runs = self._dct.get("flow_runs", [])
        node_runs = self._dct.get("node_runs", [])
        return all(flows_run["status"] == "Completed" for flows_run in flow_runs) and len(node_runs) > 0

    @property
    def eval_flow_run_id(self):
        if self._is_eval_run:
            return self.flow_run_id
        return next((run_id for run_id in self.flow_run_logs if run_id.startswith("evaluate_")), None)

    @property
    def bulk_test_run_ids(self):
        if not self.bulk_test_id:
            return []
        run_ids = [run_id for run_id in self.flow_run_logs if run_id.startswith(self.flow_run_id)]
        return sorted(run_ids)

    @property
    def node_runs(self):
        return self._dct.get("node_runs", [])

    @property
    def flow_runs(self):
        return self._dct.get("flow_runs", [])

    def resolve_flow_run_resource_id(self):
        """Get flow id and flow run id from flow run resource id."""

        flow_run_resource_id = self._dct.get("flowRunResourceId", "")
        flow_run_resource_id = remove_prefix(flow_run_resource_id, "azureml://")
        flow_run_resource_id = remove_prefix(flow_run_resource_id, "azureml:/")

        pairs = re.findall(r"([^\/]+)\/([^\/]+)", flow_run_resource_id)
        flows = [pair for pair in pairs if pair[0] == "flows"]
        flow_runs = [pair for pair in pairs if pair[0] == "flowRuns"]
        if len(flows) == 0 or len(flow_runs) == 0:
            logging.info(f"Resolve flow run resource id [{flow_run_resource_id}] failed")
            return None, None
        else:
            return flows[0][1], flow_runs[0][1]

    def dump_to_file(self, file):
        file.parent.mkdir(parents=True, exist_ok=True)
        Path(file).write_text(json.dumps(self._dct, indent=4))

    def __str__(self):
        if self.is_run_completed:
            return f"\nFlow Completed: {self.flow_name}: {self.flow_run_id}\nRun Link:{self.flow_run_link}"
        return f"\nFlow Failed: {self.operation_id} (operation id)\n{json.dumps(self.flow_run_error, indent=4)}"
