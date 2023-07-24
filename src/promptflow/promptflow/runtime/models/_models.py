# TODO: Remove this folder after new swagger generated.
import datetime
from typing import Optional

import msrest


class WorkspaceConnectionApiKey(msrest.serialization.Model):
    _validation = {
        "key": {"required": True},
    }

    _attribute_map = {
        "key": {"key": "key", "type": "str"},
    }

    def __init__(self, **kwargs):
        super(WorkspaceConnectionApiKey, self).__init__(**kwargs)
        self.key = kwargs.get("key", None)


class WorkspaceConnectionCustomKeys(msrest.serialization.Model):
    _validation = {
        "keys": {"required": True},
    }

    _attribute_map = {
        "keys": {"key": "keys", "type": "{str}"},
    }

    def __init__(self, **kwargs):
        super(WorkspaceConnectionCustomKeys, self).__init__(**kwargs)
        self.keys = kwargs.get("keys", None)


class WorkspaceConnectionPropertiesV2(msrest.serialization.Model):
    """WorkspaceConnectionPropertiesV2.

    You probably want to use the sub-classes and not this class directly. Known

    All required parameters must be populated in order to send to Azure.

    :ivar auth_type: Required. Authentication type of the connection target.Constant filled by
     server. Possible values include: "PAT", "ManagedIdentity", "UsernamePassword", "None", "SAS".
    :vartype auth_type: str or ~azure.mgmt.machinelearningservices.models.ConnectionAuthType
    :ivar category: Category of the connection. Possible values include: "PythonFeed",
     "ContainerRegistry", "Git".
    :vartype category: str or ~azure.mgmt.machinelearningservices.models.ConnectionCategory
    :ivar target:
    :vartype target: str
    :ivar value: Value details of the workspace connection.
    :vartype value: str
    :ivar value_format: format for the workspace connection value. Possible values include: "JSON".
    :vartype value_format: str or ~azure.mgmt.machinelearningservices.models.ValueFormat
    """

    _validation = {
        "auth_type": {"required": True},
    }

    _attribute_map = {
        "auth_type": {"key": "authType", "type": "str"},
        "category": {"key": "category", "type": "str"},
        "target": {"key": "target", "type": "str"},
        "value": {"key": "value", "type": "str"},
        "value_format": {"key": "valueFormat", "type": "str"},
        "metadata": {"key": "metadata", "type": "{str}"},
    }

    _subtype_map = {
        "auth_type": {
            "ApiKey": "ApiKeyAuthTypeWorkspaceConnectionProperties",
            "CustomKeys": "CustomKeysAuthTypeWorkspaceConnectionProperties",
        }
    }

    def __init__(self, **kwargs):
        super(WorkspaceConnectionPropertiesV2, self).__init__(**kwargs)
        self.auth_type = None
        self.category = kwargs.get("category", None)
        self.credentials = kwargs.get("credentials", None)
        self.target = kwargs.get("target", None)
        self.value = kwargs.get("value", None)
        self.value_format = kwargs.get("value_format", None)
        self.metadata = kwargs.get("metadata", None)


class ApiKeyAuthTypeWorkspaceConnectionProperties(WorkspaceConnectionPropertiesV2):
    _validation = {
        "auth_type": {"required": True},
    }

    _attribute_map = {
        "auth_type": {"key": "authType", "type": "str"},
        "category": {"key": "category", "type": "str"},
        "target": {"key": "target", "type": "str"},
        "value": {"key": "value", "type": "str"},
        "value_format": {"key": "valueFormat", "type": "str"},
        "credentials": {"key": "credentials", "type": "WorkspaceConnectionApiKey"},
        "metadata": {"key": "metadata", "type": "{str}"},
    }

    def __init__(self, **kwargs):
        super(ApiKeyAuthTypeWorkspaceConnectionProperties, self).__init__(**kwargs)
        self.auth_type = "ApiKey"  # type: str
        self.credentials = kwargs.get("credentials", None)


class CustomKeysAuthTypeWorkspaceConnectionProperties(WorkspaceConnectionPropertiesV2):
    _validation = {
        "auth_type": {"required": True},
    }

    _attribute_map = {
        "auth_type": {"key": "authType", "type": "str"},
        "category": {"key": "category", "type": "str"},
        "target": {"key": "target", "type": "str"},
        "value": {"key": "value", "type": "str"},
        "value_format": {"key": "valueFormat", "type": "str"},
        "credentials": {"key": "credentials", "type": "WorkspaceConnectionCustomKeys"},
        "metadata": {"key": "metadata", "type": "{str}"},
    }

    def __init__(self, **kwargs):
        super(CustomKeysAuthTypeWorkspaceConnectionProperties, self).__init__(**kwargs)
        self.auth_type = "ApiKey"  # type: str
        self.credentials = kwargs.get("credentials", None)


