# Generate Readme file for the examples folder
import json
from pathlib import Path
import workflow_generator
import readme_generator
from jinja2 import Environment, FileSystemLoader
from ghactions_driver.readme_step import ReadmeStepsManage

BRANCH = "main"


def get_notebook_readme_description(notebook) -> str:
    """
    Set each ipynb metadata description at .metadata.description
    """
    try:
        # read in notebook
        with open(notebook, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["metadata"]["description"]
    except Exception:
        return ""


def get_readme_title(readme) -> str:
    """
    Get Each readme first line
    """
    try:
        with open(readme, "r", encoding="utf-8") as f:
            # read first line
            first_line = f.readline()
            title = first_line.replace("#", "").strip()
            return title
    except Exception:
        return ""


def write_readme(workflow_telemetrys, readme_telemetrys):
    global BRANCH

    ReadmeStepsManage.git_base_dir()
    readme_file = Path(ReadmeStepsManage.git_base_dir()) / "examples/README.md"

    tutorials = []
    flows = []
    evaluations = []
    chats = []
    connections = []

    for workflow_telemetry in workflow_telemetrys:
        notebook_name = f"{workflow_telemetry.name}.ipynb"
        gh_working_dir = workflow_telemetry.gh_working_dir
        pipeline_name = workflow_telemetry.workflow_name
        yaml_name = f"{pipeline_name}.yml"

        # For workflows, open ipynb as raw json and
        # setup description at .metadata.description
        description = get_notebook_readme_description(workflow_telemetry.notebook)
        notebook_path = gh_working_dir.replace("examples/", "")
        if gh_working_dir.startswith("examples/flows/standard"):
            flows.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif gh_working_dir.startswith("examples/connections"):
            connections.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif gh_working_dir.startswith("examples/flows/evaluation"):
            evaluations.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif gh_working_dir.startswith("examples/tutorials"):
            tutorials.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif gh_working_dir.startswith("examples/flows/chat"):
            chats.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        else:
            print(f"Unknown workflow type: {gh_working_dir}")

    for readme_telemetry in readme_telemetrys:
        notebook_name = readme_telemetry.readme_folder.split("/")[-1]
        notebook_path = (
            readme_telemetry.readme_folder.replace("examples/", "") + "/flow.dag.yaml"
        )
        pipeline_name = readme_telemetry.workflow_name
        yaml_name = f"{readme_telemetry.workflow_name}.yml"
        description = get_readme_title(readme_telemetry.readme_folder + "/README.md")
        readme_folder = readme_telemetry.readme_folder

        if readme_folder.startswith("examples/flows/standard"):
            flows.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif readme_folder.startswith("examples/connections"):
            connections.append(
                {
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif readme_folder.startswith("examples/flows/evaluation"):
            evaluations.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif readme_folder.startswith("examples/tutorials"):
            tutorials.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif readme_folder.startswith("examples/flows/chat"):
            chats.append(
                {
                    "notebook_name": notebook_name,
                    "notebook_path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        else:
            print(f"Unknown workflow type: {readme_folder}")

    replacement = {
        "branch": BRANCH,
        "tutorials": tutorials,
        "flows": flows,
        "evaluations": evaluations,
        "chats": chats,
        "connections": connections,
    }

    print("writing README.md...")
    env = Environment(
        loader=FileSystemLoader(
            Path(ReadmeStepsManage.git_base_dir())
            / "scripts/readme/ghactions_driver/readme_templates"
        )
    )
    template = env.get_template("README.md.jinja2")
    with open(readme_file, "w") as f:
        f.write(template.render(replacement))
    print("finished writing README.md")


if __name__ == "__main__":
    input_glob = ["examples/**/*.ipynb"]
    workflow_telemetrys = []
    workflow_generator.main(input_glob, workflow_telemetrys)

    input_glob_readme = ["examples/flows/**/README.md"]
    readme_telemetrys = []
    readme_generator.main(input_glob_readme, readme_telemetrys)

    write_readme(workflow_telemetrys, readme_telemetrys)
