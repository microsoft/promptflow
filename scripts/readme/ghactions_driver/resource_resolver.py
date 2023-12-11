from pathlib import Path
from typing import List

import markdown
import nbformat

from .readme_step import ReadmeStepsManage

RESOURCES_KEY_NAME = "resources"
RESOURCES_KEY_ERROR_MESSAGE = (
    "Please follow examples contributing guide to declare tutorial resources: "
    "https://github.com/microsoft/promptflow/blob/main/examples/CONTRIBUTING.md"
)


def _parse_resources_string_from_notebook(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    if RESOURCES_KEY_NAME not in nb.metadata:
        raise Exception(RESOURCES_KEY_ERROR_MESSAGE)
    return nb.metadata[RESOURCES_KEY_NAME]


def _parse_resources_string_from_markdown(path: Path) -> str:
    markdown_content = path.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=["meta"])
    md.convert(markdown_content)
    if RESOURCES_KEY_NAME not in md.Meta:
        raise Exception(RESOURCES_KEY_ERROR_MESSAGE)
    return md.Meta[RESOURCES_KEY_NAME][0]


def _parse_resources(path: Path) -> List[str]:
    if path.suffix == ".ipynb":
        resources_string = _parse_resources_string_from_notebook(path)
    elif path.suffix == ".md":
        resources_string = _parse_resources_string_from_markdown(path)
    else:
        raise Exception(f"Unknown file type: {path.suffix!r}")
    return [resource.strip() for resource in resources_string.split(",")]


def resolve_tutorial_resource(workflow_name: str, resource_path: Path) -> str:
    """Resolve tutorial resources, so that workflow can be triggered more precisely.

    A tutorial workflow should listen to changes of:
    1. working directory
    2. resources declared in notebook/markdown metadata
    3. workflow file
    4. examples/requirements.txt (for release verification)
    5. examples/connections/azure_openai.yml (fall back as it is the most basic and common connection)
    """
    # working directory
    git_base_dir = Path(ReadmeStepsManage.git_base_dir())
    working_dir = resource_path.parent.relative_to(git_base_dir).as_posix()
    path_filter_list = [f"{working_dir}/**"]
    # resources declared in text file
    resources = _parse_resources(resource_path)
    for resource in resources:
        # skip empty line
        if len(resource) == 0:
            continue
        # validate resource path exists
        resource_path = (git_base_dir / resource).resolve()
        if not resource_path.exists():
            raise FileNotFoundError("Please declare tutorial resources path whose base is the git repo root.")
        elif resource_path.is_file():
            path_filter_list.append(resource)
        else:
            path_filter_list.append(f"{resource}/**")
    # workflow file
    path_filter_list.append(f".github/workflows/{workflow_name}.yml")
    # manually add examples/requirements.txt if not exists
    examples_req = "examples/requirements.txt"
    if examples_req not in path_filter_list:
        path_filter_list.append(examples_req)
    # manually add examples/connections/azure_openai.yml if not exists
    aoai_conn = "examples/connections/azure_openai.yml"
    if aoai_conn not in path_filter_list:
        path_filter_list.append(aoai_conn)
    return "[ " + ", ".join(path_filter_list) + " ]"
