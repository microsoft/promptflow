import argparse
import json
from pathlib import Path

from utils.secret_manager import get_secret, get_secret_client, list_secret_names


CONNECTION_FILE_NAME = "connections.json"
PROMPTFLOW_TOOLS_ROOT = Path(__file__).resolve().parent.parent.parent / "src/promptflow-tools"
CONNECTION_TPL_FILE_PATH = PROMPTFLOW_TOOLS_ROOT / "connections.json.example"

def fill_key_to_dict(template_dict, keys_dict):
    for key, val in template_dict.items():
        if isinstance(val, dict):
            fill_key_to_dict(val, keys_dict)
        elif val in keys_dict:
            template_dict[key] = keys_dict[val]

def load_json_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def save_json_file(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def main():
    parser = argparse.ArgumentParser(description="Manage connections configuration.")
    parser.add_argument("--tenant_id", type=str, help="The tenant id of the service principal")
    parser.add_argument("--client_id", type=str, help="The client id of the service principal")
    parser.add_argument("--client_secret", type=str, help="The client secret of the service principal")
    parser.add_argument("--local", action='store_true', help="local debug mode")
    args = parser.parse_args()

    template_dict = load_json_file(CONNECTION_TPL_FILE_PATH)

    if not args.local:
        try:
            client = get_secret_client(tenant_id=args.tenant_id, client_id=args.client_id, client_secret=args.client_secret)
            all_secret_names = list_secret_names(client)
            data = {secret_name: get_secret(secret_name, client) for secret_name in all_secret_names}
            fill_key_to_dict(template_dict, data)
        except Exception as e:
            print(f"Error accessing secrets: {e}")
            return

    file_path = PROMPTFLOW_TOOLS_ROOT / CONNECTION_FILE_NAME
    save_json_file(template_dict, file_path)
    print(f"Configuration saved to: {file_path}")

if __name__ == "__main__":
    main()
