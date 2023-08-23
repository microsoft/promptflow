import re

from azure.core.exceptions import HttpResponseError, ResourceExistsError
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient
from exceptions import (
    SecretNameAlreadyExistsException,
    SecretNameInvalidException,
    SecretNoSetPermissionException,
)

key_vault_name = "github-promptflow"
container_name = "tools"
KVUri = f"https://{key_vault_name}.vault.azure.net"


def init_used_secret_names(client: SecretClient):
    global reserved_secret_names
    reserved_secret_names = list_secret_names(client)


def get_secret_client(
    tenant_id: str, client_id: str, client_secret: str
) -> SecretClient:
    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    client = SecretClient(vault_url=KVUri, credential=credential)

    return client


reserved_secret_names = []


def get_secret(secret_name: str, client: SecretClient):
    secret = client.get_secret(secret_name)

    return secret.value


def list_secret_names(client: SecretClient) -> list:
    secret_properties = client.list_properties_of_secrets()

    return [secret.name for secret in secret_properties]


def delete_secret(secret_name: str, client: SecretClient):
    client.begin_delete_secret(secret_name)


def delete_useless_secrets(client: SecretClient):
    all_secret_names = list_secret_names(client)
    useless_secrets = [
        secret for secret in all_secret_names if secret not in reserved_secret_names
    ]

    for secret in useless_secrets:
        if secret not in reserved_secret_names:
            delete_secret(secret, client)


def validate_secret_name(secret_name: str):
    # Check if secret name is valid. Secret name can only contain alphanumeric characters and dashes.
    pattern = "^[a-zA-Z0-9-]+$"
    if not re.match(pattern, secret_name):
        raise SecretNameInvalidException(
            "Secret name can only contain alphanumeric characters and dashes"
        )
    # Check if secret name is one of the reserved names
    if secret_name in reserved_secret_names:
        raise SecretNameAlreadyExistsException(
            f"Secret name {secret_name} already exists"
        )


def upload_secret(client: SecretClient, secret_name: str, secret_value: str):
    try:
        client.set_secret(secret_name, secret_value)
    except ResourceExistsError as ex:
        if "in a deleted but recoverable state" in str(ex):
            raise SecretNameAlreadyExistsException(
                f"Secret name {secret_name} is deleted but recoverable, and its name cannot be reused"
            )
    except HttpResponseError as ex:
        if (
            ex.status_code == 403
            and "does not have secrets set permission on key vault" in str(ex)
        ):
            raise SecretNoSetPermissionException(
                f"No set permission on key vault {key_vault_name}"
            )

    print("Done.")
