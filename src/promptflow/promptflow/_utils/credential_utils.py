# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

def get_default_azure_credential():
    from azure.identity import DefaultAzureCredential
    try:
        from azure.ai.ml._azure_environments import _get_default_cloud_name, EndpointURLS, _get_cloud, AzureEnvironments
    except ImportError:
        return DefaultAzureCredential()
    # Support sovereign cloud cases, like mooncake, fairfax.
    cloud_name = _get_default_cloud_name()
    if cloud_name != AzureEnvironments.ENV_DEFAULT:
        cloud = _get_cloud(cloud=cloud_name)
        authority = cloud.get(EndpointURLS.ACTIVE_DIRECTORY_ENDPOINT)
        credential = DefaultAzureCredential(authority=authority, exclude_shared_token_cache_credential=True)
    else:
        credential = DefaultAzureCredential()

    return credential
