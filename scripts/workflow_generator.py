import os
import glob
import argparse
from pathlib import Path
import ntpath
import re
import hashlib
from jinja2 import Environment, FileSystemLoader


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


def write_notebook_workflow(notebook, name):
    temp_name_list = re.split(r"/|\.", notebook)
    temp_name_list = [
        x
        for x in temp_name_list
        if x != "tutorials" and x != "examples" and x != "ipynb"
    ]
    temp_name_list = [x.replace("-", "") for x in temp_name_list]
    workflow_name = "_".join(["samples"] + temp_name_list)

    place_to_write = (
        Path(__file__).parent.parent / ".github" / "workflows" / f"{workflow_name}.yml"
    )

    gh_working_dir = "/".join(notebook.split("/")[:-1])

    template = Environment(
        loader=FileSystemLoader("./scripts/ghactions_driver/workflow_templates")
    ).get_template("basic_workflow.yml.jinja2")

    # Schedule notebooks at different times to reduce maximum quota usage.
    name_hash = int(hashlib.sha512(workflow_name.encode()).hexdigest(), 16)
    schedule_minute = name_hash % 60
    schedule_hour = (name_hash // 60) % 4 + 19  # 19-22 UTC
    content = template.render(
        {
            "workflow_name": workflow_name,
            "name": name,
            "gh_working_dir": gh_working_dir,
            "path_filter": "[ examples/** ]",
            "crontab": f"{schedule_minute} {schedule_hour} * * *",
            "crontab_comment": f"Every day starting at {schedule_hour}:{schedule_minute} UTC",
        }
    )

    # To customize workflow, add new steps in steps.py
    # make another function for special cases.
    with open(place_to_write.resolve(), "w") as f:
        f.write(content)
    print(f"Write workflow: {place_to_write.resolve()}")


def write_workflows(notebooks):
    # process notebooks
    for notebook in notebooks:
        # get notebook name
        nb_path = Path(notebook)
        name, _ = os.path.splitext(nb_path.parts[-1])

        # write workflow file
        write_notebook_workflow(notebook, name)


def main(args):
    # get list of workflows

    workflows = _get_paths(
        [j for i in [glob.glob(p, recursive=True) for p in args.input_glob] for j in i]
    )

    # format code
    format_ipynb(workflows)

    # write workflows
    write_workflows(workflows)


# run functions
if __name__ == "__main__":
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-g", "--input-glob", nargs="+", help="Input glob example 'examples/**/*.ipynb'"
    )
    args = parser.parse_args()

    # call main
    main(args)
