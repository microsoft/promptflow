import os
import glob
from ghactions_driver.driver import Workflow, Jobs, Job
from ghactions_driver.steps import (
    CheckoutStep,
    GenerateConfigStep,
    AzureLoginStep,
    SetupPythonStep,
    InstallDependenciesStep,
    CreateAoaiConnectionStep,
    RunTestStep,
    UploadArtifactStep,
)
import argparse
from pathlib import Path
import ntpath
import re


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
    temp_name_list.remove("examples")
    temp_name_list.remove("ipynb")
    temp_name_list = [x.replace("-", "") for x in temp_name_list]
    workflow_name = "_".join(temp_name_list)

    place_to_write = (
        Path(__file__).parent.parent / ".github" / "workflows" / f"{workflow_name}.yml"
    )

    gh_working_dir = "/".join(notebook.split("/")[:-1])

    # To customize workflow, add new steps in steps.py
    # make another function for special cases.
    workflow = Workflow(
        workflow_name,
        Jobs().add_job(
            Job(
                name,
                [
                    CheckoutStep(),
                    GenerateConfigStep(),
                    AzureLoginStep(),
                    SetupPythonStep(),
                    InstallDependenciesStep(),
                    CreateAoaiConnectionStep(),
                    RunTestStep(name, gh_working_dir),
                    UploadArtifactStep(gh_working_dir),
                ],
            )
        ),
    )
    with open(place_to_write.resolve(), "w") as f:
        f.write(workflow.get_workflow())
    print(f"Write workflow: {place_to_write.resolve()}")


def write_workflows(notebooks):
    # process notebooks
    for notebook in notebooks:
        # get notebook name
        nb_path = Path(notebook)
        name, _ = os.path.splitext(nb_path.parts[-1])

        # write workflow file
        write_notebook_workflow(notebook, name)


# define functions
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
