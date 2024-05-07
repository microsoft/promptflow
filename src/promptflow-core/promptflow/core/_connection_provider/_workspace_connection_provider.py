# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from typing import Any, Dict, List, Union

import requests

from promptflow._constants import AML_WORKSPACE_TEMPLATE
from promptflow._utils.retry_utils import http_retry_wrapper
from promptflow.constants import ConnectionAuthMode
from promptflow.core._connection import CustomConnection, _Connection
from promptflow.core._errors import (
    AccessDeniedError,
    AccountNotSetUp,
    BuildConnectionError,
    MissingRequiredPackage,
    OpenURLFailed,
    OpenURLFailedUserError,
    OpenURLNotFoundError,
    OpenURLUserAuthenticationError,
    UnknownConnectionType,
    UnsupportedConnectionAuthType,
)
from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException

from ..._utils.credential_utils import get_default_azure_credential
from ._connection_provider import ConnectionProvider
from ._utils import interactive_credential_enabled, is_from_cli, is_github_codespaces

GET_CONNECTION_URL = (
    "/subscriptions/{sub}/resourcegroups/{rg}/providers/Microsoft.MachineLearningServices"
    "/workspaces/{ws}/connections/{name}/listsecrets?api-version=2023-04-01-preview"
)
LIST_CONNECTION_URL = (
    "/subscriptions/{sub}/resourcegroups/{rg}/providers/Microsoft.MachineLearningServices"
    "/workspaces/{ws}/connections?api-version=2023-04-01-preview"
)
FLOW_META_PREFIX = "azureml.flow."

logger = logging.getLogger(__name__)


# Note: We define the category and auth type here because newly added enum values may
# depend on azure-ai-ml package update, which is not in our control.
class ConnectionCategory:
    AzureOpenAI = "AzureOpenAI"
    CognitiveSearch = "CognitiveSearch"
    CognitiveService = "CognitiveService"
    CustomKeys = "CustomKeys"
    OpenAI = "OpenAI"
    Serp = "Serp"
    Serverless = "Serverless"
    BingLLMSearch = "BingLLMSearch"
    AIServices = "AIServices"


class ConnectionAuthType:
    ApiKey = "ApiKey"
    AAD = "AAD"


def get_case_insensitive_key(d, key, default=None):
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return default