class SystemData(msrest.serialization.Model):
    """Metadata pertaining to creation and last modification of the resource.

    :ivar created_by: The identity that created the resource.
    :vartype created_by: str
    :ivar created_by_type: The type of identity that created the resource. Possible values include:
     "User", "Application", "ManagedIdentity", "Key".
    :vartype created_by_type: str or ~azure.mgmt.machinelearningservices.models.CreatedByType
    :ivar created_at: The timestamp of resource creation (UTC).
    :vartype created_at: ~datetime.datetime
    :ivar last_modified_by: The identity that last modified the resource.
    :vartype last_modified_by: str
    :ivar last_modified_by_type: The type of identity that last modified the resource. Possible
     values include: "User", "Application", "ManagedIdentity", "Key".
    :vartype last_modified_by_type: str or ~azure.mgmt.machinelearningservices.models.CreatedByType
    :ivar last_modified_at: The timestamp of resource last modification (UTC).
    :vartype last_modified_at: ~datetime.datetime
    """

    _attribute_map = {
        "created_by": {"key": "createdBy", "type": "str"},
        "created_by_type": {"key": "createdByType", "type": "str"},
        "created_at": {"key": "createdAt", "type": "iso-8601"},
        "last_modified_by": {"key": "lastModifiedBy", "type": "str"},
        "last_modified_by_type": {"key": "lastModifiedByType", "type": "str"},
        "last_modified_at": {"key": "lastModifiedAt", "type": "iso-8601"},
    }

    def __init__(
        self,
        *,
        created_by: Optional[str] = None,
        created_by_type: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        last_modified_by: Optional[str] = None,
        last_modified_by_type: Optional[str] = None,
        last_modified_at: Optional[datetime.datetime] = None,
        **kwargs
    ):
        """
        :keyword created_by: The identity that created the resource.
        :paramtype created_by: str
        :keyword created_by_type: The type of identity that created the resource. Possible values
         include: "User", "Application", "ManagedIdentity", "Key".
        :paramtype created_by_type: str or ~azure.mgmt.machinelearningservices.models.CreatedByType
        :keyword created_at: The timestamp of resource creation (UTC).
        :paramtype created_at: ~datetime.datetime
        :keyword last_modified_by: The identity that last modified the resource.
        :paramtype last_modified_by: str
        :keyword last_modified_by_type: The type of identity that last modified the resource. Possible
         values include: "User", "Application", "ManagedIdentity", "Key".
        :paramtype last_modified_by_type: str or
         ~azure.mgmt.machinelearningservices.models.CreatedByType
        :keyword last_modified_at: The timestamp of resource last modification (UTC).
        :paramtype last_modified_at: ~datetime.datetime
        """
        super(SystemData, self).__init__(**kwargs)
        self.created_by = created_by
        self.created_by_type = created_by_type
        self.created_at = created_at
        self.last_modified_by = last_modified_by
        self.last_modified_by_type = last_modified_by_type
        self.last_modified_at = last_modified_at


class WorkspaceConnectionPropertiesV2BasicResource(msrest.serialization.Model):
    """WorkspaceConnectionPropertiesV2BasicResource.

    Variables are only populated by the server, and will be ignored when sending a request.

    All required parameters must be populated in order to send to Azure.

    :ivar id: Fully qualified resource ID for the resource. Ex -
     /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/{resourceProviderNamespace}/{resourceType}/{resourceName}.
    :vartype id: str
    :ivar name: The name of the resource.
    :vartype name: str
    :ivar type: The type of the resource. E.g. "Microsoft.Compute/virtualMachines" or
     "Microsoft.Storage/storageAccounts".
    :vartype type: str
    :ivar system_data: Azure Resource Manager metadata containing createdBy and modifiedBy
     information.
    :vartype system_data: ~azure.mgmt.machinelearningservices.models.SystemData
    :ivar properties: Required.
    :vartype properties: ~azure.mgmt.machinelearningservices.models.WorkspaceConnectionPropertiesV2
    """

    _validation = {
        "id": {"readonly": True},
        "name": {"readonly": True},
        "type": {"readonly": True},
        "system_data": {"readonly": True},
        "properties": {"required": True},
    }

    _attribute_map = {
        "id": {"key": "id", "type": "str"},
        "name": {"key": "name", "type": "str"},
        "type": {"key": "type", "type": "str"},
        "system_data": {"key": "systemData", "type": "SystemData"},
        "properties": {"key": "properties", "type": "WorkspaceConnectionPropertiesV2"},
    }

    def __init__(self, **kwargs):
        """
        :keyword properties: Required.
        :paramtype properties:
         ~azure.mgmt.machinelearningservices.models.WorkspaceConnectionPropertiesV2
        """
        super(WorkspaceConnectionPropertiesV2BasicResource, self).__init__(**kwargs)
        self.properties = kwargs["properties"]
