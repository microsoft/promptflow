from pathlib import Path

import markdown
import nbformat

from .readme_step import ReadmeStepsManage

RESOURCES_KEY_NAME = "resources"
RESOURCES_KEY_ERROR_MESSAGE = (
    "Please follow examples contributing guide to declare tutorial resources: "
    "https://github.com/microsoft/promptflow/blob/main/examples/CONTRIBUTING.md"
)
TITLE_KEY_NAME = "title"
CLOUD_KEY_NAME = "cloud"
CATEGORY_KEY_NAME = "category"
WEIGHT_KEY_NAME = "weight"


def _parse_resources_string_from_notebook(path: Path, output_telemetry):
    with open(path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    obj = {}
    if nb.metadata.get('build_doc', False):
        if nb.metadata['build_doc'].get(CLOUD_KEY_NAME, None):
            output_telemetry.cloud = nb.metadata['build_doc']['category']
        if nb.metadata['build_doc'].get(CATEGORY_KEY_NAME, None):
            output_telemetry.category = nb.metadata['build_doc']['section']
        if nb.metadata['build_doc'].get(WEIGHT_KEY_NAME, None):
            output_telemetry.weight = int(nb.metadata['build_doc']['weight'])
    cell = nb['cells'][0]
    for cell in nb['cells']:
        if (cell['cell_type'] == 'markdown'):
            break
    if (cell['cell_type'] == 'markdown'):
        lines = cell.source.split('\n')
        for line in lines:
            if '#' in line:
                output_telemetry.title = line.replace('#', '').strip()
                break
    if RESOURCES_KEY_NAME not in nb.metadata:
        raise Exception(RESOURCES_KEY_ERROR_MESSAGE + f" . Error in {path}")
    obj[RESOURCES_KEY_NAME] = nb.metadata[RESOURCES_KEY_NAME]
    return obj


def _parse_resources_string_from_markdown(path: Path, output_telemetry):
    markdown_content = path.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=["meta"])
    md.convert(markdown_content)
    obj = {}
    for line in md.lines:
        if '#' in line:
            output_telemetry.title = line.replace('#', '').strip()
            break
    if CLOUD_KEY_NAME in md.Meta:
        output_telemetry.cloud = md.Meta[CLOUD_KEY_NAME][0]
    if CATEGORY_KEY_NAME in md.Meta:
        output_telemetry.category = md.Meta[CATEGORY_KEY_NAME][0]
    if WEIGHT_KEY_NAME in md.Meta:
        output_telemetry.weight = int(md.Meta[WEIGHT_KEY_NAME][0])
    if RESOURCES_KEY_NAME not in md.Meta:
        raise Exception(RESOURCES_KEY_ERROR_MESSAGE + f" . Error in {path}")
    obj[RESOURCES_KEY_NAME] = md.Meta[RESOURCES_KEY_NAME][0]
    return obj


def _parse_resources(path: Path, output_telemetry):
    metadata = {}
    if path.suffix == ".ipynb":
        metadata = _parse_resources_string_from_notebook(path, output_telemetry)
        resources_string = metadata["resources"]
    elif path.suffix == ".md":
        metadata = _parse_resources_string_from_markdown(path, output_telemetry)
        resources_string = metadata["resources"]
    else:
        raise Exception(f"Unknown file type: {path.suffix!r}")
    return [resource.strip() for resource in resources_string.split(",")]


def resolve_tutorial_resource(workflow_name: str, resource_path: Path, output_telemetry):
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
    resources = _parse_resources(resource_path, output_telemetry)
    for resource in resources:
        # skip empty line
        if len(resource) == 0:
            continue
        # validate resource path exists
        resource_path = (git_base_dir / resource).resolve()
        if not resource_path.exists():
            raise FileNotFoundError(
                f"Please declare tutorial resources path {resource_path} whose base is the git repo root."
            )
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