class WorkspaceConnectionProvider(ConnectionProvider):
    def __init__(
        self,
        subscription_id: str,
        resource_group_name: str,
        workspace_name: str,
        credential=None,
    ):
        self._credential = credential
        self.subscription_id = subscription_id
        self.resource_group_name = resource_group_name
        self.workspace_name = workspace_name
        self.resource_id = AML_WORKSPACE_TEMPLATE.format(
            self.subscription_id, self.resource_group_name, self.workspace_name
        )

    @property
    def credential(self):
        """Get the credential."""
        # Note: Add this to postpone credential requirement until calling get()
        if not self._credential:
            self._credential = self._get_credential()
        return self._credential

    @classmethod
    def _get_credential(cls):

        # Note: There is a try-catch in get arm token. It requires azure-ai-ml.
        # TODO: Remove the azure-ai-ml dependency.
        from ._utils import get_arm_token

        try:
            from azure.identity import DefaultAzureCredential, DeviceCodeCredential
        except ImportError as e:
            raise MissingRequiredPackage(
                message="Please install 'promptflow-core[azureml-serving]' to use workspace connection."
            ) from e

        if is_from_cli():
            try:
                # Try getting token for cli without interactive login
                credential = get_default_azure_credential()
                get_arm_token(credential=credential)
            except Exception:
                raise AccountNotSetUp()
        if interactive_credential_enabled():
            return DefaultAzureCredential(exclude_interactive_browser_credential=False)
        if is_github_codespaces():
            # For code spaces, append device code credential as the fallback option.
            credential = DefaultAzureCredential()
            credential.credentials = (*credential.credentials, DeviceCodeCredential())
            return credential
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)

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
        response = http_retry_wrapper(requests.request)(method, f"https://{host}{url}", headers=headers)
        message_format = (
            f"Open url {{url}} failed with status code: {response.status_code}, action: {action}, reason: {{reason}}"
        )
        if response.status_code == 403:
            raise AccessDeniedError(operation=url, target=ErrorTarget.CORE)
        elif response.status_code == 404:
            raise OpenURLNotFoundError(
                message_format=message_format,
                url=url,
                reason=response.reason,
            )
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
    def validate_and_fallback_connection_type(cls, name, type_name, category, metadata):
        # Note: Legacy CustomKeys may store different connection types, e.g. openai, serp.
        # In this case, type name will not be None.
        if type_name:
            return type_name
        # Below category has corresponding connection type in PromptFlow, so we can fall back directly.
        if category in [
            ConnectionCategory.AzureOpenAI,
            ConnectionCategory.OpenAI,
            ConnectionCategory.Serp,
            ConnectionCategory.CognitiveSearch,
            ConnectionCategory.Serverless,
        ]:
            return category
        if category == ConnectionCategory.AIServices:
            return "AzureAIServices"
        if category == ConnectionCategory.CustomKeys:
            return CustomConnection.__name__
        if category == ConnectionCategory.CognitiveService:
            kind = get_case_insensitive_key(metadata, "Kind")
            if kind == "Content Safety":
                return "AzureContentSafety"
            if kind == "Form Recognizer":
                return "FormRecognizer"
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
        :type obj: azure.ai.ml._restclient.v2023_06_01_preview.models.WorkspaceConnectionPropertiesV2BasicResource
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
        type_name = get_case_insensitive_key(properties.metadata, f"{FLOW_META_PREFIX}connection_type")
        type_name = cls.validate_and_fallback_connection_type(name, type_name, properties.category, properties.metadata)
        module = get_case_insensitive_key(properties.metadata, f"{FLOW_META_PREFIX}module", "promptflow.connections")
        # Note: Category is connectionType in MT, but type name should be class name, which is flowValueType in MT.
        # Handle old connections here, see details: https://github.com/Azure/promptflow/tree/main/connections
        type_name = f"{type_name}Connection" if not type_name.endswith("Connection") else type_name
        meta = {"type": type_name, "module": module, "name": name}

        def get_auth_config(props, support_aad=False):
            postfix = " and 'AAD'." if support_aad else "."
            unsupported_message = f"Unsupported connection auth type %r, supported types are 'ApiKey'{postfix}"
            if not isinstance(props.auth_type, str):
                raise UnsupportedConnectionAuthType(message=unsupported_message % props.auth_type)
            if props.auth_type.lower() == ConnectionAuthType.ApiKey.lower():
                result = {
                    "api_key": props.credentials.key if props.credentials else None,
                }
                if support_aad:
                    result["auth_mode"] = ConnectionAuthMode.KEY
                return result
            elif support_aad and props.auth_type.lower() == ConnectionAuthType.AAD.lower():
                return {"api_key": None, "auth_mode": ConnectionAuthMode.MEID_TOKEN}
            raise UnsupportedConnectionAuthType(message=unsupported_message % props.auth_type)

        if properties.category == ConnectionCategory.AzureOpenAI:
            value = {
                **get_auth_config(properties, support_aad=True),
                "api_base": properties.target,
                "api_type": get_case_insensitive_key(properties.metadata, "ApiType"),
                "api_version": get_case_insensitive_key(properties.metadata, "ApiVersion"),
            }
            # Note: Resource id is required in some cloud scenario, which is not exposed on sdk/cli entity.
            resource_id = get_case_insensitive_key(properties.metadata, "ResourceId")
            if resource_id:
                value["resource_id"] = resource_id
        elif properties.category == ConnectionCategory.CognitiveSearch:
            value = {
                **get_auth_config(properties, support_aad=True),
                "api_base": properties.target,
                "api_version": get_case_insensitive_key(properties.metadata, "ApiVersion"),
            }
        elif properties.category == ConnectionCategory.Serverless:
            value = {
                **get_auth_config(properties, support_aad=True),
                "api_base": properties.target,
            }
        elif properties.category == ConnectionCategory.CognitiveService:
            value = {
                **get_auth_config(properties, support_aad=True),
                "endpoint": properties.target,
                "api_version": get_case_insensitive_key(properties.metadata, "ApiVersion"),
            }
        elif properties.category == ConnectionCategory.AIServices:
            value = {
                **get_auth_config(properties, support_aad=True),
                "endpoint": properties.target,
            }
        elif properties.category == ConnectionCategory.OpenAI:
            value = {
                **get_auth_config(properties),
                "base_url": properties.target,
                "organization": get_case_insensitive_key(properties.metadata, "organization"),
            }
        elif properties.category == ConnectionCategory.Serp:
            value = {
                **get_auth_config(properties),
            }
        elif properties.category == ConnectionCategory.CustomKeys:
            # Merge secrets from credentials.keys and other string fields from metadata
            value = {
                **(properties.credentials.keys if properties.credentials else {}),
                **{k: v for k, v in properties.metadata.items() if not k.startswith(FLOW_META_PREFIX)},
            }
            if type_name == CustomConnection.__name__:
                meta["secret_keys"] = list(properties.credentials.keys.keys()) if properties.credentials else []
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

    @classmethod
    def _build_connection_dict(cls, name, subscription_id, resource_group_name, workspace_name, credential) -> dict:
        """
        :type name: str
        """
        url = GET_CONNECTION_URL.format(
            sub=subscription_id,
            rg=resource_group_name,
            ws=workspace_name,
            name=name,
        )
        # Note: There is a try-catch in get arm token. It requires azure-ai-ml.
        # TODO: Remove the azure-ai-ml dependency.
        from ._utils import get_arm_token

        try:
            from azure.core.exceptions import ClientAuthenticationError

            from ._models import WorkspaceConnectionPropertiesV2BasicResource
        except ImportError as e:
            raise MissingRequiredPackage(
                message="Please install 'promptflow-core[azureml-serving]' to use workspace connection."
            ) from e
        try:
            rest_obj: WorkspaceConnectionPropertiesV2BasicResource = cls.open_url(
                get_arm_token(credential=credential),
                url=url,
                action="listsecrets",
                method="POST",
                model=WorkspaceConnectionPropertiesV2BasicResource,
            )
        except AccessDeniedError:
            auth_error_message = (
                "Access denied to list workspace secret due to invalid authentication. "
                "Please ensure you have gain RBAC role 'Azure Machine Learning Workspace Connection Secrets Reader' "
                "for current workspace, and wait for a few minutes to make sure the new role takes effect. "
            )
            raise OpenURLUserAuthenticationError(message=auth_error_message)
        except ClientAuthenticationError as e:
            raise UserErrorException(target=ErrorTarget.CORE, message=str(e), error=e)
        except UserErrorException:
            raise
        except Exception as e:
            raise SystemErrorException(target=ErrorTarget.CORE, message=str(e), error=e)

        try:
            return cls.build_connection_dict_from_rest_object(name, rest_obj)
        except Exception as e:
            raise BuildConnectionError(
                message_format=f"Build connection dict for connection {{name}} failed with {e}.",
                name=name,
            )

    @classmethod
    def _convert_to_connection_dict(cls, conn_name, conn_data):
        try:
            from ._models import WorkspaceConnectionPropertiesV2BasicResource
        except ImportError as e:
            raise MissingRequiredPackage(message="Please install 'msrest' to use workspace connection.") from e
        try:
            rest_obj = WorkspaceConnectionPropertiesV2BasicResource.deserialize(conn_data)
            conn_dict = cls.build_connection_dict_from_rest_object(conn_name, rest_obj)
            return conn_dict
        except Exception as e:
            raise BuildConnectionError(
                message_format=f"Build connection dict for connection {{name}} failed with {e}.",
                name=conn_name,
            )

    @classmethod
    def _build_list_connection_dict(
        cls, subscription_id, resource_group_name, workspace_name, credential
    ) -> Dict[str, dict]:
        url = LIST_CONNECTION_URL.format(
            sub=subscription_id,
            rg=resource_group_name,
            ws=workspace_name,
        )
        # Note: There is a try-catch in get arm token. It requires azure-ai-ml.
        # TODO: Remove the azure-ai-ml dependency.
        from ._utils import get_arm_token

        try:
            from azure.core.exceptions import ClientAuthenticationError

            from ._models import WorkspaceConnectionPropertiesV2BasicResourceArmPaginatedResult
        except ImportError as e:
            raise MissingRequiredPackage(
                message="Please install 'promptflow-core[azureml-serving]' to use workspace connection."
            ) from e
        try:
            token = get_arm_token(credential=credential)
            rest_obj: WorkspaceConnectionPropertiesV2BasicResourceArmPaginatedResult = cls.open_url(
                token,
                url=url,
                action="list",
                method="GET",
                model=WorkspaceConnectionPropertiesV2BasicResourceArmPaginatedResult,
            )
            result_list = [rest_obj]
            while rest_obj.next_link is not None:
                logger.debug("Workspace connection list is paginated, fetching next page.")
                rest_obj = cls.open_url(
                    token,
                    url=rest_obj.next_link,
                    action="list",
                    method="GET",
                    model=WorkspaceConnectionPropertiesV2BasicResourceArmPaginatedResult,
                )
                result_list.append(rest_obj)
        except AccessDeniedError:
            auth_error_message = (
                "Access denied to list workspace connections due to invalid authentication. "
                "Please ensure you have gain RBAC role 'Azure Machine Learning Workspace Connection Secrets Reader' "
                "for current workspace, and wait for a few minutes to make sure the new role takes effect. "
            )
            raise OpenURLUserAuthenticationError(message=auth_error_message)
        except ClientAuthenticationError as e:
            raise UserErrorException(target=ErrorTarget.CORE, message=str(e), error=e) from e
        except UserErrorException:
            raise
        except Exception as e:
            raise SystemErrorException(target=ErrorTarget.CORE, message=str(e), error=e) from e

        rest_list_connection_dict = {}
        for rest_obj in result_list:
            for conn in rest_obj.value:
                try:
                    rest_list_connection_dict[conn.name] = cls.build_connection_dict_from_rest_object(conn.name, conn)
                except Exception as e:
                    logger.warning("Connection %r skipped: build connection dict failed with %s.", conn.name, e)
        return rest_list_connection_dict

    def list(self) -> List[_Connection]:
        rest_list_connection_dict = self._build_list_connection_dict(
            subscription_id=self.subscription_id,
            resource_group_name=self.resource_group_name,
            workspace_name=self.workspace_name,
            credential=self.credential,
        )
        connection_list = []
        for name, conn_dict in rest_list_connection_dict.items():
            try:
                connection_list.append(_Connection._from_execution_connection_dict(name=name, data=conn_dict))
            except Exception as e:
                logger.warning("Connection %r skipped: build connection object failed with %s.", name, e)
        return connection_list

    def get(self, name: str, **kwargs) -> _Connection:
        connection_dict = self._build_connection_dict(
            name,
            subscription_id=self.subscription_id,
            resource_group_name=self.resource_group_name,
            workspace_name=self.workspace_name,
            credential=self.credential,
        )
        return _Connection._from_execution_connection_dict(name=name, data=connection_dict)
