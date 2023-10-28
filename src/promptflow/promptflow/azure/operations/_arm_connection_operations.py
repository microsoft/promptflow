# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from enum import Enum
from typing import Any, Dict, Union

import requests
from azure.ai.ml._restclient.v2023_06_01_preview.models import WorkspaceConnectionPropertiesV2BasicResource
from azure.ai.ml._scope_dependent_operations import (
    OperationConfig,
    OperationsContainer,
    OperationScope,
    _ScopeDependentOperations,
)

from promptflow._sdk.entities._connection import CustomConnection, _Connection
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException

GET_CONNECTION_URL = (
    "/subscriptions/{sub}/resourcegroups/{rg}/providers/Microsoft.MachineLearningServices"
    "/workspaces/{ws}/connections/{name}/listsecrets?api-version=2023-04-01-preview"
)
LIST_CONNECTION_URL = (
    "/subscriptions/{sub}/resourcegroups/{rg}/providers/Microsoft.MachineLearningServices"
    "/workspaces/{ws}/connections?api-version=2023-04-01-preview"
)
FLOW_META_PREFIX = "azureml.flow."


class ConnectionCategory(str, Enum):
    AzureOpenAI = "AzureOpenAI"
    CognitiveSearch = "CognitiveSearch"
    CognitiveService = "CognitiveService"
    CustomKeys = "CustomKeys"


