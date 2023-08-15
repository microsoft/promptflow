# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
"""service_calller.py, module for interacting with the AzureML service."""
import os
import uuid

from azure.core.exceptions import HttpResponseError, ResourceExistsError
from azure.core.pipeline.policies import RetryPolicy

from promptflow.azure._restclient.flow import AzureMachineLearningDesignerServiceClient


class FlowRequestException(Exception):
    """FlowRequestException."""

    def __init__(self, message):
        super().__init__(message)


class TelemetryMixin(object):

    def __init__(self):
        # Need to call init for potential parent, otherwise it won't be initialized.
        super().__init__()

    def _get_telemetry_values(self, *args, **kwargs):
        return {}


class RequestTelemetryMixin(TelemetryMixin):

    def __init__(self):
        super().__init__()
        self._request_id = None
        self._from_cli = False

    def _get_telemetry_values(self, *args, **kwargs):
        return {'request_id': self._request_id, 'from_cli': self._from_cli}

    def _set_from_cli_for_telemetry(self):
        self._from_cli = True

    def _refresh_request_id_for_telemetry(self):
        self._request_id = str(uuid.uuid4())


class FlowServiceCaller(RequestTelemetryMixin):
    """FlowServiceCaller.
    :param workspace: workspace
    :type workspace: Workspace
    :param base_url: base url
    :type base_url: Service URL

    """

    # The default namespace placeholder is used when namespace is None for get_module API.
    DEFAULT_COMPONENT_NAMESPACE_PLACEHOLDER = '-'
    DEFAULT_MODULE_WORKING_MECHANISM = 'OutputToDataset'
    DEFAULT_DATATYPE_MECHANISM = 'RegisterBuildinDataTypeOnly'
    MODULE_CLUSTER_ADDRESS = 'MODULE_CLUSTER_ADDRESS'
    WORKSPACE_INDEPENDENT_ENDPOINT_ADDRESS = 'WORKSPACE_INDEPENDENT_ENDPOINT_ADDRESS'
    DEFAULT_BASE_URL = 'https://{}.api.azureml.ms'
    MASTER_BASE_API = 'https://master.api.azureml-test.ms'
    DEFAULT_BASE_REGION = 'westus2'
    AML_USE_ARM_TOKEN = 'AML_USE_ARM_TOKEN'

    def __init__(self, workspace, credential, base_url=None, region=None, **kwargs):
        """Initializes DesignerServiceCaller."""
        super().__init__()

        # self._service_context = workspace.service_context
        if base_url is None:
            base_url = workspace.discovery_url.replace("discovery", "")
            # for dev test, change base url with environment variable
            base_url = os.environ.get(self.MODULE_CLUSTER_ADDRESS, default=base_url)
        # self._subscription_id = workspace.subscription_id
        # self._resource_group_name = workspace.resource_group
        # self._workspace_name = workspace.name
        # self.auth = workspace._auth_object
        self._workspace = workspace

        self._service_endpoint = base_url
        self._credential = credential
        retry_policy = RetryPolicy()
        # stop retry 500 since it will cause 409 for run creation scenario
        retry_policy._retry_on_status_codes.remove(500)
        self.caller = AzureMachineLearningDesignerServiceClient(base_url=base_url, retry_policy=retry_policy, **kwargs)

    def _get_headers(self):
        token = self._credential.get_token("https://management.azure.com/.default")
        custom_header = {
            "Authorization": "Bearer " + token.token,
            "x-ms-client-request-id": str(uuid.uuid4())
        }
        return custom_header

    def create_flow(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        experiment_id=None,  # type: Optional[str]
        body=None,  # type: Optional["_models.CreateFlowRequest"]
        **kwargs  # type: Any
    ):
        # TODO: move the wrapper to decorator
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.flows.create_flow(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                experiment_id=experiment_id,
                body=body,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def create_component_from_flow(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        body=None,  # type: Optional["_models.LoadFlowAsComponentRequest"]
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.flows.load_as_component(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                body=body,
                headers=headers,
                **kwargs
            )
        except ResourceExistsError:
            return f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}" \
                   f"/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}" \
                   f"/components/{body.component_name}/versions/{body.component_version}"
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def list_flows(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        experiment_id=None,  # type: Optional[str]
        owned_only=None,  # type: Optional[bool]
        flow_type=None,  # type: Optional[Union[str, "_models.FlowType"]]
        list_view_type=None,  # type: Optional[Union[str, "_models.ListViewType"]]
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.flows.list_flows(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                experiment_id=experiment_id,
                owned_only=owned_only,
                flow_type=flow_type,
                list_view_type=list_view_type,
                headers=headers,
                **kwargs,
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def submit_flow(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        experiment_id,  # type: str
        endpoint_name=None,  # type: Optional[str]
        body=None,  # type: Optional["_models.SubmitFlowRequest"]
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.flows.submit_flow(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                experiment_id=experiment_id,
                endpoint_name=endpoint_name,
                body=body,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def get_flow(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        flow_id,  # type: str
        experiment_id,  # type: str
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.flows.get_flow(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                experiment_id=experiment_id,
                flow_id=flow_id,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def create_connection(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        connection_name,  # type: str
        body=None,  # type: Optional["_models.CreateOrUpdateConnectionRequest"]
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.connections.create_connection(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                connection_name=connection_name,
                body=body,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def update_connection(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        connection_name,  # type: str
        body=None,  # type: Optional["_models.CreateOrUpdateConnectionRequestDto"]
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.connections.update_connection(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                connection_name=connection_name,
                body=body,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def get_connection(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        connection_name,  # type: str
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.connections.get_connection(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                connection_name=connection_name,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def delete_connection(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        connection_name,  # type: str
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.connections.delete_connection(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                connection_name=connection_name,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def list_connections(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.connections.list_connections(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def list_connection_specs(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.connections.list_connection_specs(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def list_runs(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        **kwargs  # type: Any
    ):
        """List runs in the workspace.

        :return: A list of runs in the workspace.
        :rtype: list[~azure.ml._restclient.machinelearningservices.models.Run]
        """
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.flows.list_flow_runs(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def submit_bulk_run(
            self,
            subscription_id,  # type: str
            resource_group_name,  # type: str
            workspace_name,  # type: str
            body=None,  # type: Optional["_models.SubmitBulkRunRequest"]
            **kwargs  # type: Any
    ):
        """submit_bulk_run.

        :param subscription_id: The Azure Subscription ID.
        :type subscription_id: str
        :param resource_group_name: The Name of the resource group in which the workspace is located.
        :type resource_group_name: str
        :param workspace_name: The name of the workspace.
        :type workspace_name: str
        :param body:
        :type body: ~flow.models.SubmitBulkRunRequest
        :keyword callable cls: A custom type or function that will be passed the direct response
        :return: str, or the result of cls(response)
        :rtype: str
        :raises: ~azure.core.exceptions.HttpResponseError
        """
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.bulk_runs.submit_bulk_run(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                headers=headers,
                body=body,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def get_bulk_run(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        flow_run_id,  # type: str
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.bulk_runs.get_flow_run_info(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                flow_run_id=flow_run_id,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def get_child_runs(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        flow_run_id,  # type: str
        index=None,  # type: Optional[int]
        start_index=None,  # type: Optional[int]
        end_index=None,  # type: Optional[int]
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.bulk_runs.get_flow_child_runs(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                flow_run_id=flow_run_id,
                index=index,
                start_index=start_index,
                end_index=end_index,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e

    def get_node_runs(
        self,
        subscription_id,  # type: str
        resource_group_name,  # type: str
        workspace_name,  # type: str
        flow_run_id,  # type: str
        node_name,  # type: str
        index=None,  # type: Optional[int]
        start_index=None,  # type: Optional[int]
        end_index=None,  # type: Optional[int]
        aggregation=False,  # type: Optional[bool]
        **kwargs  # type: Any
    ):
        self._refresh_request_id_for_telemetry()
        headers = self._get_headers()
        try:
            return self.caller.bulk_runs.get_flow_node_runs(
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                flow_run_id=flow_run_id,
                node_name=node_name,
                index=index,
                start_index=start_index,
                end_index=end_index,
                aggregation=aggregation,
                headers=headers,
                **kwargs
            )
        except HttpResponseError as e:
            raise FlowRequestException(f"Request id: {headers['x-ms-client-request-id']}") from e
