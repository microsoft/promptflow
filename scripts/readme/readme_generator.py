import argparse
from pathlib import Path

from ghactions_driver.readme_workflow_generate import write_readme_workflow
from ghactions_driver.readme_step import ReadmeStepsManage, ReadmeSteps
from ghactions_driver.readme_parse import readme_parser

from ghactions_driver.telemetry_obj import Telemetry


def local_filter(callback, array: [Path]):
    results = []
    for index, item in enumerate(array):
        result = callback(item, index, array)
        # if returned true, append item to results
        if result:
            results.append(item)
    return results


def no_readme_generation_filter(item: Path, index, array) -> bool:
    """
    If there is no steps in the readme, then no generation
    """
    try:
        full_text = readme_parser(item.relative_to(ReadmeStepsManage.git_base_dir()))
        if full_text == "":
            return False
        else:
            return True
    except Exception as error:
        print(error)
        return False  # generate readme


def main(input_glob, output_files=[]):
    globs = [sorted(Path(ReadmeStepsManage.git_base_dir()).glob(p)) for p in input_glob]
    readme_items = sorted([j for i in globs for j in i])

    readme_items = local_filter(no_readme_generation_filter, readme_items)

    for readme in readme_items:
        readme_telemetry = Telemetry()
        workflow_name = readme.parent.relative_to(ReadmeStepsManage.git_base_dir())
        # Deal with readme
        write_readme_workflow(workflow_name.resolve(), readme_telemetry)
        ReadmeSteps.cleanup()
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