class ArmConnectionOperations(_ScopeDependentOperations):
    """ArmConnectionOperations.

    Get connections from arm api. You should not instantiate this class directly. Instead, you should
    create an PFClient instance that instantiates it for you and
    attaches it as an attribute.
    """

    def __init__(
        self,
        operation_scope: OperationScope,
        operation_config: OperationConfig,
        all_operations: OperationsContainer,
        credential,
        service_caller: FlowServiceCaller,
        **kwargs: Dict,
    ):
        super(ArmConnectionOperations, self).__init__(operation_scope, operation_config)
        self._all_operations = all_operations
        self._service_caller = service_caller
        self._credential = credential

    def get(self, name, **kwargs):
        connection_dict = self.build_connection_dict(name)
        return _Connection._from_execution_connection_dict(name=name, data=connection_dict)

    @classmethod
    def open_url(cls, token, url, action, host="management.azure.com", method="GET", model=None) -> Union[Any, dict]:
        """
        :type token: str
        :type url: str
        :type action: str, for the error message format.
        :type host: str
        :type method: str
        :type model: Type[msrest.serialization.Model]
        """
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.request(method, f"https://{host}{url}", headers=headers)
        message_format = (
            f"Open url {{url}} failed with status code: {response.status_code}, action: {action}, reason: {{reason}}"
        )
        if response.status_code == 403:
            raise AccessDeniedError(operation=url, target=ErrorTarget.RUNTIME)
        elif 400 <= response.status_code < 500:
            raise OpenURLFailedUserError(
                message_format=message_format,
                url=url,
                reason=response.reason,
            )
        elif response.status_code != 200:
            raise OpenURLFailed(
                message_format=message_format,
                url=url,
                reason=response.reason,
            )
        data = response.json()
        if model:
            return model.deserialize(data)
        return data

    @classmethod
    def validate_and_fallback_connection_type(cls, name, type_name, category):
        if type_name:
            return type_name
        if category == ConnectionCategory.AzureOpenAI:
            return "AzureOpenAI"
        if category == ConnectionCategory.CognitiveSearch:
            return "CognitiveSearch"
        raise UnknownConnectionType(
            message_format="Connection {name} is not recognized in PromptFlow, "
            "please make sure the connection is created in PromptFlow.",
            category=category,
            name=name,
        )

    @classmethod
    def build_connection_dict_from_rest_object(cls, name, obj) -> dict:
        """
        :type name: str
        :type obj: promptflow.runtime.models.WorkspaceConnectionPropertiesV2BasicResource
        """
        # Reference 1: https://msdata.visualstudio.com/Vienna/_git/vienna?path=/src/azureml-api/src/AccountRP/Contracts/WorkspaceConnection/WorkspaceConnectionDtoV2.cs&_a=blame&version=GBmaster  # noqa: E501
        # Reference 2: https://msdata.visualstudio.com/Vienna/_git/vienna?path=%2Fsrc%2Fazureml-api%2Fsrc%2FDesigner%2Fsrc%2FMiddleTier%2FMiddleTier%2FServices%2FPromptFlow%2FConnectionsManagement.cs&version=GBmaster&_a=contents  # noqa: E501
        # This connection type covers the generic ApiKey auth connection categories, for examples:
        # AzureOpenAI:
        #     Category:= AzureOpenAI
        #     AuthType:= ApiKey (as type discriminator)
        #     Credentials:= {ApiKey} as <see cref="ApiKey"/>
        #     Target:= {ApiBase}
        #
        # CognitiveService:
        #     Category:= CognitiveService
        #     AuthType:= ApiKey (as type discriminator)
        #     Credentials:= {SubscriptionKey} as <see cref="ApiKey"/>
        #     Target:= ServiceRegion={serviceRegion}
        #
        # CognitiveSearch:
        #     Category:= CognitiveSearch
        #     AuthType:= ApiKey (as type discriminator)
        #     Credentials:= {Key} as <see cref="ApiKey"/>
        #     Target:= {Endpoint}
        #
        # Use Metadata property bag for ApiType, ApiVersion, Kind and other metadata fields
        properties = obj.properties
        type_name = properties.metadata.get(f"{FLOW_META_PREFIX}connection_type")
        type_name = cls.validate_and_fallback_connection_type(name, type_name, properties.category)
        module = properties.metadata.get(f"{FLOW_META_PREFIX}module", "promptflow.connections")
        # Note: Category is connectionType in MT, but type name should be class name, which is flowValueType in MT.
        # Handle old connections here, see details: https://github.com/Azure/promptflow/tree/main/connections
        type_name = f"{type_name}Connection" if not type_name.endswith("Connection") else type_name
        meta = {"type": type_name, "module": module}

        def get_case_insensitive_key(d, key):
            for k, v in d.items():
                if k.lower() == key.lower():
                    return v
            return None

        if properties.category == ConnectionCategory.AzureOpenAI:
            value = {
                "api_key": properties.credentials.key,
                "api_base": properties.target,
                "api_type": get_case_insensitive_key(properties.metadata, "ApiType"),
                "api_version": get_case_insensitive_key(properties.metadata, "ApiVersion"),
            }
        elif properties.category == ConnectionCategory.CognitiveSearch:
            value = {
                "api_key": properties.credentials.key,
                "api_base": properties.target,
                "api_version": get_case_insensitive_key(properties.metadata, "ApiVersion"),
            }
        elif properties.category == ConnectionCategory.CognitiveService:
            value = {
                "api_key": properties.credentials.key,
                "endpoint": properties.target,
                "api_version": get_case_insensitive_key(properties.metadata, "ApiVersion"),
            }
        elif properties.category == ConnectionCategory.CustomKeys:
            # Merge secrets from credentials.keys and other string fields from metadata
            value = {
                **properties.credentials.keys,
                **{k: v for k, v in properties.metadata.items() if not k.startswith(FLOW_META_PREFIX)},
            }
            if type_name == CustomConnection.__name__:
                meta["secret_keys"] = list(properties.credentials.keys.keys())
        else:
            raise UnknownConnectionType(
                message_format=(
                    "Unknown connection {name} category {category}, "
                    "please upgrade your promptflow sdk version and retry."
                ),
                category=properties.category,
                name=name,
            )
        # Note: Filter empty values out to ensure default values can be picked when init class object.
        return {**meta, "value": {k: v for k, v in value.items() if v}}

    def build_connection_dict(self, name) -> dict:
        """
        :type name: str
        """
        url = GET_CONNECTION_URL.format(
            sub=self._operation_scope.subscription_id,
            rg=self._operation_scope.resource_group_name,
            ws=self._operation_scope.workspace_name,
            name=name,
        )
        try:
            rest_obj: WorkspaceConnectionPropertiesV2BasicResource = self.open_url(
                self._credential.get_token("https://management.azure.com/.default").token,
                url=url,
                action="listsecrets",
                method="POST",
                model=WorkspaceConnectionPropertiesV2BasicResource,
            )
        except AccessDeniedError:
            auth_error_message = (
                "Access denied to list workspace secret due to invalid authentication. "
                "Please ensure you have gain RBAC role 'AzureML Data Scientist' for current workspace, "
                "and wait for a few minutes to make sure the new role takes effect. "
            )
            raise OpenURLUserAuthenticationError(message=auth_error_message)
        try:
            return self.build_connection_dict_from_rest_object(name, rest_obj)
        except Exception as e:
            raise BuildConnectionError(
                message_format=f"Build connection dict for connection {{name}} failed with {e}.",
                name=name,
            )


class AccessDeniedError(UserErrorException):
    """Exception raised when run info can not be found in storage"""

    def __init__(self, operation: str, target: ErrorTarget):
        super().__init__(message=f"Access is denied to perform operation {operation!r}", target=target)


class OpenURLFailed(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CONTROL_PLANE_SDK, **kwargs)


class BuildConnectionError(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CONTROL_PLANE_SDK, **kwargs)


class UserAuthenticationError(UserErrorException):
    """Exception raised when user authentication failed"""

    pass


class OpenURLUserAuthenticationError(UserAuthenticationError):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CONTROL_PLANE_SDK, **kwargs)


class OpenURLFailedUserError(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CONTROL_PLANE_SDK, **kwargs)


class UnknownConnectionType(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CONTROL_PLANE_SDK, **kwargs)
