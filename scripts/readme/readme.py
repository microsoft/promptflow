# Generate Readme file for the examples folder
import json
from pathlib import Path
import workflow_generator
import readme_generator
from jinja2 import Environment, FileSystemLoader
from ghactions_driver.readme_step import ReadmeStepsManage
from operator import itemgetter
import argparse
import sys
import os
import re

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

def get_notebook_buildDoc_description(notebook) -> str:
    """
    Set each ipynb metadata description at .metadata.description
    """
    try:
        # read in notebook
        with open(notebook, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["metadata"]["build_doc"]
    except Exception:
        print(f"{notebook} metadata build_doc not set")
        return {}


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
                # skip metadata section
                if line.startswith("---") or line.startswith("resources:") or line.startswith("title:") or line.startswith("cloud:") or line.startswith("category:"):
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
                        sentence += " " + line.strip()
            return sentence
    except Exception:
        print(f"Error during reading {readme}")
        return ""


def write_readme(workflow_telemetries, readme_telemetries):
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
    flex_flows = {
        "readmes": [],
        "notebooks": [],
    }
    prompty = {
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
    toolusecases = {
        "readmes": [],
        "notebooks": [],
    }
    connections = {
        "readmes": [],
        "notebooks": [],
    }

    for workflow_telemetry in workflow_telemetries:
        notebook_name = f"{workflow_telemetry.name}.ipynb"
        gh_working_dir = workflow_telemetry.gh_working_dir
        pipeline_name = workflow_telemetry.workflow_name
        yaml_name = f"{pipeline_name}.yml"

        # For workflows, open ipynb as raw json and
        # setup description at .metadata.description
        description = get_notebook_readme_description(workflow_telemetry.notebook)
        build_doc = get_notebook_buildDoc_description(workflow_telemetry.notebook)
        notebook_path = gh_working_dir.replace("examples/", "") + f"/{notebook_name}"
        default_workflow_item = {
            "name": notebook_name,
            "path": notebook_path,
            "pipeline_name": pipeline_name,
            "yaml_name": yaml_name,
            "description": description,
            "build_doc": build_doc,
        }
        if gh_working_dir.startswith("examples/flows/standard"):
            flows["notebooks"].append(default_workflow_item)
        elif gh_working_dir.startswith("examples/connections"):
            connections["notebooks"].append(default_workflow_item)
        elif gh_working_dir.startswith("examples/flows/evaluation"):
            evaluations["notebooks"].append(default_workflow_item)
        elif gh_working_dir.startswith("examples/tutorials"):
            tutorial_workflow_item = {
                **default_workflow_item,
                'title': workflow_telemetry.title.capitalize() if hasattr(workflow_telemetry, 'title') else "Empty title",
                'cloud': workflow_telemetry.cloud.capitalize() if hasattr(workflow_telemetry, 'cloud') else "NOT DEFINED",
                'category': workflow_telemetry.category.capitalize() if hasattr(workflow_telemetry, 'category') else "General"
            }
            if "quickstart" in notebook_name:
                quickstarts["notebooks"].append(tutorial_workflow_item)
            else:
                tutorials["notebooks"].append(tutorial_workflow_item)
        elif gh_working_dir.startswith("examples/flows/chat"):
            chats["notebooks"].append(default_workflow_item)
        elif gh_working_dir.startswith("examples/flex-flows"):
            flex_flows["notebooks"].append(default_workflow_item)
        elif gh_working_dir.startswith("examples/prompty"):
            prompty["notebooks"].append(default_workflow_item)
        elif gh_working_dir.startswith("examples/tools/use-cases"):
            toolusecases["notebooks"].append(default_workflow_item)
        else:
            print(f"Unknown workflow type: {gh_working_dir}")

    # Adjust tutorial names:

    for readme_telemetry in readme_telemetries:
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

        default_readme_item = {
            "name": notebook_name,
            "path": notebook_path,
            "pipeline_name": pipeline_name,
            "yaml_name": yaml_name,
            "description": description,
        }
        if readme_folder.startswith("examples/flows/standard"):
            flows["readmes"].append(default_readme_item)
        elif readme_folder.startswith("examples/connections"):
            connections["readmes"].append(default_readme_item)
        elif readme_folder.startswith("examples/flows/evaluation"):
            evaluations["readmes"].append(default_readme_item)
        elif readme_folder.startswith("examples/tutorials"):
            tutorial_readme_item = {
                **default_readme_item,
                'title': readme_telemetry.title.capitalize() if hasattr(readme_telemetry, 'title') else "Empty title",
                'cloud': readme_telemetry.cloud.capitalize() if hasattr(readme_telemetry, 'cloud') else "NOT DEFINED",
                'category': readme_telemetry.category.capitalize() if hasattr(readme_telemetry, 'category') else "General",
            }
            if "quickstart" in notebook_name:
                quickstarts["readmes"].append(tutorial_readme_item)
            else:
                tutorials["readmes"].append(tutorial_readme_item)
        elif readme_folder.startswith("examples/flows/chat"):
            chats["readmes"].append(default_readme_item)
        elif readme_folder.startswith("examples/flex-flows"):
            flex_flows["readmes"].append(default_readme_item)
        elif readme_folder.startswith("examples/prompty"):
            prompty["readmes"].append(default_readme_item)
        elif readme_folder.startswith("examples/tools/use-cases"):
            toolusecases["readmes"].append(default_readme_item)
        else:
            print(f"Unknown workflow type: {readme_folder}")

    quickstarts["notebooks"] = sorted(
        quickstarts["notebooks"],
        key=itemgetter("name"),
        reverse=True,
    )

    # Debug this replacement to check if generated correctly
    replacement = {
        "branch": BRANCH,
        "tutorials": tutorials,
        "flex_flows": flex_flows,
        "prompty": prompty,
        "flows": flows,
        "evaluations": evaluations,
        "chats": chats,
        "toolusecases": toolusecases,
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
    print(f"finished writing {str(readme_file)}")

    # Build a table out of replacement
    # |Area|Cloud|Category|Sample|Description|
    # |item.category | item.cloud | item.section | [item.title](https://github.com/microsoft/promptflow/blob/main/(item.path)) | item.description |
    new_items = []
    for item in replacement["tutorials"]["notebooks"]:
        item["url"] = f"https://github.com/microsoft/promptflow/blob/main/examples/{item['path']}"
        item["area"] = "SDK"
        new_items.append(item)
    for item in replacement["quickstarts"]["notebooks"]:
        item["url"] = f"https://github.com/microsoft/promptflow/blob/main/examples/{item['path']}"
        item["area"] = "SDK"
        new_items.append(item)
    for item in replacement["tutorials"]["readmes"]:
        item["url"] = f"https://github.com/microsoft/promptflow/blob/main/examples/{item['path']}"
        item["area"] = "CLI"
        new_items.append(item)
    for item in replacement["quickstarts"]["readmes"]:
        item["url"] = f"https://github.com/microsoft/promptflow/blob/main/examples/{item['path']}"
        item["area"] = "CLI"
        new_items.append(item)
    # sort new_items by category
    new_items = sorted(new_items, key=lambda x: x["category"])
    tutorial_items = {
        "items": new_items
    }
    tutorial_index_file = Path(ReadmeStepsManage.git_base_dir()) / "docs/tutorials/index.md"
    template_tutorial = env.get_template("tutorial_index.md.jinja2")
    with open(tutorial_index_file, "w") as f:
        f.write(template_tutorial.render(tutorial_items))
    print(f"finished writing {str(tutorial_index_file)}")


def main(check):
    if check:
        # Disable print
        sys.stdout = open(os.devnull, "w")

    input_glob = ["examples/**/*.ipynb"]
    workflow_telemetry = []
    workflow_generator.main(input_glob, workflow_telemetry, check=check)

    input_glob_readme = [
        "examples/flows/**/README.md",
        "examples/flex-flows/**/README.md",
        "examples/prompty/**/README.md",
        "examples/connections/**/README.md",
        "examples/tutorials/e2e-development/*.md",
        "examples/tutorials/flow-fine-tuning-evaluation/*.md",
        "examples/tutorials/**/README.md",
        "examples/tools/use-cases/**/README.md",
    ]
    # exclude the readme since this is 3p integration folder, pipeline generation is not included
    input_glob_readme_exclude = ["examples/flows/integrations/**/README.md"]
    readme_telemetry = []
    readme_generator.main(
        input_glob_readme, input_glob_readme_exclude, readme_telemetry
    )

    write_readme(workflow_telemetry, readme_telemetry)

    if check:
        output_object = {}
        for workflow in workflow_telemetry:
            workflow_items = re.split(r"\[|,| |\]", workflow.path_filter)
            workflow_items = list(filter(None, workflow_items))
            output_object[workflow.workflow_name] = []
            for item in workflow_items:
                if item == "examples/*requirements.txt":
                    output_object[workflow.workflow_name].append(
                        "examples/requirements.txt"
                    )
                    output_object[workflow.workflow_name].append(
                        "examples/dev_requirements.txt"
                    )
                    continue
                output_object[workflow.workflow_name].append(item)
        for readme in readme_telemetry:
            output_object[readme.workflow_name] = []
            readme_items = re.split(r"\[|,| |\]", readme.path_filter)
            readme_items = list(filter(None, readme_items))
            for item in readme_items:
                if item == "examples/*requirements.txt":
                    output_object[readme.workflow_name].append(
                        "examples/requirements.txt"
                    )
                    output_object[readme.workflow_name].append(
                        "examples/dev_requirements.txt"
                    )
                    continue
                output_object[readme.workflow_name].append(item)
        # enable output
        sys.stdout = sys.__stdout__
        return output_object
    else:
        return ""


if __name__ == "__main__":
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--check", action="store_true", help="Check what file is affected"
    )
    args = parser.parse_args()
    output = main(args.check)
    print(json.dumps(output))
