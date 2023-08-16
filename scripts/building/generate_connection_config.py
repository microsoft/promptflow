import argparse
import json
from pathlib import Path

from azure.keyvault.secrets import SecretClient
from azure.identity import ClientSecretCredential


CONNECTION_FILE_NAME = "connections.json"
CONNECTION_TPL_FILE_PATH = Path('.') / "src/promptflow-tool" / "connections.json.example"


def get_secret_client(
    tenant_id: str, client_id: str, client_secret: str
) -> SecretClient:
    credential = ClientSecretCredential(tenant_id, client_id, client_secret)
    client = SecretClient(vault_url="https://promptflow-api-keys.vault.azure.net/", credential=credential)

    return client


def get_secret(secret_name: str, client: SecretClient):
    secret = client.get_secret(secret_name)

    return secret.value


def list_secret_names(client: SecretClient) -> list:
    secret_properties = client.list_properties_of_secrets()

    return [secret.name for secret in secret_properties]


def fill_key_to_dict(template_dict, keys_dict):
    if not isinstance(template_dict, dict):
        return
    for key, val in template_dict.items():
        if isinstance(val, str) and val in keys_dict:
            template_dict[key] = keys_dict[val]
            continue
        fill_key_to_dict(val, keys_dict)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant_id", type=str, help="The tenant id of the service principal")
    parser.add_argument("--client_id", type=str, help="The client id of the service principal")
    parser.add_argument("--client_secret", type=str, help="The client secret of the service principal")
    parser.add_argument("--target_folder", type=str, help="The target folder to save the generated file")
    args = parser.parse_args()

    template_dict = json.loads(
        open(CONNECTION_TPL_FILE_PATH.resolve().absolute(), "r").read()
    )
    file_path = (
        (Path('.') / args.target_folder / CONNECTION_FILE_NAME).resolve().absolute().as_posix()
    )
    print(f"file_path: {file_path}")

    client = get_secret_client(
        tenant_id=args.tenant_id, client_id=args.client_id, client_secret=args.client_secret
    )
    all_secret_names = list_secret_names(client)
    data = {
        secret_name: get_secret(secret_name, client) for secret_name in all_secret_names
    }

    fill_key_to_dict(template_dict, data)

    with open(file_path, "w") as f:
        json.dump(template_dict, f)
