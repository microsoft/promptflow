import json
import logging
import os
import uuid
from datetime import datetime
from functools import cached_property
from pathlib import Path

import mlflow
import requests
from azure.ai.ml import MLClient
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import Data

import promptflow.azure as pf
from promptflow.azure._load_functions import load_flow
from promptflow.azure.entities._flow import Flow
from promptflow.azure.operations import FlowOperations
from promptflow.contracts.run_mode import RunMode
from promptflow_test.utils import load_content, load_csv, load_json

from .mt_response import PromptflowResponse

TEST_ROOT = Path(__file__).parent.parent / "test_configs"

E2E_SAMPLES_PATH = TEST_ROOT / "e2e_samples"

E2E_FLOW_GRAPH_PATH = E2E_SAMPLES_PATH / "flow_submission" / "flow_graph"
E2E_DATA_PATH = E2E_SAMPLES_PATH / "flow_submission" / "data"
E2E_TOOL_CODE_PATH = E2E_SAMPLES_PATH / "tool_code"


class PromptflowClient:
    """A client class that can send requests to MT endpoint to create and submit flows."""

    def __init__(self, deployment, ml_client: MLClient):
        self._ml_client = ml_client
        self._ws = self._ml_client.workspaces.get()
        mlflow.set_tracking_uri(self._ws.mlflow_tracking_uri)

        self._runtime = deployment.get("runtime_name", None)
        if not self._runtime:
            raise ValueError("Missing runtime_name in model file config, please add it and test again.")

    @cached_property
    def api_host(self):
        resp = requests.get(self._ws.discovery_url, headers=self.headers)
        return resp.json().get("api")

    @cached_property
    def base_url(self):
        return f"{self.api_host}/flow/api{self._ws.id}"

    @cached_property
    def headers(self):
        token = self._ml_client._credential.get_token("https://management.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}"}

    # region helper methods
    def post(self, relative_path, payload, headers=None, params={}):
        url = f"{self.base_url}/{relative_path}"
        query_param = {"experimentId": "5fbfda62-4e3d-43da-b908-8b8feca82b17"}
        query_param.update(params)
        merged_headers = self.headers.copy()
        if headers is not None:
            merged_headers.update(headers)
        if merged_headers.get("Content-Type") == "text/plain":
            return requests.post(url, data=payload, headers=merged_headers, params=query_param)
        else:
            return requests.post(url, json=payload, headers=merged_headers, params=query_param)

    def upload_flow_to_file_share(self, flow_path):
        pf.configure(client=self._ml_client)
        flow = load_flow(source=flow_path)
        flow_operations = FlowOperations(
            operation_scope=self._ml_client._operation_scope,
            operation_config=self._ml_client._operation_config,
            all_operations=self._ml_client._operation_container,
            credential=self._ml_client._credential,
        )
        flow_operations._resolve_arm_id_or_upload_dependencies(flow)
        if not flow.path:
            raise ValueError("Failed to upload flow to file share.Please check the local flow path.")
        logging.info(f"Uploaded flow to fileshare: {flow.path}")
        return flow

    def create_and_get_data_uri(self, flow_folder_path, file_name):
        file_path = flow_folder_path / file_name
        data = Data(
            path=file_path,
            type=AssetTypes.URI_FILE,
            description="For mt endpoint testing",
            name=f"mt_endpoint_test_{os.path.splitext(file_name)[0]}",
        )
        data_asset = self._ml_client.data.create_or_update(data)
        return data_asset.path

    # endregion

    # region submit flow by json
    def submit_flow_by_json(self, file, bulk_run_response=None):
        flow_graph = {}
        flow_info = {}
        use_case = json.loads(Path(file).read_text())

        # load flow graph and create flow
        graph_file = use_case.get("flow_graph", "")
        if graph_file:
            flow_graph = load_json(E2E_FLOW_GRAPH_PATH / graph_file)
            flow_info = self.create_or_update_flow_from_json(flow_graph, Path(graph_file).stem)

        # load eval flow graph if it is defined
        eval_flow = use_case.get("evaluation_flows", "")
        if eval_flow:
            is_reference_flow = eval_flow.get("is_reference_flow", True)
            if not is_reference_flow:
                eval_flow_graph_file = eval_flow.get("evaluation", "")
                eval_flow["evaluation"] = load_json(E2E_FLOW_GRAPH_PATH / eval_flow_graph_file)
                del eval_flow["is_reference_flow"]
            flow_graph["evaluationFlows"] = eval_flow

        # check if input data is defined
        input_data_file = use_case.get("flow_run_inputs", "")
        input_data = None
        if input_data_file:
            input_data = load_csv(E2E_DATA_PATH / input_data_file)

        # put some info from bulk run response into flow run settings
        is_eval_run = False
        flow_run_settings = use_case.get("flow_run_settings", {})
        if bulk_run_response:
            is_eval_run = True
            flow_run_settings["bulkTestId"] = bulk_run_response.bulk_test_id
            flow_run_settings["bulkTestFlowRunIds"] = bulk_run_response.bulk_test_run_ids

        # submit flow
        flow_id = flow_info.get("flowId") if flow_info else bulk_run_response.flow_id
        submit_flow_resp = self.submit_flow_from_json(flow_id, flow_graph, flow_run_settings, input_data)
        return PromptflowResponse(submit_flow_resp, self._ws, is_eval_run=is_eval_run)

    def create_or_update_flow_from_json(self, flow, flow_name):
        payload = {
            "flowName": flow_name,
            "flow": flow,
        }
        resp = self.post("flows", payload)
        return resp.json()

    def submit_flow_from_json(self, flow_id, flow, flow_run_settings, flow_run_inputs=None):
        payload = {
            "flowId": flow_id,
            "flowRunId": f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "flow": flow,
            "flowSubmitRunSettings": flow_run_settings,
            "useWorkspaceConnection": True,
        }

        # overwrite runtime name as client target runtime
        payload["flowSubmitRunSettings"]["runtimeName"] = self._runtime

        # overwrite batch_inputs if exists
        if flow_run_inputs:
            payload["flowSubmitRunSettings"]["batch_inputs"] = flow_run_inputs
            payload["flowSubmitRunSettings"].pop("batchDataInput", None)

        resp = self.post("flows/submit", payload)
        return resp.json()

    # endregion

    # region submit flow by yaml
    def submit_flow_by_yaml(self, file):
        use_case = json.loads(Path(file).read_text())

        # upload flow to fileshare
        flow_folder_name = use_case.get("flow_directory")
        flow_folder = Path(E2E_SAMPLES_PATH) / flow_folder_name
        flow = self.upload_flow_to_file_share(flow_folder)
        flow_run_settings = use_case.get("flow_run_settings", None)

        # create flow using fileshare
        create_flow_resp = self.create_or_update_flow_from_fileshare(flow, flow_folder_name, flow_run_settings)
        flow_id = create_flow_resp.get("flowId")

        # check if input data is defined
        input_data_file = use_case.get("flow_run_inputs", "")
        flow_run_settings = self.resolve_flow_run_inputs(flow_run_settings, flow_folder, input_data_file)

        # submit flow
        submit_flow_resp = self.submit_flow_from_fileshare(flow_id, flow_run_settings)
        return PromptflowResponse(submit_flow_resp, self._ws)

    def create_or_update_flow_from_fileshare(self, flow: Flow, flow_name, flow_run_settings):
        payload = {
            "flowName": flow_name,
            "flowRunSettings": flow_run_settings,
            "flowDefinitionFilePath": flow.path,
            "isArchived": False,
        }
        resp = self.post("flows", payload)
        return resp.json()

    def submit_flow_from_fileshare(self, flow_id, flow_run_settings):
        payload = {
            "flowId": flow_id,
            "flowRunId": str(uuid.uuid4()),
            "flowSubmitRunSettings": flow_run_settings,
            "useWorkspaceConnection": True,
            "useFlowSnapshotToSubmit": True,
        }

        # overwrite runtime name as client target runtime
        payload["flowSubmitRunSettings"]["runtimeName"] = self._runtime

        resp = self.post("flows/submit", payload)
        return resp.json()

    def resolve_flow_run_inputs(self, flow_run_settings, flow_folder, inputs_file):
        input_path = Path(flow_folder / inputs_file)
        if not input_path.exists():
            return flow_run_settings

        run_mode = RunMode.parse(flow_run_settings.get("runMode", "Flow"))
        if run_mode == RunMode.Flow:
            extension = os.path.splitext(inputs_file)[1]
            if extension == ".csv":
                input_data = load_csv(input_path)
            elif extension == ".json":
                input_data = load_json(input_path)
            else:
                raise ValueError(f"Unsupported inputs file extension: {extension}")
            if isinstance(input_data, dict):
                input_data = [input_data]
            flow_run_settings["batch_inputs"] = input_data
            flow_run_settings.pop("batchDataInput", None)
        elif run_mode == RunMode.BulkTest:
            flow_run_settings["batchDataInput"] = {"dataUri": self.create_and_get_data_uri(flow_folder, inputs_file)}
            flow_run_settings.pop("batch_inputs", None)
        return flow_run_settings

    # endregion

    # region submit tool meta
    def submit_tool_meta_from_file(self, file):
        use_case = json.loads(Path(file).read_text())

        # load tool code
        code_file = use_case.get("tool_code_file", "")
        if code_file:
            code_content = load_content(E2E_TOOL_CODE_PATH / code_file)

        # submit meta
        tool_type = use_case.get("tool_type", "")
        tool_name = use_case.get("tool_name", "")
        tool_code = use_case.get("tool_code", "") if code_file == "" else code_content

        resp = self.submit_tool_meta_request(tool_type, tool_name, tool_code)
        return resp

    def submit_tool_meta_request(self, tool_type, tool_name, payload):
        headers = {"Content-Type": "text/plain"}
        params = {"toolType": tool_type, "toolName": tool_name, "flowRuntimeName": self._runtime}
        resp = self.post("Tools/meta", payload, headers, params)
        return resp

    # endregion

    # region deprecated
    def create_and_submit_flow(self, flow_dict, is_bulktest=False):
        """Given a sample file with flow definition and input data, create and submit a flow to MT endpoint."""

        flow = flow_dict.get("flow")
        create_flow_resp = self.create_or_update_flow(flow)
        flow_id = create_flow_resp.get("flowId")
        submit_flow_resp = self.submit_flow(flow_id, flow, flow_dict, is_bulktest)
        return PromptflowResponse(submit_flow_resp, self._ws)

    def create_or_update_flow(self, flow):
        payload = {
            "flowName": flow["name"],
            "flow": {
                "flowGraph": flow,
            },
        }
        resp = self.post("flows", payload)
        return resp.json()

    def submit_flow(self, flow_id, flow, flow_dic, is_bulktest):
        batch_inputs = flow_dic.get("batch_inputs")
        variants = flow_dic.get("variants", None)
        variants_tools = flow_dic.get("variants_tools", None)
        baseline_variant_id = flow_dic.get("baseline_variant_id", None)
        run_mode = "BulkTest" if is_bulktest else "Flow"

        payload = {
            "flowId": flow_id,
            "flowRunId": f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "flow": {
                "flowGraph": flow,
            },
            "flowSubmitRunSettings": {
                "runMode": run_mode,
                "runtimeName": self._runtime,
                "BaselineVariantId": baseline_variant_id,
                "batch_inputs": batch_inputs,
                "variants": variants,
                "variantsTools": variants_tools,
            },
            "useWorkspaceConnection": True,
        }

        # Add evaluation flow if exists
        eval_flow = flow_dic.get("eval_flow", None)
        if eval_flow:
            eval_flow_name = eval_flow.get("name", "evaluation")
            inputs_mapping = flow_dic.get("eval_flow_inputs_mapping")
            payload["flow"]["evaluationFlows"] = {
                eval_flow_name: {
                    "FlowGraph": eval_flow,
                }
            }
            payload["flowSubmitRunSettings"]["evaluationFlowRunSettings"] = {
                eval_flow_name: {
                    "inputsMapping": inputs_mapping,
                }
            }

        resp = self.post("flows/submit", payload)
        return resp.json()

    # endregion
