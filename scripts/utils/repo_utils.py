import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import requests

scripts_dir = os.path.join(os.getcwd(), "scripts")
index_url = "https://azuremlsdktestpypi.azureedge.net/test-promptflow/prompt-flow-tools"
ado_promptflow_repo_url_format = "https://{0}@dev.azure.com/msdata/Vienna/_git/PromptFlow"


def replace_lines_from_file_under_hint(file_path, hint: str, lines_to_replace: list):
    lines_count = len(lines_to_replace)
    with open(file_path, "r") as f:
        lines = f.readlines()
    has_hint = False
    for i in range(len(lines)):
        if lines[i].strip() == hint:
            has_hint = True
            lines[i + 1 : i + 1 + lines_count] = lines_to_replace
    if not has_hint:
        lines.append(hint + "\n")
        lines += lines_to_replace
    with open(file_path, "w") as f:
        f.writelines(lines)


def create_remote_branch_in_ADO_with_new_tool_pkg_version(
    ado_pat: str, tool_pkg_version: str, blob_prefix="test-promptflow"
) -> str:
    # Clone the Azure DevOps repo
    parent_dir = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    tmp_dir = os.path.join(parent_dir, "temp")
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)

    subprocess.run(["git", "config", "--global", "user.email", "github-promptflow@dummy.com"])
    subprocess.run(["git", "config", "--global", "user.name", "github-promptflow"])

    # Change directory to the 'tmp' directory
    os.chdir(tmp_dir)
    repo_dir = os.path.join(tmp_dir, "PromptFlow")
    repo_url = ado_promptflow_repo_url_format.format(ado_pat)
    subprocess.run(["git", "clone", repo_url, repo_dir])
    # Change directory to the repo directory
    os.chdir(repo_dir)
    # Pull the devs/test branch
    subprocess.run(["git", "reset", "."])
    subprocess.run(["git", "checkout", "."])
    subprocess.run(["git", "clean", "-f", "."])
    subprocess.run(["git", "checkout", "main"])
    subprocess.run(["git", "fetch"])
    subprocess.run(["git", "pull"])

    # Make changes
    # 1. add test endpoint 'promptflow-gallery-tool-test.yaml'
    # 2. update tool package version
    source_file = Path(scripts_dir) / "utils/configs/promptflow-gallery-tool-test.yaml"
    destination_folder = "deploy/model"
    shutil.copy(source_file, destination_folder)

    new_lines = [
        f"--extra-index-url https://azuremlsdktestpypi.azureedge.net/{blob_prefix}\n",
        f"prompt_flow_tools=={tool_pkg_version}\n",
    ]
    replace_lines_from_file_under_hint(
        file_path="docker_build/linux/extra_requirements.txt",
        hint="# Prompt-flow tool package",
        lines_to_replace=new_lines,
    )

    # Create a new remote branch
    new_branch_name = f"devs/test_tool_pkg_{tool_pkg_version}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    subprocess.run(["git", "branch", "-D", "origin", new_branch_name])
    subprocess.run(["git", "checkout", "-b", new_branch_name])
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", f"Update tool package version to {tool_pkg_version}"])
    subprocess.run(["git", "push", "-u", repo_url, new_branch_name])

    return new_branch_name


def deploy_test_endpoint(branch_name: str, ado_pat: str):
    # PromptFlow-deploy-endpoint pipeline in ADO: https://msdata.visualstudio.com/Vienna/_build?definitionId=24767&_a=summary  # noqa: E501
    url = "https://dev.azure.com/msdata/Vienna/_apis/pipelines/24767/runs?api-version=7.0-preview.1"
    request_body_file = Path(scripts_dir) / "utils/configs/deploy-endpoint-request-body.json"
    with open(request_body_file, "r") as f:
        body = json.load(f)
    body["resources"]["repositories"]["self"]["refName"] = f"refs/heads/{branch_name}"
    print(f"request body: {body}")
    response = requests.post(url, json=body, auth=("dummy_user_name", ado_pat))
    print(response.status_code)
    print(response.content)
