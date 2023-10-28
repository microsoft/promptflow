import argparse
import ast
import importlib
import json
import os
import sys

import yaml

sys.path.append("src/promptflow-tools")
sys.path.append(os.getcwd())

from utils.generate_tool_meta_utils import generate_custom_llm_tools_in_module_as_dict, generate_python_tools_in_module_as_dict  # noqa: E402, E501


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate meta for a tool.")
    parser.add_argument("--module", "-m", help="Module to generate tools.", type=str, required=True)
    parser.add_argument("--output", "-o", help="Path to the output tool json file.", required=True)
    parser.add_argument(
        "--tool-type",
        "-t",
        help="Provide tool type: 'python' or 'custom_llm'. By default, 'python' will be set as the tool type.",
        type=str,
        choices=["python", "custom_llm"],
        default="python",
    )
    parser.add_argument(
        "--name",
        "-n",
        help="Provide a custom name for the tool. By default, the function name will be used as the tool name.",
        type=str,
    )
    parser.add_argument("--description", "-d", help="Provide a brief description of the tool.", type=str)
    parser.add_argument(
        "--icon",
        "-i",
        type=str,
        help="your tool's icon image path, if not provided, the system will use the default icon.",
        required=False)
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        help="your tool's category, if not provided, the tool will be displayed under the root folder.",
        required=False)
    parser.add_argument(
        "--tags",
        type=ast.literal_eval,
        help="your tool's tags. It should be a dictionary-like string, e.g.: --tags \"{'tag1':'v1','tag2':'v2'}\".",
        required=False)
    args = parser.parse_args()
    m = importlib.import_module(args.module)

    icon = ""
    if args.icon:
        from convert_image_to_data_url import check_image_type_and_generate_data_url  # noqa: E402
        icon = check_image_type_and_generate_data_url(args.icon)

    if args.tool_type == "custom_llm":
        tools_dict = generate_custom_llm_tools_in_module_as_dict(
            m,
            name=args.name,
            description=args.description,
            icon=icon,
            category=args.category,
            tags=args.tags)
    else:
        tools_dict = generate_python_tools_in_module_as_dict(
            m,
            name=args.name,
            description=args.description,
            icon=icon,
            category=args.category,
            tags=args.tags)
    # The generated dict cannot be dumped as yaml directly since yaml cannot handle string enum.
    tools_dict = json.loads(json.dumps(tools_dict))
    with open(args.output, "w") as f:
        yaml.safe_dump(tools_dict, f, indent=2)
    print(f"Tools meta generated to '{args.output}'.")
