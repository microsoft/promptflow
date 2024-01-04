import argparse
import json
from pathlib import Path

from utils.secret_manager import get_secret, get_secret_client, list_secret_names

CONNECTION_FILE_NAME = "connections.json"
PROMPTFLOW_TOOLS_ROOT = Path(__file__) / "../../../src/promptflow-tools"
CONNECTION_TPL_FILE_PATH = PROMPTFLOW_TOOLS_ROOT / "connections.json.example"


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
    parser.add_argument("--local", action='store_true', help="local debug mode")
    args = parser.parse_args()

    template_dict = json.loads(open(CONNECTION_TPL_FILE_PATH.resolve().absolute(), "r").read())
    file_path = (PROMPTFLOW_TOOLS_ROOT / CONNECTION_FILE_NAME).resolve().absolute().as_posix()
    print(f"file_path: {file_path}")

    if not args.local:
        client = get_secret_client(tenant_id=args.tenant_id, client_id=args.client_id, client_secret=args.client_secret)
        all_secret_names = list_secret_names(client)
        data = {secret_name: get_secret(secret_name, client) for secret_name in all_secret_names}

        fill_key_to_dict(template_dict, data)

    with open(file_path, "w") as f:
        json.dump(template_dict, f)
