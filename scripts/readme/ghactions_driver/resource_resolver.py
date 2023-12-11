from pathlib import Path

from .readme_step import ReadmeStepsManage


def resolve_tutorial_resource(workflow_name: str, resource_path: Path) -> str:
    """Resolve tutorial resources, so that workflow can be triggered more precisely.

    A tutorial workflow should listen to changes of:
    1. working directory
    2. resources declared in text file
    3. workflow file
    4. examples/requirements.txt (for release verification)
    5. examples/connections/azure_openai.yml (fall back as it is the most basic and common connection)
    """
    if not resource_path.is_file():
        raise FileNotFoundError(f"Please declare tutorial resources in {resource_path.as_posix()!r}.")
    # working directory
    git_base_dir = Path(ReadmeStepsManage.git_base_dir())
    working_dir = resource_path.parent.relative_to(git_base_dir).as_posix()
    path_filter_list = [f"{working_dir}/**"]
    # resources declared in text file
    resources = resource_path.read_text(encoding="utf-8").split("\n")
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
