# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import importlib
import json

import yaml

from promptflow._utils.generate_tool_meta_utils import generate_python_tools_in_module_as_dict

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate meta for a tool.")
    parser.add_argument("--module", "-m", help="Module to generate tools.", type=str, required=True)
    parser.add_argument("--output", "-o", help="Path to the output tool json file.", required=True)
    args = parser.parse_args()
    m = importlib.import_module(args.module)
    tools_dict = generate_python_tools_in_module_as_dict(m)
    # The generated dict cannot be dumped as yaml directly since yaml cannot handle string enum.
    tools_dict = json.loads(json.dumps(tools_dict))
    with open(args.output, "w") as f:
        yaml.safe_dump(tools_dict, f, indent=2)
    print(f"Tools meta generated to '{args.output}'.")
