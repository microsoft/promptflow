# Generate Readme file for the examples folder
import json
from pathlib import Path
import workflow_generator
import readme_generator
from jinja2 import Environment, FileSystemLoader
from ghactions_driver.readme_step import ReadmeStepsManage
from operator import itemgetter

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
        print(f"{notebook} metadata description not set")
        return ""


def get_readme_description_first_sentence(readme) -> str:
    """
    Get each readme first sentence of first paragraph
    """
    try:
        with open(readme, "r", encoding="utf-8") as f:
            # read first line
            line = f.readline()
            sentence = ""
            while True:
                line = f.readline()
                if line.startswith("#"):
                    line = ""
                if line.strip() == "" and sentence != "":
                    break
                elif "." in line:
                    sentence += " " + line.split(".")[0].strip()
                    break
                else:
                    if sentence == "":
                        sentence += line.strip()
                    elif line.strip() != "":
                        sentence += line.strip()
            return sentence
    except Exception:
        print(f"Error during reading {readme}")
        return ""


def write_readme(workflow_telemetrys, readme_telemetrys):
    global BRANCH

    ReadmeStepsManage.git_base_dir()
    readme_file = Path(ReadmeStepsManage.git_base_dir()) / "examples/README.md"

    quickstarts = {
        "readmes": [],
        "notebooks": [],
    }
    tutorials = {
        "readmes": [],
        "notebooks": [],
    }
    flows = {
        "readmes": [],
        "notebooks": [],
    }
    evaluations = {
        "readmes": [],
        "notebooks": [],
    }
    chats = {
        "readmes": [],
        "notebooks": [],
    }
    connections = {
        "readmes": [],
        "notebooks": [],
    }

    for workflow_telemetry in workflow_telemetrys:
        notebook_name = f"{workflow_telemetry.name}.ipynb"
        gh_working_dir = workflow_telemetry.gh_working_dir
        pipeline_name = workflow_telemetry.workflow_name
        yaml_name = f"{pipeline_name}.yml"

        # For workflows, open ipynb as raw json and
        # setup description at .metadata.description
        description = get_notebook_readme_description(workflow_telemetry.notebook)
        notebook_path = gh_working_dir.replace("examples/", "") + f"/{notebook_name}"
        if gh_working_dir.startswith("examples/flows/standard"):
            flows["notebooks"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif gh_working_dir.startswith("examples/connections"):
            connections["notebooks"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif gh_working_dir.startswith("examples/flows/evaluation"):
            evaluations["notebooks"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif gh_working_dir.startswith("examples/tutorials"):
            if "quickstart" in notebook_name:
                quickstarts["notebooks"].append(
                    {
                        "name": notebook_name,
                        "path": notebook_path,
                        "pipeline_name": pipeline_name,
                        "yaml_name": yaml_name,
                        "description": description,
                    }
                )
            else:
                tutorials["notebooks"].append(
                    {
                        "name": notebook_name,
                        "path": notebook_path,
                        "pipeline_name": pipeline_name,
                        "yaml_name": yaml_name,
                        "description": description,
                    }
                )
        elif gh_working_dir.startswith("examples/flows/chat"):
            chats["notebooks"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        else:
            print(f"Unknown workflow type: {gh_working_dir}")

    # Adjust tutorial names:

    for readme_telemetry in readme_telemetrys:
        if readme_telemetry.readme_name.endswith("README.md"):
            notebook_name = readme_telemetry.readme_folder.split("/")[-1]
        else:
            notebook_name = readme_telemetry.readme_name.split("/")[-1].replace(
                ".md", ""
            )
        notebook_path = readme_telemetry.readme_name.replace("examples/", "")
        pipeline_name = readme_telemetry.workflow_name
        yaml_name = f"{readme_telemetry.workflow_name}.yml"
        description = get_readme_description_first_sentence(
            readme_telemetry.readme_name
        )
        readme_folder = readme_telemetry.readme_folder

        if readme_folder.startswith("examples/flows/standard"):
            flows["readmes"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif readme_folder.startswith("examples/connections"):
            connections["readmes"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif readme_folder.startswith("examples/flows/evaluation"):
            evaluations["readmes"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        elif readme_folder.startswith("examples/tutorials"):
            if "quickstart" in notebook_name:
                quickstarts["readmes"].append(
                    {
                        "name": notebook_name,
                        "path": notebook_path,
                        "pipeline_name": pipeline_name,
                        "yaml_name": yaml_name,
                        "description": description,
                    }
                )
            else:
                tutorials["readmes"].append(
                    {
                        "name": notebook_name,
                        "path": notebook_path,
                        "pipeline_name": pipeline_name,
                        "yaml_name": yaml_name,
                        "description": description,
                    }
                )
        elif readme_folder.startswith("examples/flows/chat"):
            chats["readmes"].append(
                {
                    "name": notebook_name,
                    "path": notebook_path,
                    "pipeline_name": pipeline_name,
                    "yaml_name": yaml_name,
                    "description": description,
                }
            )
        else:
            print(f"Unknown workflow type: {readme_folder}")

    quickstarts["notebooks"] = sorted(
        quickstarts["notebooks"],
        key=itemgetter("name"),
        reverse=True,
    )
    replacement = {
        "branch": BRANCH,
        "tutorials": tutorials,
        "flows": flows,
        "evaluations": evaluations,
        "chats": chats,
        "connections": connections,
        "quickstarts": quickstarts,
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

    input_glob_readme = [
        "examples/flows/**/README.md",
        "examples/connections/**/README.md",
        "examples/tutorials/**/chat*.md",
    ]
    readme_telemetrys = []
    readme_generator.main(input_glob_readme, readme_telemetrys)

    write_readme(workflow_telemetrys, readme_telemetrys)
