from azure.identity import AzureCliCredential
from azure.keyvault.secrets import SecretClient

key_vault_name = "github-promptflow"
KVUri = f"https://{key_vault_name}.vault.azure.net"


def get_secret_client() -> SecretClient:
    credential = AzureCliCredential()
    client = SecretClient(vault_url=KVUri, credential=credential)

    return client


def get_secret(secret_name: str, client: SecretClient):
    secret = client.get_secret(secret_name)

    return secret.value


def list_secret_names(client: SecretClient) -> list:
    secret_properties = client.list_properties_of_secrets()

    return [secret.name for secret in secret_properties]
