import argparse
import json
from pathlib import Path

ENDPOINT_CONFIG_FILE_NAME = "endpoint_config.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="The endpoint url")
    parser.add_argument("--key", type=str, required=True, help="The endpoint key")
    parser.add_argument("--folder-path", type=str, required=True, help="The folder to save the endpoint config file")
    args = parser.parse_args()

    file_path = Path(args.folder_path) / ENDPOINT_CONFIG_FILE_NAME
    print(file_path)
    data = {
        "endpoint_url": args.url,
        "endpoint_key": args.key,
    }

    with open(file_path, "w") as f:
        json.dump(data, f)
