from pathlib import Path

import yaml


def collect_tools_from_directory(base_dir) -> dict:
    tools = {}
    for f in Path(base_dir).glob("**/*.yaml"):
        with open(f, "r") as f:
            tools_in_file = yaml.safe_load(f)
            for identifier, tool in tools_in_file.items():
                tools[identifier] = tool
                if "inputs" in tool:
                    inputs_dict = tool["inputs"]
                    inputs_order = list(inputs_dict.keys())
                    for input, settings in inputs_dict.items():
                        settings.setdefault("uhint", {}).setdefault("index", inputs_order.index(input))
    return tools


def list_package_tools():
    """List package tools"""
    yaml_dir = Path(__file__).parent / "yamls"
    return collect_tools_from_directory(yaml_dir)
