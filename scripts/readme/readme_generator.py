import argparse
from pathlib import Path
from functools import reduce

from ghactions_driver.readme_workflow_generate import write_readme_workflow
from ghactions_driver.readme_step import ReadmeStepsManage, ReadmeSteps
from ghactions_driver.readme_parse import readme_parser

from ghactions_driver.telemetry_obj import Telemetry


def local_filter(callback, array: [Path]):
    results = []
    backups = []
    for index, item in enumerate(array):
        result = callback(item, index, array)
        # if returned true, append item to results
        if result:
            results.append(item)
        else:
            backups.append(item)
    return results, backups


def no_readme_generation_filter(item: Path, index, array) -> bool:
    """
    If there is no steps in the readme, then no generation
    """
    try:
        if 'build' in str(item):  # skip build folder
            return False

        full_text = readme_parser(item.relative_to(ReadmeStepsManage.git_base_dir()))
        if full_text == "":
            return False
        else:
            return True
    except Exception as error:
        print(error)
        return False  # generate readme


def main(input_glob, exclude_glob=[], output_files=[]):
    def set_add(p, q):
        return p | q

    def set_difference(p, q):
        return p - q

    globs = reduce(set_add, [set(Path(ReadmeStepsManage.git_base_dir()).glob(p)) for p in input_glob], set())
    globs_exclude = reduce(set_difference,
                           [set(Path(ReadmeStepsManage.git_base_dir()).glob(p)) for p in exclude_glob],
                           globs)
    readme_items = sorted([i for i in globs_exclude])

    readme_items, no_generation_files = local_filter(no_readme_generation_filter, readme_items)
    for readme in readme_items:
        readme_telemetry = Telemetry()
        workflow_name = readme.relative_to(ReadmeStepsManage.git_base_dir())
        # Deal with readme
        write_readme_workflow(workflow_name.resolve(), readme_telemetry)
        ReadmeSteps.cleanup()
        output_files.append(readme_telemetry)
    for readme in no_generation_files:
        readme_telemetry = Telemetry()
        from ghactions_driver.resource_resolver import resolve_tutorial_resource
        try:
            resolve_tutorial_resource(
                "TEMP", readme.resolve(), readme_telemetry
            )
        except Exception:
            pass
        readme_telemetry.readme_name = str(readme.relative_to(ReadmeStepsManage.git_base_dir()))
        readme_telemetry.readme_folder = str(readme.relative_to(ReadmeStepsManage.git_base_dir()).parent)
        output_files.append(readme_telemetry)


if __name__ == "__main__":
    # setup argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-g",
        "--input-glob",
        nargs="+",
        help="Input Readme.md glob example 'examples/flows/**/Readme.md'",
    )
    args = parser.parse_args()

    # call main
    main(args.input_glob)
