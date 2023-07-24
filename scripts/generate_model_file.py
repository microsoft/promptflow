import argparse
import json
import re
from pathlib import Path

import yaml


def remove_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)
    return text.lower().replace(" ", "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern-model-file", type=str, required=True, help="Generate a new model file based on this")
    parser.add_argument("--deployment", type=str, required=True, help="The deployment name of the new model file")
    parser.add_argument("--target-folder", type=str, required=True, help="The folder to save the endpoint config file")
    parser.add_argument("--requested-for", type=str, help="The name of the person who triggered the build")
    args = parser.parse_args()

    pattern_model_file = Path(args.target_folder) / args.pattern_model_file
    pattern_model_file = pattern_model_file.resolve().absolute()
    print(f"Pattern model file path: {pattern_model_file}")

    if not pattern_model_file.exists():
        raise FileNotFoundError(f"Missing {pattern_model_file}, please update the file path if it is moved elsewhere.")

    with open(pattern_model_file, "r") as f:
        model = yaml.safe_load(f)

    name = f"{args.deployment}-{remove_emoji(args.requested_for)}" if args.requested_for else args.deployment
    model["deployment"]["deployment_name"] = name
    model["deployment"]["runtime_name"] = name
    print(f"New model file content:\n{json.dumps(model, indent=4)}")

    file_path = Path(args.target_folder) / f"promptflow-{args.deployment}.yaml"
    print(f"New model file path: {file_path}")

    with open(file_path, "w") as file:
        yaml.dump(model, file)
