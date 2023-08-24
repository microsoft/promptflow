import os
import glob
import argparse
from pathlib import Path
import ntpath
import re
import hashlib
import json
from jinja2 import Environment, FileSystemLoader
from ghactions_driver.readme_step import ReadmeStepsManage
from ghactions_driver.telemetry_obj import Telemetry


def format_ipynb(notebooks):
    # run code formatter on .ipynb files
    for notebook in notebooks:
        os.system(f"black-nb --clear-output {notebook}")


def _get_paths(paths_list):
    """
    Convert the path list to unix format.
    :param paths_list: The input path list.
    :returns: The same list with unix-like paths.
    """
    paths_list.sort()
    if ntpath.sep == os.path.sep:
        return [pth.replace(ntpath.sep, "/") for pth in paths_list]
    return paths_list


def write_notebook_workflow(notebook, name, output_telemetry=Telemetry()):
    temp_name_list = re.split(r"/|\.", notebook)
    temp_name_list = [
        x
        for x in temp_name_list
        if x != "tutorials" and x != "examples" and x != "ipynb"
    ]
    temp_name_list = [x.replace("-", "") for x in temp_name_list]
    workflow_name = "_".join(["samples"] + temp_name_list)

    place_to_write = (
        Path(ReadmeStepsManage.git_base_dir())
        / ".github"
        / "workflows"
        / f"{workflow_name}.yml"
    )

    gh_working_dir = "/".join(notebook.split("/")[:-1])
    env = Environment(
        loader=FileSystemLoader("./scripts/readme/ghactions_driver/workflow_templates")
    )
    template = env.get_template("basic_workflow.yml.jinja2")

    # Schedule notebooks at different times to reduce maximum quota usage.
    name_hash = int(hashlib.sha512(workflow_name.encode()).hexdigest(), 16)
    schedule_minute = name_hash % 60
    schedule_hour = (name_hash // 60) % 4 + 19  # 19-22 UTC

    if "tutorials" in gh_working_dir:
        path_filter = f"[ examples/**, .github/workflows/{workflow_name}.yml ]"
    else:
        path_filter = f"[ {gh_working_dir}/**, examples/*requirements.txt, .github/workflows/{workflow_name}.yml ]"

    if "chatwithpdf" in workflow_name:
        template_pdf = env.get_template("pdf_workflow.yml.jinja2")
        content = template_pdf.render(
            {
                "workflow_name": workflow_name,
                "ci_name": "samples_notebook_ci",
                "name": name,
                "gh_working_dir": gh_working_dir,
                "path_filter": path_filter,
                "crontab": f"{schedule_minute} {schedule_hour} * * *",
                "crontab_comment": f"Every day starting at {schedule_hour - 16}:{schedule_minute} BJT",
            }
        )
    else:
        content = template.render(
            {
                "workflow_name": workflow_name,
                "ci_name": "samples_notebook_ci",
                "name": name,
                "gh_working_dir": gh_working_dir,
                "path_filter": path_filter,
                "crontab": f"{schedule_minute} {schedule_hour} * * *",
                "crontab_comment": f"Every day starting at {schedule_hour - 16}:{schedule_minute} BJT",
            }
        )

    # To customize workflow, add new steps in steps.py
    # make another function for special cases.
    with open(place_to_write.resolve(), "w") as f:
        f.write(content)
    print(f"Write workflow: {place_to_write.resolve()}")
    output_telemetry.workflow_name = workflow_name
    output_telemetry.name = name
    output_telemetry.gh_working_dir = gh_working_dir


def write_workflows(notebooks, output_telemetrys=[]):
    # process notebooks
    for notebook in notebooks:
        # get notebook name
        output_telemetry = Telemetry()
        nb_path = Path(notebook)
        name, _ = os.path.splitext(nb_path.parts[-1])

        # write workflow file
        write_notebook_workflow(notebook, name, output_telemetry)
        output_telemetry.notebook = nb_path
        output_telemetrys.append(output_telemetry)


def local_filter(callback, array):
    results = []
    for index, item in enumerate(array):
        result = callback(item, index, array)
        # if returned true, append item to results
        if result:
            results.append(item)
    return results


def no_readme_generation_filter(item, index, array) -> bool:
    """
    Set each ipynb metadata no_readme_generation to "true" to skip readme generation
    """
    try:
        # read in notebook
        with open(item, "r", encoding="utf-8") as f:
            data = json.load(f)
        try:
            if data["metadata"]["no_readme_generation"] is not None:
                # no_readme_generate == "true", then no generation
                return data["metadata"]["no_readme_generation"] != "true"
        except Exception:
            return True  # generate readme
    except Exception:
        return False  # generate readme


def main(input_glob, output_files=[]):
    # get list of workflows

    notebooks = _get_paths(
        [j for i in [glob.glob(p, recursive=True) for p in input_glob] for j in i]
    )

    # check each workflow, get metadata.
    notebooks = local_filter(no_readme_generation_filter, notebooks)

    # format code
    format_ipynb(notebooks)

    # write workflows
    write_workflows(notebooks, output_files)


# run functions
if __name__ == "__main__":
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-g", "--input-glob", nargs="+", help="Input glob example 'examples/**/*.ipynb'"
    )
    args = parser.parse_args()

    # call main
    main(input_glob=args.input_glob)
