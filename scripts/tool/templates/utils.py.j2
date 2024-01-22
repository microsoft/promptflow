from ruamel.yaml import YAML
from pathlib import Path


def collect_tools_from_directory(base_dir) -> dict:
    tools = {}
    yaml = YAML()
    for f in Path(base_dir).glob("**/*.yaml"):
        with open(f, "r") as f:
            tools_in_file = yaml.load(f)
            for identifier, tool in tools_in_file.items():
                tools[identifier] = tool
    return tools


def list_package_tools():
    """List package tools"""
    yaml_dir = Path(__file__).parents[1] / "yamls"
    return collect_tools_from_directory(yaml_dir)
