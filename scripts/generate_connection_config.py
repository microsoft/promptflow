import argparse
import json
from pathlib import Path

CONNECTION_FILE_NAME = "connections.json"

CONNECTION_TPL_FILE_PATH = Path(__file__).parent / "connections.json.example"


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
    parser.add_argument("--bing-key", type=str, required=True, help="The api key of Bing")
    parser.add_argument("--openai-key", type=str, required=True, help="The api key of OpenAI")
    parser.add_argument("--aoai-endpoint", type=str, required=True, help="The api endpoint of AzureOpenAI")
    parser.add_argument("--aoai-key", type=str, required=True, help="The api key of AzureOpenAI")
    parser.add_argument("--serpapi-key", type=str, required=True, help="The api key of serpapi")
    parser.add_argument("--content-safety-key", type=str, required=True, help="The api key of content safety")
    parser.add_argument("--folder-path", type=str, required=True, help="The folder to save the connection config file")
    args = parser.parse_args()

    print(__file__)

    template_dict = json.loads(open(CONNECTION_TPL_FILE_PATH.resolve().absolute(), "r").read())
    file_path = Path(args.folder_path) / CONNECTION_FILE_NAME
    print(file_path)
    data = {
        "bing-api-key": args.bing_key,
        "aoai-api-key": args.aoai_key,
        "aoai-api-endpoint": args.aoai_endpoint,
        "openai-api-key": args.openai_key,
        "serpapi-api-key": args.serpapi_key,
        "content-safety-api-key": args.content_safety_key,
    }
    fill_key_to_dict(template_dict, data)

    with open(file_path, "w") as f:
        json.dump(template_dict, f)
