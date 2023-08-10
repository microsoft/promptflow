import argparse
import importlib
import yaml
import json
import sys
import os

sys.path.append('src/promptflow-tools')
sys.path.append(os.getcwd())

from utils.generate_tool_meta_utils import generate_python_tools_in_module_as_dict, generate_custom_llm_tools_in_module_as_dict  # noqa: E402


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate meta for a tool.")
    parser.add_argument("--module", "-m", help="Module to generate tools.", type=str, required=True)
    parser.add_argument("--output", "-o", help="Path to the output tool json file.", required=True)
    parser.add_argument("--tool-type", "-t", help="Provide the type of the tool. Options are 'python' or 'custom_llm'. By default, 'python' will be set as the tool type.", type=str, choices=["python", "custom_llm"], default="python")
    parser.add_argument("--name", "-n", help="Provide a custom name for the tool. By default, the function name will be used as the tool name.", type=str)
    parser.add_argument("--description",  "-d", help="Provide a brief description of the tool.", type=str)
    args = parser.parse_args()
    m = importlib.import_module(args.module)
    if args.tool_type == "custom_llm":
        tools_dict = generate_custom_llm_tools_in_module_as_dict(m, name=args.name, description=args.description)
    else:
        tools_dict = generate_python_tools_in_module_as_dict(m, name=args.name, description=args.description)
    # The generated dict cannot be dumped as yaml directly since yaml cannot handle string enum.
    tools_dict = json.loads(json.dumps(tools_dict))
    with open(args.output, "w") as f:
        yaml.safe_dump(tools_dict, f, indent=2)
    print(f"Tools meta generated to '{args.output}'.")
