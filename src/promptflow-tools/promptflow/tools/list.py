from pathlib import Path

from promptflow.core.tools_manager import collect_tools_from_directory


def list_package_tools():
    """List package tools"""
    yaml_dir = Path(__file__).parent / "yamls"
    return collect_tools_from_directory(yaml_dir)
